#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
storage/local.py — implementação local (arquivos) das interfaces de storage.

Compatível com o ambiente atual: não exige banco, serviço externo, credencial ou
GPU. O diretório-raiz é configurável por `MONITOR_RAW_DIR` (padrão:
`<repo>/var/raw/diarios`), deliberadamente **fora do Git** — o dataset público
versionado continua sendo `data/legislation/*.json`.

Layout do RawStorage local:

    <raiz>/<source_id>/<referencia>/itens.jsonl.gz      itens brutos (1 JSON/linha)
    <raiz>/<source_id>/<referencia>/meta.json           metadados da coleta
    <raiz>/<source_id>/<referencia>/fonte/<arquivo>     arquivo-fonte (XML/PDF/ZIP), se houver

Layout do MetadataStore local (índice consultável, com escrita atômica):

    <raiz>/../indice_<nome>.json      {meta, itens: {chave: registro}}

A troca para Object Storage/PostgreSQL é feita registrando outra implementação
em `storage/__init__.py:obter_*` — o coletor não muda.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone

from .base import BackendIndisponivel, MetadataStore, RawStorage, StorageError

RAIZ_PADRAO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "var", "raw", "diarios")


def _slug(valor, limite=120):
    """Sanitiza partes do caminho (nenhum identificador de fonte cria diretório)."""
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", str(valor or "desconhecido"))[:limite].strip("_") or "x"


def _agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _escrever_atomico(caminho, escrever):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=os.path.dirname(caminho), prefix=".tmp_", suffix=".json")
    os.close(fd)
    try:
        with open(temp, "w", encoding="utf-8") as f:
            escrever(f)
        os.replace(temp, caminho)
    except Exception:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


class LocalRawStorage(RawStorage):
    """RawStorage em disco local (gzip para o payload, cópia do arquivo-fonte)."""

    nome = "local"

    def __init__(self, raiz=None):
        self.raiz = os.path.abspath(raiz or os.environ.get("MONITOR_RAW_DIR") or RAIZ_PADRAO)

    # ------------------------------------------------------------------ caminhos
    def caminho(self, source_id, referencia):
        return os.path.join(self.raiz, _slug(source_id), _slug(referencia))

    def _meta_path(self, source_id, referencia):
        return os.path.join(self.caminho(source_id, referencia), "meta.json")

    # --------------------------------------------------------------------- API
    def save(self, source_id, referencia, itens, meta=None, arquivos=None):
        base = self.caminho(source_id, referencia)
        try:
            os.makedirs(base, exist_ok=True)
            caminho_itens = os.path.join(base, "itens.jsonl.gz")
            with gzip.open(caminho_itens, "wt", encoding="utf-8") as f:
                for item in itens or []:
                    f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
            registro_meta = {
                "source_id": source_id,
                "referencia": referencia,
                "itens": len(itens or []),
                "salvo_em": _agora(),
                "itens_arquivo": os.path.relpath(caminho_itens, self.raiz),
                "arquivos_fonte": [],
            }
            registro_meta.update(meta or {})

            for nome, conteudo in (arquivos or {}).items():
                destino = os.path.join(base, "fonte", _slug(nome, 160))
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                modo = "wb" if isinstance(conteudo, (bytes, bytearray)) else "w"
                with open(destino, modo, **({} if modo == "wb" else {"encoding": "utf-8"})) as f:
                    f.write(conteudo)
                registro_meta["arquivos_fonte"].append(os.path.relpath(destino, self.raiz))

            _escrever_atomico(self._meta_path(source_id, referencia),
                              lambda f: json.dump(registro_meta, f, ensure_ascii=False, indent=2))
        except OSError as e:
            raise StorageError(f"falha ao gravar raw storage local ({e})") from e
        return os.path.relpath(base, self.raiz)

    def exists(self, source_id, referencia):
        return os.path.exists(os.path.join(self.caminho(source_id, referencia), "itens.jsonl.gz"))

    def get(self, source_id, referencia):
        base = self.caminho(source_id, referencia)
        if not os.path.exists(base):
            return None
        registro = {"source_id": source_id, "referencia": referencia, "itens": []}
        meta_path = self._meta_path(source_id, referencia)
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as f:
                registro.update(json.load(f))
        itens_path = os.path.join(base, "itens.jsonl.gz")
        if os.path.exists(itens_path):
            with gzip.open(itens_path, "rt", encoding="utf-8") as f:
                registro["itens"] = [json.loads(linha) for linha in f if linha.strip()]
        return registro

    def listar(self, source_id=None, desde=None):
        if not os.path.isdir(self.raiz):
            return []
        referencias = []
        fontes = [_slug(source_id)] if source_id else sorted(os.listdir(self.raiz))
        for fonte in fontes:
            caminho_fonte = os.path.join(self.raiz, fonte)
            if not os.path.isdir(caminho_fonte):
                continue
            for ref in sorted(os.listdir(caminho_fonte)):
                if desde and ref < str(desde):
                    continue
                meta = {}
                meta_path = self._meta_path(fonte, ref)
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, encoding="utf-8") as f:
                            meta = json.load(f)
                    except (OSError, ValueError):
                        meta = {}
                referencias.append({"source_id": fonte, "referencia": ref, **meta})
        return referencias

    def descricao(self):
        return {"backend": self.nome, "classe": type(self).__name__, "raiz": self.raiz,
                "versionado_no_git": False}


class LocalMetadataStore(MetadataStore):
    """MetadataStore em JSON único, com escrita atômica e teto de registros.

    O teto (`limite`, padrão 20.000) evita crescimento infinito do arquivo: os
    registros mais antigos por `ultima_verificacao` são descartados do índice
    (o histórico dos itens relevantes fica preservado no estado versionado —
    ver `scripts/diarios/dedup.py`).
    """

    nome = "local-json"

    def __init__(self, caminho=None, limite=20000):
        if caminho is None:
            raiz = os.path.abspath(os.environ.get("MONITOR_RAW_DIR") or RAIZ_PADRAO)
            caminho = os.path.join(os.path.dirname(raiz), "indice_itens.json")
        self.caminho = os.path.abspath(caminho)
        self.limite = max(100, int(limite))
        self._dados = None

    # ------------------------------------------------------------------ interno
    def _carregar(self):
        if self._dados is not None:
            return self._dados
        dados = {"meta": {"descricao": "Índice de deduplicação da ingestão dos Diários "
                                       "Oficiais (fora do Git; migrável para PostgreSQL)",
                          "atualizado_em": None, "total": 0},
                 "itens": {}}
        if os.path.exists(self.caminho):
            try:
                with open(self.caminho, encoding="utf-8") as f:
                    lido = json.load(f)
                if isinstance(lido, dict) and isinstance(lido.get("itens"), dict):
                    dados = lido
                    dados.setdefault("meta", {})
            except (OSError, ValueError) as e:
                raise StorageError(f"índice de metadados ilegível ({self.caminho}): {e}") from e
        self._dados = dados
        return dados

    def _podar(self):
        itens = self._dados["itens"]
        if len(itens) <= self.limite:
            return 0
        ordenados = sorted(itens.items(),
                           key=lambda kv: (kv[1] or {}).get("ultima_verificacao") or "")
        excedente = len(itens) - self.limite
        for chave, _ in ordenados[:excedente]:
            itens.pop(chave, None)
        return excedente

    def salvar(self):
        """Grava o índice em disco (chamada explícita; nunca por item)."""
        dados = self._carregar()
        self._podar()
        dados["meta"]["total"] = len(dados["itens"])
        dados["meta"]["atualizado_em"] = _agora()
        try:
            _escrever_atomico(self.caminho,
                              lambda f: json.dump(dados, f, ensure_ascii=False, indent=2))
        except OSError as e:
            raise StorageError(f"falha ao gravar índice de metadados ({e})") from e
        return dados["meta"]["total"]

    # --------------------------------------------------------------------- API
    def upsert(self, registro):
        dados = self._carregar()
        chave = registro.get("chave")
        if not chave:
            raise StorageError("upsert sem 'chave'")
        anterior = dados["itens"].get(chave)
        novo = dict(anterior or {})
        novo.update({k: v for k, v in registro.items() if v is not None})
        if anterior is None:
            novo.setdefault("primeira_deteccao", registro.get("ultima_verificacao"))
            novo.setdefault("historico", [])
        else:
            novo["historico"] = list(anterior.get("historico") or [])
            # hash anterior/atual: nenhum registro é sobrescrito em silêncio.
            if anterior.get("hash_conteudo") and registro.get("hash_conteudo") != anterior.get("hash_conteudo"):
                novo["hash_anterior"] = anterior.get("hash_conteudo")
                novo["hash_atual"] = registro.get("hash_conteudo")
                novo["ultima_alteracao"] = registro.get("ultima_verificacao")
        novo["hash_conteudo"] = registro.get("hash_conteudo", anterior.get("hash_conteudo")
                                             if anterior else None)
        dados["itens"][chave] = novo
        alterado = anterior is None or anterior.get("hash_conteudo") != novo.get("hash_conteudo")
        return {"chave": chave, "novo": anterior is None, "alterado": bool(alterado),
                "registro": novo}

    def find(self, chave):
        return self._carregar()["itens"].get(chave)

    def exists(self, chave):
        return chave in self._carregar()["itens"]

    def todos(self):
        return dict(self._carregar()["itens"])

    def limpar(self):
        """Remove o índice (usado por testes; nunca pela coleta)."""
        self._dados = {"meta": {"descricao": "índice vazio"}, "itens": {}}
        if os.path.exists(self.caminho):
            os.unlink(self.caminho)

    def descricao(self):
        return {"backend": self.nome, "classe": type(self).__name__, "caminho": self.caminho,
                "limite": self.limite, "registros": len(self._carregar()["itens"]),
                "versionado_no_git": False}


# ---------------------------------------------------- backends preparados (futuro)
class ObjectStorageRaw(RawStorage):
    """Espaço reservado para Object Storage (S3/MinIO/GCS) — FASE 7.

    Interface idêntica à local; a implementação exige credenciais e serviço
    externo, que não fazem parte desta etapa (nada de infraestrutura paga
    obrigatória). Enquanto não implementado, qualquer chamada falha de forma
    explícita — nunca grava nada parcial.
    """

    nome = "object-storage"

    def _erro(self):
        raise BackendIndisponivel(
            "backend de Object Storage ainda não implementado nesta etapa; use "
            "MONITOR_RAW_STORAGE=local (padrão) ou registre uma implementação em "
            "scripts/storage/__init__.py")

    def save(self, source_id, referencia, itens, meta=None, arquivos=None):
        self._erro()

    def exists(self, source_id, referencia):
        self._erro()

    def get(self, source_id, referencia):
        self._erro()

    def listar(self, source_id=None, desde=None):
        self._erro()


def limpar_raiz(caminho):
    """Remove uma árvore de raw storage (usado apenas por testes)."""
    if os.path.isdir(caminho):
        shutil.rmtree(caminho)
