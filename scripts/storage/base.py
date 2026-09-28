#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
storage/base.py — interfaces abstratas de armazenamento (FASE 7).

O projeto publica hoje um **dataset público resumido** em JSON versionado no Git
(`data/legislation/*.json`). Isso continua valendo e é o que o site consome.

O que **não** escala para milhões de publicações é usar Git como armazenamento
primário de tudo que foi ingerido. Por isso a ingestão integral dos Diários
Oficiais grava em duas camadas distintas:

    RawStorage       conteúdo bruto como veio da fonte (XML, JSON, HTML, PDF)
                     + metadados de coleta. Alto volume, baixo valor de leitura
                     humana → não vai para o Git.
    MetadataStore    índice/deduplicação por item (chave, hashes, histórico de
                     alterações). Consultável, também fora do Git.

As interfaces abaixo são deliberadamente mínimas e independentes de backend:
a implementação atual é local (arquivos), e a migração futura para Object
Storage (S3/MinIO/GCS), PostgreSQL e OpenSearch é uma troca de implementação —
não uma reescrita do coletor.

Nada aqui inventa dado: `save` só grava o que a fonte entregou; `upsert` só
registra o que foi verificado.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class StorageError(RuntimeError):
    """Falha de armazenamento (disco cheio, permissão, backend indisponível)."""


class BackendIndisponivel(StorageError):
    """O backend configurado existe como interface, mas não está disponível."""


class RawStorage(ABC):
    """Guarda o bruto (arquivo-fonte) e o payload já parseado de uma coleta.

    Contrato mínimo:
        save(source_id, referencia, itens, meta=None) -> str   (identificador)
        exists(source_id, referencia, meta=None)      -> bool
        get(identificador)                            -> dict | None
        listar(source_id=None, desde=None)            -> list[dict]  (referências)

    `referencia` é a chave lógica do lote — na prática `YYYY-MM-DD` da edição
    (ou `YYYY-MM-DD_do1` para uma seção). `itens` é a lista de itens brutos
    (dicionários JSON-serializáveis), exatamente como o parser os produziu.
    """

    nome = "raw"

    @abstractmethod
    def save(self, source_id, referencia, itens, meta=None):
        ...

    @abstractmethod
    def exists(self, source_id, referencia):
        ...

    @abstractmethod
    def get(self, source_id, referencia):
        ...

    @abstractmethod
    def listar(self, source_id=None, desde=None):
        ...

    def descricao(self):
        """Descrição legível do backend (aparece no relatório da coleta)."""
        return {"backend": self.nome, "classe": type(self).__name__}


class MetadataStore(ABC):
    """Índice por item: chave estável → hash atual, histórico e primeira detecção.

    Contrato mínimo:
        upsert(registro)  -> dict  (registro efetivo + flag de mudança)
        find(chave)       -> dict | None
        exists(chave)     -> bool
        todos()           -> dict[chave, registro]

    `registro` precisa de, no mínimo:
        chave, source_id, hash_conteudo, primeira_deteccao, ultima_verificacao
    """

    nome = "metadata"

    @abstractmethod
    def upsert(self, registro):
        ...

    @abstractmethod
    def find(self, chave):
        ...

    @abstractmethod
    def exists(self, chave):
        ...

    @abstractmethod
    def todos(self):
        ...

    def descricao(self):
        return {"backend": self.nome, "classe": type(self).__name__}
