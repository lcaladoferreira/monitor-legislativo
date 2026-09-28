#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual_fallback/base.py — interface do fallback visual (FASE 9), desligada.

Regra conceitual do pipeline (implementada em `decidir_pipeline`):

    if structured_data_available:      use_structured_parser()
    elif clean_text_extraction_available: use_text_parser()
    elif pdf_requires_visual_processing:  use_visual_fallback()

O que é verdade nesta etapa:

  · o fallback visual é **interface apenas** — `PixelRAGFallback.disponivel()`
    devolve False;
  · nenhuma dependência pesada foi adicionada (sem PyTorch, sem Qwen, sem
    FAISS): nada disso está em `requirements.txt` e nenhum import é tentado;
  · o pipeline de Diários Oficiais **não chama** o visual fallback;
  · o que existe é a decisão explícita e auditável de quando ele valeria a pena
    (PDF escaneado, PDF sem camada textual, extração textual vazia ou ruim,
    layout crítico, tabela complexa) — registrada no item, para o dia em que a
    integração for autorizada.

Implementação futura: criar uma subclasse de `VisualFallback` com
`disponivel() -> True` e registrar em `registrar_visual_fallback()`. Nenhuma
outra parte do pipeline precisa mudar.
"""
from __future__ import annotations

import os

ETAPAS = ("estruturado", "texto", "visual", "indisponivel")


class VisualFallbackNaoImplementado(RuntimeError):
    """Chamada ao pipeline visual antes de ele existir (nada é executado)."""


def _quality_do_texto(texto):
    """Importa o quality gate sem criar dependência circular obrigatória."""
    try:
        from ..diarios.quality import evaluate_text_quality  # type: ignore
    except (ImportError, ValueError):  # executado como script solto
        try:
            from diarios.quality import evaluate_text_quality  # type: ignore
        except ImportError:
            return None
    return evaluate_text_quality(texto)


def decidir_pipeline(*, estruturado_disponivel=False, texto="", qualidade=None,
                     pdf=False, pdf_escaneado=False, layout_critico=False,
                     tabela_complexa=False):
    """Decide a etapa do pipeline para um documento — sem executar nada.

    Devolve {'etapa': 'estruturado'|'texto'|'visual'|'indisponivel',
             'motivos': [...], 'visual_disponivel': bool}.
    """
    if estruturado_disponivel:
        return {"etapa": "estruturado", "motivos": ["fonte_estruturada_oficial"],
                "visual_disponivel": False}

    q = qualidade if qualidade is not None else _quality_do_texto(texto)
    tem_texto = bool((texto or "").strip())
    motivos_visual = []
    if pdf_escaneado:
        motivos_visual.append("pdf_escaneado")
    if pdf and not tem_texto:
        motivos_visual.append("pdf_sem_camada_textual")
    if q is not None and q.estado == "failed":
        motivos_visual.append("extracao_falhou")
    if q is not None and q.estado == "degraded":
        motivos_visual.append("extracao_degradada")
    if layout_critico:
        motivos_visual.append("layout_critico")
    if tabela_complexa:
        motivos_visual.append("tabela_complexa")

    if motivos_visual:
        return {"etapa": "visual", "motivos": motivos_visual,
                "visual_disponivel": visual_fallback().disponivel()}
    if tem_texto:
        return {"etapa": "texto", "motivos": ["extracao_textual_ok"],
                "visual_disponivel": False}
    return {"etapa": "indisponivel", "motivos": ["sem_texto_e_sem_fonte_estruturada"],
            "visual_disponivel": False}


class VisualFallback:
    """Contrato do fallback visual (extração a partir do que está *visto*)."""

    nome = "visual"

    def disponivel(self):
        return False

    def extrair(self, documento, **kw):  # pragma: no cover - interface
        raise VisualFallbackNaoImplementado(
            f"{type(self).__name__}.extrair() ainda não implementado")

    def descricao(self):
        return {"nome": self.nome, "classe": type(self).__name__,
                "disponivel": self.disponivel(), "ativa_no_pipeline": False}


_REGISTRO = {}


def registrar_visual_fallback(instancia):
    _REGISTRO[instancia.nome] = instancia
    return instancia


def visual_fallback(nome=None):
    """Devolve o fallback visual configurado (padrão: stub PixelRAG, desligado)."""
    if nome:
        if nome not in _REGISTRO:
            raise KeyError(f"visual fallback desconhecido: {nome}")
        return _REGISTRO[nome]
    habilitado = os.environ.get("MONITOR_VISUAL_FALLBACK") or ""
    if habilitado and habilitado in _REGISTRO:
        return _REGISTRO[habilitado]
    return _REGISTRO.get("pixelrag") or VisualFallback()


def status_visual_fallback():
    """Estado do fallback visual para relatório/painel (nunca finge disponibilidade)."""
    inst = visual_fallback()
    return {"implementado": bool(inst.disponivel()),
            "classe": type(inst).__name__,
            "habilitado_por_env": bool(os.environ.get("MONITOR_VISUAL_FALLBACK")),
            "ativa_no_pipeline": False,
            "dependencias_pesadas_instaladas": False,
            "observacao": ("Interface preparada; nenhuma dependência de visão "
                           "(PyTorch/Qwen/FAISS) foi adicionada nesta etapa.")}
