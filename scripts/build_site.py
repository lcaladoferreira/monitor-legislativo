#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point do build com domínio oficial e camada de visibilidade SEO/AEO/agentic."""
import os

import build_site_core as _core
import ai_visibility as _ai_visibility

SITE_URL = "https://monitor.lcfconsulting.com.br"
OLD_SITE_URL = "https://monitor-legislativo-five.vercel.app"

# Força o domínio oficial em toda a geração: canonical, OG, navegação,
# sitemap.xml, robots.txt, JSON-LD e arquivos de descoberta para agentes.
_core.SITE_URL = SITE_URL
_ai_visibility.install(_core)

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


if __name__ == "__main__":
    _core.main()
    _assert_domain_migration()
    print(f"OK: sitemap e arquivos críticos validados em {SITE_URL}")
