#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarios/municipal/adapters.py — famílias de adapter para Diários municipais (FASE 6).

Objetivo: **não** criar um scraper artesanal por prefeitura. Municípios que
compartilham plataforma, agregador ou forma de acesso usam o *mesmo* adapter,
mudando apenas configuração.

Famílias (`adapter_family`):

    querido_diario            agregador nacional de diários municipais (dados
                              abertos + API pública) — um adapter cobre N cidades
    plataforma_compartilhada  mesma plataforma/fornecedor usado por vários
                              municípios (ex.: portais de imprensa oficial)
    api_municipal             API oficial própria do município
    diario_individual         cada município com seu próprio diário, mesmo
                              formato (listagem HTML/PDF) → configuração por cidade
    pdf_listing               diário publicado só como PDF por edição

Nenhum município vem habilitado por padrão e **nenhum endereço é suposto**:
a configuração versionada (`config/diarios_municipios.json`) é preenchida pelo
operador com o endereço confirmado por sonda (`scripts/probe_diarios.py`). Sem
configuração, o registry mostra o município como `nao_implementado` — cobertura
zero declarada, jamais estimada.

Os adapters aqui são a *arquitetura*: `AdapterQueridoDiario` já traz o parser da
lista de edições, mas só coleta quando o município está habilitado na configuração
e o endpoint responde. Falha de endpoint = falha registrada, nunca dado estimado.
"""
from __future__ import annotations

import json
import os
import urllib.parse

from ..base import (BASE, FonteDiario, carregar_json, limpar_texto, normalizar_item, ts_iso)

CONFIG_MUNICIPIOS = os.path.join(BASE, "config", "diarios_municipios.json")

FAMILIAS_ADAPTER = {
    "querido_diario": {
        "descricao": "Agregador nacional de Diários Oficiais municipais (dados abertos).",
        "tipo_acesso": "agregador",
        "formato": "json",
        "como_funciona": ("busca por município (código IBGE) e janela de datas; "
                          "devolve as edições publicadas com URL da publicação"),
        "observacao": ("Endpoint/API precisam ser confirmados por sonda antes de "
                       "habilitar cidades; o adapter é genérico (N municípios)."),
    },
    "plataforma_compartilhada": {
        "descricao": "Mesma plataforma/fornecedor usado por vários municípios.",
        "tipo_acesso": "html",
        "formato": "misto",
        "como_funciona": ("um adapter parametrizado por cidade (slug/ID na URL) "
                          "atende todos os municípios que usam a plataforma"),
        "observacao": "Exige criação de layout + detecção de mudança de layout.",
    },
    "api_municipal": {
        "descricao": "API oficial do próprio município.",
        "tipo_acesso": "api",
        "formato": "json",
        "como_funciona": "endpoint documentado pelo município; parser genérico de lista",
        "observacao": "Preferida sempre que existir — mais estável que scraping.",
    },
    "diario_individual": {
        "descricao": "Diário próprio do município, um endereço por cidade.",
        "tipo_acesso": "html",
        "formato": "html",
        "como_funciona": "listagem oficial + página da edição; configuração por município",
        "observacao": "Último recurso antes de PDF; exige sonda e teste de layout.",
    },
    "pdf_listing": {
        "descricao": "Diário publicado apenas como PDF por edição.",
        "tipo_acesso": "pdf",
        "formato": "pdf",
        "como_funciona": ("listagem oficial de PDFs + extração textual com quality gate "
                          "(scripts/diarios/quality.py); fallback visual fica desligado"),
        "observacao": "Só entra com quality gate ativo: PDF sem camada textual não vira texto inventado.",
    },
}


class AdapterMunicipal(FonteDiario):
    """Base dos adapters municipais: uma família, N municípios."""

    nivel = "municipal"
    adaptador_familia = "nao_aplicavel"
    implementado = False

    def __init__(self, municipio, uf, config=None, logger=print):
        super().__init__(logger=logger)
        self.municipio = municipio
        self.uf = uf
        self.config = dict(config or {})
        self.source_id = self.config.get("source_id") or \
            f"municipal_{str(uf).lower()}_{_slug(municipio)}"
        self.nome = self.config.get("nome") or f"Diário Oficial de {municipio}/{uf}"
        self.url = self.config.get("url")

    def descricao_adapter(self):
        return {"source_id": self.source_id, "adapter_family": self.adaptador_familia,
                "implementado": self.implementado, "configurado": bool(self.url)}


class AdapterQueridoDiario(AdapterMunicipal):
    """Adapter do agregador Querido Diário (um adapter para N municípios).

    Configuração por município (em `config/diarios_municipios.json`):

        {
          "source_id": "municipal_sp_saopaulo",
          "municipio": "São Paulo", "uf": "SP",
          "codigo_ibge": "3550308",
          "adapter_family": "querido_diario",
          "url": "<endpoint confirmado por sonda>",
          "habilitado": true
        }

    O parser aceita a lista de edições devolvida em JSON (`gazettes`/`data`/`items`)
    e usa apenas campos presentes: data, edição, URL oficial da publicação e
    trechos/excertos quando houver. Campo ausente fica ausente.
    """

    adaptador_familia = "querido_diario"
    tipo_acesso = "agregador"
    formato = "json"
    implementado = False
    modo_padrao = "agregador"
    marcadores_estruturais = (r'"(gazettes|data|items|results)"',)

    @property
    def endpoint(self):
        return (self.config.get("url")
                or os.environ.get("MONITOR_QUERIDO_DIARIO_API") or "").strip() or None

    def url_consulta(self, dia, endpoint=None):
        base = endpoint or self.endpoint
        if not base:
            return None
        params = {"territory_ids": self.config.get("codigo_ibge") or "",
                  "published_since": dia, "published_until": dia,
                  "page_size": int(self.config.get("page_size") or 100)}
        params = {k: v for k, v in params.items() if v not in (None, "")}
        separador = "&" if "?" in base else "?"
        return base + separador + urllib.parse.urlencode(params)

    def coletar(self, ctx, resultado):
        if not self.implementado or not self.ativo:
            raise RuntimeError(f"{self.source_id}: adapter municipal não habilitado")
        endpoint = self.endpoint
        if not endpoint:
            raise RuntimeError(f"{self.source_id}: endpoint não confirmado "
                               f"(preencha 'url' na configuração após a sonda)")
        for dia in ctx.dias_janela():
            ctx.checar(5)
            url = self.url_consulta(dia, endpoint)
            resultado.endpoints.append(url)
            resp = ctx.cliente.get(url, accept="application/json")
            if not resp.ok:
                resultado.canais_falhos.append(f"querido_diario {dia}")
                resultado.erros.append(f"querido_diario {dia}: {resp.erro or resp.status}")
                continue
            dados = resp.json()
            if dados is None:
                resultado.metricas.falhas_parse += 1
                resultado.erros.append(f"querido_diario {dia}: resposta não é JSON")
                continue
            itens = parse_querido_diario(dados, self, dia)
            if not itens:
                self.avaliar_layout(resultado, resp.texto, self.marcadores_estruturais,
                                    itens, f"querido_diario {dia}")
            resultado.itens.extend(itens)
            resultado.canais_ok.append(f"querido_diario {dia}")
            resultado.metricas.itens_fonte += len(itens)
        return resultado


def parse_querido_diario(dados, fonte, dia):
    """Lista de edições do agregador → itens brutos (só o que existe no payload)."""
    lista = None
    if isinstance(dados, list):
        lista = dados
    elif isinstance(dados, dict):
        for chave in ("gazettes", "data", "items", "results", "resultados"):
            if isinstance(dados.get(chave), list):
                lista = dados[chave]
                break
    itens = []
    for registro in lista or []:
        if not isinstance(registro, dict):
            continue
        url = (registro.get("url") or registro.get("txt_url")
               or registro.get("edition_url") or "").strip() or None
        if not url:
            continue
        excertos = registro.get("excerpts") or registro.get("excerto") or []
        if isinstance(excertos, list):
            texto = "\n".join(limpar_texto(e, 800) for e in excertos if isinstance(e, str))
        else:
            texto = limpar_texto(excertos, 2000)
        itens.append({
            "id_oficial": str(registro.get("id") or registro.get("edition") or "") or None,
            "titulo": limpar_texto(registro.get("edition") or registro.get("titulo")
                                   or f"Diário Oficial de {fonte.municipio}/{fonte.uf}", 300),
            "texto": texto or None,
            "data": registro.get("date") or registro.get("data") or dia,
            "secao": None,
            "edicao": registro.get("edition") or registro.get("edicao"),
            "tipo_ato": None,
            "orgao": registro.get("territory_name") or None,
            "hierarquia": None,
            "url_oficial": url,
            "arquivo_fonte": registro.get("filename") or registro.get("arquivo"),
            "coletado_em": ts_iso(),
            "modo_ingestao": "agregador",
            "origem": "Querido Diário (agregador de dados abertos)",
            "extras": {"codigo_ibge": registro.get("territory_id") or None,
                       "publicado_em": registro.get("date") or None},
        })
    return [normalizar_item(i, fonte) for i in itens if i.get("url_oficial")]


def _slug(valor):
    return "".join(c for c in str(valor or "").lower().replace(" ", "_")
                   if c.isalnum() or c in "_-") or "municipio"


ADAPTERS = {
    "querido_diario": AdapterQueridoDiario,
}

# Famílias que já têm código pronto no repositório (habilitadas por configuração
# e endpoint confirmado). As demais são arquitetura documentada, sem implementação.
IMPLEMENTADAS = {"querido_diario": True}


def adapters_disponiveis():
    """Estado real de cada família de adapter (nunca finge implementação)."""
    return {familia: {"descricao": meta["descricao"],
                      "implementado": bool(IMPLEMENTADAS.get(familia)),
                      "tipo_acesso": meta["tipo_acesso"],
                      "formato": meta["formato"],
                      "observacao": meta["observacao"]}
            for familia, meta in FAMILIAS_ADAPTER.items()}


def carregar_config_municipios(caminho=None):
    """Configuração versionada dos municípios (vazia por padrão: sem cobertura fictícia)."""
    dados = carregar_json(caminho or CONFIG_MUNICIPIOS, None)
    if not isinstance(dados, dict):
        return {"meta": {}, "municipios": []}
    dados.setdefault("municipios", [])
    return dados


def salvar_config_municipios(dados, caminho=None):
    from ..base import salvar_json
    return salvar_json(caminho or CONFIG_MUNICIPIOS, dados)


__all__ = ["FAMILIAS_ADAPTER", "AdapterMunicipal", "AdapterQueridoDiario", "ADAPTERS",
           "adapters_disponiveis", "parse_querido_diario", "carregar_config_municipios",
           "salvar_config_municipios", "CONFIG_MUNICIPIOS"]
