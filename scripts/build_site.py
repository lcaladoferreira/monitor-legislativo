#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point do build com domínio oficial, autoridade institucional e visibilidade SEO/AEO/agentic."""
import os

import build_site_core as _core
import ai_visibility as _ai_visibility
import commercial_pages as _commercial
import google_ai_citation as _google_ai_citation

SITE_URL = "https://monitor.lcfconsulting.com.br"
OLD_SITE_URL = "https://monitor-legislativo-five.vercel.app"

# Força o domínio oficial em toda a geração: canonical, OG, navegação,
# sitemap.xml, robots.txt, JSON-LD e arquivos de descoberta para agentes.
_core.SITE_URL = SITE_URL
_ai_visibility.install(_core)
_commercial.install(_core)
_google_ai_citation.install(_core)

# Preserva compatibilidade para qualquer código/teste que importe build_site.
for _name, _value in vars(_core).items():
    if not _name.startswith("__"):
        globals()[_name] = _value


def _assert_domain_migration():
    """Falha o build se qualquer artefato crítico ainda publicar o domínio antigo."""
    critical = [
        "sitemap.xml",
        "robots.txt",
        "llms.txt",
        "llms-full.txt",
        "ai-content.md",
        "agent-permissions.json",
        "mcp-actions.json",
        "index.html",
    ]
    problems = []
    for rel in critical:
        path = os.path.join(_core.OUT, rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if OLD_SITE_URL in content:
            problems.append(rel)
    if problems:
        raise RuntimeError(
            "Build bloqueado: domínio antigo ainda presente em: " + ", ".join(problems)
        )

    sitemap = os.path.join(_core.OUT, "sitemap.xml")
    if not os.path.isfile(sitemap):
        raise RuntimeError("Build bloqueado: docs/sitemap.xml não foi gerado")
    with open(sitemap, encoding="utf-8") as f:
        xml = f.read()
    if f"<loc>{SITE_URL}/" not in xml:
        raise RuntimeError("Build bloqueado: sitemap.xml não usa o domínio oficial")



def _optimize_monitor_home():
    """GSC 09/10/2026: home 148 impressões/3 cliques em 28 dias;
    query 'monitor legislativo' 11 impressões/0 cliques. Intervenção
    restrita ao snippet e à primeira dobra, sem mudar dados ou rotas.
    """
    home = os.path.join(_core.OUT, "index.html")
    with open(home, encoding="utf-8") as f:
        html = f.read()
    edits = [
        (
            "<title>Monitor Legislativo e Regulatório de IA | LCF Consulting</title>",
            "<title>Monitor Legislativo de IA no Brasil | PLs, Leis e Tramitação</title>",
        ),
        (
            '<meta name="description" content="Inteligência Regulatória da LCF Consulting sobre IA no Brasil: projetos, leis, atos, agenda, Regulatory Data e histórico auditável com fontes oficiais.">',
            '<meta name="description" content="Acompanhe o PL 2338/2023 e outros projetos de lei sobre IA no Brasil. Consulte tramitação, leis, atos e atualizações com links para fontes oficiais.">',
        ),
        (
            '<meta property="og:title" content="Monitor Legislativo e Regulatório de IA | LCF Consulting">',
            '<meta property="og:title" content="Monitor Legislativo de IA no Brasil | PLs, Leis e Tramitação">',
        ),
        (
            '<meta property="og:description" content="Inteligência Regulatória da LCF Consulting sobre IA no Brasil: projetos, leis, atos, agenda, Regulatory Data e histórico auditável com fontes oficiais.">',
            '<meta property="og:description" content="Acompanhe o PL 2338/2023 e outros projetos de lei sobre IA no Brasil. Consulte tramitação, leis, atos e atualizações com links para fontes oficiais.">',
        ),
        (
            '<p class="lead">Regulatory Monitoring com dados estruturados sobre projetos, leis e atos federais de IA — incluindo score de impacto, timeline, relações normativas e histórico auditável de mudanças.</p>',
            '<p class="lead">Acompanhe projetos de lei sobre inteligência artificial no Brasil, incluindo o PL 2338/2023, além de leis e atos regulatórios. Consulte tramitação, mudanças, histórico e fontes oficiais verificáveis.</p>'
            '<p class="hero-links"><a href="/proposicoes/">Projetos de lei e tramitação</a> · '
            '<a href="/atualizacoes/">Atualizações recentes</a> · '
            '<a href="/timeline/">Linha do tempo da regulação de IA</a></p>',
        ),
    ]
    for before, after in edits:
        if html.count(before) != 1:
            raise RuntimeError("SEO home: trecho esperado ausente ou duplicado")
        html = html.replace(before, after, 1)
    with open(home, "w", encoding="utf-8") as f:
        f.write(html)

def _optimize_pl_2338_search_result():
    """Ajuste GSC específico da ficha do PL 2338/2023; não altera outras URLs."""
    import json
    import re
    from html import escape as html_escape

    path = os.path.join(_core.OUT, "proposicoes", "pl-2338-2023", "index.html")
    source = os.path.join(_core.BASE, "data", "legislation", "propositions.json")
    with open(source, encoding="utf-8") as f:
        propositions = json.load(f).get("proposicoes", [])
    prop = next((p for p in propositions if p.get("tipo") == "PL"
                 and p.get("numero") == 2338 and p.get("ano") == 2023), None)
    if not prop:
        raise RuntimeError("SEO PL 2338: registro oficial não encontrado no dataset")
    with open(path, encoding="utf-8") as f:
        page_html = f.read()

    title = "PL 2338/2023: tramitação na Câmara e situação atual"
    desc = ("PL 2338/2023 na Câmara: situação, relator, tramitação e propostas "
            "do Marco Legal da IA. Ainda não é lei; consulte fontes oficiais.")
    page_html, title_count = re.subn(r"<title>[^<]*</title>",
                                      "<title>" + title + "</title>",
                                      page_html, count=1)
    if title_count != 1:
        raise RuntimeError("SEO PL 2338: title não localizado")
    page_html, og_count = re.subn(
        r'(<meta property="og:title" content=")[^"]*(">)',
        lambda m: m.group(1) + title + m.group(2), page_html, count=1)
    if og_count != 1:
        raise RuntimeError("SEO PL 2338: OG title não localizado")
    old_h1 = "<h1>PL 2338/2023</h1>"
    if page_html.count(old_h1) != 1:
        raise RuntimeError("SEO PL 2338: H1 não localizado")
    page_html = page_html.replace(old_h1,
                                  "<h1>PL 2338/2023: tramitação na Câmara</h1>", 1)
    for attribute in ('name="description"', 'property="og:description"'):
        pattern = r'(<meta ' + re.escape(attribute) + r' content=")[^"]*(">)'
        page_html, count = re.subn(pattern, lambda m: m.group(1) + desc + m.group(2),
                                   page_html, count=1)
        if count != 1:
            raise RuntimeError("SEO PL 2338: meta description não localizada")

    status = prop.get("situacao") or "Situação não confirmada nesta atualização"
    anchor = '      <div style="margin-top:10px"><span class="tag '
    if page_html.count(anchor) != 1:
        raise RuntimeError("SEO PL 2338: âncora da primeira dobra não localizada")
    snippet = (
        '      <p class="sub" style="font-size:14px;margin-top:12px">'
        '<strong>Situação atual na Câmara:</strong> ' + html_escape(status)
        + ' · <a href="' + html_escape(prop["url_oficial"], quote=True)
        + '" target="_blank" rel="noopener">Ficha oficial ↗</a>'
        + ' · <a href="/timeline/">Linha do tempo da regulação de IA</a></p>\n'
    )
    snippet += (
        '      <p class="sub" style="font-size:14px;margin-top:8px">'
        '<strong>O PL 2338/2023 já é lei?</strong> Não. O projeto aprovado '
        'pelo Senado está em análise na Câmara dos Deputados e ainda não '
        'estabelece obrigações legais vigentes.</p>\\n'
    )
    page_html = page_html.replace(anchor, snippet + anchor, 1)
    # Distinguir regras propostas de obrigações já vigentes na síntese editorial.
    for original, correto in (
        (">Obrigações criadas</dt>", ">Obrigações previstas no projeto</dt>"),
        (">Proibições</dt>", ">Proibições propostas</dt>"),
        (">Órgãos responsáveis pela fiscalização</dt>",
         ">Autoridades de fiscalização previstas no projeto</dt>"),
        ("Estabelece o marco regulatório geral da IA no Brasil",
         "O projeto propõe um marco regulatório geral da IA no Brasil"),
    ):
        page_html = page_html.replace(original, correto, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page_html)


if __name__ == "__main__":
    _core.main()
    _optimize_monitor_home()
    _optimize_pl_2338_search_result()
    _assert_domain_migration()
    print(f"OK: sitemap e arquivos críticos validados em {SITE_URL}")

