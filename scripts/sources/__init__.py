#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sources/__init__.py — catálogo dos coletores multiórgão.

Câmara e Senado continuam em `scripts/update_legislation.py` (coletores
originais, intocados). Este pacote acrescenta os conectores dos demais órgãos:

    anpd · cnj · tse · dou · planalto · mcti

Todos seguem o mesmo contrato: `Fonte.coletar(ctx, resultado)` devolve itens
normalizados (título, data, URL oficial, descrição) ou levanta
`FonteIndisponivel` — nunca preenche lacunas com dado estimado.
"""
from .base import (  # noqa: F401
    CLASSIFICATION_GROUPS, CLASSIFICATION_PATTERNS, DISCOVERY_TERMS,
    Canal, Cliente, ContextoFonte, Fonte, FonteIndisponivel, OrcamentoEsgotado,
    ResultadoFonte, classificar_detalhado, classificar_relevancia,
    fontes_disponiveis, instanciar, registrar, TOPICOS_BUSCA,
)

# Importa os módulos para registrar as fontes no catálogo (efeito de importação).
from . import anpd, cnj, tse, dou, planalto, mcti  # noqa: E402,F401

__all__ = ["Canal", "Cliente", "ContextoFonte", "Fonte", "FonteIndisponivel",
           "OrcamentoEsgotado", "ResultadoFonte", "classificar_relevancia",
           "fontes_disponiveis", "instanciar", "registrar", "TOPICOS_BUSCA",
           "DISCOVERY_TERMS", "CLASSIFICATION_GROUPS", "CLASSIFICATION_PATTERNS",
           "classificar_detalhado",
           "anpd", "cnj", "tse", "dou", "planalto", "mcti"]
