#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_site.py — Validações automáticas do Monitor Legislativo de IA.

Detecta:
  - JSON inválido em data/legislation
  - proposições duplicadas (id e chave casa/tipo/número/ano)
  - IDs duplicados entre arquivos
  - URLs oficiais ausentes ou inválidas quando obrigatórias
  - scores fora da faixa / classificação incompatível
  - páginas HTML sem <title> ou sem canonical
  - canonical/sitemap/robots apontando para domínio errado
  - links internos quebrados (hrefs do SITE_URL sem arquivo correspondente)
  - referências remanescentes ao domínio antigo do GitHub Pages
  - área editorial /artigos/: esquema dos artigos, datas, canonical,
    sitemap (1 URL por artigo com lastmod = modified_at), JSON-LD NewsArticle,
    preservação de published_at, feed público espelhado em docs/data

Uso: python3 scripts/validate_site.py
Saída: exit 0 se OK (avisos permitidos), exit 1 se houver erros.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data", "legislation")
OUT = os.path.join(BASE, "docs")
OLD_DOMAIN = "lcaladoferreira.github.io/monitor-legislativo"


def site_url():
    """Lê o SITE_URL canônico de scripts/build_site.py (fonte única)."""
    with open(os.path.join(BASE, "scripts", "build_site.py"), encoding="utf-8") as f:
        m = re.search(r'SITE_URL\s*=\s*"([^"]+)"', f.read())
    if not m:
        raise SystemExit("SITE_URL não encontrado em scripts/build_site.py")
    return m.group(1).rstrip("/")


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)


def load_json(path, rep, label):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        rep.err(f"{label}: arquivo não encontrado ({path})")
    except json.JSONDecodeError as e:
        rep.err(f"{label}: JSON inválido — {e}")
    return None


def band(score):
    if score >= 90:
        return "CRÍTICO"
    if score >= 75:
        return "MUITO RELEVANTE"
    if score >= 60:
        return "RELEVANTE"
    if score >= 40:
        return "MONITORAR"
    return "BAIXA PRIORIDADE"


def check_data(rep):
    props_f = load_json(os.path.join(DATA, "propositions.json"), rep, "propositions.json")
    laws_f = load_json(os.path.join(DATA, "laws.json"), rep, "laws.json")
    tl_f = load_json(os.path.join(DATA, "timeline.json"), rep, "timeline.json")
    pm_f = load_json(os.path.join(DATA, "parliamentarians.json"), rep, "parliamentarians.json")
    ev_f = load_json(os.path.join(DATA, "events.json"), rep, "events.json")
    up_f = load_json(os.path.join(DATA, "updates.json"), rep, "updates.json")
    cat_f = load_json(os.path.join(DATA, "categories.json"), rep, "categories.json")

    props = (props_f or {}).get("proposicoes", [])
    # duplicadas: id
    seen, dup = set(), set()
    for p in props:
        if p.get("id") in seen:
            dup.add(p.get("id"))
        seen.add(p.get("id"))
    for d in sorted(dup):
        rep.err(f"propositions.json: id duplicado '{d}'")
    # duplicadas: chave lógica
    seen2 = {}
    for p in props:
        key = (p.get("casa_origem"), p.get("tipo"), p.get("numero"), p.get("ano"))
        if key in seen2:
            rep.err(f"propositions.json: proposição duplicada {key} "
                    f"({seen2[key]} x {p.get('id')})")
        seen2[key] = p.get("id")
    # campos obrigatórios
    required = ["id", "tipo", "numero", "ano", "titulo", "ementa", "casa_origem",
                "situacao", "url_oficial"]
    for p in props:
        for field in required:
            if not p.get(field):
                rep.err(f"propositions.json: {p.get('id')}: campo obrigatório ausente '{field}'")
        url = p.get("url_oficial") or ""
        if url and not re.match(r"https?://", url):
            rep.err(f"propositions.json: {p.get('id')}: url_oficial inválida '{url}'")
        imp = p.get("impacto") or {}
        s = imp.get("score")
        if not isinstance(s, int) or not (0 <= s <= 100):
            rep.err(f"propositions.json: {p.get('id')}: score inválido ({s!r})")
        elif not str(imp.get("classificacao", "")).startswith(band(s)):
            rep.err(f"propositions.json: {p.get('id')}: classificação "
                    f"'{imp.get('classificacao')}' incompatível com score {s} (esperado {band(s)}...)")
        for doc in p.get("documentos", []) or []:
            if not (doc.get("url") or "").startswith("http"):
                rep.warn(f"propositions.json: {p.get('id')}: documento sem URL válida ({doc})")
    # mudanças apontam para proposições existentes?
    prop_ids = {p.get("id") for p in props}
    for m in (up_f or {}).get("mudancas", []):
        if m.get("proposicao") and m["proposicao"] not in prop_ids:
            rep.warn(f"updates.json: mudança '{(m.get('titulo') or '')[:60]}' referencia "
                     f"proposição inexistente '{m.get('proposicao')}'")
        if not m.get("fonte_url"):
            rep.warn(f"updates.json: mudança sem fonte_url ('{(m.get('titulo') or '')[:60]}')")
    if not (up_f or {}).get("execucoes"):
        rep.err("updates.json: sem registros de execução")
    # leis / timeline / parlamentares / eventos: ids únicos + urls
    for label, items, url_field in (
            ("laws.json", (laws_f or {}).get("normas", []), "url"),
            ("parliamentarians.json", (pm_f or {}).get("parlamentares", []), None),
            ("events.json", (ev_f or {}).get("eventos", []), "fonte_url")):
        ids = [x.get("id") for x in items]
        if len(ids) != len(set(ids)):
            rep.err(f"{label}: ids duplicados")
        for x in items:
            if url_field and not (x.get(url_field) or "").startswith("http"):
                rep.warn(f"{label}: {x.get('id')}: {url_field} ausente/inválida")
    for e in (tl_f or {}).get("eventos", []):
        if not (e.get("fonte_url") or "").startswith("http"):
            rep.warn(f"timeline.json: evento '{(e.get('titulo') or '')[:50]}' sem fonte_url válida")
    cats = (cat_f or {}).get("categorias", [])
    if len({c.get("id") for c in cats}) != len(cats):
        rep.err("categories.json: ids duplicados")
    return props


def local_path_for_url(url, site):
    """Mapeia URL interna do site para arquivo em docs/. Retorna path ou None."""
    if not url.startswith(site):
        return None
    rel = url[len(site):].split("?", 1)[0].split("#", 1)[0]
    if rel.startswith("/"):
        rel = rel[1:]
    if rel == "" or rel.endswith("/"):
        rel = rel + "index.html" if rel else "index.html"
    return os.path.join(OUT, rel)


def check_docs(rep, site):
    if not os.path.isdir(OUT):
        rep.err("docs/: diretório não encontrado (execute build_site.py)")
        return
    html_files = []
    for root, _, files in os.walk(OUT):
        for fn in files:
            if fn.endswith(".html"):
                html_files.append(os.path.join(root, fn))
    if not html_files:
        rep.err("docs/: nenhuma página HTML encontrada")
        return
    href_re = re.compile(r'href="([^"]+)"')
    for path in sorted(html_files):
        with open(path, encoding="utf-8", errors="replace") as f:
            html = f.read()
        rel = os.path.relpath(path, OUT)
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        if not m or not m.group(1).strip():
            rep.err(f"docs/{rel}: sem <title>")
        mc = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        if not mc:
            rep.err(f"docs/{rel}: sem canonical")
        elif not mc.group(1).startswith(site + "/") and mc.group(1).rstrip("/") != site:
            rep.err(f"docs/{rel}: canonical fora do domínio oficial ({mc.group(1)[:80]})")
        if OLD_DOMAIN in html:
            rep.err(f"docs/{rel}: contém referência ao domínio antigo do GitHub Pages")
        if rel not in ("app/index.html", "login/index.html") and re.search(r'<meta name="robots" content="[^"]*noindex', html):
            rep.err(f"docs/{rel}: contém noindex (bloqueia indexação)")
        for href in href_re.findall(html):
            if href.startswith(site):
                lp = local_path_for_url(href, site)
                if lp and not os.path.exists(lp):
                    # permite âncora em páginas de dados? não — todo link interno deve existir
                    rep.err(f"docs/{rel}: link interno quebrado → {href[len(site):][:90]}")
    # robots.txt e sitemap.xml
    robots = os.path.join(OUT, "robots.txt")
    try:
        with open(robots, encoding="utf-8") as f:
            rtxt = f.read()
        if OLD_DOMAIN in rtxt:
            rep.err("robots.txt: aponta para o domínio antigo")
        if f"Sitemap: {site}/sitemap.xml" not in rtxt:
            rep.err("robots.txt: sem Sitemap para o domínio oficial")
    except FileNotFoundError:
        rep.err("robots.txt: ausente")
    sm = os.path.join(OUT, "sitemap.xml")
    try:
        with open(sm, encoding="utf-8") as f:
            stxt = f.read()
        if OLD_DOMAIN in stxt:
            rep.err("sitemap.xml: contém URLs do domínio antigo")
        root = ET.fromstring(stxt)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [u.text for u in root.findall("s:url/s:loc", ns)]
        if not urls:
            rep.err("sitemap.xml: nenhuma URL encontrada")
        for u in urls:
            if not u.startswith(site + "/") and u.rstrip("/") != site:
                rep.err(f"sitemap.xml: URL fora do domínio oficial ({u[:80]})")
            lp = local_path_for_url(u, site)
            if lp and not os.path.exists(lp):
                rep.err(f"sitemap.xml: URL sem arquivo correspondente ({u[len(site):][:80]})")
        if len(urls) != len(set(urls)):
            rep.err("sitemap.xml: URLs duplicadas")
    except FileNotFoundError:
        rep.err("sitemap.xml: ausente")
    except ET.ParseError as e:
        rep.err(f"sitemap.xml: XML inválido — {e}")


def check_artigos(rep, site):
    """Validações da área editorial /artigos/ (quando o dataset existir)."""
    arts_path = os.path.join(BASE, "data", "articles", "articles.json")
    state_path = os.path.join(BASE, "data", "articles", "editorial_state.json")
    if not os.path.isfile(arts_path):
        if os.path.isdir(os.path.join(OUT, "artigos")):
            rep.err("docs/artigos/ existe sem data/articles/articles.json")
        return
    arts_f = load_json(arts_path, rep, "articles.json")
    if arts_f is None:
        return
    arts = arts_f.get("artigos", [])
    acoes_validas = {"new_article", "article_update", "ignored"}
    obrigatorios = ["id", "editorial_topic_id", "slug", "title", "description",
                    "published_at", "modified_at", "source_change_ids", "url",
                    "status", "revision_count", "revisions", "official_sources"]
    ids, slugs = set(), set()
    for a in arts:
        ref = (a.get("slug") or a.get("id") or "?")[:60]
        for campo in obrigatorios:
            if campo not in a:
                rep.err(f"articles.json: {ref}: campo ausente '{campo}'")
        if a.get("id") in ids:
            rep.err(f"articles.json: id duplicado {a.get('id')}")
        ids.add(a.get("id"))
        slug = a.get("slug") or ""
        if slug in slugs:
            rep.err(f"articles.json: slug duplicado {slug}")
        slugs.add(slug)
        if slug and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
            rep.err(f"articles.json: slug fora do padrão: {slug[:60]}")
        pub, mod = a.get("published_at"), a.get("modified_at")
        if pub and mod and str(mod) < str(pub):
            rep.err(f"articles.json: {ref}: modified_at ({mod}) < published_at ({pub})")
        if a.get("status") == "published":
            n_rev = len(a.get("revisions") or [])
            if int(a.get("revision_count") or 0) != n_rev:
                rep.err(f"articles.json: {ref}: revision_count ({a.get('revision_count')}) "
                        f"≠ nº de revisões ({n_rev})")
            # TODA revisão além da criação deve preservar published_at
            if n_rev > 1 and (a["revisions"][0].get("date") or "") != str(pub):
                rep.err(f"articles.json: {ref}: primeira revisão não é a data de publicação")
    # estado editorial: ações válidas e nenhuma mudança em duplicidade
    st = load_json(state_path, rep, "editorial_state.json") or {}
    n_actions = 0
    for cid, v in (st.get("processadas") or {}).items():
        n_actions += 1
        if v.get("editorial_action") not in acoes_validas:
            rep.err(f"editorial_state.json: ação inválida '{v.get('editorial_action')}' para {cid[:16]}")
        if cid not in (st.get("pendentes") or {}):
            continue
    dup = set(st.get("processadas") or {}) & set(st.get("pendentes") or {})
    if dup:
        rep.err(f"editorial_state.json: {len(dup)} mudança(s) processada(s) E pendente(s)")
    # cota diária: somente new_article conta
    por_dia = {}
    for a in arts:
        por_dia[str(a.get("published_at"))[:10]] = por_dia.get(str(a.get("published_at"))[:10], 0) + 1
    for dia, n in por_dia.items():
        if n > 1:
            rep.err(f"articles.json: {n} artigos novos publicados no mesmo dia ({dia}) — "
                    f"cota diária de 1 novo artigo violada")
    # sitemap: uma única URL por artigo, lastmod = modified_at, canonical estável
    sm = os.path.join(OUT, "sitemap.xml")
    if arts and os.path.isfile(sm):
        try:
            root = ET.fromstring(open(sm, encoding="utf-8").read())
            ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = [u.text for u in root.findall("s:url/s:loc", ns)]
            for a in arts:
                if a.get("status") != "published":
                    continue
                esperada = f"{site}/artigos/{a['slug']}/"
                n_vezes = sum(1 for u in urls if u == esperada)
                if n_vezes != 1:
                    rep.err(f"sitemap.xml: artigo {a['slug'][:50]} aparece {n_vezes}x "
                            f"(esperado 1)")
        except ET.ParseError:
            pass  # já validado em check_docs
    # páginas geradas
    if arts:
        idx = os.path.join(OUT, "artigos", "index.html")
        if not os.path.isfile(idx):
            rep.err("docs/artigos/index.html ausente com artigos publicados")
        for a in arts:
            if a.get("status") != "published":
                continue
            pg = os.path.join(OUT, "artigos", a["slug"], "index.html")
            if not os.path.isfile(pg):
                rep.err(f"docs/artigos/{a['slug'][:50]}/index.html ausente")
                continue
            html = open(pg, encoding="utf-8").read()
            canon = re.search(r'<link rel="canonical" href="([^"]+)"', html)
            if canon and canon.group(1) != f"{site}/artigos/{a['slug']}/":
                rep.err(f"artigo {a['slug'][:50]}: canonical divergente do slug")
            if f'"datePublished": "{a.get("published_at")}' not in html.replace(': ', ': ').replace('"datePublished":"', '"datePublished": "'):
                if f'"datePublished":"{a.get("published_at")}' not in html:
                    rep.err(f"artigo {a['slug'][:50]}: JSON-LD sem datePublished correto")
            if f'"dateModified":"{a.get("modified_at")}' not in html and \
                    f'"dateModified": "{a.get("modified_at")}' not in html:
                rep.err(f"artigo {a['slug'][:50]}: JSON-LD sem dateModified correto")
            if "NewsArticle" not in html:
                rep.err(f"artigo {a['slug'][:50]}: JSON-LD sem NewsArticle")
            if a.get("modified_at") and a["modified_at"] != a.get("published_at") \
                    and "Atualizado em" not in html:
                rep.err(f"artigo {a['slug'][:50]}: atualizado sem exibir 'Atualizado em'")
            if "Leandro Calado" not in html or "LCF Consulting" not in html:
                rep.err(f"artigo {a['slug'][:50]}: autoria ausente")
    # feed público espelhado
    docs_arts = os.path.join(OUT, "data", "articles.json")
    if os.path.isfile(docs_arts):
        try:
            if json.load(open(docs_arts, encoding="utf-8")) != arts_f:
                rep.err("docs/data/articles.json difere de data/articles/articles.json")
        except json.JSONDecodeError:
            rep.err("docs/data/articles.json: JSON inválido")
    # descoberta por IA deve citar /artigos/ quando há artigos
    if arts:
        for nome in ("llms.txt", "ai-content.md"):
            fpath = os.path.join(OUT, nome)
            if os.path.isfile(fpath) and "/artigos/" not in open(fpath, encoding="utf-8").read():
                rep.err(f"{nome}: não cita /artigos/ com artigos publicados")


def main():
    site = site_url()
    rep = Report()
    print(f"Validando site (domínio oficial: {site}) ...")
    if OLD_DOMAIN in site:
        rep.err("SITE_URL ainda aponta para o GitHub Pages")
    check_data(rep)
    check_docs(rep, site)
    check_artigos(rep, site)
    # varredura geral do domínio antigo em arquivos-fonte (exceto histórico git).
    # Ignora a linha de definição da constante OLD_DOMAIN (usada por esta checagem);
    # qualquer outro uso (ex.: SITE_URL regressivo) é erro.
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d != ".git"]
        for fn in files:
            if fn.endswith((".html", ".py", ".json", ".txt", ".xml", ".md", ".yml", ".css", ".js")):
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, BASE)
                if rel.startswith("docs/"):
                    continue  # docs/ já reportado acima, arquivo a arquivo
                try:
                    with open(p, encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if OLD_DOMAIN in line and "OLD_DOMAIN" not in line:
                                rep.err(f"{rel}:{i}: contém referência ao domínio antigo")
                                break
                except OSError:
                    pass
    print(f"\nErros: {len(rep.errors)} · Avisos: {len(rep.warnings)}")
    for e in rep.errors:
        print(f"  ERRO: {e}")
    for w in rep.warnings[:30]:
        print(f"  aviso: {w}")
    if len(rep.warnings) > 30:
        print(f"  ... +{len(rep.warnings) - 30} avisos")
    if rep.errors:
        print("\nVALIDAÇÃO FALHOU")
        return 1
    print("\nVALIDAÇÃO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

