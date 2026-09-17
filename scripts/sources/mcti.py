#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sources/mcti.py — Coletor do MCTI (Ministério da Ciência, Tecnologia e Inovação).

Fontes oficiais:
  · Publicação oficial dos atos do MCTI: Diário Oficial da União (Imprensa
    Nacional) — portarias, resoluções, instruções normativas e atos do
    Ministério aparecem na Seção 1/2 sob "Ministério da Ciência, Tecnologia e
    Inovação". A busca oficial do DOU é usada com filtro de órgão e conferência
    da hierarquia item a item (é a via que funciona de forma estável para
    robôs, sem desafio anti-bot).
  · Portal do MCTI (https://www.gov.br/mcti) — notícias, portarias publicadas,
    planos e consultas públicas. O portal do gov.br aplica desafio anti-bot
    (F5) para clientes que não executam JavaScript; quando isso ocorre o canal
    entra como falho no painel, sem inventar conteúdo.

Canais:
  · atos do MCTI por tema (DOU)          · notícias institucionais (portal)
  · portarias publicadas (portal)        · planos, programas e consultas
"""
from .base import (Canal, Fonte, TOPICOS_BUSCA, normalizar, registrar)

BUSCA = "https://www.in.gov.br/consulta/-/buscar/dou"
ORGAO_MCTI = "Ministério da Ciência, Tecnologia e Inovação"
PORTAL = "https://www.gov.br/mcti/pt-br"


def _filtro_mcti(item):
    """Mantém apenas atos cuja hierarquia do DOU é do MCTI (ou de suas unidades)."""
    hier = normalizar(item.get("hierarquia") or "")
    return hier.startswith(normalizar(ORGAO_MCTI))


@registrar
class MCTI(Fonte):
    orgao = "mcti"
    nome = "MCTI — Ministério da Ciência, Tecnologia e Inovação"
    obrigatoria = True
    canais = [
        Canal(
            "atos do MCTI por tema (DOU)", BUSCA, formato="html", parser="dou_embutido",
            tipo_padrao="portaria", topicos=TOPICOS_BUSCA, dias=30,
            filtro_tema=_filtro_mcti, padrao_href=r"/web/dou/-/",
            url_template=(BUSCA + "?q=%22{topico}%22&s=todos&exactDate=personalizado"
                                  "&sortType=0&delta=50&currentPage=1"
                                  "&publishFrom={from}&publishTo={to}&orgPrin="
                                  "Minist%C3%A9rio%20da%20Ci%C3%AAncia%2C%20Tecnologia"
                                  "%20e%20Inova%C3%A7%C3%A3o"),
        ),
        Canal(
            "notícias institucionais", PORTAL + "/acompanhe-o-mcti/noticias",
            formato="html", parser="plone_html", obrigatorio=False,
            tipo_padrao="noticia",
            padrao_href=r"gov\.br/mcti/pt-br/acompanhe-o-mcti/noticias/[a-z0-9-]{8,}",
        ),
        Canal(
            "portarias publicadas", PORTAL + "/acesso-a-informacao/legislacao/portarias",
            formato="html", parser="plone_html", obrigatorio=False,
            tipo_padrao="portaria",
            padrao_href=r"gov\.br/mcti/pt-br/acesso-a-informacao/legislacao/[a-z0-9/-]{4,}",
        ),
        Canal(
            "planos, programas e consultas", PORTAL + "/acompanhe-o-mcti/programas-e-projetos",
            formato="html", parser="plone_html", obrigatorio=False,
            tipo_padrao="programa",
            padrao_href=r"gov\.br/mcti/pt-br/[a-z0-9/-]{6,}",
        ),
    ]
