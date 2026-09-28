#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarios/__init__.py — camada de Diários Oficiais do Monitor Legislativo.

    scripts/diarios/
        base.py           vocabulário/contrato (item bruto, normalização, saúde)
        registry.py       Source Registry (federal, 27 estaduais, judiciário, municipal)
        dou.py            DOU: XML do INLABS → edição integral → busca temática (fallback)
        states/           entes estaduais (cadastro pronto; coletores incrementais)
        municipal/        adapters municipais por família (querido_diario, api, pdf…)
        classificacao.py  classificação temática (depois da ingestão)
        dedup.py          identidade estável, hash, histórico de alterações
        coverage.py       Coverage Monitor (o que está implementado e o que não está)
        quality.py        quality gate da extração textual (good/degraded/failed)
        pipeline.py       SOURCE → FETCH → RAW → PARSE → NORMALIZE → DEDUP → CLASSIFY → STORE → ALERT

Princípios (não negociáveis, verificados por testes):

  · coletar primeiro; classificar depois — nada de filtro temático na origem;
  · nenhum dado inventado: campo ausente fica ausente (`None`);
  · nenhuma fonte é apresentada como coberta se não estiver implementada;
  · quebra de layout nunca é reportada como "não houve publicação";
  · fonte que falha não derruba as demais nem o build.
"""
from __future__ import annotations

# Coletores disponíveis hoje: {source_id: classe}. Estados e municípios entram
# aqui conforme forem implementados — o registry é quem decide o que roda.
COLETORES = {}


def registrar_coletor(source_id, classe):
    COLETORES[source_id] = classe
    return classe


def coletores_padrao(logger=print):
    """Instancia os coletores implementados (DOU integral + XML + busca temática)."""
    from .dou import ColetorDiarioDou, ColetorDouBuscaTematica, ColetorDouXMLINLABS
    return {
        "dou": ColetorDiarioDou(logger=logger),
        "dou_inlabs_xml": ColetorDouXMLINLABS(logger=logger),
        "dou_busca_tematica": ColetorDouBuscaTematica(logger=logger),
    }


def registry_com_saude(caminho_snapshot=None, logger=print):
    """Registry padrão já com a saúde do último snapshot (quando existir)."""
    from .base import ARQUIVO_SNAPSHOT
    from .registry import registry_padrao
    reg = registry_padrao()
    caminho = caminho_snapshot or ARQUIVO_SNAPSHOT
    if caminho:
        try:
            reg.aplicar_saude(_ler(caminho))
        except Exception:  # noqa: BLE001 — snapshot ausente/ilegível não impede a coleta
            logger(f"    [aviso] snapshot de cobertura ilegível: {caminho}")
    return reg


def _ler(caminho):
    from .base import carregar_json
    return carregar_json(caminho, None) or {}


__all__ = ["COLETORES", "registrar_coletor", "coletores_padrao", "registry_com_saude"]
