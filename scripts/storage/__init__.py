#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
storage/__init__.py — camada abstrata de armazenamento (FASE 7).

    RawStorage      conteúdo bruto das coletas (alto volume) → fora do Git
    MetadataStore   índice/deduplicação por item            → fora do Git

O dataset público resumido continua em `data/legislation/*.json`, versionado no
Git — essa camada é adicional, não substitutiva.

Backend padrão: **local** (arquivos), compatível com o ambiente atual e com o
GitHub Actions. A seleção é por variável de ambiente:

    MONITOR_RAW_STORAGE=local        (padrão)
    MONITOR_RAW_STORAGE=object       → interface preparada, indisponível (falha explícita)

Migração futura (sem reescrever o coletor): implementar `RawStorage`/`MetadataStore`
para Object Storage, PostgreSQL ou OpenSearch e registrar em `_RAW_BACKENDS` /
`_METADATA_BACKENDS`.
"""
from __future__ import annotations

import os

from .base import (  # noqa: F401
    BackendIndisponivel, MetadataStore, RawStorage, StorageError,
)
from .local import (  # noqa: F401
    LocalMetadataStore, LocalRawStorage, ObjectStorageRaw,
)

_RAW_BACKENDS = {"local": LocalRawStorage, "object": ObjectStorageRaw}
_METADATA_BACKENDS = {"local": LocalMetadataStore}


def backend_configurado():
    return (os.environ.get("MONITOR_RAW_STORAGE") or "local").strip().lower() or "local"


def obter_raw_storage(backend=None, **kw):
    nome = (backend or backend_configurado()).lower()
    if nome not in _RAW_BACKENDS:
        raise StorageError(f"backend de raw storage desconhecido: {nome!r} "
                           f"(disponíveis: {', '.join(sorted(_RAW_BACKENDS))})")
    return _RAW_BACKENDS[nome](**kw)


def obter_metadata_store(backend=None, **kw):
    nome = (backend or backend_configurado()).lower()
    if nome == "object":
        nome = "local"  # o índice de metadados não precisa de object storage
    if nome not in _METADATA_BACKENDS:
        raise StorageError(f"backend de metadados desconhecido: {nome!r} "
                           f"(disponíveis: {', '.join(sorted(_METADATA_BACKENDS))})")
    return _METADATA_BACKENDS[nome](**kw)


__all__ = ["RawStorage", "MetadataStore", "StorageError", "BackendIndisponivel",
           "LocalRawStorage", "LocalMetadataStore", "ObjectStorageRaw",
           "obter_raw_storage", "obter_metadata_store", "backend_configurado"]
