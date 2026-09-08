#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_site.py — Gera o site estático do Monitor Legislativo de IA a partir de /data/legislation.

Uso: python3 scripts/build_site.py
Saída: /docs (compatível com GitHub Pages na opção "main /docs").

Sem dependências externas. Cada execução regenera todas as páginas a partir do
dataset versionado em /data/legislation (fonte única da verdade).
"""
import json
import os
import re
import shutil
from datetime import date, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data", "legislation")
ASSETS = os.path.join(BASE, "scripts", "assets")
OUT = os.path.join(BASE, "docs")

# Ajuste se o site for publicado em outro domínio (usado em canonical/OG/sitemap)
SITE_URL = "https://lcaladoferreira.github.io/monitor-legislativo"
SITE_NAME = "Monitor Legislativo de IA"
TAGLINE = "Monitoramento público, documentado e auditável da legislação brasileira de Inteligência Artificial"

EXECUTION_DATE = "2026-09-08"


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def esc(t):
    if t is None:
        return ""
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def slugify_prop(pid):
    # camara_pl_2338_2023 -> pl-2338-2023
    return re.sub(r"^(camara|senado|congresso)_", "", pid).replace("_", "-")


def prop_fs_path(pid):
    # caminho do arquivo no sistema (relativo a docs/)
    return f"proposicoes/{slugify_prop(pid)}/index.html"


def fmt_date(d):
    if not d:
        return "—"
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(d)


def days_ago(d, ref=None):
    ref = ref or date(2026, 9, 8)
    try:
        dt = datetime.strptime(d, "%Y-%m-%d").date()
        return (ref - dt).days
    except (ValueError, TypeError):
        return None


def rel_label(d):
    n = days_ago(d)
    if n is None:
        return fmt_date(d)
    if n <= 0:
        return "Hoje"
    if n == 1:
        return "Ontem"
    return f"{n} dias atrás"


def score_class(s):
    if s >= 90:
        return "score-critico"
    if s >= 75:
        return "score-muito"
    if s >= 60:
        return "score-relevante"
    if s >= 40:
        return "score-monitorar"
    return "score-baixa"


def score_label(s):
    if s >= 90:
        return "CRÍTICO"
    if s >= 75:
        return "MUITO RELEVANTE"
    if s >= 60:
        return "RELEVANTE"
    if s >= 40:
        return "MONITORAR"
    return "BAIXA PRIORIDADE"


def status_group(p):
    s = (p.get("situacao") or "").lower()
    pid = p["id"]
    if "convertida em lei" in s or "transformada em norma" in s:
        return "aprovada_lei"
    if "à sanção" in s or "aguarda sanção" in s:
        return "a_sancao"
    if "arquivada" in s:
        return "arquivada"
    return "em_tramitacao"


STATUS_LABEL = {
    "em_tramitacao": ("Em tramitação", "status-active"),
    "a_sancao": ("À sanção presidencial", "status-approved"),
    "aprovada_lei": ("Convertida em lei", "status-law"),
    "arquivada": ("Arquivada", "status-archived"),
}


def cat_map():
    cats = load("categories.json")["categorias"]
    return {c["id"]: c for c in cats}


def prop_link(p):
    return f'{SITE_URL}/proposicoes/{slugify_prop(p["id"])}/'


# ---------------------------------------------------------------- layout
def page(title, desc, path, body, extra_head="", og_type="website", jsonld=None):
    canon = SITE_URL + "/" + path if path else SITE_URL + "/"
    crumbs = ""
    nav_items = [
        ("", "Início"),
        ("proposicoes/", "Proposições"),
        ("leis/", "Leis e normas"),
        ("timeline/", "Timeline"),
        ("parlamentares/", "Parlamentares"),
        ("agenda/", "Agenda"),
        ("relatorio/", "Relatório"),
    ]
    nav_parts = []
    for u, l in nav_items:
        cls = ' class="active"' if path == u else ""
        nav_parts.append(f'<a href="{SITE_URL}/{u}"{cls}>{l}</a>')
    nav = "".join(nav_parts)
    ld = ""
    if jsonld:
        ld = '<script type="application/ld+json">' + json.dumps(jsonld, ensure_ascii=False) + "</script>"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canon}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="{og_type}">
<meta property="og:locale" content="pt_BR">
<meta property="og:url" content="{canon}">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="{SITE_URL}/assets/style.css">
{extra_head}
{ld}
</head>
<body>
<header class="site">
  <div class="wrap nav">
    <div class="brand">
      <a href="{SITE_URL}/">{SITE_NAME}</a>
      <small>Inteligência Artificial · Brasil</small>
    </div>
    <nav class="links" aria-label="Principal">{nav}</nav>
  </div>
</header>
<main>
{body}
</main>
<footer class="site">
  <div class="wrap cols">
    <div>
      <h4>Monitor Legislativo de IA</h4>
      <p>{TAGLINE}. Dados estruturados, fontes oficiais e histórico de alterações versionados no repositório.</p>
    </div>
    <div>
      <h4>Dados</h4>
      <p><a href="{SITE_URL}/data/propositions.json">propositions.json</a><br>
      <a href="{SITE_URL}/data/laws.json">laws.json</a><br>
      <a href="{SITE_URL}/data/timeline.json">timeline.json</a><br>
      <a href="{SITE_URL}/data/updates.json">updates.json</a></p>
    </div>
    <div>
      <h4>Metodologia</h4>
      <p>Última execução do monitoramento: <b>{fmt_date(EXECUTION_DATE)}</b>.<br>
      Fontes primárias: Câmara, Senado, Congresso, Planalto, DOU, TSE, CNJ e ANPD.<br>
      <a href="{SITE_URL}/relatorio/">Relatório da execução e metodologia</a></p>
    </div>
    <div>
      <h4>Aviso</h4>
      <p>Conteúdo informativo baseado em fontes oficiais. Não substitui os textos legais e as fichas de tramitação das Casas do Congresso Nacional.</p>
    </div>
  </div>
</footer>
</body>
</html>"""


def write(path, content):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def tags_for_prop(p, cats):
    out = []
    sg = status_group(p)
    lbl, cls = STATUS_LABEL[sg]
    out.append(f'<span class="tag {cls}">{lbl}</span>')
    for c in p.get("categorias", [])[:4]:
        out.append(f'<span class="tag cat">{esc(cats[c]["nome"])}</span>')
    return " ".join(out)


# ---------------------------------------------------------------- páginas
def build_home(props, laws, events, updates, timeline, cats):
    mudancas = sorted(updates["mudancas"], key=lambda m: m["data"], reverse=True)[:6]
    changes_html = "".join(
        f'<div class="change-item"><div class="when">{esc(rel_label(m["data"]))} · {fmt_date(m["data"])}</div>'
        f'<h3><a href="{SITE_URL}/proposicoes/">{esc(m["titulo"])}</a></h3>'
        f'<p>{esc(m["descricao"])}</p>'
        f'<p style="margin-top:6px;font-size:12.5px"><a href="{m["fonte_url"]}" target="_blank" rel="noopener">Fonte: {esc(m["fonte_url"][:90])}…</a></p></div>'
        for m in mudancas
    )

    active = [p for p in props if status_group(p) == "em_tramitacao"]
    archived = [p for p in props if status_group(p) == "arquivada"]
    to_sancao = [p for p in props if status_group(p) == "a_sancao"]
    laws_ok = [l for l in laws if "Vigente" in l.get("status", "")]
    mv7 = len([m for m in updates["mudancas"] if days_ago(m["data"]) is not None and days_ago(m["data"]) <= 7])
    mv30 = len([m for m in updates["mudancas"] if days_ago(m["data"]) is not None and days_ago(m["data"]) <= 30])

    top = sorted(props, key=lambda p: -p["impacto"]["score"])[:6]
    top_html = "".join(
        f'<div class="card"><h3><a href="{prop_link(p)}">{esc(p["tipo"])} {p["numero"]}/{p["ano"]} — {esc(p["titulo"])}</a></h3>'
        f'<p>{esc((p.get("resumo") or p["ementa"])[:220])}…</p>'
        f'<div class="meta"><span class="score-badge {score_class(p["impacto"]["score"])}">Score {p["impacto"]["score"]}/100 · {esc(p["impacto"]["classificacao"].split(" (")[0])}</span>'
        f'{tags_for_prop(p, cats)}</div></div>'
        for p in top
    )

    agenda_soon = [e for e in events["eventos"] if e.get("janela") in ("proximos_7_dias", "proximos_30_dias")]
    agenda_html = "".join(
        f'<div class="card"><h3>{esc(e["titulo"])}</h3>'
        f'<p><b>{fmt_date(e.get("data_inicio"))}</b> · {esc(e["casa"])} · {esc(e["tipo"])}</p>'
        f'<p>{esc(e["tema"][:200])}</p></div>'
        for e in agenda_soon
    ) or '<div class="card"><p>Nenhum evento futuro confirmado na agenda oficial da Câmara para o período eleitoral. A Comissão Especial do PL 2338/2023 não tem pauta publicada.</p></div>'

    cat_chips = " ".join(
        f'<a class="tag cat" href="{SITE_URL}/proposicoes/">{esc(c["nome"])}</a>'
        for c in list(cats.values())[:12]
    )

    body = f"""
<div class="hero"><div class="wrap">
  <div class="kicker">Sistema de inteligência legislativa · Execução de {fmt_date(EXECUTION_DATE)}</div>
  <h1>Inteligência Artificial — Monitoramento Legislativo Brasileiro</h1>
  <p class="lead">Central pública de acompanhamento de projetos de lei, leis, resoluções e atos regulatórios federais sobre inteligência artificial no Brasil — com AI Legislative Impact Score, timeline histórica, mapa de relações entre proposições e registro auditável de mudanças.</p>
  <div class="updated">Última verificação das fontes oficiais: <b>{fmt_date(EXECUTION_DATE)}</b> · {len(props)} proposições monitoradas · {len(laws)} normas mapeadas · <a href="#o-que-mudou">veja o que mudou recentemente</a></div>
</div></div>

<section class="block" id="o-que-mudou"><div class="wrap">
  <h2 class="section-title">O que mudou na regulação de IA</h2>
  <p class="section-sub">Alterações recentes com impacto documentado. Nada é publicado sem fonte oficial. Quando não há mudança relevante, registramos apenas a verificação.</p>
  {changes_html}
</div></section>

<section class="block"><div class="wrap">
  <h2 class="section-title">Dashboard</h2>
  <p class="section-sub">Indicadores do banco legislativo nesta execução.</p>
  <div class="grid cols-4">
    <div class="metric blue"><div class="num">{len(props)}</div><div class="lbl">Projetos monitorados</div></div>
    <div class="metric green"><div class="num">{len(active)}</div><div class="lbl">Em tramitação</div></div>
    <div class="metric"><div class="num">{len(archived)}</div><div class="lbl">Arquivados</div></div>
    <div class="metric yellow"><div class="num">{len(to_sancao)}</div><div class="lbl">À sanção</div></div>
    <div class="metric green"><div class="num">{len(laws_ok)}</div><div class="lbl">Normas vigentes mapeadas</div></div>
    <div class="metric"><div class="num">{len(agenda_soon)}</div><div class="lbl">Eventos futuros previstos</div></div>
    <div class="metric"><div class="num">{mv7}</div><div class="lbl">Movimentações (7 dias)</div></div>
    <div class="metric"><div class="num">{mv30}</div><div class="lbl">Movimentações (30 dias)</div></div>
  </div>
</div></section>

<section class="block"><div class="wrap">
  <h2 class="section-title">Matérias de maior impacto agora</h2>
  <p class="section-sub">Ordenadas pelo AI Legislative Impact Score — abrangência, estágio, proximidade de votação e efeito regulatório. <a href="{SITE_URL}/proposicoes/">Ver todas as proposições com filtros →</a></p>
  <div class="grid cols-3">{top_html}</div>
</div></section>

<section class="block"><div class="wrap">
  <h2 class="section-title">Estado da regulação de IA no Brasil</h2>
  <p class="section-sub">Síntese editorial — fatos e interpretação separados. Análise completa na <a href="{SITE_URL}/relatorio/">página de relatório</a>.</p>
  <div class="note"><b>Em uma frase:</b> o Brasil tem hoje leis pontuais vigentes (LGPD, ECA Digital, Lei 15.487/2026, resoluções TSE/CNJ e decretos do Marco Civil) e um marco geral de IA (PL 2338/2023) aprovado no Senado, mas parado há 16 meses na Câmara — com votação oficialmente adiada para depois das eleições de outubro/2026, enquanto o Redata (infraestrutura de data centers) já foi aprovado pelo Congresso e aguarda sanção.</div>
</div></section>

<section class="block"><div class="wrap">
  <h2 class="section-title">Agenda legislativa de IA</h2>
  <p class="section-sub">Próximos eventos e marcos normativos. <a href="{SITE_URL}/agenda/">Agenda completa →</a></p>
  <div class="grid cols-3">{agenda_html}</div>
</div></section>

<section class="block"><div class="wrap">
  <h2 class="section-title">Categorias temáticas</h2>
  <p class="section-sub">Classificação das matérias em até 30 categorias, de regulação geral a soberania digital. Veja os filtros na página de proposições.</p>
  <div style="display:flex;gap:8px;flex-wrap:wrap">{cat_chips} <a class="tag cat" href="{SITE_URL}/proposicoes/">+ todas</a></div>
</div></section>
"""
    jsonld = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "Monitor Legislativo de Inteligência Artificial no Brasil",
        "description": TAGLINE,
        "url": SITE_URL + "/",
        "keywords": ["regulação inteligência artificial Brasil", "PL 2338/2023", "marco legal da IA", "lei de IA", "Brazil AI law"],
        "temporalCoverage": "2019/2026",
        "dateModified": EXECUTION_DATE,
        "creator": {"@type": "Organization", "name": SITE_NAME},
    }
    write("index.html", page(
        "Inteligência Artificial — Monitoramento Legislativo Brasileiro",
        "Central pública de acompanhamento da legislação de IA no Brasil: PL 2338/2023 (marco legal), Redata, leis vigentes, timeline, agenda e parlamentares. Dados com fonte oficial.",
        "", body, jsonld=jsonld))


def build_propositions(props, cats):
    rows = []
    years = sorted({str(p["ano"]) for p in props}, reverse=True)
    for p in sorted(props, key=lambda x: -x["impacto"]["score"]):
        sg = status_group(p)
        lbl, cls = STATUS_LABEL[sg]
        cats_csv = "," + ",".join(str(c) for c in p.get("categorias", [])) + ","
        search = " ".join(filter(None, [
            p["titulo"], p["ementa"], p.get("autor", {}).get("nome", ""),
            p.get("autor", {}).get("partido", "") or "",
            str(p["numero"]), str(p["ano"]), p["tipo"],
        ])).lower()
        docs = p.get("documentos", [])
        doc0 = docs[0]["url"] if docs else p.get("url_oficial", "#")
        cat_tags = "".join(
            '<span class="tag cat">' + esc(cats[c]["nome"]) + "</span>"
            for c in p.get("categorias", [])[:3])
        ell = "…" if len(p["ementa"]) > 260 else ""
        rows.append(
            f'<div class="prop-row" data-prop data-casa="{esc(p["casa_origem"])}" data-ano="{p["ano"]}" '
            f'data-statusgroup="{sg}" data-cats="{cats_csv}" data-score="{p["impacto"]["score"]}" data-search="{esc(search)}">'
            f'<div class="head"><div><h3><a href="{prop_link(p)}">{esc(p["tipo"])} {p["numero"]}/{p["ano"]} — {esc(p["titulo"])}</a></h3>'
            f'<p class="ementa">{esc(p["ementa"][:260])}{ell}</p></div>'
            f'<span class="score-badge {score_class(p["impacto"]["score"])}">{p["impacto"]["score"]}/100</span></div>'
            f'<div class="tagsline"><span class="tag {cls}">{lbl}</span>'
            f'<span class="tag">Autor: {esc(p.get("autor", {}).get("nome", "—"))}</span>'
            f'{cat_tags}'
            f'<span class="tag"><a href="{doc0}" target="_blank" rel="noopener">ficha oficial ↗</a></span></div></div>'
        )
    opts_ano = '<option value="">Todos os anos</option>' + "".join(f'<option value="{y}">{y}</option>' for y in years)
    opts_cat = '<option value="">Todas as categorias</option>' + "".join(
        f'<option value="{c["id"]}">{esc(c["nome"])}</option>' for c in cats.values())

    body = f"""
<div class="page-head"><div class="wrap">
  <div class="crumbs"><a href="{SITE_URL}/">Início</a> › Proposições</div>
  <h1>Proposições legislativas sobre IA</h1>
  <p class="sub">Todas as matérias monitoradas, com filtros por casa, ano, situação, categoria e score. Cada ficha traz ementa oficial, autoria, tramitação, relatoria, relações e fontes primárias.</p>
</div></div>
<section class="block"><div class="wrap">
  <div class="filters">
    <input id="f-q" class="search" type="search" placeholder="Buscar por número, título, ementa, autor ou partido…">
    <select id="f-casa"><option value="">Todas as casas</option><option value="Câmara dos Deputados">Câmara dos Deputados</option><option value="Senado Federal">Senado Federal</option></select>
    <select id="f-ano">{opts_ano}</select>
    <select id="f-status"><option value="">Toda situação</option><option value="em_tramitacao">Em tramitação</option><option value="a_sancao">À sanção</option><option value="aprovada_lei">Convertida em lei</option><option value="arquivada">Arquivada</option></select>
    <select id="f-cat">{opts_cat}</select>
    <select id="f-score"><option value="0">Qualquer score</option><option value="60">Score ≥ 60</option><option value="75">Score ≥ 75</option><option value="90">Score ≥ 90 (crítico)</option></select>
  </div>
  <p id="count" style="color:var(--muted);font-size:13px;margin-bottom:14px"></p>
  {"".join(rows)}
</div></section>"""
    write("proposicoes/index.html", page(
        "Proposições legislativas sobre IA no Brasil — Monitor Legislativo",
        "Lista completa e filtrável de projetos de lei sobre inteligência artificial no Congresso Nacional, com AI Legislative Impact Score e fontes oficiais.",
        "proposicoes/", body))


def build_prop_pages(props, cats):
    for p in props:
        sg = status_group(p)
        lbl, cls = STATUS_LABEL[sg]
        autor = p.get("autor", {})
        kv = [
            ("Autor", f'{esc(autor.get("nome", "—"))}' + (f' ({esc(autor["partido"])}-{esc(autor["estado"])})' if autor.get("partido") else "") + (f' · {esc(autor["cargo"])}' if autor.get("cargo") else "")),
            ("Casa de origem", esc(p["casa_origem"])),
            ("Local atual", esc(p["casa_atual"])),
            ("Apresentação", fmt_date(p.get("data_apresentacao"))),
            ("Situação", esc(p.get("situacao", "—"))),
            ("Comissão", esc(p.get("comissao_atual", "—"))),
            ("Regime / apreciação", esc(", ".join(filter(None, [p.get("regime_tramitacao"), p.get("forma_apreciacao")])) or "—")),
        ]
        relator = p.get("relator") or p.get("relator_camara")
        if relator:
            kv.append(("Relator", f'{esc(relator["nome"])}' + (f' ({esc(relator["partido"])}-{esc(relator["estado"])})' if relator.get("partido") else "")))
        if p.get("relator_senado"):
            kv.append(("Relator no Senado", esc(p["relator_senado"]["nome"])))
        if p.get("ultima_movimentacao"):
            kv.append(("Última movimentação", f'{fmt_date(p["ultima_movimentacao"].get("data"))} — {esc(p["ultima_movimentacao"].get("descricao") or p["ultima_movimentacao"].get("evento", ""))}'))
        if p.get("proxima_etapa"):
            kv.append(("Próxima etapa provável", esc(p["proxima_etapa"])))

        kv_html = "".join(f'<div class="kv"><dt>{k}</dt><dd>{v}</dd></div>' for k, v in kv)

        docs_html = "".join(
            f'<li>▸ <a href="{d["url"]}" target="_blank" rel="noopener">{esc(d["titulo"])}</a></li>'
            for d in p.get("documentos", []))
        rels = p.get("relacionamentos", []) + p.get("apensados_principais", [])
        rel_ids = {r for r in rels if r in {q["id"] for q in props}}
        rels_html = ""
        if rel_ids:
            by_id = {q["id"]: q for q in props}
            rels_html = "<ul class=\"plain\">" + "".join(
                f'<li>▸ <a href="{prop_link(by_id[r])}">{esc(by_id[r]["tipo"])} {by_id[r]["numero"]}/{by_id[r]["ano"]} — {esc(by_id[r]["titulo"])}</a></li>'
                for r in sorted(rel_ids)) + "</ul>"
        elif p.get("relacionamentos"):
            rels_html = "<p>" + esc("; ".join(p["relacionamentos"])) + "</p>"

        extra_sections = ""
        for key, heading in [("obrigacoes_criadas", "Obrigações criadas"), ("proibicoes", "Proibições"), ("orgaos_responsaveis", "Órgãos responsáveis pela fiscalização")]:
            if p.get(key):
                extra_sections += f'<div class="kv" style="margin-bottom:12px"><dt style="font-size:12px">{heading}</dt><dd>{esc(p[key])}</dd></div>'

        tl_html = "".join(
            f'<div class="tl-item"><div class="date">{fmt_date(t["data"])}</div>'
            f'<div class="desc">{esc(t["evento"])}</div>'
            f'<div class="src"><a href="{t["fonte"]}" target="_blank" rel="noopener">fonte ↗</a></div></div>'
            for t in p.get("timeline", []))
        if tl_html:
            tl_html = '<div class="timeline">' + tl_html + "</div>"
        else:
            tl_html = "<p style='color:var(--muted)'>Timeline a ser construída nas próximas execuções do monitoramento.</p>"

        fonts_extra = "".join(
            f'<li>▸ <a href="{f["url"]}" target="_blank" rel="noopener">{esc(f["titulo"])}</a></li>'
            for f in p.get("fontes_adicionais", []))

        cats_html = " ".join(f'<span class="tag cat">{esc(cats[c]["nome"])}</span>' for c in p.get("categorias", []))

        body = f"""
<div class="page-head prop-page"><div class="wrap">
  <div class="crumbs"><a href="{SITE_URL}/">Início</a> › <a href="{SITE_URL}/proposicoes/">Proposições</a> › {esc(p["tipo"])} {p["numero"]}/{p["ano"]}</div>
  <div class="identity">
    <div style="flex:1;min-width:260px">
      <h1>{esc(p["tipo"])} {p["numero"]}/{p["ano"]}</h1>
      <p class="sub" style="font-size:17px;color:var(--text);font-weight:600">{esc(p["titulo"])}</p>
      <p class="sub">{esc(p["ementa"])}</p>
      <div style="margin-top:10px"><span class="tag {cls}">{lbl}</span> {cats_html}</div>
    </div>
    <div class="score-box">
      <div class="big" style="color:var(--{'accent' if p['impacto']['score'] >= 75 else 'accent-2' if p['impacto']['score'] >= 50 else 'muted'})">{p["impacto"]["score"]}</div>
      <div class="cls">AI Legislative<br>Impact Score</div>
      <div class="score-badge {score_class(p["impacto"]["score"])}" style="margin-top:8px">{esc(p["impacto"]["classificacao"])}</div>
    </div>
  </div>
</div></div>
<section class="block"><div class="wrap">
  <h2 class="section-title">Identificação e tramitação</h2>
  <p class="section-sub">Dados confirmados em fonte oficial nesta execução. Campos não confirmados não são exibidos.</p>
  <div class="dl-grid">{kv_html}</div>
  <p style="margin-top:12px;font-size:13.5px"><a href="{esc(p["url_oficial"])}" target="_blank" rel="noopener">Abrir ficha oficial de tramitação ↗</a></p>
</div></section>
<section class="block"><div class="wrap">
  <h2 class="section-title">Resumo objetivo</h2>
  <p style="max-width:860px">{esc(p.get("resumo", p["ementa"]))}</p>
  {extra_sections}
  <div class="note" style="margin-top:16px"><b>Chance de impacto regulatório:</b> {esc(p.get("chance_impacto_regulatorio", "—"))}</div>
</div></section>
<section class="block"><div class="wrap">
  <h2 class="section-title">Documentos e textos</h2>
  <ul class="plain">{docs_html or '<li>—</li>'}</ul>
</div></section>
<section class="block"><div class="wrap">
  <h2 class="section-title">Proposições relacionadas</h2>
  {rels_html or "<p style='color:var(--muted)'>Nenhuma relação formal registrada (não apensada).</p>"}
</div></section>
<section class="block"><div class="wrap">
  <h2 class="section-title">Timeline de tramitação</h2>
  {tl_html}
</div></section>
<section class="block"><div class="wrap">
  <h2 class="section-title">Fontes</h2>
  <ul class="plain">
    <li>▸ <a href="{esc(p["url_oficial"])}" target="_blank" rel="noopener">{esc(p["tipo"])} {p["numero"]}/{p["ano"]} — fonte oficial</a></li>
    {fonts_extra}
  </ul>
</div></section>"""
        jsonld = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": f'{p["tipo"]} {p["numero"]}/{p["ano"]} — {p["titulo"]}',
            "description": p["ementa"][:300],
            "url": prop_link(p),
            "dateModified": EXECUTION_DATE,
            "about": "Regulação de inteligência artificial no Brasil",
        }
        write(prop_fs_path(p["id"]), page(
            f'{p["tipo"]} {p["numero"]}/{p["ano"]} — {p["titulo"]} | Monitor Legislativo de IA',
            p["ementa"][:157],
            prop_fs_path(p["id"]).replace("index.html", ""), body, og_type="article", jsonld=jsonld))


def build_laws(laws):
    rows = "".join(
        f'<tr><td><b>{esc(l["tipo"])} {esc(l["numero"])}</b><br><small style="color:var(--muted)">{fmt_date(l["data"])}</small></td>'
        f'<td><b>{esc(l["nome"])}</b><br><span style="color:var(--muted);font-size:13px">{esc(l["ementa_sintese"][:180])}…</span></td>'
        f'<td style="font-size:13px">{esc(l["relacao_ia"][:320])}…</td>'
        f'<td><span class="tag">{esc(l["status"])}</span></td>'
        f'<td><a href="{l["url"]}" target="_blank" rel="noopener">link ↗</a></td></tr>'
        for l in sorted(laws, key=lambda x: x["data"], reverse=True))
    body = f"""
<div class="page-head"><div class="wrap">
  <div class="crumbs"><a href="{SITE_URL}/">Início</a> › Leis e normas</div>
  <h1>Leis e normas vigentes relacionadas à IA</h1>
  <p class="sub">Legislação federal em vigor que já disciplina sistemas de IA, decisões automatizadas e conteúdo sintético — além de atos caducos mantidos por valor documental.</p>
</div></div>
<section class="block"><div class="wrap" style="overflow-x:auto">
  <table class="tbl">
    <thead><tr><th>Norma</th><th>Nome</th><th>Relação com IA</th><th>Status</th><th>Fonte</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div></section>"""
    write("leis/index.html", page(
        "Leis e normas vigentes sobre IA no Brasil — LGPD, ECA Digital, Lei 15.487/2026 e mais",
        "Legislação federal brasileira vigente relacionada à inteligência artificial: leis, decretos, resoluções do TSE e CNJ e atos da ANPD, com fonte oficial.",
        "leis/", body))


def build_timeline(timeline):
    items = sorted(timeline["eventos"], key=lambda e: e["data"], reverse=True)
    tl = "".join(
        f'<div class="tl-item"><div class="date">{fmt_date(e["data"])} · {esc(e["casa"])}</div>'
        f'<div class="desc"><b>{esc(e["titulo"])}</b> — {esc(e["descricao"])}</div>'
        f'<div class="src">Ator: {esc(e["ator"])} · <a href="{e["fonte_url"]}" target="_blank" rel="noopener">{esc(e["fonte_titulo"])} ↗</a></div></div>'
        for e in items)
    body = f"""
<div class="page-head"><div class="wrap">
  <div class="crumbs"><a href="{SITE_URL}/">Início</a> › Timeline</div>
  <h1>Timeline da regulamentação de IA no Brasil</h1>
  <p class="sub">Histórico cronológico documentado — dos primeiros projetos de 2019 ao cenário de 2026. Cada evento traz casa, ator e fonte.</p>
</div></div>
<section class="block"><div class="wrap">
  <div class="timeline">{tl}</div>
</div></section>"""
    write("timeline/index.html", page(
        "Timeline da regulamentação de IA no Brasil (2019–2026)",
        "Linha do tempo documentada da legislação brasileira de inteligência artificial: comissão de juristas, CTIA, PL 2338/2023, leis sancionadas e atos regulatórios.",
        "timeline/", body))


def build_parliamentarians(parms, props):
    by_id = {p["id"]: p for p in props}
    cards = ""
    for m in parms:
        props_links = "".join(
            f'<a href="{prop_link(by_id[pid])}">{esc(by_id[pid]["tipo"])} {by_id[pid]["numero"]}/{by_id[pid]["ano"]}</a>'
            for pid in m.get("proposicoes_relacionadas", []) if pid in by_id)
        atu = "".join(f"<li>{esc(a)}</li>" for a in m.get("atuacao_ia", []))
        fonts = "".join(f'<li><a href="{f["url"]}" target="_blank" rel="noopener">{esc(f["titulo"])} ↗</a></li>' for f in m.get("fontes", []))
        casa = "Câmara" if m["casa"] == "Câmara" else "Senado"
        cards += f"""
<div class="card">
  <h3>{esc(m["nome"])} <span class="tag">{esc(m["partido"])}-{esc(m["estado"])}</span> <span class="tag">{casa}</span></h3>
  <p><b>{esc(m["papel"])}</b></p>
  <ul class="plain" style="margin:10px 0 10px 0;color:var(--muted);font-size:13.5px">{atu}</ul>
  <p style="font-size:13px"><b>Matérias:</b> {props_links or "—"}</p>
  <p style="font-size:12.5px;margin-top:8px;color:var(--muted)">Fontes: {fonts}</p>
</div>"""
    body = f"""
<div class="page-head"><div class="wrap">
  <div class="crumbs"><a href="{SITE_URL}/">Início</a> › Parlamentares</div>
  <h1>Parlamentares na legislação de IA</h1>
  <p class="sub">Mapa de autoria, relatoria e condução das matérias de IA no Congresso Nacional. Posições só são registradas quando documentadas — não atribuímos juízo político sem fonte.</p>
</div></div>
<section class="block"><div class="wrap">
  <div class="grid cols-2">{cards}</div>
</div></section>"""
    write("parlamentares/index.html", page(
        "Parlamentares envolvidos com a legislação de IA no Brasil",
        "Autores, relatores e presidentes de comissões das principais matérias de inteligência artificial no Congresso Nacional, com atuação documentada.",
        "parlamentares/", body))


def build_agenda(events):
    groups = {
        "proximos_7_dias": ("Próximos 7 dias", []),
        "proximos_30_dias": ("Próximos 30 dias", []),
        "sem_data_confirmada": ("Sem data confirmada (marcos previstos)", []),
    }
    for e in events["eventos"]:
        g = groups.get(e.get("janela"))
        if g:
            g[1].append(e)

    html = ""
    for key, (label, evts) in groups.items():
        if not evts:
            continue
        items = "".join(
            f'<div class="card"><h3>{esc(e["titulo"])}</h3>'
            f'<p><b>{fmt_date(e.get("data_inicio"))}{(" a " + fmt_date(e["data_fim"])) if e.get("data_fim") and e["data_fim"] != e.get("data_inicio") else ""}</b>'
            + (f' · {esc(e["hora"])}' if e.get("hora") else "") + f' · {esc(e["casa"])}</p>'
            f'<p><b>Local:</b> {esc(e.get("local", "—"))} · <b>Tipo:</b> {esc(e["tipo"])}</p>'
            f'<p>{esc(e["tema"])}</p>'
            f'<p style="margin-top:8px"><b>Relação com IA:</b> {esc(e["relacao_ia"])}</p>'
            f'<p style="margin-top:8px;font-size:12.5px"><a href="{e["fonte_url"]}" target="_blank" rel="noopener">{esc(e["fonte_titulo"])} ↗</a></p></div>'
            for e in evts)
        html += f'<div class="agenda-group"><h3>{label}</h3><div class="grid cols-2">{items}</div></div>'

    v = events["verificacao"]
    body = f"""
<div class="page-head"><div class="wrap">
  <div class="crumbs"><a href="{SITE_URL}/">Início</a> › Agenda</div>
  <h1>Agenda Legislativa de IA</h1>
  <p class="sub">Eventos futuros relacionados à IA no Congresso e marcos normativos previstos. Verificada em {fmt_date(v["data"])}.</p>
</div></div>
<section class="block"><div class="wrap">
  <div class="note warn"><b>Hoje ({fmt_date(v["data"])}):</b> nenhum evento de IA agendado nas fontes oficiais consultadas. {esc(v["resultado"])}</div>
  {html}
</div></section>"""
    write("agenda/index.html", page(
        "Agenda Legislativa de IA — próximos eventos e marcos",
        "Agenda de eventos legislativos e regulatórios de inteligência artificial no Brasil: audiências, votações previstas, marcos eleitorais e sanções pendentes.",
        "agenda/", body))


def build_report(props, laws, updates, events):
    run = updates["execucoes"][0]
    top5 = [
        ("Redata aprovado pelo Congresso e à sanção presidencial",
         "O Senado aprovou o PL 278/2026 em 01/09/2026, sem alteração de mérito. É a matéria de infraestrutura de IA mais próxima de virar lei no Brasil, com renúncia estimada em bilhões de reais e contrapartidas de P&D, energia e capacidade para o mercado interno."),
        ("Primeira lei penal específica de deepfakes em vigor",
         "A Lei 15.487/2026 (ex-PL 3066/2025), sancionada em 06/08/2026, criminaliza simulação sexual de crianças por IA/deepfake e aumenta penas em 1/3 a 2/3 quando o crime usa IA — precedente normativo para todo o cluster de conteúdo sintético."),
        ("Marco Legal da IA (PL 2338/2023) oficialmente adiado para depois das eleições",
         "Após 16 meses sem parecer e cinco datas perdidas, o relator Aguinaldo Ribeiro confirmou em 24/08/2026 que a votação só ocorre após outubro. O pacote acumula 37 proposições apensadas, incluindo o PL 6237/2025 do Executivo (SIA/ANPD)."),
        ("ANPD inicia fiscalização direta de ferramentas de IA generativa",
         "Desde 21/08/2026, a ANPD monitora 22 agentes (redes sociais, lojas de apps e IA generativa) com base no Marco Civil atualizado e no ECA Digital — a autoridade já atua como reguladora de fato enquanto o marco legal não é votado."),
        ("TSE consolida o regime eleitoral de IA e fixa tese sobre deepfakes",
         "A Resolução 23.748/2026 (rotulagem, janela de 72h, vedação de recomendação por IA) foi reforçada em 01/09/2026 por tese que exige grau de realismo para caracterizar deepfake — primeira eleição geral do mundo com regras dessa amplitude."),
    ]
    top5_html = "".join(
        f'<div class="change-item"><div class="when">#{i+1}</div><h3>{esc(t)}</h3><p>{esc(d)}</p></div>'
        for i, (t, d) in enumerate(top5))

    facts = [
        "O PL 2338/2023 (Marco Legal da IA) foi aprovado pelo Senado em 10/12/2024 e tramita desde 17/03/2025 em Comissão Especial da Câmara, com relatoria de Aguinaldo Ribeiro (PP-PB) e presidência de Luísa Canziani (PSD-PR).",
        "A comissão não protocolou parecer em 16 meses (prazo regimental: 10 sessões do Plenário). Cinco datas de votação foram marcadas e perdidas desde 25/11/2025. Em 24/08/2026, o relator anunciou votação somente após as eleições de outubro.",
        "37 proposições estão apensadas ao PL 2338/2023, incluindo o PL 6237/2025 do Poder Executivo (Sistema Nacional de IA, com a ANPD como autoridade de normas gerais e regulador residual).",
        "O Redata (PL 278/2026) foi aprovado pela Câmara em 24-25/02/2026 e pelo Senado em 01/09/2026, sem alteração de mérito, e aguarda sanção. Sua antecessora, a MP 1.318/2025, caducou em 25/02/2026.",
        "Leis vigentes relevantes: LGPD (13.709/2018, art. 20), Governo Digital (14.129/2021, arts. 20-24), PNED (14.533/2023), ECA Digital (15.211/2025) e Lei 15.487/2026 (deepfakes/IA).",
        "Atos regulatórios vigentes: Resolução TSE 23.732/2024 e 23.748/2026 (eleições), Resolução CNJ 615/2025 (Judiciário), Decretos 12.975 e 12.976/2026 (Marco Civil e proteção de mulheres), EBIA (Portaria MCTI 4.617/2021) e PBIA 2024-2028 (R$ 23 bi).",
        "A ANPD elegeu IA como eixo prioritário de fiscalização para 2026-2027 e, desde 21/08/2026, monitora 22 agentes do mercado, incluindo ferramentas de IA generativa.",
    ]
    interps = [
        "A janela pós-eleitoral (novembro/dezembro de 2026) será decisiva: a convergência entre o PL 2338/2023 e o PL 6237/2025 em um único substitutivo é o cenário mais provável, já que o texto do governo resolve o vício de iniciativa apontado na arquitetura de governança.",
        "Como a Câmara deverá alterar o texto aprovado pelo Senado, a matéria precisará retornar à Casa de origem antes da sanção — o vaivém entre as Casas é o principal risco de calendário.",
        "O cluster de transparência/rotulagem de conteúdo sintético (mais de uma dezena de proposições) tende a ser disciplinado no bojo do marco legal, e não por leis separadas, dado o precedente da Resolução TSE 23.748/2026.",
        "A infraestrutura (Redata + PBIA + data centers) ganhou prioridade política concreta em 2026, enquanto a regulação material (riscos, direitos, direitos autorais) segue como o ponto mais sensível e retardatário.",
        "O debate de direitos autorais e treinamento de modelos permanece sem consenso documentado entre Casa, mercado e setor criativo — é a variável com maior potencial de alteração de última hora no substitutivo.",
    ]

    body = f"""
<div class="page-head"><div class="wrap">
  <div class="crumbs"><a href="{SITE_URL}/">Início</a> › Relatório</div>
  <h1>Relatório da execução e Estado da Regulação</h1>
  <p class="sub">LEGISLATIVE MONITORING REPORT da execução de {fmt_date(run["data_hora"])} (bootstrap) e síntese editorial do cenário regulatório.</p>
</div></div>

<section class="block"><div class="wrap">
  <h2 class="section-title">Estado da regulação de IA no Brasil — resumo executivo</h2>
  <p class="section-sub">Fatos (com fonte) e interpretação (análise editorial) rigorosamente separados.</p>
  <h3 style="margin:14px 0 8px;font-size:16px">Fatos documentados</h3>
  <ul class="plain facts">{"".join(f"<li>▸ {esc(f)}</li>" for f in facts)}</ul>
  <h3 style="margin:20px 0 8px;font-size:16px">Interpretação editorial</h3>
  <ul class="plain interp">{"".join(f"<li>▸ {esc(i)}</li>" for i in interps)}</ul>
  <div class="note" style="margin-top:18px"><b>Resposta direta:</b> a matéria mais próxima de virar lei é o <b>PL 278/2026 (Redata)</b> — já aprovado pelo Congresso, pendente apenas de sanção. O projeto mais importante em conteúdo é o <b>PL 2338/2023</b>, parado na comissão especial até depois das eleições. As comissões mais relevantes são a Comissão Especial do PL 2338/23 (Câmara) e, no plano regulatório, o TSE (Res. 23.748/2026) e a ANPD (fiscalização ativa).</div>
</div></section>

<section class="block"><div class="wrap">
  <h2 class="section-title">Top 5 desenvolvimentos legislativos de IA</h2>
  <p class="section-sub">Ordenados por impacto regulatório nesta execução.</p>
  {top5_html}
</div></section>

<section class="block"><div class="wrap">
  <h2 class="section-title">LEGISLATIVE MONITORING REPORT — execução de {fmt_date(run["data_hora"])}</h2>
  <div class="dl-grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">
    <div class="kv"><dt>Data/hora da execução</dt><dd>{fmt_date(run["data_hora"])} (bootstrap completo)</dd></div>
    <div class="kv"><dt>Proposições verificadas</dt><dd>{run["proposicoes_verificadas"]} (fichas oficiais, APIs de dados abertos e matérias bicamerais)</dd></div>
    <div class="kv"><dt>Novas proposições cadastradas</dt><dd>{run["novas_proposicoes"]}</dd></div>
    <div class="kv"><dt>Novas leis/regulamentos mapeados</dt><dd>{run["novas_leis_regulamentos"]}</dd></div>
    <div class="kv"><dt>Fontes consultadas</dt><dd>{"".join(esc(s) + "<br>" for s in run["fontes_consultadas"])}</dd></div>
    <div class="kv"><dt>Erros encontrados</dt><dd>Nenhum erro de build. Lacunas de dados marcadas explicitamente nos registros.</dd></div>
  </div>
</div></section>

<section class="block"><div class="wrap">
  <h2 class="section-title">Metodologia e política de qualidade</h2>
  <ul class="plain facts">
    <li>▸ <b>Fontes primárias obrigatórias:</b> cada fato legislativo relevante cita a URL oficial (Câmara, Senado, Congresso, Planalto, DOU, TSE, CNJ, ANPD). Imprensa é usada apenas para descoberta e contexto, nunca como fonte final quando há fonte legislativa disponível.</li>
    <li>▸ <b>Chave primária:</b> casa + tipo + número + ano (ex.: camara_pl_2338_2023). Nenhuma duplicata é criada; execuções futuras atualizam os mesmos registros.</li>
    <li>▸ <b>AI Legislative Impact Score (0-100):</b> considera abrangência nacional, estágio, proximidade de votação, regime de urgência/prioridade, número de apensados, impacto sobre empresas, desenvolvedores, cidadãos e direitos fundamentais e potencial de virar referência. Faixas: 90-100 crítico, 75-89 muito relevante, 60-74 relevante, 40-59 monitorar, 0-39 baixa prioridade. Scores não são manipulados para inflacionar pautas.</li>
    <li>▸ <b>Proibido:</b> inventar proposições, tramitações, datas, autores, pareceres, probabilidades ou posições políticas sem evidência documental.</li>
    <li>▸ <b>Controle de alterações:</b> o dataset é versionado no Git; mudanças de situação geram registro em updates.json com status anterior, status novo, data e fonte.</li>
    <li>▸ <b>Execuções futuras:</b> carregar o estado anterior → consultar fontes oficiais → detectar mudanças → atualizar registros e páginas → validar build → publicar. Se nada mudou, registra-se apenas a verificação.</li>
  </ul>
</div></section>"""
    write("relatorio/index.html", page(
        "Relatório e Estado da Regulação de IA no Brasil — setembro de 2026",
        "Relatório executivo do monitoramento legislativo de IA: fatos documentados, interpretação editorial, top 5 desenvolvimentos e metodologia auditável.",
        "relatorio/", body))


def build_sitemap(paths):
    today = EXECUTION_DATE
    urls = "".join(
        f"<url><loc>{SITE_URL}/{p}</loc><lastmod>{today}</lastmod></url>"
        for p in paths)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")


def main():
    props = load("propositions.json")["proposicoes"]
    laws = load("laws.json")["normas"]
    events = load("events.json")
    updates = load("updates.json")
    timeline = load("timeline.json")
    cats = cat_map()

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(BASE, "data", "legislation"), os.path.join(OUT, "data"))
    shutil.copytree(ASSETS, os.path.join(OUT, "assets"))

    build_home(props, laws, events, updates, timeline, cats)
    build_propositions(props, cats)
    build_prop_pages(props, cats)
    build_laws(laws)
    build_timeline(timeline)
    build_parliamentarians(load("parliamentarians.json")["parlamentares"], props)
    build_agenda(events)
    build_report(props, laws, updates, events)

    paths = ["", "proposicoes/", "leis/", "timeline/", "parlamentares/", "agenda/", "relatorio/"]
    paths += [prop_fs_path(p["id"]).replace("index.html", "") for p in props]
    build_sitemap(paths)

    n_pages = 7 + len(props)
    print(f"OK: site gerado em docs/ — {n_pages} páginas, {len(paths)} URLs no sitemap.")


if __name__ == "__main__":
    main()
