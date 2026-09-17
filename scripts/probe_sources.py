#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_sources.py — Sonda de endpoints oficiais (diagnóstico, não altera o dataset).

Consulta uma lista de candidatos a endpoint de cada órgão (ANPD, CNJ, TSE, DOU,
Planalto, MCTI) e imprime, para cada um: HTTP status, content-type, tamanho e um
trecho do corpo. Serve para decidir, com evidência real, qual fonte estruturada
cada coletor deve usar — nada aqui é gravado no dataset.

Uso:
    python3 scripts/probe_sources.py                 # todos os candidatos
    python3 scripts/probe_sources.py --orgao anpd    # apenas um órgão
    python3 scripts/probe_sources.py --exemplos      # imprime trechos maiores
    python3 scripts/probe_sources.py --salvar-dir out/probe   # grava os corpos
"""
import argparse
import gzip
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36 monitor-legislativo-ia/1.0")

# (orgao, rótulo, url, accept) — accept None = cabeçalhos de navegador padrão
CANDIDATOS = [
    # ------------------------------------------------------------------ ANPD
    ("anpd", "noticias-lista", "https://www.gov.br/anpd/pt-br/assuntos/noticias", None),
    ("anpd", "noticias-pagina2", "https://www.gov.br/anpd/pt-br/assuntos/noticias?b_start:int=20", None),
    ("anpd", "noticias-RSS", "https://www.gov.br/anpd/pt-br/assuntos/noticias/RSS", None),
    ("anpd", "noticias-rss-minusculo", "https://www.gov.br/anpd/pt-br/assuntos/noticias/rss", None),
    ("anpd", "api-rest-noticias", "https://www.gov.br/anpd/pt-br/assuntos/noticias/++api++", "application/json"),
    ("anpd", "busca-interna", "https://www.gov.br/anpd/pt-br/search?SearchableText=intelig%C3%AAncia%20artificial", None),
    ("anpd", "legislacao", "https://www.gov.br/anpd/pt-br/assuntos/legislacao", None),
    ("anpd", "regulacao", "https://www.gov.br/anpd/pt-br/assuntos/regulacao", None),
    ("anpd", "consultas-publicas", "https://www.gov.br/anpd/pt-br/assuntos/consultas-publicas", None),
    ("anpd", "agenda-regulatoria", "https://www.gov.br/anpd/pt-br/assuntos/agenda-regulatoria", None),
    ("anpd", "atos-normativos", "https://www.gov.br/anpd/pt-br/acesso-a-informacao/atos-normativos", None),
    ("anpd", "participamaisbrasil", "https://www.gov.br/participamaisbrasil/consultas-publicas", None),

    # ------------------------------------------------------------------- CNJ
    ("cnj", "wp-posts", "https://www.cnj.jus.br/wp-json/wp/v2/posts?per_page=3&_fields=id,date,link,title,excerpt", "application/json"),
    ("cnj", "wp-busca-ia", "https://www.cnj.jus.br/wp-json/wp/v2/posts?search=intelig%C3%AAncia%20artificial&per_page=3&_fields=id,date,link,title", "application/json"),
    ("cnj", "wp-busca-artificial", "https://www.cnj.jus.br/wp-json/wp/v2/posts?search=artificial&per_page=3&_fields=id,date,link,title", "application/json"),
    ("cnj", "wp-busca-algoritmo", "https://www.cnj.jus.br/wp-json/wp/v2/posts?search=algoritmo&per_page=3&_fields=id,date,link,title", "application/json"),
    ("cnj", "wp-paginas-busca", "https://www.cnj.jus.br/wp-json/wp/v2/pages?search=intelig%C3%AAncia%20artificial&per_page=3&_fields=id,date,link,title", "application/json"),
    ("cnj", "wp-categorias", "https://www.cnj.jus.br/wp-json/wp/v2/categories?per_page=5&_fields=id,name,slug", "application/json"),
    ("cnj", "atos-lista", "https://atos.cnj.jus.br/atos", None),
    ("cnj", "atos-api-guess", "https://atos.cnj.jus.br/api/atos?q=inteligencia%20artificial", "application/json"),
    ("cnj", "atos-api-v1", "https://atos.cnj.jus.br/api/v1/atos?search=inteligencia", "application/json"),
    ("cnj", "site-busca", "https://www.cnj.jus.br/?s=intelig%C3%AAncia+artificial", None),
    ("cnj", "wp-resolucoes-busca", "https://www.cnj.jus.br/wp-json/wp/v2/posts?search=resolu%C3%A7%C3%A3o%20intelig%C3%AAncia%20artificial&per_page=3&_fields=id,date,link,title", "application/json"),

    # ------------------------------------------------------------------- TSE
    ("tse", "noticias-lista", "https://www.tse.jus.br/comunicacao/noticias", None),
    ("tse", "noticias-RSS", "https://www.tse.jus.br/comunicacao/noticias/RSS", None),
    ("tse", "noticias-rss2", "https://www.tse.jus.br/rss/noticias", None),
    ("tse", "api-rest-noticias", "https://www.tse.jus.br/comunicacao/noticias/++api++", "application/json"),
    ("tse", "busca-site", "https://www.tse.jus.br/@@search-es?SearchableText=intelig%C3%AAncia%20artificial", None),
    ("tse", "legislacao", "https://www.tse.jus.br/legislacao/compilada", None),
    ("tse", "resolucoes-2026", "https://www.tse.jus.br/legislacao/compilada/resolucao/2026", None),
    ("tse", "atos-normativos", "https://www.tse.jus.br/legislacao/atos-normativos", None),
    ("tse", "ckan-packages", "https://dadosabertos.tse.jus.br/api/3/action/package_list", "application/json"),
    ("tse", "noticias-mes", "https://www.tse.jus.br/comunicacao/noticias/2026/Setembro", None),
    ("tse", "jurisprudencia-busca", "https://www.tse.jus.br/jurisprudencia/decisoes/@@search-es?SearchableText=intelig%C3%AAncia%20artificial", None),

    # ------------------------------------------------------------------- DOU
    ("dou", "busca-json", "https://www.in.gov.br/consulta/-/buscar/dou?q=%22intelig%C3%AAncia+artificial%22&s=todos&exactDate=personalizado&sortType=0&delta=20&currentPage=1&publishFrom=10-09-2026&publishTo=17-09-2026", "application/json"),
    ("dou", "busca-html", "https://www.in.gov.br/consulta/-/buscar/dou?q=%22intelig%C3%AAncia+artificial%22&s=todos&exactDate=personalizado&sortType=0&delta=20&currentPage=1&publishFrom=10-09-2026&publishTo=17-09-2026", None),
    ("dou", "busca-filtro-orgao", "https://www.in.gov.br/consulta/-/buscar/dou?q=intelig%C3%AAncia+artificial&s=todos&exactDate=personalizado&sortType=0&delta=20&currentPage=1&publishFrom=10-09-2026&publishTo=17-09-2026&orgPrin=presidencia-da-republica", None),
    ("dou", "leiturajornal", "https://www.in.gov.br/leiturajornal?data=17-09-2026&secao=do1", "application/json"),
    ("dou", "legado-consulta", "https://pesquisa.in.gov.br/imprensa/jsp/visualiza/index.jsp?jornal=515&pagina=1&data=17/09/2026", None),
    ("dou", "item", "https://www.in.gov.br/web/dou/-/despacho-minc-n-164-de-16-de-setembro-de-2026-732378994", None),

    # -------------------------------------------------------------- Planalto
    ("planalto", "gov-br-planalto", "https://www.gov.br/planalto/pt-br", None),
    ("planalto", "gov-br-noticias", "https://www.gov.br/planalto/pt-br/acompanhe-o-planalto/noticias", None),
    ("planalto", "gov-br-legislacao", "https://www.gov.br/planalto/pt-br/acesso-a-informacao/legislacao", None),
    ("planalto", "legislacao-portal", "https://www4.planalto.gov.br/legislacao/", None),
    ("planalto", "planalto-ccivil", "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/lei/l15000.htm", None),
    ("planalto", "lexml-oai", "https://www.lexml.gov.br/oai?verb=Identify", "application/xml"),
    ("planalto", "lexml-sru", "https://www.lexml.gov.br/busca/SRU?operation=searchRetrieve&version=1.1&maximumRecords=3&query=%22inteligencia%20artificial%22", "application/xml"),
    ("planalto", "lexml-busca", "https://www.lexml.gov.br/busca/search?f1-tipoDocumento=Legisla%C3%A7%C3%A3o&keyword=inteligencia+artificial", None),
    ("planalto", "dou-planalto-lei", "https://www.in.gov.br/consulta/-/buscar/dou?q=&s=todos&exactDate=personalizado&sortType=0&delta=20&currentPage=1&publishFrom=10-09-2026&publishTo=17-09-2026&artType=Lei&orgPrin=presidencia-da-republica", None),

    # ------------------------------------------------------------------ MCTI
    ("mcti", "noticias", "https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/noticias/noticias-julho-outubro-2026", None),
    ("mcti", "noticias-RSS", "https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/noticias/noticias-julho-outubro-2026/RSS", None),
    ("mcti", "api-rest-noticias", "https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/noticias/noticias-julho-outubro-2026/++api++", "application/json"),
    ("mcti", "busca-interna", "https://www.gov.br/mcti/pt-br/search?SearchableText=intelig%C3%AAncia%20artificial", None),
    ("mcti", "portarias", "https://www.gov.br/mcti/pt-br/acesso-a-informacao/legislacao/portarias", None),
    ("mcti", "atos-normativos", "https://www.gov.br/mcti/pt-br/acesso-a-informacao/legislacao", None),
    ("mcti", "consultas-publicas", "https://www.gov.br/mcti/pt-br/acesso-a-informacao/participacao-social/consultas-publicas", None),
    ("mcti", "programas", "https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/programas-e-projetos", None),

    # ------------------------------------------------------- sanidade atual
    ("camara", "proposicoes", "https://dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo=PL&ano=2026&itens=2&ordem=DESC&ordenarPor=id", "application/json"),
    ("senado", "pesquisa", "https://legis.senado.leg.br/dadosabertos/materia/pesquisa/lista?sigla=PL&ano=2026&v=7", "application/json"),
]

# ------------------------------------------- candidatos plone.restapi (@search)
# Os sites do gov.br migraram para Volto (React): o HTML cru não traz a
# listagem. A API oficial por trás dessas páginas é o plone.restapi (++api++),
# com o endpoint @search — estruturado, paginado e estável.
API_GOVBR = [
    ("anpd", "api-root", "https://www.gov.br/anpd/++api++", "application/json"),
    ("anpd", "api-search-noticias", "https://www.gov.br/anpd/++api++/@search?portal_type=News%20Item&b_size=5&sort_on=effective&sort_order=descending", "application/json"),
    ("anpd", "api-search-noticias-path", "https://www.gov.br/anpd/++api++/@search?path=/anpd/pt-br/assuntos/noticias&b_size=5&sort_on=effective&sort_order=descending", "application/json"),
    ("anpd", "api-search-tema", "https://www.gov.br/anpd/++api++/@search?SearchableText=inteligencia%20artificial&b_size=5", "application/json"),
    ("anpd", "api-folder-noticias", "https://www.gov.br/anpd/++api++/pt-br/assuntos/noticias?b_size=5", "application/json"),
    ("anpd", "api-folder-legislacao", "https://www.gov.br/anpd/++api++/pt-br/assuntos/legislacao?b_size=5", "application/json"),
    ("anpd", "api-folder-regulacao", "https://www.gov.br/anpd/++api++/pt-br/assuntos/regulacao?b_size=5", "application/json"),
    ("anpd", "api-search-documentos", "https://www.gov.br/anpd/++api++/@search?portal_type=File&b_size=5&sort_on=effective&sort_order=descending", "application/json"),
    ("mcti", "api-root", "https://www.gov.br/mcti/++api++", "application/json"),
    ("mcti", "api-search-noticias", "https://www.gov.br/mcti/++api++/@search?portal_type=News%20Item&b_size=5&sort_on=effective&sort_order=descending", "application/json"),
    ("mcti", "api-search-tema", "https://www.gov.br/mcti/++api++/@search?SearchableText=inteligencia%20artificial&b_size=5", "application/json"),
    ("mcti", "api-search-portarias", "https://www.gov.br/mcti/++api++/@search?SearchableText=portaria&portal_type=File&b_size=5", "application/json"),
    ("mcti", "api-search-legislacao-path", "https://www.gov.br/mcti/++api++/@search?path=/mcti/pt-br/acesso-a-informacao/legislacao&b_size=5&sort_on=effective&sort_order=descending", "application/json"),
    ("planalto", "api-root", "https://www.gov.br/planalto/++api++", "application/json"),
    ("planalto", "api-search-noticias", "https://www.gov.br/planalto/++api++/@search?portal_type=News%20Item&b_size=5&sort_on=effective&sort_order=descending", "application/json"),
    ("planalto", "api-search-tema", "https://www.gov.br/planalto/++api++/@search?SearchableText=inteligencia%20artificial&b_size=5", "application/json"),
    ("tse", "api-root", "https://www.tse.jus.br/++api++", "application/json"),
    ("tse", "api-search-noticias", "https://www.tse.jus.br/++api++/@search?portal_type=News%20Item&b_size=5&sort_on=effective&sort_order=descending", "application/json"),
    ("tse", "api-search-tema", "https://www.tse.jus.br/++api++/@search?SearchableText=inteligencia%20artificial&b_size=5", "application/json"),
    ("tse", "api-search-resolucao", "https://www.tse.jus.br/++api++/@search?SearchableText=resolucao%20inteligencia%20artificial&b_size=5", "application/json"),
    ("cnj", "api-root", "https://www.cnj.jus.br/wp-json", "application/json"),
    ("cnj", "wp-busca-ia-sem-artificial", "https://www.cnj.jus.br/wp-json/wp/v2/posts?search=intelig%C3%AAncia%20artificial%20IA&per_page=3&_fields=id,date,link,title", "application/json"),
    ("cnj", "wp-busca-IA", "https://www.cnj.jus.br/wp-json/wp/v2/posts?search=IA&per_page=3&_fields=id,date,link,title", "application/json"),
    ("cnj", "wp-busca-lgpd", "https://www.cnj.jus.br/wp-json/wp/v2/posts?search=LGPD&per_page=3&_fields=id,date,link,title", "application/json"),
    ("dou", "busca-json-ajax", "https://www.in.gov.br/consulta/-/buscar/dou?q=intelig%C3%AAncia+artificial&s=todos&exactDate=personalizado&sortType=0&delta=20&currentPage=1&publishFrom=10-09-2026&publishTo=17-09-2026", "application/json"),
    ("dou", "secao1-dia", "https://www.in.gov.br/leiturajornal?data=17-09-2026&secao=do1", "application/json"),
    ("dou", "api-oficial", "https://www.in.gov.br/api/consulta/publicacao?data=17-09-2026&secao=do1", "application/json"),
    ("dou", "busca-titulo", "https://www.in.gov.br/consulta/-/buscar/dou?q=%22intelig%C3%AAncia+artificial%22&s=titulo&exactDate=personalizado&sortType=0&delta=20&currentPage=1&publishFrom=01-01-2026&publishTo=17-09-2026", None),
    ("planalto", "planalto-lexml-novo", "https://www.lexml.gov.br/busca/search?keyword=inteligencia+artificial", None),
    ("planalto", "planalto-legislacao-pesquisa", "https://www4.planalto.gov.br/legislacao/portal-legis/legislacao-1", None),
]
CANDIDATOS = CANDIDATOS + API_GOVBR

MARCADORES = [
    ("json", lambda b, ct: ct.startswith("application/json") or b.lstrip()[:1] in "{["),
    ("rss", lambda b, ct: "<rss" in b[:2000].lower() or "<feed" in b[:2000].lower()),
    ("atom", lambda b, ct: "<feed" in b[:2000].lower()),
    ("jsonArray", lambda b, ct: "jsonArray" in b[:200000]),
    ("plone-restapi", lambda b, ct: "@id" in b[:2000] and "items" in b[:20000]),
    ("wp-json", lambda b, ct: '"rendered"' in b[:20000]),
]


def fetch(url, accept=None, timeout=45):
    headers = {"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
               "Accept": accept or ("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")}
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except OSError:
                    pass
            return {"status": r.status, "ct": (r.headers.get("Content-Type") or ""),
                    "body": raw, "segundos": round(time.monotonic() - t0, 2),
                    "final_url": r.geturl()}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "ct": (e.headers.get("Content-Type") or ""),
                "body": e.read()[:4000], "segundos": round(time.monotonic() - t0, 2),
                "final_url": getattr(e, "url", url)}
    except Exception as e:  # noqa: BLE001 — sonda: qualquer falha vira resultado
        return {"status": "ERR", "ct": "", "erro": f"{type(e).__name__}: {e}",
                "body": b"", "segundos": round(time.monotonic() - t0, 2), "final_url": url}


def resumo_estrutura(body_bytes):
    """Sinais úteis para decidir o parser (sem imprimir o corpo inteiro)."""
    txt = body_bytes.decode("utf-8", "replace")
    achados = [nome for nome, fn in MARCADORES if fn(txt, "")][:4]
    if "<a href" in txt.lower():
        achados.append(f"links={len(re.findall(r'<a href', txt, re.I))}")
    if "<item" in txt.lower():
        achados.append(f"itens_rss={len(re.findall(r'<item[ >]', txt, re.I))}")
    if "b_start" in txt:
        achados.append("paginacao=b_start")
    if "data-json" in txt or "#json" in txt:
        achados.append("json-embutido")
    return ",".join(achados)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sonda de endpoints oficiais do monitor.")
    ap.add_argument("--orgao", action="append", default=None,
                    help="filtra por órgão (pode repetir)")
    ap.add_argument("--exemplos", action="store_true", help="imprime trechos maiores")
    ap.add_argument("--limite-exemplo", type=int, default=400)
    ap.add_argument("--salvar-dir", default=None,
                    help="diretório para gravar os corpos (para inspeção offline)")
    ap.add_argument("--amostra-bytes", type=int, default=24000,
                    help="bytes preservados por endpoint no arquivo de amostras")
    args = ap.parse_args(argv)

    alvos = [c for c in CANDIDATOS if not args.orgao or c[0] in args.orgao]
    if args.salvar_dir:
        os.makedirs(os.path.join(args.salvar_dir, "amostras"), exist_ok=True)

    ok_total = 0
    linhas_resumo = []
    for org, rotulo, url, accept in alvos:
        res = fetch(url, accept)
        body = res.get("body") or b""
        txt = body.decode("utf-8", "replace")
        print(f"\n=== [{org}] {rotulo}")
        print(f"    GET {url}")
        print(f"    status={res['status']} ct={res['ct'][:60]} bytes={len(body)} "
              f"t={res['segundos']}s final={res['final_url'][:120]}")
        if res.get("erro"):
            print(f"    erro={res['erro']}")
        else:
            est = resumo_estrutura(body)
            print(f"    sinais: {est or '-'}")
            amostra = re.sub(r"\s+", " ", txt[:args.limite_exemplo])
            print(f"    amostra: {amostra}")
        if res["status"] == 200 and body:
            ok_total += 1
            linhas_resumo.append({"orgao": org, "rotulo": rotulo, "url": url,
                                  "status": res["status"], "ct": res["ct"],
                                  "bytes": len(body), "sinais": resumo_estrutura(body)})
            if args.salvar_dir:
                nome = re.sub(r"[^a-zA-Z0-9_.-]", "_", f"{org}__{rotulo}")[:80]
                ext = ".json" if "json" in res["ct"] else (".xml" if "xml" in res["ct"] else ".html")
                with open(os.path.join(args.salvar_dir, nome + ext), "wb") as f:
                    f.write(body[:400000])
                campos = ["TIT:", "DATA:", "RES:", "URL:"] if "json" in res["ct"] else []
                with open(os.path.join(args.salvar_dir, "amostras", nome + ".txt"),
                          "w", encoding="utf-8") as f:
                    f.write(f"URL: {url}\nACCEPT: {accept}\nSTATUS: {res['status']} "
                            f"CT: {res['ct']}\nSINAIS: {resumo_estrutura(body)}\n---\n")
                    f.write(txt[:args.amostra_bytes])

    print(f"\n--- {ok_total}/{len(alvos)} candidatos responderam 200 ---")
    if args.salvar_dir:
        with open(os.path.join(args.salvar_dir, "_resumo.json"), "w", encoding="utf-8") as f:
            json.dump(linhas_resumo, f, ensure_ascii=False, indent=2)
        print(f"corpos salvos em {args.salvar_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
