#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sources/tse.py — Coletor do TSE (Tribunal Superior Eleitoral).

Fontes oficiais:
  · Publicação oficial dos atos do TSE: Diário Oficial da União (Imprensa
    Nacional) — resoluções e atos normativos do TSE são publicados na Seção 1
    sob "Poder Judiciário/Tribunal Superior Eleitoral". A busca oficial do DOU
    é usada com filtro de órgão e conferência da hierarquia item a item.
  · Portal do TSE (https://www.tse.jus.br) — notícias e páginas de legislação.
    O portal aplica bloqueio de robôs (HTTP 403) para clientes sem navegador;
    quando isso ocorre, o canal é registrado como falho e o painel mostra a
    falha — o monitoramento continua pelos atos publicados no DOU, que é a
    fonte primária oficial de vigência.

Canais:
  · resoluções/atos do TSE por tema (DOU, filtrado para o TSE)
  · resoluções do TSE (DOU, órgão/subórgão — pega a resolução pelo título)
  · notícias oficiais do TSE (portal)  · legislação (portal)  · CKAN

Evidência da sonda (CI, 17/09/2026): a busca do DOU com `s=titulo` devolveu
zero resultados para `orgPrin=Poder Judiciário` (o modo de busca por título não
combina com o filtro de órgão); com `s=todos` + `orgSub=Tribunal Superior
Eleitoral` a mesma consulta devolve os atos do TSE. Por isso o canal usa
`s=todos` com o subórgão explícito e confere o tipo do ato item a item.
"""
from .base import (Canal, Fonte, TOPICOS_BUSCA, normalizar, registrar)

BUSCA = "https://www.in.gov.br/consulta/-/buscar/dou"
ORGAO_JUDICIARIO = "Poder Judiciário"
TSE_CHAVES = ("tribunal superior eleitoral", "justica eleitoral")


def _filtro_tse(item):
    """Mantém apenas atos cuja hierarquia do DOU é do TSE/Justiça Eleitoral."""
    hier = normalizar(item.get("hierarquia") or "")
    return any(c in hier for c in TSE_CHAVES)


def _filtro_resolucao_tse(item):
    """Atos do TSE que são resolução (norma que o monitoramento persegue).

    É `startswith` porque o DOU rotula ora "Resolução", ora "Resolução
    Conjunta"/"Resolução Administrativa" — todos são atos normativos do TSE.
    """
    return _filtro_tse(item) and normalizar(item.get("tipo_ato") or "").startswith(
        normalizar("Resolução"))


@registrar
class TSE(Fonte):
    orgao = "tse"
    nome = "TSE — Tribunal Superior Eleitoral"
    obrigatoria = True
    canais = [
        Canal(
            "atos do TSE por tema (DOU)", BUSCA, formato="html", parser="dou_embutido",
            tipo_padrao="ato_normativo", topicos=TOPICOS_BUSCA, dias=30,
            filtro_tema=_filtro_tse, padrao_href=r"/web/dou/-/",
            url_template=(BUSCA + "?q=%22{topico}%22&s=todos&exactDate=personalizado"
                                  "&sortType=0&delta=50&currentPage=1"
                                  "&publishFrom={from}&publishTo={to}&orgPrin="
                                  "Poder%20Judici%C3%A1rio"),
        ),
        Canal(
            "resoluções do TSE (DOU, órgão/subórgão)", BUSCA, formato="html",
            parser="dou_embutido", tipo_padrao="resolucao", dias=30,
            filtro_tema=_filtro_resolucao_tse, padrao_href=r"/web/dou/-/",
            url_template=(BUSCA + "?q=RESOLU%C3%87%C3%83O&s=todos"
                                  "&exactDate=personalizado&sortType=0&delta=50"
                                  "&currentPage=1&publishFrom={from}&publishTo={to}"
                                  "&orgPrin=Poder%20Judici%C3%A1rio"
                                  "&orgSub=Tribunal%20Superior%20Eleitoral"),
        ),
        Canal(
            "notícias oficiais", "https://www.tse.jus.br/comunicacao/noticias",
            formato="html", parser="plone_html", obrigatorio=False,
            tipo_padrao="noticia", paginas=2, passo=20,
            padrao_href=r"tse\.jus\.br/comunicacao/noticias/\d{4}/[A-Za-z]+/[a-z0-9-]{8,}",
        ),
        Canal(
            "legislação (portal TSE)", "https://www.tse.jus.br/legislacao/compilada",
            formato="html", parser="plone_html", obrigatorio=False,
            tipo_padrao="ato_normativo",
            padrao_href=r"tse\.jus\.br/legislacao/[a-z0-9/-]{4,}",
        ),
        Canal(
            "dados abertos (CKAN)", "https://dadosabertos.tse.jus.br/api/3/action/package_search",
            formato="json", parser="ckan", obrigatorio=False,
            tipo_padrao="dados_abertos",
            opcoes={"params": {"q": "inteligência artificial", "rows": 20}},
        ),
    ]
