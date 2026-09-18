#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_articles.py — Renderiza a área pública /artigos/ do Monitor Legislativo de IA.

Lê data/articles/articles.json (produzido por scripts/generate_articles.py a partir
do dataset legislativo) e gera:

  docs/artigos/index.html           — índice dos artigos (CollectionPage)
  docs/artigos/<slug>/index.html    — página permanente de cada artigo
  docs/data/articles.json           — feed público estruturado para IA/agentes
  docs/data/editorial_state.json    — log editorial auditável (ação por mudança)

Cada página de artigo traz SEO completo (canonical, OG de artigo, Twitter),
JSON-LD `NewsArticle` com datePublished/dateModified/author/publisher/about/
mentions, breadcrumbs, linkagem interna para fichas do monitor e fontes oficiais.

Tolerante à ausência de artigos: sem dataset editorial, /artigos/ não é gerado
e o restante do site permanece intacto.
"""
from __future__ import annotations

import json
import os
import re
import shutil


# --------------------------------------------------------------- carregamento
def carregar_artigos(base=None):
    """Retorna dict do articles.json ou None (área ainda não existente)."""
    base = base or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "articles")
    path = os.path.join(base, "articles.json")
    try:
        with open(path, encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, dict) and isinstance(dados.get("artigos"), list):
            return dados
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def artigos_publicados(artigos_f):
    return [a for a in (artigos_f or {}).get("artigos", [])
            if a.get("status") == "published"]


def artigos_para_prop(artigos_f, pid):
    """Artigos ligados a uma proposição (via IDs, não por texto)."""
    if not artigos_f:
        return []
    return [a for a in artigos_publicados(artigos_f)
            if pid in (a.get("related_propositions") or [])
            or pid in (a.get("source_entity_ids") or [])]


def _url(core, a):
    return f"{core.SITE_URL}/{a.get('url') or ('artigos/' + a['slug'] + '/')}"


# ------------------------------------------------------------------- JSON-LD
def article_jsonld(SITE_URL, a):
    """NewsArticle completo (SEO/AEO/citação). Puro para teste offline."""
    url = f"{SITE_URL}/{a.get('url') or ('artigos/' + a['slug'] + '/')}"
    about, mentions = [], []
    for pid in a.get("related_propositions") or []:
        parts = pid.split("_")
        if len(parts) >= 4:
            nome = f"{parts[1].upper()} {parts[2]}/{parts[3]}"
            about.append({"@type": "Legislation", "name": nome})
    for ato in a.get("related_acts") or []:
        about.append({"@type": "CreativeWork", "name": ato})
    for orgao in a.get("related_organs") or []:
        if orgao:
            mentions.append({"@type": "GovernmentOrganization", "name": orgao})
    for nome in a.get("related_parliamentarians") or []:
        mentions.append({"@type": "Person", "name": nome})
    ld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": (a.get("title") or "")[:110],
        "description": a.get("description") or "",
        "url": url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "datePublished": a.get("published_at"),
        "dateModified": a.get("modified_at"),
        "inLanguage": "pt-BR",
        "isAccessibleForFree": True,
        "author": [{"@type": "Person", "name": "Leandro Calado",
                    "url": "https://leandrocaladoferreira.com/"}],
        "publisher": {"@type": "Organization", "name": "LCF Consulting",
                      "url": "https://lcfconsulting.com.br/"},
        "keywords": a.get("keywords") or [],
    }
    if a.get("categories"):
        ld["articleSection"] = a["categories"]
    if about:
        ld["about"] = about
    if mentions:
        ld["mentions"] = mentions
    return ld


# ------------------------------------------------------------------ utilitário
def _fmt(d):
    try:
        from datetime import datetime
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(d or "—")


def _resolver_site(html, site_url):
    """O conteúdo é gerado sem domínio (portátil); o build resolve o canonical."""
    return html.replace("{SITE_URL}", site_url)


# ------------------------------------------------------- página de um artigo
def _secao(titulo, corpo, id_ancora=None):
    if not corpo:
        return ""
    anc = f' id="{id_ancora}"' if id_ancora else ""
    return f'<h2{anc}>{titulo}</h2>\n{corpo}\n'


def _bullets_o_que_mudou(conteudo, limite=8):
    bullets = conteudo.get("o_que_mudou") or []
    if not bullets:
        return ""
    visiveis = "\n".join(bullets[:limite])
    if len(bullets) > limite:
        restantes = "\n".join(bullets[limite:])
        return (f'<div class="changes-list">{visiveis}</div>'
                f'<details class="article-more"><summary>Ver todas as '
                f'{len(bullets)} movimentações registradas</summary>'
                f'<div class="changes-list">{restantes}</div></details>')
    return f'<div class="changes-list">{visiveis}</div>'


def render_article(core, a, artigos_f):
    """HTML completo de um artigo (usa o `page()` do gerador do site)."""
    site = core.SITE_URL
    url = _url(core, a)
    conteudo = a.get("content") or {}
    pub, mod = a.get("published_at"), a.get("modified_at")
    dateline = f"Publicado em <time datetime=\"{pub}\">{_fmt(pub)}</time>"
    if mod and mod != pub:
        dateline += (f" · Atualizado em <time datetime=\"{mod}\">{_fmt(mod)}</time>")
    dateline += (f" · Revisão nº {a.get('revision_count', 1)} · "
                 f"Por <a href=\"https://leandrocaladoferreira.com/\">Leandro Calado</a> — "
                 f"<a href=\"https://lcfconsulting.com.br/\">LCF Consulting</a>")

    por_id = {p["id"]: p for p in core.load("propositions.json")["proposicoes"]}

    # ---- assuntos e linkagem interna (fichas do monitor)
    rel_links = []
    for pid in a.get("related_propositions") or []:
        p = por_id.get(pid)
        if p:
            rel_links.append(f'<li>▸ <a href="{core.prop_link(p)}">'
                             f'Ficha no monitor: {p["tipo"]} {p["numero"]}/{p["ano"]} — '
                             f'{core.esc(p["titulo"])}</a></li>')
    if a.get("related_acts") and os.path.exists(
            os.path.join(core.BASE, "data", "legislation", "atos.json")):
        rotulos = ", ".join(a["related_acts"][:3])
        orgao_rot = core.ROTULO_ORGAO.get((a.get("related_organs") or [""])[0], "órgão oficial")
        rel_links.append(f'<li>▸ <a href="{site}/atualizacoes/">Registro do ato no monitor '
                         f'({core.esc(orgao_rot)} — {core.esc(rotulos[:80])}…)</a></li>')
    if a.get("related_parliamentarians"):
        rel_links.append(f'<li>▸ <a href="{site}/parlamentares/">Parlamentares com atuação '
                         f'documentada em IA ({core.esc(", ".join(a["related_parliamentarians"][:3]))}…)</a></li>')
    artigos_relacionados = [
        x for x in artigos_publicados(artigos_f)
        if x["id"] != a["id"]
        and (set(x.get("categories") or []) & set(a.get("categories") or [])
             or set(x.get("related_propositions") or []) & set(a.get("related_propositions") or []))
    ][:3]
    for x in artigos_relacionados:
        rel_links.append(f'<li>▸ <a href="{_url(core, x)}">{core.esc(x["title"])}</a></li>')
    rel_html = (f'<ul class="plain article-related">{"".join(rel_links)}</ul>'
                if rel_links else
                f'<p><a href="{site}/proposicoes/">Ver todas as proposições monitoradas →</a></p>')

    # ---- fontes oficiais
    fontes = []
    for s in a.get("official_sources") or []:
        if s.get("url"):
            rotulo = f' ({core.esc(s["orgao"])})' if s.get("orgao") else ""
            fontes.append(f'<li>▸ <a href="{core.esc(s["url"])}" target="_blank" rel="noopener">'
                          f'{core.esc(s["titulo"])}</a>{rotulo}</li>')
    fontes.append(f'<li>▸ <a href="{site}/metodologia/">Fontes e critérios do monitoramento</a></li>')
    fontes_html = f'<ul class="plain article-sources">{"".join(fontes)}</ul>'

    # ---- histórico de revisões (log completo fica no dataset editorial)
    revs = a.get("revisions") or []
    if len(revs) > 1:
        linhas = "".join(
            f'<li><b>{_fmt(r.get("date"))}</b> — {core.esc(r.get("summary") or "")}</li>'
            for r in revs)
        revisoes_html = (f'<details class="article-revisions"><summary>Histórico de revisões '
                         f'deste artigo ({len(revs)})</summary><ul class="plain">{linhas}</ul>'
                         f'<p class="disclaimer">Log técnico completo (mudança por mudança) em '
                         f'<a href="{site}/data/editorial_state.json">editorial_state.json</a>.</p></details>')
    else:
        revisoes_html = ""

    cats_html = " ".join(f'<span class="tag cat">{core.esc(c)}</span>'
                         for c in (a.get("categories") or [])[:4])
    historico = conteudo.get("historico") or []
    hist_html = ""
    if historico:
        itens = "".join(
            f'<div class="tl-item"><div class="date">{core.esc(_fmt(t.get("data")))}</div>'
            f'<div class="desc">{core.esc(t.get("evento"))}</div>'
            + (f'<div class="src"><a href="{core.esc(t["fonte"])}" target="_blank" '
               f'rel="noopener">fonte ↗</a></div>' if t.get("fonte") else "")
            + '</div>' for t in historico)
        hist_html = f'<div class="timeline">{itens}</div>'

    body = f"""
<div class="page-head"><div class="wrap">
  <div class="crumbs"><a href="{site}/">Início</a> › <a href="{site}/artigos/">Artigos</a> › {core.esc((a.get('title') or '')[:60])}</div>
  <h1>{core.esc(a.get('title'))}</h1>
  <p class="sub article-dateline">{dateline}</p>
  <div style="margin-top:10px">{cats_html}</div>
</div></div>
<article class="block article-body" itemscope itemtype="https://schema.org/NewsArticle">
<div class="wrap">
  <div class="note article-lead" itemprop="description"><b>Resumo factual.</b> {core.esc(conteudo.get('lead') or a.get('summary') or '')}</div>
  {_secao('O que mudou', _bullets_o_que_mudou(conteudo), 'o-que-mudou')}\
{_secao('Situação atual', conteudo.get('situacao_atual'), 'situacao-atual')}\
{_secao('Por que isso importa', conteudo.get('por_que_importa'), 'por-que-importa')}\
{_secao('O que acontece agora', conteudo.get('o_que_acontece_agora'), 'o-que-acontece-agora')}\
{_secao('Histórico da matéria', hist_html, 'historico')}\
{_secao('Quem pode ser afetado', conteudo.get('quem_atinge'), 'quem-pode-ser-afetado')}\
  <h2 id="relacionados">Proposições, atos e páginas relacionadas</h2>
  {rel_html}
  <h2 id="fontes-oficiais">Fontes oficiais</h2>
  {fontes_html}
  {revisoes_html}
  <p class="disclaimer" style="margin-top:18px">Conteúdo gerado automaticamente a partir do dataset público do
  <a href="{site}/metodologia/">Monitor Legislativo de IA</a> — cada afirmação factual é rastreável às fontes
  oficiais citadas. Não constitui parecer jurídico; confira sempre os textos oficiais.</p>
</div>
</article>"""

    extra_head = (
        f'<meta property="article:published_time" content="{core.esc(pub)}">\n'
        f'<meta property="article:modified_time" content="{core.esc(mod or pub)}">\n'
        f'<meta name="author" content="Leandro Calado — LCF Consulting">\n'
        f'<meta property="og:site_name" content="{core.SITE_NAME}">\n'
        f'<meta name="twitter:card" content="summary">')

    jsonld = core.combine_ld(
        article_jsonld(site, a),
        core.ld_breadcrumbs([("Início", ""), ("Artigos", "artigos/"),
                             (a.get("title") or "", None)]))
    title = f"{a.get('title')} — Artigos | {core.SITE_NAME}"
    desc = (a.get("description") or a.get("summary") or "")[:300]
    return core.page(title, desc, f"artigos/{a['slug']}/", body,
                     extra_head=extra_head, og_type="article", jsonld=jsonld)


# ----------------------------------------------------------------- índice
def render_index(core, artigos_f):
    site = core.SITE_URL
    arts = artigos_publicados(artigos_f)
    arts = sorted(arts, key=lambda a: (a.get("modified_at") or a.get("published_at") or "",
                                       a.get("published_at") or ""), reverse=True)
    cards = []
    for a in arts:
        pub, mod = a.get("published_at"), a.get("modified_at")
        datas = (f'Publicado em <time datetime="{pub}">{_fmt(pub)}</time>'
                 + (f' · <b>Atualizado em</b> <time datetime="{mod}">{_fmt(mod)}</time>'
                    if mod and mod != pub else ""))
        meta = [f'<span class="tag">{core.esc(a.get("assunto") or "")}</span>']
        for c in (a.get("categories") or [])[:2]:
            meta.append(f'<span class="tag cat">{core.esc(c)}</span>')
        rev = (f' · {a.get("revision_count", 1)} revisão(ões)' if (mod and mod != pub) else "")
        cards.append(
            f'<div class="card article-card"><h3><a href="{_url(core, a)}">'
            f'{core.esc(a.get("title"))}</a></h3>'
            f'<p class="article-dates">{datas}{rev}</p>'
            f'<p>{core.esc((a.get("summary") or "")[:220])}</p>'
            f'<div class="meta">{"".join(meta)}</div></div>')
    sem = ('<div class="note">Nenhum artigo publicado ainda. A área é alimentada '
           'automaticamente pelas mudanças detectadas no monitoramento.</div>' if not cards else "")
    body = f"""
<div class="page-head"><div class="wrap">
  <div class="crumbs"><a href="{site}/">Início</a> › Artigos</div>
  <h1>Artigos — regulação de IA em análise</h1>
  <p class="sub">Análises factuais geradas automaticamente pelo sistema editorial do Monitor:
  cada artigo nasce de uma mudança relevante detectada nas fontes oficiais e é ATUALIZADO — na mesma
  URL — quando o assunto evolui. Todo fato aponta para a fonte oficial. Critérios na
  <a href="{site}/metodologia/">metodologia</a> · log editorial em
  <a href="{site}/data/editorial_state.json">editorial_state.json</a>.</p>
</div></div>
<section class="block"><div class="wrap">
  <div class="grid cols-2">{"".join(cards)}</div>{sem}
</div></section>"""
    jsonld = core.combine_ld(
        core.ld_collection("Artigos sobre regulação de IA no Brasil",
                           "Análises e atualizações factuais sobre legislação e regulação de inteligência artificial no Brasil, geradas a partir do monitoramento de fontes oficiais.",
                           "artigos/"),
        core.ld_breadcrumbs([("Início", ""), ("Artigos", None)]))
    return core.page(
        "Artigos sobre regulação de IA no Brasil — Monitor Legislativo de IA",
        "Análises factuais e continuamente atualizadas sobre leis, projetos e atos de inteligência artificial no Brasil: PL 2338/2023, Redata, ANPD, TSE, CNJ e mais — com fontes oficiais.",
        "artigos/", body, jsonld=jsonld)


# ------------------------------------------------------------------ build
def build(core, artigos_f=None):
    """Gera /artigos/ e publica os feeds. Retorna nº de páginas escritas."""
    if artigos_f is None:
        artigos_f = carregar_artigos()
    if not artigos_f:
        return 0
    arts = artigos_publicados(artigos_f)
    n = 0
    if arts:
        core.write("artigos/index.html", render_index(core, artigos_f))
        n += 1
        lastmods = getattr(core, "_SITEMAP_LASTMOD", None)
        if lastmods is not None:
            lastmods["artigos/"] = max((a.get("modified_at") or a.get("published_at") or "")
                                       for a in arts)
        for a in arts:
            core.write(f"artigos/{a['slug']}/index.html", render_article(core, a, artigos_f))
            n += 1
            if lastmods is not None:
                lastmods[f"artigos/{a['slug']}/"] = (a.get("modified_at")
                                                     or a.get("published_at") or "")
    # feeds públicos para IA/agentes e auditoria
    if not os.path.isdir(os.path.join(core.OUT, "data")):
        os.makedirs(os.path.join(core.OUT, "data"), exist_ok=True)
    src_dir = os.path.join(core.BASE, "data", "articles")
    for nome in ("articles.json", "editorial_state.json"):
        origem = os.path.join(src_dir, nome)
        if os.path.isfile(origem):
            shutil.copyfile(origem, os.path.join(core.OUT, "data", nome))
    return n
