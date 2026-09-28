#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarios/pipeline.py — pipeline dos Diários Oficiais (FASE 2, 7, 8 e 12).

    SOURCE → FETCH → RAW → PARSE → NORMALIZE → DEDUP → CLASSIFY → STORE → ALERT

Cada etapa é uma função explícita (`_coletar`, `_persistir_raw`, `_normalizar`,
`_deduplicar`, `_classificar`, `_publicar`), de modo que ingestão e classificação
fiquem **mensuráveis separadamente**: um item administrativo sem nenhum termo
temático não é erro de ingestão — é item descartado, e isso aparece nas métricas
(`itens_descartados`), não nas falhas (`falhas_parse`).

Saída para o restante do sistema:

  · `para_resultado_legado()` devolve o formato histórico de `ResultadoFonte`
    (orgao/nome/obrigatoria/itens/saude/http/erro_fatal), consumido por
    `update_sources.mesclar()` para gravar `atos.json`/`updates.json`;
  · `saude` traz os contadores legados **e** o bloco `diarios` (modo de
    ingestão, cobertura integral, métricas de ingestão/classificação);
  · `data/legislation/diarios.json` (via `coverage.monitor`) publica o
    Coverage Monitor, que é o que mostra o que está e o que não está coberto.

Regra de ouro: a integral é a via principal; a busca temática é fallback e
verificação complementar (ver `diarios/dou.py`). Se a via integral rodou
completa, `cobertura_integral=True`; se caiu para o fallback, isso é registrado.
"""
from __future__ import annotations

import time

from . import coverage
from .quality import evaluate_text_quality
from .base import (ContextoDiario, MetricasIngestao, ResultadoColeta, limpar_texto,
                   normalizar_item, ts_iso)
from .classificacao import aplicar_classificacao, classificar_item
from .dedup import Deduplicador

# Descrição publicada no dataset: tamanho máximo do texto (mesma ordem do que já
# existe em atos.json — o texto integral fica no raw storage).
LIMITE_DESCRICAO_DATASET = 1200

# Teto de texto submetido ao quality gate por item (mede a extração, não o
# armazenamento: o texto completo continua no item/raw storage).
LIMITE_QUALIDADE = 200_000


# Ordem dos caminhos de ingestão para o rótulo de saúde (auditoria).
MODOS_INGESTAO = ("xml", "integral", "integral+complementar", "fallback", None)


class ResultadoFonteDiario:
    """Resultado do pipeline para **uma** fonte (coleta + classificação)."""

    def __init__(self, fonte, coleta=None):
        self.fonte = fonte
        self.coleta = coleta or ResultadoColeta(fonte.source_id, fonte.nome)
        self.metricas = MetricasIngestao()
        self.itens_normalizados = []   # contrato comum (todos os itens ingeridos)
        self.itens_publicaveis = []    # relevantes + revisão (formato do dataset)
        self.erro_fatal = None
        self.duracao = 0.0
        self.raw_referencia = None
        self.avisos = []
        self.dedup_por_chave = {}
        # Quality gate do texto (FASE 10) — contadores auditáveis por fonte.
        self.textos_ok = 0
        self.textos_degradados = 0
        self.textos_falhos = 0

    # ------------------------------------------------------------------ leitura
    @property
    def status(self):
        """ok | parcial | falha — vocabulário do contrato legado de saúde."""
        if self.erro_fatal and not self.coleta.itens:
            return "falha"
        return self.coleta.status

    @property
    def status_registry(self):
        """funcionando | parcial | falha — vocabulário do registry/painel."""
        if self.erro_fatal and not self.coleta.itens:
            return "falha"
        return self.coleta.status_registry

    @property
    def cobertura_integral(self):
        return bool(self.coleta.cobertura_integral)

    def saude(self, novidades=0):
        """Saúde no formato do contrato legado, com o bloco `diarios` adicional.

        Os contadores de normalização/classificação/dedup nascem no pipeline (não
        no coletor). Copiá-los para a coleta antes de serializar garante que o
        painel e o payload legado publiquem exatamente o que foi medido — sem
        contador zerado por engano de onde ele mora.
        """
        for campo in ("itens_fonte", "itens_normalizados", "itens_classificados",
                      "itens_relevantes", "itens_descartados", "itens_revisao",
                      "duplicados"):
            setattr(self.coleta.metricas, campo, getattr(self.metricas, campo, 0))
        return self.coleta.para_saude(
            novidades=novidades,
            itens_relevantes=self.metricas.itens_relevantes,
            itens_descartados=self.metricas.itens_descartados,
            itens_revisao=self.metricas.itens_revisao)

    def para_resultado_legado(self):
        """Formato consumido pelo `update_sources.mesclar()`."""
        return {
            "orgao": self.fonte.source_id,
            "nome": self.fonte.nome,
            "obrigatoria": bool(getattr(self.fonte, "obrigatorio", True)),
            "itens": list(self.itens_publicaveis),
            "saude": self.saude(),
            "http": dict(self.coleta.http or {}),
            "erro_fatal": self.erro_fatal,
            "diarios": {
                "source_id": self.fonte.source_id,
                "nivel": self.fonte.nivel,
                "jurisdicao": self.fonte.jurisdicao,
                "modo_ingestao": self.coleta.modo_ingestao,
                "cobertura_integral": self.coleta.cobertura_integral,
                "fallback_usado": self.coleta.fallback_usado,
                "verificacao_complementar": self.coleta.verificacao_complementar,
                "layout_changed": self.coleta.layout_changed,
                "layout_evidencia": self.coleta.layout_evidencia,
                "zero_publicacao_confirmado": self.coleta.zero_publicacao_confirmado,
                "paginacao_detectada": self.coleta.paginacao_detectada,
                "truncado": self.coleta.truncado,
                "ultima_publicacao": self.coleta.ultima_publicacao,
                "metricas_ingestao": self.metricas.para_dict(),
                "qualidade_texto": {"good": self.textos_ok,
                                    "degraded": self.textos_degradados,
                                    "failed": self.textos_falhos},
                "itens_publicaveis": len(self.itens_publicaveis),
                "raw_referencia": self.raw_referencia,
                "avisos": list(self.coleta.avisos),
            },
        }


def item_publicavel(item):
    """Item normalizado → registro no formato do dataset público (`atos.json`).

    Só entram itens **relevantes ou de revisão**; o restante fica integralmente no
    raw storage e no índice de metadados.
    """
    return {
        "id": item.get("chave"),
        "titulo": item.get("titulo"),
        "descricao": limpar_texto(item.get("texto") or "", LIMITE_DESCRICAO_DATASET) or None,
        "data": item.get("data"),
        "url_oficial": item.get("url_oficial"),
        "tipo": "publicacao",
        "fonte": f"{item.get('fonte_nome') or item.get('source_id')} — {item.get('modo_ingestao') or 'ingestão'}",
        "fonte_id": item.get("source_id"),
        "jurisdicao": item.get("jurisdicao"),
        "nivel": item.get("nivel"),
        "uf": item.get("uf"),
        "municipio": item.get("municipio"),
        "relevancia": item.get("relevancia"),
        "revisao_pendente": bool(item.get("revisao_pendente")),
        "grupos_tematicos": list(item.get("grupos_tematicos") or []),
        "padroes_tematicos": list(item.get("padroes_tematicos") or []),
        "situacao": None,
        "tipo_ato": item.get("tipo_ato"),
        "hierarquia": " > ".join(item.get("hierarquia") or []) or None,
        "orgao_emissor": item.get("orgao"),
        "secao": item.get("secao"),
        "edicao": item.get("edicao"),
        "edicao_extraordinaria": item.get("edicao_extraordinaria"),
        "pagina": item.get("pagina"),
        "id_oficial": item.get("id_oficial"),
        "id_publicacao": item.get("id_publicacao"),
        "arquivo_fonte": item.get("arquivo_fonte"),
        "texto_hash": item.get("hash_conteudo"),
        "hash_conteudo": item.get("hash_conteudo"),
        "hash_anterior": item.get("hash_anterior"),
        "hash_atual": item.get("hash_atual"),
        "dedup_estado": item.get("dedup_estado"),
        "primeira_deteccao": item.get("primeira_deteccao"),
        "ultima_verificacao": item.get("ultima_verificacao"),
        "ultima_alteracao": item.get("ultima_alteracao"),
        "coletado_em": item.get("coletado_em"),
        "origem": item.get("origem"),
        "modo_ingestao": item.get("modo_ingestao"),
    }


class PipelineDiarios:
    """Executa fontes de Diários Oficiais: ingere, deduplica, classifica e publica."""

    def __init__(self, registry, coletores, raw_storage=None, metadata_store=None,
                 logger=print, dry_run=False, dedup=None, estado=None,
                 registrar_relevantes=True):
        self.registry = registry
        self.coletores = coletores                # {source_id: FonteDiario}
        self.raw = raw_storage
        self.metadata = metadata_store
        self.log = logger
        self.dry_run = dry_run
        self.registrar_relevantes = registrar_relevantes
        self.dedup = dedup or Deduplicador(metadata_store=metadata_store, estado=estado,
                                           logger=logger)
        self.relatorios = {}
        self.contextos = {}                       # source_id → ContextoDiario (telemetria)

    # ------------------------------------------------------------------- fontes
    def fonte(self, source_id):
        return self.coletores.get(source_id)

    def fontes_executaveis(self, incluir_fallback=False):
        """Fontes implementadas com coletor disponível (ordem: obrigatórias primeiro).

        `dou_busca_tematica` só entra como fonte independente quando pedida
        explicitamente: por padrão ela roda **dentro** da fonte `dou`, como
        fallback/complemento (para não contar duas vezes a mesma cobertura).
        """
        fontes = []
        for fonte in self.registry.todas():
            if not fonte.implementado or not fonte.ativo:
                continue
            if fonte.source_id not in self.coletores:
                continue
            if fonte.source_id == "dou_busca_tematica" and not incluir_fallback:
                continue
            fontes.append(fonte)
        return fontes

    # --------------------------------------------------------------- execução
    def contexto(self, fonte_cadastrada, dias=1, timeout_s=240, orcamento=None):
        """Cria (ou reaproveita) o contexto HTTP da fonte — cliente do projeto, com
        timeout, retry, cache, telemetria e orçamento compartilhados."""
        ctx = self.contextos.get(fonte_cadastrada.source_id)
        if ctx is None:
            ctx = ContextoDiario(fonte_cadastrada.source_id, timeout_s=timeout_s,
                                 orcamento=orcamento, dry_run=self.dry_run, logger=self.log,
                                 dias=dias)
            self.contextos[fonte_cadastrada.source_id] = ctx
        return ctx

    def executar_fonte(self, fonte_cadastrada, ctx=None, incluir_busca=False,
                       dias=1, ctx_factory=None):
        """Executa uma fonte. `ctx`/`ctx_factory` permitem injetar contexto de teste."""
        if ctx is None:
            ctx = (ctx_factory(fonte_cadastrada, self.coletores.get(fonte_cadastrada.source_id))
                   if ctx_factory else self.contexto(fonte_cadastrada, dias=dias))
        """Roda o pipeline completo de uma fonte e devolve `ResultadoFonteDiario`."""
        coletor = self.coletores.get(fonte_cadastrada.source_id)
        resultado = ResultadoFonteDiario(fonte_cadastrada)
        t0 = time.monotonic()
        if coletor is None:
            resultado.erro_fatal = (f"coletor {fonte_cadastrada.source_id} não disponível "
                                    f"neste processo")
            resultado.coleta.erros.append(resultado.erro_fatal)
            self.log(f"    [falha] {resultado.erro_fatal}")
            return resultado
        try:
            coletor.coletar(ctx, resultado.coleta)
        except Exception as e:  # noqa: BLE001 — fonte que falha não derruba as demais
            resultado.erro_fatal = f"{type(e).__name__}: {e}"
            if resultado.erro_fatal not in resultado.coleta.erros:
                resultado.coleta.erros.append(resultado.erro_fatal)
            self.log(f"    [falha] {fonte_cadastrada.source_id}: {resultado.erro_fatal}")
        resultado.coleta.http = ctx.cliente.resumo_stats()

        self._persistir_raw(resultado)
        self._normalizar(resultado)
        self._deduplicar(resultado)
        self._classificar(resultado)

        resultado.duracao = time.monotonic() - t0
        resultado.coleta.duracao = resultado.duracao
        self.relatorios[fonte_cadastrada.source_id] = resultado
        return resultado

    def executar(self, fontes=None, dias=1, timeout_s=240, orcamento=None,
                 incluir_fallback=False, ctx_factory=None):
        """Executa as fontes pedidas (ou todas as implementadas).

        `ctx_factory(fonte, coletor)` é opcional e existe para diagnóstico/teste:
        quando informado, ele é o dono do contexto HTTP de cada fonte.
        """
        alvos = ([f for f in self.fontes_executaveis(incluir_fallback) if f.source_id in fontes]
                 if fontes else self.fontes_executaveis(incluir_fallback))
        for fonte in alvos:
            self.log(f"  · fonte '{fonte.source_id}' ({fonte.nome})")
            ctx = (ctx_factory(fonte, self.coletores.get(fonte.source_id)) if ctx_factory
                   else self.contexto(fonte, dias=dias, timeout_s=timeout_s,
                                      orcamento=orcamento))
            relatorio = self.executar_fonte(fonte, ctx,
                                            incluir_busca=(incluir_fallback
                                                           and fonte.source_id == "dou_busca_tematica"))
            coverage.aplicar_resultado(self.registry, relatorio)
            self.log(f"    → {relatorio.status} · modo={relatorio.coleta.modo_ingestao} · "
                     f"itens={relatorio.metricas.itens_fonte} · "
                     f"normalizados={relatorio.metricas.itens_normalizados} · "
                     f"relevantes={relatorio.metricas.itens_relevantes} · "
                     f"revisão={relatorio.metricas.itens_revisao} · "
                     f"descartados={relatorio.metricas.itens_descartados} · "
                     f"duplicados={relatorio.metricas.duplicados} · "
                     f"falhas_parse={relatorio.metricas.falhas_parse}")
            for aviso in relatorio.coleta.avisos[:2]:
                self.log(f"      aviso: {aviso[:160]}")
            for erro in relatorio.coleta.erros[:2]:
                self.log(f"      erro: {erro[:160]}")
        return self.relatorios

    # ------------------------------------------------------------------- etapas
    def _persistir_raw(self, resultado):
        """RAW — payload bruto e arquivos-fonte vão para o storage (nunca para o Git)."""
        if self.raw is None or self.dry_run or not resultado.coleta.itens:
            # Sem storage (dry-run/diagnóstico) ou sem itens: nada é gravado e o
            # arquivo-fonte não fica pendurado em memória.
            resultado.coleta.arquivos_fonte.clear()
            resultado.coleta.arquivos_fonte = {}
            return
        referencia = (resultado.coleta.ultima_publicacao or ts_iso()[:10])
        meta = {
            "source_id": resultado.fonte.source_id,
            "nome": resultado.fonte.nome,
            "nivel": resultado.fonte.nivel,
            "modo_ingestao": resultado.coleta.modo_ingestao,
            "estrutura_fonte": resultado.coleta.estrutura_fonte,
            "cobertura_integral": resultado.coleta.cobertura_integral,
            "layout_changed": resultado.coleta.layout_changed,
            "paginacao_detectada": resultado.coleta.paginacao_detectada,
            "truncado": resultado.coleta.truncado,
            "itens_brutos": len(resultado.coleta.itens),
            "edicoes": resultado.coleta.edicoes,
            "canais_ok": resultado.coleta.canais_ok,
            "canais_falhos": resultado.coleta.canais_falhos,
            "erros": resultado.coleta.erros[:10],
            "coletado_em": resultado.coleta.tentativa_em,
        }
        try:
            resultado.raw_referencia = self.raw.save(
                resultado.fonte.source_id, referencia, resultado.coleta.itens, meta,
                arquivos=dict(resultado.coleta.arquivos_fonte or {}))
        except Exception as e:  # noqa: BLE001 — storage não derruba a coleta
            aviso = f"raw storage indisponível ({type(e).__name__}: {e})"
            resultado.avisos.append(aviso)
            self.log(f"      aviso: {aviso[:160]}")
        finally:
            # O arquivo-fonte (HTML/XML de páginas inteiras) é liberado depois de
            # gravado: mantê-lo até o fim da execução era o que inflava a memória
            # da ingestão integral de uma edição real.
            resultado.coleta.arquivos_fonte.clear()

    def _normalizar(self, resultado):
        """PARSE/NORMALIZE — item bruto → contrato comum (campo ausente fica ausente)."""
        for bruto in resultado.coleta.itens:
            item = normalizar_item(bruto, resultado.fonte, coletado_em=bruto.get("coletado_em"))
            if not item.get("url_oficial"):
                # Sem URL oficial verificável o item não entra: não é publicado nada
                # que não possa ser conferido na fonte.
                resultado.metricas.falhas_parse += 1
                continue
            item["fonte_nome"] = resultado.fonte.nome
            # Quality gate da extração textual (FASE 10): mede o texto que veio da
            # fonte oficial. Só `degraded`/`failed` podem, no futuro, acionar o
            # pipeline visual (que hoje é apenas interface — ver visual_fallback/).
            # O texto é limitado para manter o custo da medição previsível.
            qualidade = evaluate_text_quality((item.get("texto") or "")[:LIMITE_QUALIDADE])
            item["qualidade_texto"] = qualidade.para_dict()
            if qualidade.estado == "good":
                resultado.textos_ok += 1
            elif qualidade.estado == "degraded":
                resultado.textos_degradados += 1
            else:
                resultado.textos_falhos += 1
            resultado.itens_normalizados.append(item)
        resultado.metricas.itens_fonte = len(resultado.coleta.itens)
        resultado.metricas.itens_normalizados = len(resultado.itens_normalizados)
        if resultado.metricas.falhas_parse:
            resultado.coleta.avisos.append(
                f"{resultado.metricas.falhas_parse} item(ns) sem URL oficial — "
                f"não normalizados (falha de parse, não 'sem publicações')")

    def _deduplicar(self, resultado):
        """DEDUP — identidade estável, hash de conteúdo e histórico (nada sobrescrito)."""
        for item in resultado.itens_normalizados:
            estado = self.dedup.processar(item, registrar_relevante=False)
            resultado.dedup_por_chave[item["chave"]] = estado
            if estado.duplicado:
                resultado.metricas.duplicados += 1
        resultado.coleta.metricas.duplicados = resultado.metricas.duplicados
        # Digest da edição: sobrevive entre execuções e detecta reingestão.
        referencia = (resultado.coleta.ultima_publicacao or ts_iso()[:10])
        self.dedup.registrar_edicao(
            resultado.fonte.source_id, referencia, resultado.itens_normalizados,
            meta={"secoes": {e.get("secao") or e.get("secao_rotulo"): e.get("itens")
                             for e in resultado.coleta.edicoes},
                  "modo_ingestao": resultado.coleta.modo_ingestao,
                  "layout_ok": not bool(resultado.coleta.layout_changed),
                  "paginacao_detectada": resultado.coleta.paginacao_detectada,
                  "truncado": resultado.coleta.truncado})

    def _classificar(self, resultado):
        """CLASSIFY — relevância **depois** da ingestão (mesmos padrões publicados)."""
        for item in resultado.itens_normalizados:
            classificacao = classificar_item(item)
            aplicar_classificacao(item, classificacao)
            resultado.metricas.itens_classificados += 1
            if classificacao.relevante:
                resultado.metricas.itens_relevantes += 1
            elif classificacao.revisao:
                resultado.metricas.itens_revisao += 1
            else:
                resultado.metricas.itens_descartados += 1
            if classificacao.relevancia:
                resultado.itens_publicaveis.append(item_publicavel(item))
                if self.registrar_relevantes:
                    estado = resultado.dedup_por_chave.get(item["chave"])
                    if estado is not None:
                        self.dedup.registrar_relevante(item, estado)

    # ----------------------------------------------------------------- utilidade
    def metricas_totais(self, relatorios=None):
        total = MetricasIngestao()
        for relatorio in (relatorios or self.relatorios).values():
            total.somar(**relatorio.metricas.para_dict())
        return total

    def cobertura(self, resultados=None):
        return coverage.monitor(self.registry, resultados=resultados)


__all__ = ["PipelineDiarios", "ResultadoFonteDiario", "item_publicavel",
           "LIMITE_DESCRICAO_DATASET"]
