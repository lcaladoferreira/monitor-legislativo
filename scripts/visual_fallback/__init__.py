#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual_fallback/__init__.py — fallback visual opcional (FASE 9).

Pacote **desligado por desenho**. A ordem do pipeline é documentada em
`base.decidir_pipeline`:

    FONTE OFICIAL → (XML/JSON estruturado) → texto limpo → [visual, futuro]

Nenhuma dependência pesada (PyTorch, Qwen, FAISS) é importada ou declarada em
`requirements.txt`. O pipeline de Diários Oficiais não chama este pacote; ele
apenas consulta `decidir_pipeline`/`status_visual_fallback` para registrar, de
forma auditável, quando o visual seria necessário.

Importação aqui é *lazy* por design: quem só quer a decisão não paga o custo de
carregar o stub do PixelRAG.
"""
from __future__ import annotations

from .base import (  # noqa: F401
    ETAPAS, VisualFallback, VisualFallbackNaoImplementado, decidir_pipeline,
    registrar_visual_fallback, status_visual_fallback, visual_fallback,
)
from .pixelrag import PixelRAGFallback  # noqa: F401

__all__ = ["ETAPAS", "VisualFallback", "VisualFallbackNaoImplementado",
           "PixelRAGFallback", "decidir_pipeline", "registrar_visual_fallback",
           "status_visual_fallback", "visual_fallback"]
