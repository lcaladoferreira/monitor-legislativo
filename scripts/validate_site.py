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
  - camada comercial B2B: CTA no cabeçalho, páginas /solucoes, /diagnostico,
    /briefing-executivo e /para-empresas, eventos de analytics, pricing sem
    vazar faixa interna, lead scoring, prova social desativada, separação
    fato oficial × análise e linguagem sem promessa de aconselhamento jurídico

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
        if re.search(r'<meta name="robots" content="[^"]*noindex', html):
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


PAGINAS_COMERCIAIS = ["solucoes/", "diagnostico/", "briefing-executivo/", "para-empresas/"]

EVENTOS_ANALYTICS_OBRIGATORIOS = [
    "commercial_cta_click", "diagnostic_started", "diagnostic_submitted", "briefing_sample_view",
    "pricing_view", "sector_page_view", "high_impact_view", "alert_signup", "demo_request",
    "whatsapp_click",
]

# Guard-rail editorial (item 18): linguagem de aconselhamento jurídico só é
# aceita em contexto de negação/aviso ("não presta...", "não constitui...").
TERMOS_JURIDICOS = ["parecer jurídico", "aconselhamento jurídico", "garantia de conformidade",
                    "consultoria jurídica", "garantimos conformidade", "interpretamos a lei"]
NEGACOES = ("não", "nao ", "sem ", "nunca", "nem ", "nenhum", "nenhuma", "nada", "jamais",
            "não constitui", "não presta", "não emite", "não garante")


def _contexto_negado(html, idx, termo):
    """Aceita o termo apenas em aviso/negação ou em pergunta explícita (FAQ)."""
    janela = html[max(0, idx - 90):idx].lower()
    if any(n in janela for n in NEGACOES):
        return True
    # uso interrogativo: "Isso é aconselhamento jurídico?" (pergunta de FAQ)
    apos = html[idx + len(termo):idx + len(termo) + 4]
    return "?" in apos


def check_commercial(rep, site):
    """Valida a camada comercial B2B (P0) sem afrouxar nenhuma regra existente."""
    html_files = []
    for root, _, files in os.walk(OUT):
        for fn in files:
            if fn.endswith(".html"):
                html_files.append(os.path.join(root, fn))

    # 1) CTA de alta visibilidade + disclaimer em TODAS as páginas
    for path in sorted(html_files):
        rel = os.path.relpath(path, OUT)
        with open(path, encoding="utf-8", errors="replace") as f:
            html = f.read()
        if "nav-cta" not in html:
            rep.err(f"docs/{rel}: CTA comercial do cabeçalho ausente")
        if 'id="monitor-commercial-config"' not in html:
            rep.err(f"docs/{rel}: config comercial/analytics ausente no <head>")
        # 2) termos jurídicos apenas em contexto negado
        low = html.lower()
        for termo in TERMOS_JURIDICOS:
            for m in re.finditer(re.escape(termo), low):
                if not _contexto_negado(low, m.start(), termo):
                    rep.err(f"docs/{rel}: uso de '{termo}' fora de contexto de aviso/negação")

    # 3) Páginas comerciais
    geradas = 0
    for p in PAGINAS_COMERCIAIS:
        fp = os.path.join(OUT, p, "index.html")
        if not os.path.isfile(fp):
            rep.warn(f"docs/{p}: página comercial não gerada (build sem commercial.install?)")
            continue
        geradas += 1
        with open(fp, encoding="utf-8", errors="replace") as f:
            html = f.read()
        for obrig in ("commercial.css", "commercial.js", "Solicitar diagnóstico",
                      "aconselhamento jurídico"):
            if obrig not in html:
                rep.err(f"docs/{p}: elemento comercial obrigatório ausente ({obrig})")
        if "cta-btn" not in html:
            rep.err(f"docs/{p}: sem CTA primário")

    if not geradas:
        return

    # 4) Analytics: catálogo de eventos presente no JS publicado
    js = os.path.join(OUT, "assets", "commercial.js")
    if not os.path.isfile(js):
        rep.err("docs/assets/commercial.js: ausente")
    else:
        with open(js, encoding="utf-8") as f:
            js_txt = f.read()
        for ev in EVENTOS_ANALYTICS_OBRIGATORIOS:
            if ev not in js_txt:
                rep.err(f"commercial.js: evento de analytics não instrumentado ({ev})")
        for obrig in ("dataLayer", "utm_source", "leadScoring", "sendBeacon"):
            if obrig not in js_txt:
                rep.err(f"commercial.js: recurso obrigatório ausente ({obrig})")

    # 5) Config pública de pricing — sem vazar faixa interna nem segredo
    cfg_path = os.path.join(OUT, "data", "commercial.json")
    cfg = load_json(cfg_path, rep, "data/commercial.json")
    if cfg:
        for s in cfg.get("solucoes", []):
            if not s.get("preco_publico") and (s.get("preco_min") or s.get("preco_max")):
                rep.err(f"commercial.json: faixa interna de '{s.get('nome')}' exposta publicamente")
        if not cfg.get("lead_scoring", {}).get("regras"):
            rep.err("commercial.json: regras de lead scoring ausentes")
        regras = cfg.get("lead_scoring", {}).get("regras", [])
        if len(regras) != 7:
            rep.err(f"commercial.json: esperado 7 critérios de lead scoring, encontrado {len(regras)}")
        raw = json.dumps(cfg, ensure_ascii=False).lower()
        for segredo in ("access_key", "apikey", "api_key", "secret", "password", "token"):
            if segredo in raw:
                rep.err(f"commercial.json: possível segredo exposto ({segredo})")
    solucoes_html = os.path.join(OUT, "solucoes", "index.html")
    with open(solucoes_html, encoding="utf-8") as f:
        sh = f.read()
    if "R$ 10.000" in sh or "R$ 20.000" in sh:
        rep.err("docs/solucoes/: faixa interna de Inteligência Institucional publicada (deve ser 'Sob consulta')")
    if "Sob consulta" not in sh:
        rep.err("docs/solucoes/: Inteligência Institucional sem rótulo 'Sob consulta'")

    # 6) Prova social inventada (item 13): nenhuma estrutura de logos/depoimentos
    #     pode aparecer enquanto não houver case real autorizado.
    for path in sorted(html_files):
        rel = os.path.relpath(path, OUT)
        with open(path, encoding="utf-8", errors="replace") as f:
            html = f.read()
        if 'class="logos"' in html or "Quem já usa" in html:
            rep.err(f"docs/{rel}: prova social renderizada sem evidência real autorizada")

    # 7) Amostra de briefing precisa separar fato oficial de análise
    brief = os.path.join(OUT, "briefing-executivo", "index.html")
    with open(brief, encoding="utf-8") as f:
        bh = f.read()
    for obrig in ("tag-fato", "tag-analise", "Fato oficial", "Análise / interpretação",
                  "Ação recomendada", "Fonte oficial", "Por que esta matéria recebeu score"):
        if obrig not in bh:
            rep.err(f"docs/briefing-executivo/: elemento obrigatório ausente ({obrig})")
    if bh.count("brief-item") < 3:
        rep.err("docs/briefing-executivo/: amostra com menos de 3 matérias reais")


def main():
    site = site_url()
    rep = Report()
    print(f"Validando site (domínio oficial: {site}) ...")
    if OLD_DOMAIN in site:
        rep.err("SITE_URL ainda aponta para o GitHub Pages")
    check_data(rep)
    check_docs(rep, site)
    check_commercial(rep, site)
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
