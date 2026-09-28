#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual_fallback/pixelrag.py — stub documentado do PixelRAG (FASE 9).

PixelRAG (extração a partir da imagem da página, com modelo de visão + índice
vetorial) **não** faz parte do pipeline principal nesta etapa.

Por quê: exigiria PyTorch, um modelo de visão (ex.: Qwen-VL) e FAISS — o que
aumentaria o tempo do workflow de minutos para horas em CPU, adicionaria risco de
falha na GitHub Action e contrariaria a restrição explícita de não instalar
dependência pesada. A decisão de engenharia foi: preparar a interface, medir a
qualidade do texto e **registrar quando** o visual seria necessário — sem ligá-lo.

Quando faria sentido chamar (futuro, mediante autorização):

    · PDF escaneado (sem camada textual);
    · PDF com extração textual vazia ou muito ruim;
    · layout crítico — a informação só existe na estrutura visual;
    · tabela complexa cuja leitura linearmente extraída perde o sentido.

Nada aqui importa torch/qwen/faiss. `disponivel()` é sempre False e
`extrair()` levanta `VisualFallbackNaoImplementado` em vez de devolver dado
estimado — nunca preencher lacuna com suposição.
"""
from __future__ import annotations

from .base import (  # noqa: F401
    VisualFallback, VisualFallbackNaoImplementado, decidir_pipeline,
    registrar_visual_fallback, status_visual_fallback,
)


class PixelRAGFallback(VisualFallback):
    """Stub do PixelRAG: interface pronta, execução desligada."""

    nome = "pixelrag"
    # Deliberadamente vazio: nada é importado de dependência pesada.
    DEPENDENCIAS = ("torch", "transformers/qwen-vl", "faiss")  # apenas documentação

    def disponivel(self):
        """Sempre False enquanto a integração não for autorizada.

        Não basta o pacote existir no ambiente: habilitar o visual é uma decisão
        explícita (`MONITOR_VISUAL_FALLBACK=pixelrag` + implementação), porque
        muda custo, tempo de workflow e natureza do dado extraído.
        """
        return False

    def extrair(self, documento, **kw):
        raise VisualFallbackNaoImplementado(
            "PixelRAG não está integrado ao pipeline principal (FASE 9). "
            "O item deve ser registrado com extração degraded/failed; nenhum "
            "conteúdo visual é inferido nesta etapa.")

    def descricao(self):
        return {
            "nome": self.nome,
            "classe": type(self).__name__,
            "disponivel": False,
            "ativa_no_pipeline": False,
            "dependencias_nao_instaladas": list(self.DEPENDENCIAS),
            "motivos_de_uso_futuro": [
                "pdf_escaneado", "pdf_sem_camada_textual", "extracao_textual_vazia",
                "extracao_textual_degradada", "layout_critico", "tabela_complexa",
            ],
        }


registrar_visual_fallback(PixelRAGFallback())


__all__ = ["PixelRAGFallback", "decidir_pipeline", "status_visual_fallback",
           "VisualFallbackNaoImplementado"]
