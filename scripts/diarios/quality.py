#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarios/quality.py — Quality gate da extração textual (FASE 10).

Antes de confiar no texto extraído de qualquer publicação (HTML, PDF, XML), o
pipeline mede a **qualidade** da extração. Só `degraded` ou `failed` poderão,
no futuro, acionar o pipeline visual (ver `scripts/visual_fallback/`). Nesta
etapa nada é acionado automaticamente: a decisão é registrada no item, para
auditoria, e o pipeline visual permanece um stub desligado.

Estados (vocabulário fechado):

    good      texto extraído utilizável para classificação temática
    degraded  utilizável com ressalva — sinais de fragmentação/encoding/camada
              textual fraca; é onde o fallback visual faria sentido
    failed    inutilizável (vazio, ilegível, páginas sem texto) — sem fallback
              visual configurado, o item é registrado como falha de parse; o
              sistema NUNCA inventa conteúdo nem presume "sem publicação"

Sinais medidos (todos derivados do próprio texto, sem chamada externa):
  · texto vazio ou curtíssimo;
  · proporção de caracteres alfabéticos muito baixa;
  · excesso de caracteres inválidos (U+FFFD, controles, símbolos de caixa);
  · fragmentação excessiva (poucas palavras por linha, linhas de 1–2 caracteres);
  · repetição anormal (mesma linha dominante, entropia baixa de tokens);
  · encoding corrompido (mojibake típico: "Ã©", "Â ", "â€", "\x00");
  · páginas/marcadores sem texto ("[página sem texto]", páginas vazias em PDF).

Uso:
    from diarios.quality import evaluate_text_quality
    q = evaluate_text_quality(texto)
    q.estado            # 'good' | 'degraded' | 'failed'
    q.metricas          # números medidos (auditáveis)
    q.motivos           # por que caiu de estado
    q.para_dict()       # serializável para o item/dataset
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

# Limiares (constantes nomeadas: o relatório pode citá-las; mudar aqui muda o
# comportamento de todo o pipeline, de propósito e em um único lugar).
MIN_CARACTERES = 40
MIN_ALFA_MINIMO = 0.35          # proporção mínima de letras
MAX_INVALIDOS_RAZAO = 0.02      # U+FFFD e controles
MIN_PALAVRAS_POR_LINHA = 1.2    # fragmentação
MAX_LINHAS_CURTAS_RAZAO = 0.55  # linhas com <= 2 caracteres
MAX_REPETICAO_LINHA = 0.30      # mesma linha repetida (cabeçalho/rodapé infinito)
MIN_ENTROPIA_TOKENS = 2.2       # bits — repetição anormal de tokens
MAX_MOJIBAKE = 2                # ocorrências de sequências típicas de encoding quebrado

_MOJIBAKE = re.compile(r"Ã[©ª¡¢£¤¥¦§¨¬®¯°±²³´µ¶·¸¹º»¼½¾¿]|Â[ |\u00a0]|â€|Ã\u201a|\ufffd")
_INVALIDO = re.compile(r"[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f]")
_CONTROLE_CAIXA = re.compile(r"[\u2500-\u257f\u25a0-\u25ff]{2,}")  # desenhos de caixa em série
_PAGINA_VAZIA = re.compile(r"\[\s*p[áa]gina\s+sem\s+texto\s*\]|\[sem texto\]", re.I)
_NAO_ALFA = re.compile(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿ]")


@dataclass
class QualidadeTexto:
    """Resultado auditável do quality gate (nunca inventa: só mede)."""

    estado: str = "failed"            # good | degraded | failed
    motivos: list = field(default_factory=list)
    metricas: dict = field(default_factory=dict)

    @property
    def utilizavel(self):
        return self.estado == "good"

    @property
    def aciona_visual(self):
        """Somente degraded/failed podem acionar o pipeline visual (FASE 9/10)."""
        return self.estado in ("degraded", "failed")

    def para_dict(self):
        return {"estado": self.estado, "motivos": list(self.motivos),
                "metricas": dict(self.metricas)}

    def __str__(self):
        return f"{self.estado} ({', '.join(self.motivos) or 'sem ressalva'})"


def _entropia(tokens):
    if not tokens:
        return 0.0
    conta = Counter(tokens)
    total = sum(conta.values())
    return -sum((n / total) * math.log2(n / total) for n in conta.values())


def evaluate_text_quality(texto):
    """Mede a qualidade do texto extraído → `QualidadeTexto` (good/degraded/failed).

    Função pura: mesma entrada → mesma saída. Não acessa rede nem disco.
    """
    bruto = "" if texto is None else str(texto)
    texto_norm = unicodedata.normalize("NFC", bruto)
    linhas = [l.strip() for l in texto_norm.splitlines()]
    linhas_nao_vazias = [l for l in linhas if l]
    caracteres = len(texto_norm.strip())
    total_para_razao = max(1, caracteres)
    letras = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]", texto_norm))
    razao_alfa = letras / total_para_razao
    invalidos = len(_INVALIDO.findall(texto_norm))
    mojibake = len(_MOJIBAKE.findall(texto_norm))
    caixas = len(_CONTROLE_CAIXA.findall(texto_norm))
    paginas_sem_texto = len(_PAGINA_VAZIA.findall(texto_norm))
    palavras = re.findall(r"\S+", texto_norm)
    tokens = [p.lower() for p in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}", texto_norm)]
    linhas_curtas = sum(1 for l in linhas_nao_vazias if len(l) <= 2)
    razao_linhas_curtas = (linhas_curtas / len(linhas_nao_vazias)) if linhas_nao_vazias else 1.0
    palavras_por_linha = (len(palavras) / len(linhas_nao_vazias)) if linhas_nao_vazias else 0.0
    if linhas_nao_vazias:
        _, repeticoes = Counter(linhas_nao_vazias).most_common(1)[0]
        razao_repeticao = repeticoes / len(linhas_nao_vazias)
    else:
        razao_repeticao = 1.0
    entropia = _entropia(tokens)

    metricas = {
        "caracteres": caracteres,
        "linhas": len(linhas_nao_vazias),
        "palavras": len(palavras),
        "tokens": len(tokens),
        "razao_alfabetica": round(razao_alfa, 4),
        "caracteres_invalidos": invalidos,
        "razao_invalidos": round(invalidos / total_para_razao, 4),
        "mojibake": mojibake,
        "blocos_de_caixa": caixas,
        "paginas_sem_texto": paginas_sem_texto,
        "linhas_curtas_razao": round(razao_linhas_curtas, 4),
        "palavras_por_linha": round(palavras_por_linha, 3),
        "repeticao_linha": round(razao_repeticao, 4),
        "entropia_tokens": round(entropia, 3),
    }

    motivos_falha, motivos_degradado = [], []
    if caracteres == 0:
        return QualidadeTexto("failed", ["texto_vazio"], metricas)
    if caracteres < MIN_CARACTERES:
        motivos_falha.append("texto_curto")
    if razao_alfa < MIN_ALFA_MINIMO:
        motivos_falha.append("proporcao_alfabetica_baixa")
    if invalidos / total_para_razao > MAX_INVALIDOS_RAZAO:
        motivos_falha.append("caracteres_invalidos")
    if caixas >= 3:
        motivos_falha.append("conteudo_grafico_sem_texto")
    if paginas_sem_texto and caracteres < 300:
        motivos_falha.append("paginas_sem_texto")
    if mojibake > MAX_MOJIBAKE and razao_alfa < 0.6:
        motivos_degradado.append("encoding_corrompido")
    elif mojibake > MAX_MOJIBAKE:
        motivos_degradado.append("encoding_suspeito")
    if razao_linhas_curtas > MAX_LINHAS_CURTAS_RAZAO:
        motivos_degradado.append("fragmentacao_excessiva")
    if palavras_por_linha < MIN_PALAVRAS_POR_LINHA and len(linhas_nao_vazias) > 8:
        motivos_degradado.append("baixa_densidade_textual")
    if razao_repeticao > MAX_REPETICAO_LINHA and len(linhas_nao_vazias) > 6:
        motivos_degradado.append("repeticao_anormal")
    if len(tokens) >= 30 and entropia < MIN_ENTROPIA_TOKENS:
        motivos_degradado.append("vocabulario_repetitivo")

    if motivos_falha:
        return QualidadeTexto("failed", motivos_falha + motivos_degradado, metricas)
    if motivos_degradado:
        return QualidadeTexto("degraded", motivos_degradado, metricas)
    return QualidadeTexto("good", [], metricas)


def precisa_fallback_visual(qualidade, tem_texto=True, layout_critico=False,
                            tabela_complexa=False, pdf_escaneado=False):
    """Regra conceitual (FASE 9): quando o pipeline visual faria sentido.

    Só `degraded`/`failed` — ou sinais explícitos de que a informação depende da
    estrutura visual (PDF escaneado/sem camada textual, layout crítico, tabela
    complexa) — podem acionar o visual. Nunca é acionado para item bom.
    """
    if qualidade is None:
        return {"acionar": bool(pdf_escaneado or layout_critico or tabela_complexa),
                "motivos": ["sem_quality_gate"] if pdf_escaneado else []}
    motivos = []
    if qualidade.estado == "failed":
        motivos.append("extracao_falhou")
    elif qualidade.estado == "degraded":
        motivos.append("extracao_degradada")
    if not tem_texto:
        motivos.append("camada_textual_ausente")
    if pdf_escaneado:
        motivos.append("pdf_escaneado")
    if layout_critico:
        motivos.append("layout_critico")
    if tabela_complexa:
        motivos.append("tabela_complexa")
    return {"acionar": bool(motivos), "motivos": motivos}
