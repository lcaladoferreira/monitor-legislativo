#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarios/states/__init__.py — Diários Oficiais estaduais (FASE 5).

Os **27 entes** (26 estados + Distrito Federal) estão cadastrados no Source
Registry, cada um com `source_id` estável (`estadual_sp`, `estadual_df`, …),
nível `estadual`, UF e status `nao_implementado` — explicitamente pendente.

Nenhum coletor estadual foi escrito ainda, e isso não é escondido:

  · o painel mostra os 27 como `nao_implementado`;
  · `fontes_nao_implementadas=27` aparece nas métricas do Coverage Monitor;
  · `cobertura_tecnica_pct` conta apenas o que existe de fato.

O caminho para implementar um estado (incremental, um por vez):

  1. confirmar o endereço oficial e o formato com a sonda:
         python3 scripts/probe_diarios.py --orgao estadual_sp --url <endpoint>
  2. escolher o tipo de acesso (xml/json/rss/api → preferido; senão html/pdf);
  3. criar `diarios/states/<uf>.py` com uma subclasse de `FonteDiario`
     (reaproveitando `ColetorDouIntegral`/`ColetorDouXMLINLABS` quando o formato
     for o mesmo, e os parsers de `diarios/dou.py` para JSON embutido/HTML);
  4. preencher `url`, `tipo_acesso`, `formato` e `collector` no registry e marcar
     `implementado=True`;
  5. rodar `python3 scripts/update_diarios.py --fonte estadual_<uf> --dry-run`
     e conferir `metricas_ingestao` + `layout_changed` antes de habilitar.

Enquanto o passo 4 não acontece, `implementado=False` — a fonte aparece como
pendência, nunca como cobertura.
"""
from __future__ import annotations

from ..base import UFS  # noqa: F401  (27 entes: 26 estados + DF)
from ..registry import FonteCadastrada, RegistryFontes  # noqa: F401


def estaduais_pendentes(registry):
    """Lista dos entes estaduais ainda sem coletor (transparência do painel)."""
    return [f.source_id for f in registry.por_nivel("estadual") if not f.implementado]


def estaduais_implementados(registry):
    return [f.source_id for f in registry.por_nivel("estadual") if f.implementado]


__all__ = ["UFS", "estaduais_pendentes", "estaduais_implementados",
           "FonteCadastrada", "RegistryFontes"]
