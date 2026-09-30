#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
frescor.py — Fonte única de verdade sobre a frequência de atualização do monitor.

Incidente 2026-09-30: o selo "Última verificação" e o painel /monitoramento/
usavam limiares fixos (30 h / 54 h, pensados para quatro coletas diárias) e
descreviam um agendamento que não existe mais, enquanto o cron real roda a cada
hora (`17 * * * *`). Resultado: um dataset parado havia 23 h era classificado
como "Monitoramento em dia" e o site anunciava frescor que não tinha.

Aqui a cadência é lida do próprio workflow (.github/workflows/
update-legislation.yml) e dela derivam:
  * a descrição do agendamento (texto exibido em /monitoramento/ e /metodologia/);
  * os limiares de estado (ok / atenção / crítico), usados no build em Python e
    reenviados ao navegador por data-* para que o JS use exatamente os mesmos
    números — sem cópia manual em dois lugares.

O cálculo expande minuto e hora de um cron de 5 campos e ignora dia-do-mês e
dia-da-semana (neste repositório o coletor é de cadência intradiária; um agendamento
mensal ou semanal cairia no piso de 3 h / 8 h, que é o comportamento conservador
desejado). Sem dependências externas.
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW_REL = os.path.join(".github", "workflows", "update-legislation.yml")

# Cron assumido se o workflow não estiver legível (ex.: build fora do repositório).
# Mesmo valor do cron real; o build imprime um aviso quando cai neste caminho.
CRON_PADRAO = "17 * * * *"

# Fatores sobre o intervalo real do cron até o estado pior.
FATOR_OK = 2.5
FATOR_ATENCAO = 6.0
PISO_OK_H = 3.0        # mesmo com coleta horária, 3 h de silêncio já é atraso
PISO_ATENCAO_H = 8.0   # acima disso (e do piso), o estado é crítico

AVISOS = []


# ------------------------------------------------------------------ cron
def _expand(campo, lo, hi):
    """Expande um campo cron ('*', '*/N', '3', '1-5', '1,2') em um conjunto."""
    campo = (campo or "").strip()
    if campo == "*":
        return set(range(lo, hi + 1))
    out = set()
    for parte in campo.split(","):
        parte = parte.strip()
        if not parte:
            continue
        passo = 1
        if "/" in parte:
            parte, _, p = parte.partition("/")
            try:
                passo = int(p)
            except ValueError:
                return set()
            if passo <= 0:
                return set()
        if parte in ("*", ""):
            a, b = lo, hi
        elif "-" in parte:
            x, _, y = parte.partition("-")
            try:
                a, b = int(x), int(y)
            except ValueError:
                return set()
        else:
            try:
                a = b = int(parte)
            except ValueError:
                return set()
        if a < lo or b > hi or a > b:
            return set()
        out.update(range(a, b + 1, passo))
    return out


def crons(caminho=None):
    """Expressões cron declaradas no `schedule:` do workflow de atualização."""
    caminho = caminho or os.path.join(BASE, WORKFLOW_REL)
    try:
        with open(caminho, encoding="utf-8") as f:
            linhas = f.read().splitlines()
    except OSError:
        AVISOS.append(f"workflow de atualização ilegível em {caminho}; usando o cron padrão")
        return [CRON_PADRAO]
    expr, dentro = [], False
    for linha in linhas:
        if re.match(r"^\s{2}schedule:\s*$", linha):
            dentro = True
            continue
        if dentro:
            if not linha.strip() or linha.lstrip().startswith("#"):
                continue                      # comentário não encerra o bloco
            m = re.match(r"^\s*-\s*cron:\s*[\"']?([^\"']+?)[\"']?\s*$", linha)
            if m and len(m.group(1).split()) == 5:
                expr.append(m.group(1))
            dentro = False                     # lista `- cron:` de 1 item só
    if not expr:
        AVISOS.append("nenhum `schedule: cron:` lido no workflow; usando o cron padrão")
        return [CRON_PADRAO]
    return expr


def _minutos_do_dia(expr):
    """Minutos do dia (0..1439, UTC) em que o cron dispara, num dia de semana."""
    partes = (expr or "").split()
    if len(partes) != 5:
        return []
    minuto, hora, _dom, _mes, _dow = partes
    return sorted(h * 60 + m
                  for h in _expand(hora, 0, 23)
                  for m in _expand(minuto, 0, 59))


def intervalo_horas(expr=None):
    """Intervalo médio entre execuções, em horas (a menor janela observada)."""
    expr = expr or crons()[0]
    minutos = _minutos_do_dia(expr)
    if not minutos:
        return 1.0
    if len(minutos) == 1:
        return 24.0
    anterior = minutos[0] - 1440        # o disparo das 00:00 fecha o ciclo anterior
    gaps = [minutos[i] - (anterior if i == 0 else minutos[i - 1])
            for i in range(len(minutos))]
    return round(min(gaps) / 60.0, 2)


def _hhmm_brt(minuto):
    h, m = divmod((minuto - 180) % 1440, 60)   # BRT = UTC-3, sem horário de verão
    return f"{h:02d}:{m:02d}"


def _duracao(horas):
    if horas < 1:
        return f"a cada {int(round(horas * 60))} minutos"
    if float(horas).is_integer():
        h = int(horas)
        return "a cada hora" if h == 1 else f"a cada {h} horas"
    return f"a cada {horas:g} horas"


def descricao(expr=None):
    """Texto do agendamento real, em português, com os horários em UTC e BRT."""
    expr = expr or crons()[0]
    minutos = _minutos_do_dia(expr)
    if not minutos:
        return "agendamento não identificado"
    n = len(minutos)
    if n >= 20:
        mins = sorted({x % 60 for x in minutos})
        when = (f"no minuto {mins[0]}" if len(mins) == 1
                else "nos minutos " + ", ".join(str(m) for m in mins))
        return f"{_duracao(intervalo_horas(expr))}, {when} (UTC e BRT)"
    brt = ", ".join(_hhmm_brt(x) for x in minutos[:4]) + (", …" if n > 4 else "")
    if n == 1:
        return (f"uma vez ao dia, às {minutos[0] // 60:02d}:{minutos[0] % 60:02d} "
                f"(UTC) · {brt} (BRT)")
    return f"{n}x ao dia, às {brt} (BRT)"


def n_por_dia(expr=None):
    return len(_minutos_do_dia(expr or crons()[0]))


# -------------------------------------------------------------- limiares
def limiares():
    """(ok_h, atencao_h) derivados do intervalo real do cron.

    Estado: até `ok_h` → ok; até `atencao_h` → atenção; acima → crítico. Com o
    cron horário isso dá 3 h / 8 h — um dataset 23 h parado cai em crítico, que
    é a leitura honesta.
    """
    h = intervalo_horas()
    return (round(max(PISO_OK_H, FATOR_OK * h), 1),
            round(max(PISO_ATENCAO_H, FATOR_ATENCAO * h), 1))


def estado(idade_horas, lim=None):
    """Classifica a idade (em horas) do último dataset."""
    if idade_horas is None:
        return "atencao"
    ok_h, warn_h = lim or limiares()
    if idade_horas <= ok_h:
        return "ok"
    if idade_horas <= warn_h:
        return "atencao"
    return "critico"


def resumo():
    """Bloco usado pelo build, pelo painel e pelos testes."""
    ok_h, warn_h = limiares()
    return {
        "cron": crons()[0],
        "intervalo_horas": intervalo_horas(),
        "execucoes_por_dia": n_por_dia(),
        "descricao": descricao(),
        "ok_horas": ok_h,
        "atencao_horas": warn_h,
    }
