#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point do build com o domínio oficial da LCF Consulting.

O gerador completo permanece em build_site_core.py. Este wrapper força o domínio
canônico usado em canonical, Open Graph, navegação, robots.txt e sitemap.xml.
"""
import build_site_core as _core

_core.SITE_URL = "https://monitor.lcfconsulting.com.br"

# Preserva compatibilidade para qualquer código/teste que importe build_site.
for _name, _value in vars(_core).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

if __name__ == "__main__":
    _core.main()
