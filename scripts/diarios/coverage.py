#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarios/coverage.py — Coverage Monitor dos Diários Oficiais (FASE 11).

Publica, por fonte, o que **de fato** aconteceu na última tentativa:

    source_id · jurisdicao · nivel · ultima_tentativa · ultima_coleta_ok ·
    ultima_publicacao_detectada · itens_coletados · erro · status · duracao ·
    layout_changed

e agrega:

    fontes_totais · fontes_implementadas · fontes_ok · fontes_parciais ·
    fontes_falha · fontes_nao_implementadas · cobertura_tecnica_pct

`cobertura_tecnica_pct` é a fração das fontes **cadastradas** que têm coletor
implementado. Nunca é "100% de cobertura" pelo simples fato de os coletores
terem rodado: fonte cadastrada sem implementação aparece como
`nao_implementado`, e fonte implementada que ainda não executou aparece como
`implementado` — as duas contam como fora da cobertura técnica.
"""
from __future__ import annotations

from .base import agora_brt, ts_iso
from .registry import ORDEM_STATUS

# Campos do registro de cobertura por fonte (contrato público, testado).
CAMPOS_COBERTURA = (
    "source_id", "nome", "jurisdicao", "nivel", "uf", "municipio",
    "tipo_acesso", "formato", "adapter_family", "collector",
    "ultima_tentativa", "ultima_coleta_ok", "ultima_publicacao_detectada",
    "itens_coletados", "erro", "status", "duracao", "layout_changed",
)

DEFINICAO_COBERTURA = DEFINICAO_COBERTURA_TECNICA = (
    "Percentual de fontes cadastradas que já têm coletor implementado. "
    "Não mede a fração de publicações cobertas nem a qualidade editorial: "
    "fonte cadastrada sem coletor entra como pendência explícita "
    "(fontes_nao_implementadas) e fonte implementada que nunca executou "
    "ainda não conta como cobertura."
)


def registro_cobertura(fonte):
    """Registro de cobertura de uma fonte (campos ausentes ficam `None`)."""
    registro = {
        "source_id": fonte.source_id,
        "nome": fonte.nome,
        "jurisdicao": fonte.jurisdicao,
        "nivel": fonte.nivel,
        "uf": fonte.uf,
        "municipio": fonte.municipio,
        "tipo_acesso": fonte.tipo_acesso,
        "formato": fonte.formato,
        "adapter_family": fonte.adapter_family,
        "collector": fonte.collector,
        "implementado": bool(fonte.implementado),
        "ultima_tentativa": fonte.ultima_tentativa,
        "ultima_coleta_ok": fonte.ultima_execucao_ok,
        "ultima_publicacao_detectada": fonte.ultima_publicacao,
        "itens_coletados": fonte.itens_coletados,
        "erro": fonte.erro,
        "status": fonte.status,
        "duracao": fonte.duracao,
        "layout_changed": fonte.layout_changed,
        # Indicadores que só existem quando o coletor rodou (nunca estimados):
        # ficam em `fonte.extra`, preenchidos por `aplicar_resultado`.
        "modo_ingestao": (fonte.extra or {}).get("modo_ingestao"),
        "cobertura_integral": (fonte.extra or {}).get("cobertura_integral"),
        "fallback_usado": (fonte.extra or {}).get("fallback_usado"),
        "itens_normalizados": (fonte.extra or {}).get("itens_normalizados"),
        "itens_relevantes": (fonte.extra or {}).get("itens_relevantes"),
    }
    return registro


def metricas_agregadas(registry, fontes=None):
    """Métricas do monitor — contagens explícitas, sem percentual enganoso."""
    fontes = fontes if fontes is not None else registry.todas()
    total = len(fontes)
    por_status = {status: 0 for status in ORDEM_STATUS}
    implementadas = 0
    integrais = 0
    com_execucao = 0
    for fonte in fontes:
        por_status[fonte.status] = por_status.get(fonte.status, 0) + 1
        if fonte.implementado:
            implementadas += 1
            if fonte.ultima_tentativa:
                com_execucao += 1
            if (fonte.status == "funcionando"
                    and (fonte.extra or {}).get("cobertura_integral") is True):
                integrais += 1
    cobertura_tecnica = round(100.0 * implementadas / total, 2) if total else 0.0
    cobertura_integral = (round(100.0 * integrais / implementadas, 2)
                          if implementadas else 0.0)
    return {
        "fontes_totais": total,
        "fontes_implementadas": implementadas,
        "fontes_ok": por_status.get("funcionando", 0),
        "fontes_parciais": por_status.get("parcial", 0),
        "fontes_falha": por_status.get("falha", 0),
        "fontes_nao_implementadas": por_status.get("nao_implementado", 0),
        "fontes_implementadas_sem_execucao": por_status.get("implementado", 0),
        "fontes_executadas": com_execucao,
        "cobertura_tecnica_pct": cobertura_tecnica,
        "cobertura_integral_pct": cobertura_integral,
        "definicao_cobertura": DEFINICAO_COBERTURA_TECNICA,
        "definicao_cobertura_tecnica": DEFINICAO_COBERTURA_TECNICA,
        "por_status": por_status,
    }


def contagem_por_nivel(registry):
    """Totais por nível com implementadas × pendentes (o painel usa este recorte)."""
    resumo = {}
    for fonte in registry.todas():
        dados = resumo.setdefault(fonte.nivel, {
            "total": 0, "implementadas": 0, "funcionando": 0, "parciais": 0,
            "falha": 0, "nao_implementadas": 0, "sem_execucao": 0,
            "cobertura_tecnica_pct": 0.0,
        })
        dados["total"] += 1
        if fonte.implementado:
            dados["implementadas"] += 1
            if fonte.status == "funcionando":
                dados["funcionando"] += 1
            elif fonte.status == "parcial":
                dados["parciais"] += 1
            elif fonte.status == "falha":
                dados["falha"] += 1
            elif fonte.status == "implementado":
                dados["sem_execucao"] += 1
        else:
            dados["nao_implementadas"] += 1
    for dados in resumo.values():
        dados["cobertura_tecnica_pct"] = (round(100.0 * dados["implementadas"] / dados["total"], 2)
                                          if dados["total"] else 0.0)
    return resumo


def pendentes(registry):
    """Pendências nomeadas (nada de cobertura implícita)."""
    fontes = [f for f in registry.todas() if not f.implementado]
    por_nivel = {nivel: sum(1 for f in fontes if f.nivel == nivel)
                 for nivel in sorted({f.nivel for f in fontes})}
    return {
        "total": len(fontes),
        "por_nivel": por_nivel,
        "source_ids": [f.source_id for f in fontes],
        "amostra": [f.source_id for f in fontes][:40],
        "truncado": len(fontes) > 40,
    }


def monitor(registry, resultados=None, agora=None, gerado_em=None):
    """Snapshot completo do monitor (é isto que vai para `data/legislation/diarios.json`).

    `resultados` é um mapa opcional `source_id → ResultadoColeta` (ou
    `ResultadoFonteDiario`) que atualiza a saúde antes de medir.
    """
    if resultados:
        for source_id, resultado in resultados.items():
            aplicar_resultado(registry, resultado, source_id=source_id)
    fontes = registry.todas()
    return {
        "gerado_em": gerado_em or ts_iso(),
        "data_referencia": (agora or agora_brt()).date().isoformat(),
        "metricas": metricas_agregadas(registry, fontes),
        "por_nivel": contagem_por_nivel(registry),
        "pendentes": pendentes(registry),
        "fontes": {f.source_id: registro_cobertura(f) for f in fontes},
    }


def aplicar_resultado(registry, resultado, source_id=None, modo_extra=None):
    """Atualiza a saúde de uma fonte a partir de um `ResultadoColeta`/relatório.

    Aceita `ResultadoColeta` ou `ResultadoFonteDiario` (que tem `.coleta`) e as
    duas ordens de chamada usadas no projeto:
    `aplicar_resultado(registry, resultado[, source_id])` e
    `aplicar_resultado(registry, source_id, resultado)`.
    Fonte sem coletor nunca recebe status operacional — continua `nao_implementado`.
    """
    if isinstance(resultado, str):     # assinatura (registry, source_id, resultado)
        resultado, source_id = source_id, resultado
    coleta = getattr(resultado, "coleta", resultado)
    sid = source_id or getattr(coleta, "source_id", None) or getattr(resultado, "source_id", None)
    fonte = registry.obter(sid) if sid else None
    if fonte is None or not fonte.implementado:
        return
    metricas = coleta.metricas
    fonte.atualizar_saude(
        status=coleta.status_registry,
        ultima_tentativa=coleta.tentativa_em,
        ultima_execucao_ok=(coleta.tentativa_em if coleta.status == "ok" else
                            fonte.ultima_execucao_ok),
        ultima_publicacao=coleta.ultima_publicacao,
        itens_coletados=(metricas.itens_fonte or len(coleta.itens)),
        duracao=round(coleta.duracao, 1),
        layout_changed=bool(coleta.layout_changed),
        erro="; ".join(coleta.erros[:1]) or None,
    )
    fonte.extra.update({
        "modo_ingestao": coleta.modo_ingestao,
        "cobertura_integral": coleta.cobertura_integral,
        "fallback_usado": coleta.fallback_usado,
        "verificacao_complementar": coleta.verificacao_complementar,
        "estrutura_fonte": coleta.estrutura_fonte,
        "itens_normalizados": metricas.itens_normalizados,
        "itens_relevantes": getattr(resultado, "metricas", metricas).itens_relevantes,
        "itens_descartados": getattr(resultado, "metricas", metricas).itens_descartados,
        "itens_revisao": getattr(resultado, "metricas", metricas).itens_revisao,
        "duplicados": metricas.duplicados,
        "falhas_parse": metricas.falhas_parse,
        "zero_publicacao_confirmado": coleta.zero_publicacao_confirmado,
        "paginacao_detectada": coleta.paginacao_detectada,
        "truncado": coleta.truncado,
        "layout_evidencia": coleta.layout_evidencia,
        "avisos": list(coleta.avisos),
    })
    if modo_extra:
        fonte.extra.update(modo_extra)
    return fonte


# Aliases documentados (nomes usados em relatórios e testes do projeto).
registro_fonte = registro_cobertura

__all__ = ["monitor", "metricas_agregadas", "contagem_por_nivel", "pendentes",
           "registro_cobertura", "registro_fonte", "aplicar_resultado",
           "CAMPOS_COBERTURA", "DEFINICAO_COBERTURA", "DEFINICAO_COBERTURA_TECNICA"]
