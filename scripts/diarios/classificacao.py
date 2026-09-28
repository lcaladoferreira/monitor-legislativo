#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarios/classificacao.py — classificação temática **depois** da ingestão (FASE 2–3).

Esta etapa roda sobre itens já normalizados e persistidos. Ela não filtra a
coleta: o coletor entrega a edição inteira; aqui decidimos o que é relevante,
o que fica para revisão e o que é descartado — com a trilha de auditoria de
quais grupos temáticos dispararam.

Não há segundo classificador: os padrões vêm de `sources/base.py`
(`CLASSIFICATION_GROUPS` / `FORTE_PATTERNS` / `REVISAR_PATTERNS`), os mesmos já
publicados e testados. `DISCOVERY_TERMS` (antes `TOPICOS_BUSCA`) continua
existindo para as consultas por assunto (fallback/verificação complementar),
mas não define mais a cobertura do Diário Oficial.
"""
from __future__ import annotations

from dataclasses import dataclass, field

try:
    from sources.base import (
        CLASSIFICATION_GROUPS, CLASSIFICATION_PATTERNS, DISCOVERY_TERMS,
        classificar_detalhado, normalizar,
    )
except ImportError:  # executado a partir da raiz do repositório
    from scripts.sources.base import (
        CLASSIFICATION_GROUPS, CLASSIFICATION_PATTERNS, DISCOVERY_TERMS,
        classificar_detalhado, normalizar,
    )

# Tamanho do texto considerado na classificação por item. O item integral fica
# preservado; este limite existe só para não gastar tempo de CPU em publicações
# gigantes (contratos, editais) que já foram classificadas pelo título/início.
LIMITE_TEXTO_CLASSIFICACAO = 20000

RELEVANCIA_FORTE = "forte"
RELEVANCIA_REVISAR = "revisar"


@dataclass
class Classificacao:
    """Resultado auditável da classificação de um item."""

    relevancia: str = None                       # 'forte' | 'revisar' | None
    grupos_tematicos: list = field(default_factory=list)
    padroes_detectados: list = field(default_factory=list)

    @property
    def relevante(self):
        return self.relevancia == RELEVANCIA_FORTE

    @property
    def descartado(self):
        return self.relevancia is None

    @property
    def revisao(self):
        return self.relevancia == RELEVANCIA_REVISAR

    def para_dict(self):
        return {"relevancia": self.relevancia,
                "grupos_tematicos": list(self.grupos_tematicos),
                "padroes_detectados": list(self.padroes_detectados)}


def classificar_item(item, limite=LIMITE_TEXTO_CLASSIFICACAO):
    """Classifica um item normalizado → `Classificacao`.

    Usa título, órgão/hierarquia, tipo do ato e texto (limitado) — nessa ordem de
    importância. Sem sinal claro → `relevancia=None` (descartado), jamais
    "relevante por aproximação".
    """
    hierarquia = item.get("hierarquia") or []
    if isinstance(hierarquia, str):
        hierarquia = [hierarquia]
    detalhe = classificar_detalhado(
        item.get("titulo"),
        " ".join(str(h) for h in hierarquia),
        item.get("orgao"),
        item.get("tipo_ato"),
        (item.get("texto") or "")[:limite],
    )
    return Classificacao(relevancia=detalhe.get("relevancia"),
                         grupos_tematicos=list(detalhe.get("grupos_tematicos") or []),
                         padroes_detectados=list(detalhe.get("padroes_detectados") or []))


def aplicar_classificacao(item, classificacao):
    """Grava a classificação no item (campos do dataset atual + trilha nova)."""
    item["relevancia"] = classificacao.relevancia
    item["revisao_pendente"] = classificacao.revisao
    item["grupos_tematicos"] = list(classificacao.grupos_tematicos)
    item["padroes_tematicos"] = list(classificacao.padroes_detectados)
    return item


def termos_descoberta():
    """Termos de busca ainda usados nos canais de fallback/complemento."""
    return list(DISCOVERY_TERMS)


def grupos_disponiveis():
    return sorted(CLASSIFICATION_GROUPS)


def padroes_do_grupo(grupo):
    return list(CLASSIFICATION_GROUPS.get(grupo) or [])


def resumo_regras():
    """Resumo auditável das regras (aparece no relatório e nos testes)."""
    return {
        "termos_descoberta": list(DISCOVERY_TERMS),
        "total_grupos": len(CLASSIFICATION_GROUPS),
        "total_padroes": len(CLASSIFICATION_PATTERNS),
        "grupos": {g: len(p) for g, p in sorted(CLASSIFICATION_GROUPS.items())},
    }


__all__ = ["Classificacao", "classificar_item", "aplicar_classificacao",
           "termos_descoberta", "grupos_disponiveis", "padroes_do_grupo",
           "resumo_regras", "CLASSIFICATION_GROUPS", "CLASSIFICATION_PATTERNS",
           "DISCOVERY_TERMS", "RELEVANCIA_FORTE", "RELEVANCIA_REVISAR", "normalizar"]
