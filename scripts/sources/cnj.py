#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sources/cnj.py — Coletor do CNJ (Conselho Nacional de Justiça).

Fontes oficiais:
  · Sistema de Atos Normativos do CNJ — https://atos.cnj.jus.br/api/atos
    (API pública que alimenta o buscador de atos: tipo, número, data de
    publicação, situação, ementa e URL de detalhe de cada ato)
  · Portal do CNJ — https://www.cnj.jus.br/wp-json/wp/v2/posts
    (API de conteúdo do próprio portal: notícias oficiais com data e link)

Canais:
  · atos normativos por tema   (resoluções, provimentos, portarias, decisões)
  · atos normativos recentes   (últimos atos publicados)
  · notícias oficiais          (portal CNJ, filtro temático item a item)

O filtro temático é conservador: item sem sinal temático claro é descartado e
item duvidoso entra marcado como "revisar" (curadoria editorial).
"""
from .base import Canal, Fonte, TOPICOS_BUSCA, registrar

ATOS = "https://atos.cnj.jus.br/api/atos"
WP = "https://www.cnj.jus.br/wp-json/wp/v2/posts"


@registrar
class CNJ(Fonte):
    orgao = "cnj"
    nome = "CNJ — Conselho Nacional de Justiça"
    obrigatoria = True
    canais = [
        Canal(
            "atos normativos recentes", ATOS, formato="json", parser="cnj_atos",
            tipo_padrao="ato_normativo",
            opcoes={"params": {"per_page": 50, "order": "data_publicacao", "sort": "desc"}},
        ),
        Canal(
            "atos normativos por tema", ATOS, formato="json", parser="cnj_atos",
            tipo_padrao="ato_normativo", topicos=TOPICOS_BUSCA,
            url_template=ATOS + "?search={topico}&per_page=30",
        ),
        Canal(
            "resoluções sobre IA e dados", ATOS, formato="json", parser="cnj_atos",
            tipo_padrao="resolucao", obrigatorio=False, topicos=[
                "inteligência artificial", "algoritmo", "reconhecimento facial",
                "proteção de dados", "deepfake",
            ],
            url_template=ATOS + "?search={topico}&tipo=Resolu%C3%A7%C3%A3o&per_page=30",
        ),
        Canal(
            "notícias oficiais", WP, formato="json", parser="wp_json",
            tipo_padrao="noticia",
            opcoes={"params": {"per_page": 50, "_fields":
                               "id,date,link,title,excerpt,type"}},
        ),
    ]
