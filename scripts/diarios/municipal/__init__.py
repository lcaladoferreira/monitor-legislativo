#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarios/municipal/__init__.py — Diários municipais (FASE 6).

Arquitetura pronta, cobertura explícita: **nenhum município é monitorado hoje**.
O registry de municípios é alimentado por `config/diarios_municipios.json`
(versionado e vazio por padrão) e cada município declara sua `adapter_family`
(querido_diario, plataforma_compartilhada, api_municipal, diario_individual,
pdf_listing), de modo que vários municípios compartilhem o mesmo adapter.

Fonte vinda da configuração sem `habilitado: true` fica `nao_implementado` — o
painel mostra a pendência em vez de uma cobertura que não existe.
"""
from __future__ import annotations

from ..registry import FonteCadastrada
from .adapters import (  # noqa: F401
    ADAPTERS, CONFIG_MUNICIPIOS, FAMILIAS_ADAPTER, AdapterMunicipal,
    AdapterQueridoDiario, adapters_disponiveis, carregar_config_municipios,
    parse_querido_diario, salvar_config_municipios,
)

# UF de um código IBGE (2 primeiros dígitos) — usado só para validar a configuração.
_UF_POR_CODIGO_IBGE = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}


def uf_do_codigo_ibge(codigo):
    """UF derivada do código IBGE oficial (None quando o código não é reconhecido)."""
    codigo = str(codigo or "").strip()
    return _UF_POR_CODIGO_IBGE.get(codigo[:2]) if len(codigo) >= 2 else None


def fontes_municipais_do_config(caminho=None):
    """Constrói as entradas de registry a partir da configuração versionada.

    Regra: só entra como `implementado=True` o município com `habilitado: true`,
    `adapter_family` com implementação existente e `url` confirmada. Todo o resto
    é cadastro pendente — sem cobertura.
    """
    config = carregar_config_municipios(caminho)
    fontes = []
    for entrada in (config.get("municipios") or []):
        if not isinstance(entrada, dict):
            continue
        municipio = (entrada.get("municipio") or "").strip()
        uf = (entrada.get("uf") or uf_do_codigo_ibge(entrada.get("codigo_ibge")) or "").strip().upper()
        if not municipio or not uf:
            # Configuração incompleta não vira fonte: nada é suposto.
            continue
        familia = (entrada.get("adapter_family") or "nao_aplicavel").strip()
        url = (entrada.get("url") or "").strip() or None
        habilitado = bool(entrada.get("habilitado")) and url is not None and \
            bool(IMPLEMENTACOES.get(familia))
        fonte = FonteCadastrada(
            source_id=entrada.get("source_id")
            or f"municipal_{uf.lower()}_{str(municipio).lower().replace(' ', '_')}",
            nome=entrada.get("nome") or f"Diário Oficial de {municipio}/{uf}",
            nivel="municipal",
            uf=uf,
            municipio=municipio,
            poder=entrada.get("poder") or "todos",
            url=url,
            tipo_acesso=(FAMILIAS_ADAPTER.get(familia, {}) or {}).get("tipo_acesso", "nao_definido"),
            formato=(FAMILIAS_ADAPTER.get(familia, {}) or {}).get("formato", "nao_definido"),
            collector=(f"scripts/diarios/municipal/adapters.py::{ADAPTERS[familia].__name__}"
                       if habilitado else None),
            implementado=habilitado,
            obrigatorio=False,
            adapter_family=familia if familia in FAMILIAS_ADAPTER else "nao_aplicavel",
            observacao=(entrada.get("observacao")
                        or ("Município habilitado na configuração." if habilitado else
                            "Cadastro pendente: falta habilitar/confirmar adapter, "
                            "endpoint oficial e formato por sonda — nenhuma cobertura "
                            "é declarada.")),
        )
        fontes.append(fonte)
    return fontes


# Reexportado para o registry (evita import circular com adapters).
IMPLEMENTACOES = {"querido_diario": True}


__all__ = ["FAMILIAS_ADAPTER", "AdapterMunicipal", "AdapterQueridoDiario", "ADAPTERS",
           "adapters_disponiveis", "carregar_config_municipios",
           "salvar_config_municipios", "fontes_municipais_do_config",
           "uf_do_codigo_ibge", "parse_querido_diario", "CONFIG_MUNICIPIOS"]
