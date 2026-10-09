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

if __name__ == "__main__":
    _core.main()
    _optimize_monitor_home()
    _assert_domain_migration()
    print(f"OK: sitemap e arquivos críticos validados em {SITE_URL}")

