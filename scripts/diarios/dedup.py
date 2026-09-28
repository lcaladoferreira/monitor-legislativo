#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarios/dedup.py — deduplicação com histórico (FASE 8).

A filosofia é a mesma já publicada em `updates.json`: **nada é sobrescrito em
silêncio**. Quando o conteúdo de um item muda, o registro preserva o hash
anterior, o novo hash, a data da alteração e a trilha em `historico`.

Identidade (ver `base.chave_identidade`):
  1. identificador oficial da fonte, quando existe;
  2. `source_id + data + url_oficial + titulo`;
  3. `source_id + data + url_oficial`;
  4. `source_id + hash_conteudo` (último recurso).

Camadas de estado:
  · `MetadataStore` (local, fora do Git) → **todos** os itens ingeridos, incluindo
    os descartados por tema. Sustenta a deduplicação de volume no dia a dia.
  · `data/diarios/estado.json` (versionado, pequeno) → itens **relevantes/de
    revisão** (com histórico completo) e um *digest* por edição
    (`hash_lista` da lista de chaves ingeridas). É isso que sobrevive entre
    execuções no GitHub Actions sem carregar o corpus inteiro para o Git.

Estados possíveis de um item em uma execução:
    novo        nunca visto (primeira_deteccao = agora)
    inalterado  já visto, mesmo hash
    alterado    já visto, hash diferente (histórico registrado)
    duplicado   repetido na mesma execução (dedup intra-run)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from .base import agora_brt, hash_conteudo, salvar_json, ts_iso

# Retenção do estado versionado (o dataset público continua sendo a fonte de leitura).
RETENCAO_DIAS_RELEVANTES = 400
LIMITE_ITENS_RELEVANTES = 4000
LIMITE_EDICOES_POR_FONTE = 200
LIMITE_HISTORICO_ITEM = 20


@dataclass
class ResultadoDedup:
    """O que a deduplicação decidiu para um item (e a trilha preservada)."""

    chave: str
    estado: str = "novo"                 # novo | inalterado | alterado | duplicado
    hash_atual: str = None
    hash_anterior: str = None
    primeira_deteccao: str = None
    ultima_verificacao: str = None
    ultima_alteracao: str = None
    historico: list = field(default_factory=list)

    @property
    def novo(self):
        return self.estado == "novo"

    @property
    def alterado(self):
        return self.estado == "alterado"

    @property
    def duplicado(self):
        return self.estado == "duplicado"

    def para_dict(self):
        return {"chave": self.chave, "estado": self.estado, "hash_atual": self.hash_atual,
                "hash_anterior": self.hash_anterior,
                "primeira_deteccao": self.primeira_deteccao,
                "ultima_verificacao": self.ultima_verificacao,
                "ultima_alteracao": self.ultima_alteracao,
                "historico": list(self.historico)}


class Deduplicador:
    """Dedup em duas camadas (índice local + estado versionado) com histórico."""

    def __init__(self, metadata_store=None, estado=None, logger=print):
        self.store = metadata_store
        self.log = logger
        self.estado = estado if estado is not None else {
            "meta": {"descricao": ("Estado de deduplicação da ingestão dos Diários "
                                   "Oficiais: itens relevantes com histórico de "
                                   "alterações + digest das edições ingeridas."),
                     "versao": 1, "atualizado_em": None},
            "itens_relevantes": {},
            "edicoes": {},
        }
        self.estado.setdefault("itens_relevantes", {})
        self.estado.setdefault("edicoes", {})
        self._vistos_na_execucao = set()
        self._edicoes_na_execucao = {}

    # ------------------------------------------------------------- item a item
    def processar(self, item, registrar_relevante=True, verificado_em=None):
        """Aplica dedup a um item normalizado e devolve `ResultadoDedup`."""
        verificado_em = verificado_em or ts_iso()
        chave = item.get("chave") or item.get("id")
        hash_atual = item.get("hash_conteudo") or hash_conteudo(item.get("titulo"),
                                                                item.get("texto"))
        if chave in self._vistos_na_execucao:
            return ResultadoDedup(chave=chave, estado="duplicado", hash_atual=hash_atual,
                                  ultima_verificacao=verificado_em)
        self._vistos_na_execucao.add(chave)

        anterior = self._buscar(chave)
        resultado = ResultadoDedup(chave=chave, hash_atual=hash_atual,
                                   ultima_verificacao=verificado_em)
        if anterior is None:
            resultado.estado = "novo"
            resultado.primeira_deteccao = verificado_em
            historico = []
        else:
            resultado.primeira_deteccao = anterior.get("primeira_deteccao") or verificado_em
            historico = list(anterior.get("historico") or [])
            # O hash registrado pode vir como `hash_atual` (estado do item) ou
            # `hash_conteudo` (índice de metadados) — os dois são o mesmo valor.
            hash_registrado = anterior.get("hash_atual") or anterior.get("hash_conteudo")
            if hash_registrado == hash_atual:
                resultado.estado = "inalterado"
                resultado.hash_anterior = anterior.get("hash_anterior") or hash_registrado
                resultado.ultima_alteracao = anterior.get("ultima_alteracao")
            else:
                resultado.estado = "alterado"
                resultado.hash_anterior = hash_registrado
                resultado.ultima_alteracao = verificado_em
                historico.append({"data_deteccao": verificado_em, "campo": "texto",
                                  "anterior": resultado.hash_anterior, "novo": hash_atual})
        resultado.historico = historico[-LIMITE_HISTORICO_ITEM:]
        self._persistir_indice(item, resultado)
        item["primeira_deteccao"] = resultado.primeira_deteccao
        item["ultima_verificacao"] = resultado.ultima_verificacao
        item["ultima_alteracao"] = resultado.ultima_alteracao
        item["hash_anterior"] = resultado.hash_anterior
        item["hash_atual"] = hash_atual
        item["dedup_estado"] = resultado.estado

        if registrar_relevante and item.get("relevancia") in ("forte", "revisar"):
            self.registrar_relevante(item, resultado)
        return resultado

    def _persistir_indice(self, item, resultado):
        """Grava o item no índice consultável (MetadataStore) — todos os itens.

        O índice é a memória de volume da deduplicação (inclui os itens
        descartados por tema). O estado versionado no Git guarda só os itens
        relevantes/de revisão + o digest das edições.
        """
        if self.store is None:
            return
        try:
            self.store.upsert({
                "chave": resultado.chave,
                "source_id": item.get("source_id"),
                "jurisdicao": item.get("jurisdicao"),
                "titulo": item.get("titulo"),
                "data": item.get("data"),
                "url_oficial": item.get("url_oficial"),
                "id_oficial": item.get("id_oficial"),
                "hash_conteudo": resultado.hash_atual,
                "hash_atual": resultado.hash_atual,
                "relevancia": item.get("relevancia"),
                "primeira_deteccao": resultado.primeira_deteccao,
                "ultima_verificacao": resultado.ultima_verificacao,
                "ultima_alteracao": resultado.ultima_alteracao,
            })
        except Exception:  # noqa: BLE001 — índice não derruba a coleta
            self.log(f"    [aviso] falha ao gravar o índice de metadados ({resultado.chave})")

    def _buscar(self, chave):
        if self.estado["itens_relevantes"].get(chave):
            return self.estado["itens_relevantes"][chave]
        if self.store is not None:
            registro = self.store.find(chave)
            if registro:
                return registro
        return None

    def registrar_relevante(self, item, resultado):
        """Grava o item relevante/de revisão no estado versionado (com histórico).

        Chamado depois da classificação: a dedup em si já aconteceu, mas só os
        itens que interessam ao dataset público entram no estado que vai para o
        Git — o corpus integral fica no índice local/raw storage.
        """
        registro = self.estado["itens_relevantes"].setdefault(resultado.chave, {})
        registro.update({
            "chave": resultado.chave,
            "source_id": item.get("source_id"),
            "jurisdicao": item.get("jurisdicao"),
            "titulo": item.get("titulo"),
            "data": item.get("data"),
            "url_oficial": item.get("url_oficial"),
            "id_oficial": item.get("id_oficial"),
            "relevancia": item.get("relevancia"),
            "grupos_tematicos": list(item.get("grupos_tematicos") or []),
            "hash_atual": resultado.hash_atual,
            "primeira_deteccao": resultado.primeira_deteccao,
            "ultima_verificacao": resultado.ultima_verificacao,
            "ultima_alteracao": resultado.ultima_alteracao,
            "historico": list(registro.get("historico") or []) + (
                [{"data_deteccao": resultado.ultima_alteracao, "campo": "texto",
                  "anterior": resultado.hash_anterior, "novo": resultado.hash_atual}]
                if resultado.alterado else []),
        })
        if resultado.hash_anterior:
            registro["hash_anterior"] = resultado.hash_anterior
        registro["historico"] = registro["historico"][-LIMITE_HISTORICO_ITEM:]

    # ----------------------------------------------------------------- edições
    def registrar_edicao(self, source_id, referencia, itens, meta=None):
        """Digest de uma edição/seção ingerida (auditoria de integralidade).

        `hash_lista` é o hash da lista de chaves ingeridas: se a mesma edição for
        reingerida com conteúdo diferente (retificação, republicação), o digest
        muda e isso fica registrado — sem guardar a edição inteira no Git.
        """
        chaves = sorted(str(i.get("chave") or i.get("id") or "") for i in (itens or []))
        digest = hash_conteudo("|".join(chaves))
        registro = {
            "itens": len(chaves),
            "hash_lista": digest,
            "ingerido_em": ts_iso(),
            "secoes": (meta or {}).get("secoes") or {},
            "modo_ingestao": (meta or {}).get("modo_ingestao"),
            "layout_ok": (meta or {}).get("layout_ok"),
            "paginacao_detectada": (meta or {}).get("paginacao_detectada"),
            "truncado": (meta or {}).get("truncado"),
        }
        por_fonte = self.estado["edicoes"].setdefault(source_id, {})
        anterior = por_fonte.get(referencia)
        if anterior and anterior.get("hash_lista") != digest:
            registro["reingestao"] = {
                "quando": ts_iso(),
                "itens_antes": anterior.get("itens"),
                "hash_antes": anterior.get("hash_lista"),
                "hash_agora": digest,
            }
        elif anterior:
            registro["ingerido_em"] = anterior.get("ingerido_em", registro["ingerido_em"])
            registro["reingestao"] = anterior.get("reingestao")
        por_fonte[referencia] = registro
        self._edicoes_na_execucao.setdefault(source_id, {})[referencia] = registro
        self._podar_edicoes(source_id)
        return registro

    def _podar_edicoes(self, source_id):
        por_fonte = self.estado["edicoes"].get(source_id) or {}
        if len(por_fonte) <= LIMITE_EDICOES_POR_FONTE:
            return
        for ref in sorted(por_fonte)[:-LIMITE_EDICOES_POR_FONTE]:
            por_fonte.pop(ref, None)

    def edicao_registrada(self, source_id, referencia):
        return ((self.estado["edicoes"].get(source_id) or {}).get(referencia))

    # -------------------------------------------------------------- estado geral
    def resumo(self):
        return {
            "itens_relevantes": len(self.estado["itens_relevantes"]),
            "edicoes_registradas": sum(len(v) for v in self.estado["edicoes"].values()),
            "por_fonte": {fonte: len(refs) for fonte, refs in sorted(self.estado["edicoes"].items())},
        }

    def podar(self, agora=None):
        """Aplica retenção ao estado versionado (mantém histórico recente)."""
        agora = agora or agora_brt()
        corte = (agora - timedelta(days=RETENCAO_DIAS_RELEVANTES)).isoformat()
        itens = self.estado["itens_relevantes"]
        removidos = 0
        if len(itens) > LIMITE_ITENS_RELEVANTES:
            ordenados = sorted(itens.items(),
                               key=lambda kv: (kv[1] or {}).get("ultima_verificacao") or "")
            for chave, registro in ordenados:
                if len(itens) <= LIMITE_ITENS_RELEVANTES:
                    break
                # nunca descarta item verificável recente nem alterado
                if (registro or {}).get("ultima_verificacao", "") >= corte:
                    break
                itens.pop(chave, None)
                removidos += 1
        return removidos

    def salvar(self, caminho):
        self.podar()
        self.estado["meta"]["atualizado_em"] = ts_iso()
        self.estado["meta"]["resumo"] = self.resumo()
        salvar_json(caminho, self.estado)
        return caminho


def carregar_estado(caminho):
    """Carrega o estado versionado; ausente/ilegível → estado vazio (nunca estimado)."""
    from .base import carregar_json
    estado = carregar_json(caminho)
    if not isinstance(estado, dict):
        return None
    estado.setdefault("itens_relevantes", {})
    estado.setdefault("edicoes", {})
    estado.setdefault("meta", {})
    return estado


__all__ = ["Deduplicador", "ResultadoDedup", "carregar_estado",
           "LIMITE_ITENS_RELEVANTES", "RETENCAO_DIAS_RELEVANTES"]
