#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_diarios.py — ingestão dos Diários Oficiais (CLI).

Roda o pipeline `SOURCE → FETCH → RAW → PARSE → NORMALIZE → DEDUP → CLASSIFY →
STORE → ALERT` para as fontes implementadas do registry e grava:

    var/raw/diarios/<source_id>/<referencia>/…   payload bruto (fora do Git)
    var/raw/diarios/indice.json                  índice de metadados (dedup de volume)
    data/diarios/estado.json                     estado versionado (relevantes + digest das edições)
    data/legislation/diarios.json                Coverage Monitor (o que está e o que não está coberto)

Ele **não** grava `atos.json`/`updates.json`: quem faz isso é o `update_sources.py`,
que consome o payload via `--json-legado`. Assim a ingestão fica separada da
publicação do dataset.

Uso:
    python3 scripts/update_diarios.py --listar
    python3 scripts/update_diarios.py --cobertura
    python3 scripts/update_diarios.py --quality "Art. 1º …"
    python3 scripts/update_diarios.py --fonte dou --dry-run
    python3 scripts/update_diarios.py --fonte dou --dias 2
    python3 scripts/update_diarios.py --todos --json-legado /tmp/diarios.json

Variáveis de ambiente (todas opcionais):

    MONITOR_DOU_XML_DIR       pacotes XML oficiais já baixados (INLABS/acervo)
    MONITOR_INLABS_USUARIO    credencial do INLABS (download autenticado) — nunca no repositório
    MONITOR_INLABS_SENHA      idem
    MONITOR_DOU_XML=0         desliga o caminho XML
    MONITOR_DOU_FALLBACK=0    desliga a busca temática (fallback/complemento)
    MONITOR_DOU_MAX_ITENS_EDICAO  teto de itens por edição (padrão 2000)
    MONITOR_DOU_DIAS          janela de datas padrão
"""
from __future__ import annotations

import argparse
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
sys.path.insert(0, BASE)

from diarios import coletores_padrao, registry_com_saude  # noqa: E402
from diarios.base import (ARQUIVO_ESTADO, ARQUIVO_SNAPSHOT, DIARIOS_DIR,  # noqa: E402
                          MetricasIngestao, agora_brt, carregar_json, salvar_json)
from diarios.coverage import monitor  # noqa: E402
from diarios.dedup import carregar_estado  # noqa: E402
from diarios.pipeline import PipelineDiarios  # noqa: E402
from storage import LocalMetadataStore, LocalRawStorage, obter_raw_storage  # noqa: E402

VAR_DIR = os.path.join(BASE, "var", "raw", "diarios")
INDICE_PADRAO = os.path.join(VAR_DIR, "indice.json")


def _env_int(nome, padrao):
    try:
        return int(os.environ.get(nome, "") or padrao)
    except ValueError:
        return padrao


TIMEOUT_FONTE_S = _env_int("MONITOR_DIARIOS_TIMEOUT_S", 240)
DIAS = _env_int("MONITOR_DOU_DIAS", 1)


# ------------------------------------------------------------------ montagem
def montar_pipeline(args, logger=print):
    """Registry (com a saúde do último snapshot) + coletores + storages + pipeline."""
    registry = registry_com_saude(logger=logger)
    coletores = coletores_padrao(logger=logger)
    if args.datas:
        # Janela explícita: backfill/importação de um pacote oficial de data conhecida.
        for coletor in coletores.values():
            if hasattr(coletor, "datas"):
                coletor.datas = list(args.datas)

    raw = None
    metadata = None
    if not args.sem_storage:
        try:
            raw = obter_raw_storage()
        except Exception as e:  # noqa: BLE001 — sem storage o pipeline ainda roda
            logger(f"[aviso] raw storage indisponível ({type(e).__name__}: {e})")
            raw = LocalRawStorage(VAR_DIR)
        metadata = LocalMetadataStore(caminho=args.indice or INDICE_PADRAO)

    estado = carregar_estado(args.estado) if not args.dry_run else None
    pipeline = PipelineDiarios(registry, coletores, raw_storage=raw,
                               metadata_store=metadata, logger=logger,
                               dry_run=args.dry_run, estado=estado,
                               registrar_relevantes=not args.dry_run)
    return pipeline, registry, raw, metadata


def imprimir_resumo(relatorios, registry, logger=print):
    logger("")
    for source_id, relatorio in relatorios.items():
        coleta = relatorio.coleta
        logger(f"[{source_id}] {relatorio.fonte.nome}")
        logger(f"  status: {relatorio.status} · modo: {coleta.modo_ingestao} · "
               f"cobertura integral: {coleta.cobertura_integral} · "
               f"fallback: {coleta.fallback_usado}")
        logger(f"  itens: fonte={relatorio.metricas.itens_fonte} "
               f"normalizados={relatorio.metricas.itens_normalizados} "
               f"classificados={relatorio.metricas.itens_classificados} "
               f"relevantes={relatorio.metricas.itens_relevantes} "
               f"revisão={relatorio.metricas.itens_revisao} "
               f"descartados={relatorio.metricas.itens_descartados} "
               f"duplicados={relatorio.metricas.duplicados} "
               f"falhas_parse={relatorio.metricas.falhas_parse}")
        if coleta.layout_changed:
            logger(f"  [ALERTA] layout_changed=True — {coleta.layout_evidencia}")
        if coleta.zero_publicacao_confirmado:
            logger(f"  zero publicações confirmado: {coleta.zero_evidencia}")
        if coleta.erro_resumo():
            logger(f"  erro: {coleta.erro_resumo()[:300]}")
        for aviso in (coleta.avisos or [])[:3]:
            logger(f"  aviso: {aviso[:200]}")
        for item in relatorio.itens_publicaveis[:5]:
            logger(f"    - [{item.get('data') or '—'}] ({item.get('relevancia')}) "
                   f"{(item.get('titulo') or '')[:100]}")
            logger(f"      {item.get('url_oficial')}")
    metricas = monitor(registry)["metricas"]
    logger("")
    logger(f"Cobertura técnica: {metricas['cobertura_tecnica_pct']}% "
           f"({metricas['fontes_implementadas']}/{metricas['fontes_totais']} fontes cadastradas "
           f"com coletor implementado) · nao_implementadas="
           f"{metricas['fontes_nao_implementadas']} · ok={metricas['fontes_ok']} · "
           f"parciais={metricas['fontes_parciais']} · falha={metricas['fontes_falha']}")
    logger("  " + metricas["definicao_cobertura_tecnica"])
    return 0


def montar_relatorio(relatorios, registry, pipeline=None, contextos=None):
    """Relatório público: contadores de ingestão/classificação + cobertura."""
    fontes = {}
    for source_id, relatorio in relatorios.items():
        coleta = relatorio.coleta
        ctx = (contextos or pipeline.contextos if pipeline else {}).get(source_id)
        if ctx is not None:
            coleta.http = ctx.cliente.resumo_stats()
        fontes[source_id] = {
            "nome": relatorio.fonte.nome,
            "nivel": relatorio.fonte.nivel,
            "jurisdicao": relatorio.fonte.jurisdicao,
            "status": relatorio.status,
            "status_registry": relatorio.status_registry,
            "modo_ingestao": coleta.modo_ingestao,
            "cobertura_integral": coleta.cobertura_integral,
            "fallback_usado": coleta.fallback_usado,
            "verificacao_complementar": coleta.verificacao_complementar,
            "estrutura_fonte": coleta.estrutura_fonte,
            "layout_changed": coleta.layout_changed,
            "layout_evidencia": coleta.layout_evidencia,
            "zero_publicacao_confirmado": coleta.zero_publicacao_confirmado,
            "paginacao_detectada": coleta.paginacao_detectada,
            "truncado": coleta.truncado,
            "ultima_publicacao": coleta.ultima_publicacao,
            "duracao": round(coleta.duracao, 1),
            "erro": coleta.erro_resumo(),
            "erro_fatal": relatorio.erro_fatal,
            "avisos": list(coleta.avisos),
            "canais_ok": list(coleta.canais_ok),
            "canais_falhos": list(coleta.canais_falhos),
            "endpoints": list(coleta.endpoints),
            "http": dict(coleta.http or {}),
            "metricas_ingestao": relatorio.metricas.para_dict(),
            "itens_publicaveis": len(relatorio.itens_publicaveis),
            "raw_referencia": relatorio.raw_referencia,
            "amostra": [{campo: item.get(campo) for campo in
                         ("titulo", "data", "url_oficial", "secao", "tipo_ato",
                          "relevancia", "grupos_tematicos")}
                        for item in relatorio.itens_publicaveis[:5]],
        }
    totais = MetricasIngestao()
    for relatorio in relatorios.values():
        totais.somar(**relatorio.metricas.para_dict())
    return {
        "gerado_em": agora_brt().isoformat(timespec="seconds"),
        "diarios": fontes,
        "metricas_ingestao": totais.para_dict(),
        "cobertura": monitor(registry)["metricas"],
        "execucao": {"dias": DIAS, "timeout_fonte_s": TIMEOUT_FONTE_S},
    }


# ------------------------------------------------------------------- comandos
def comando_listar(registry, logger=print):
    logger(f"{'source_id':22} {'nivel':11} {'status':17} {'coletor':45} nome")
    for fonte in registry.todas():
        logger(f"{fonte.source_id:22} {fonte.nivel:11} {fonte.status:17} "
               f"{(fonte.collector or '—')[:45]:45} {fonte.nome}")
    metricas = monitor(registry)["metricas"]
    logger("")
    logger(f"{metricas['fontes_totais']} fontes cadastradas · "
           f"{metricas['fontes_implementadas']} implementadas · "
           f"{metricas['fontes_nao_implementadas']} pendentes · "
           f"cobertura técnica {metricas['cobertura_tecnica_pct']}%")
    logger("  " + metricas["definicao_cobertura_tecnica"])
    return 0


def comando_cobertura(registry, args, logger=print):
    snapshot = monitor(registry)
    if args.json_saida:
        salvar_json(args.json_saida, snapshot)
        logger(f"snapshot de cobertura: {args.json_saida}")
    else:
        logger(json.dumps(snapshot["metricas"], ensure_ascii=False, indent=2))
        logger(json.dumps(snapshot["pendentes"], ensure_ascii=False, indent=2))
    return 0


def comando_quality(texto, logger=print):
    from diarios.quality import evaluate_text_quality
    from visual_fallback import decidir_pipeline, status_visual_fallback
    qualidade = evaluate_text_quality(texto)
    logger(json.dumps({"qualidade": qualidade.para_dict(),
                       "decisao_pipeline": decidir_pipeline(texto=texto,
                                                            qualidade=qualidade),
                       "visual_fallback": status_visual_fallback()},
                      ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ingestão integral dos Diários Oficiais.")
    ap.add_argument("--fonte", action="append", help="source_id (pode repetir)")
    ap.add_argument("--todos", action="store_true", help="todas as fontes implementadas")
    ap.add_argument("--incluir-fallback", action="store_true",
                    help="inclui a busca temática como fonte independente do relatório")
    ap.add_argument("--datas", action="append",
                    help="data específica AAAA-MM-DD para ingestão (pode repetir)")
    ap.add_argument("--listar", action="store_true", help="lista o registry")
    ap.add_argument("--cobertura", action="store_true",
                    help="imprime (ou salva em --json) o snapshot de cobertura")
    ap.add_argument("--quality", help="avalia a qualidade de um texto e encerra")
    ap.add_argument("--dias", type=int, default=None, help=f"janela de datas (padrão {DIAS})")
    ap.add_argument("--timeout", type=int, default=None, help="timeout por fonte (s)")
    ap.add_argument("--json", dest="json_saida", help="grava o relatório/resultado em JSON")
    ap.add_argument("--json-legado", dest="json_legado",
                    help="grava o payload completo no formato consumido pelo update_sources.py")
    ap.add_argument("--estado", default=ARQUIVO_ESTADO, help="arquivo de estado da dedup")
    ap.add_argument("--indice", default=INDICE_PADRAO, help="índice local de metadados")
    ap.add_argument("--dry-run", action="store_true", help="consulta sem gravar nada")
    ap.add_argument("--sem-storage", action="store_true",
                    help="não usa raw storage/índice (testes e diagnósticos)")
    args = ap.parse_args(argv)

    if args.quality:
        return comando_quality(args.quality)

    pipeline, registry, raw, metadata = montar_pipeline(args)
    if args.listar:
        return comando_listar(registry)
    if args.cobertura:
        return comando_cobertura(registry, args)

    if args.fonte:
        desconhecidas = [f for f in args.fonte if registry.obter(f) is None]
        if desconhecidas:
            print(f"[erro] fonte(s) não cadastrada(s) no registry: {', '.join(desconhecidas)}")
            return 2
        alvos = args.fonte
    elif args.todos:
        alvos = None
    else:
        ap.print_help()
        return 0

    dias = args.dias or (len(args.datas) if args.datas else None) or DIAS
    timeout = args.timeout or TIMEOUT_FONTE_S
    relatorios = pipeline.executar(alvos, dias=dias, timeout_s=timeout,
                                   incluir_fallback=args.incluir_fallback)
    if not relatorios:
        print("[aviso] nenhuma fonte implementada/configurada para executar "
              "(os 27 estaduais e os municipais seguem como nao_implementado no registry).")

    relatorio_json = montar_relatorio(relatorios, registry, pipeline)
    if args.json_saida:
        salvar_json(args.json_saida, relatorio_json)
        print(f"relatório: {args.json_saida}")
    if args.json_legado:
        salvar_json(args.json_legado,
                    {sid: rel.para_resultado_legado() for sid, rel in relatorios.items()})
        print(f"payload para o dataset: {args.json_legado}")

    if args.dry_run:
        imprimir_resumo(relatorios, registry, logger=print)
        print("\nDRY-RUN: nada foi gravado (nem bruto, nem estado, nem snapshot).")
        return 0

    if raw is not None and hasattr(raw, "descricao"):
        print(f"raw storage: {raw.descricao()}")
    if metadata is not None:
        print(f"índice de metadados: {metadata.salvar()} registro(s)")
    estado_salvo = pipeline.dedup.salvar(args.estado)
    snapshot = monitor(registry)
    salvar_json(ARQUIVO_SNAPSHOT, snapshot)
    imprimir_resumo(relatorios, registry, logger=print)
    print(f"\nestado de dedup: {estado_salvo} · snapshot público: {ARQUIVO_SNAPSHOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
