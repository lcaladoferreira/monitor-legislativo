#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point do build com domínio oficial e camada de visibilidade SEO/AEO/agentic."""
import build_site_core as _core
import ai_visibility as _ai_visibility

_core.SITE_URL = "https://monitor.lcfconsulting.com.br"
_ai_visibility.install(_core)

# Preserva compatibilidade para qualquer código/teste que importe build_site.
for _name, _value in vars(_core).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

if __name__ == "__main__":
    _core.main()
