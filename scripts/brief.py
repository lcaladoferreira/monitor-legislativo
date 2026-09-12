#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
brief.py — Motor do "Executive Regulatory Brief".

Monta, a partir EXCLUSIVAMENTE do dataset versionado em /data/legislation, o
payload usado por:
  * /briefing-executivo/  (amostra pública do produto pago)
  * scripts/build_alert_email.py  (e-mail de alerta / relatório executivo)

Regra de ouro (obrigatória no produto comercial):
  FATO OFICIAL  → veio de campo do dataset com fonte oficial associada.
  ANÁLISE       → interpretação do Monitor, derivada de regras públicas e
                  auditáveis deste arquivo. Nunca é apresentada como fato.

Nenhuma informação é inventada: quando o dataset não contém o dado, o campo
sai como None / "não informado na fonte oficial" e a interface mostra isso.
Nada aqui constitui aconselhamento jurídico.

Sem dependências externas (stdlib).
"""
from datetime import date, datetime, timedelta

try:  # rúbrica pública do AI Legislative Impact Score (mesmo módulo do gerador)
    from scoring import RUBRIC_MAX
except ImportError:  # pragma: no cover — execução fora de scripts/
    RUBRIC_MAX = {}

# ---------------------------------------------------------------------------
# Tabelas de regras (públicas e auditáveis) — ANÁLISE, não fato oficial
# ---------------------------------------------------------------------------

# Categoria temática (id em categories.json) → setores empresariais potencialmente
# afetados. Base para "Quem pode ser afetado" e para as páginas setoriais (P1).
CATEGORIA_PARA_SETORES = {
    1: ["Tecnologia", "Todos os setores que usam IA"],
    2: ["Tecnologia", "Jurídico", "Saúde", "Plataformas digitais"],
    3: ["Tecnologia", "Bancos e fintech", "Seguros", "Saúde", "Cloud e data center", "Varejo"],
    4: ["Tecnologia", "Seguros", "Jurídico", "Indústria"],
    5: ["Jurídico", "Segurança pública", "Tecnologia"],
    6: ["Mídia e entretenimento", "Tecnologia", "Educação"],
    7: ["RH e grandes empregadores", "Tecnologia"],
    8: ["Educação", "Edtech"],
    9: ["Saúde", "Healthtech", "Seguros"],
    10: ["Segurança pública", "Defesa", "Tecnologia"],
    11: ["Defesa", "Indústria"],
    12: ["Jurídico", "Escritórios de advocacia"],
    13: ["Político-eleitoral", "Plataformas digitais", "Mídia"],
    14: ["Mídia e entretenimento", "Plataformas digitais", "Político-eleitoral"],
    15: ["Plataformas digitais", "Mídia", "Publicidade"],
    16: ["Plataformas digitais", "Tecnologia", "Publicidade"],
    17: ["Segurança", "Varejo", "Bancos e fintech", "Saúde"],
    18: ["Segurança", "Varejo", "Bancos e fintech"],
    19: ["Governo", "Consultoria", "Associações"],
    20: ["Bancos e fintech", "Seguros", "Meios de pagamento"],
    21: ["Varejo", "Consumo", "Bancos e fintech", "Telecom"],
    22: ["Tecnologia", "Cloud e data center", "Bancos e fintech", "Infraestrutura"],
    23: ["Tecnologia", "Cloud e data center", "Indústria"],
    24: ["Tecnologia", "Jurídico", "Compliance", "Plataformas digitais"],
    25: ["Tecnologia", "Compliance", "Auditoria", "Bancos e fintech"],
    26: ["Saúde", "Bancos e fintech", "Infraestrutura", "Telecom", "Tecnologia"],
    27: ["Tecnologia", "Academia e P&D", "Cloud e data center"],
    28: ["Cloud e data center", "Infraestrutura", "Tecnologia", "Investidores"],
    29: ["Cloud e data center", "Infraestrutura", "Telecom", "Energia"],
    30: ["Governo", "Infraestrutura", "Tecnologia", "Associações"],
}

# Faixa do AI Legislative Impact Score → impacto potencial (escala do produto).
def impacto_potencial(score):
    """Escala comercial: Crítico / Alto / Médio / Baixo.

    Derivada diretamente do score proprietário (fato: o score existe no dataset).
    """
    try:
        s = int(score or 0)
    except (TypeError, ValueError):
        s = 0
    if s >= 85:
        return "Crítico"
    if s >= 70:
        return "Alto"
    if s >= 50:
        return "Médio"
    return "Baixo"


# Regras de "Ação recomendada" (análise). A primeira regra que casar vence.
# Cada regra declara a base objetiva que a dispara — exibida na interface.
ACAO_RECOMENDADA_REGRAS = [
    {
        "acao": "Informar relações governamentais e preparar atuação",
        "quando": "Matéria em estágio decisório imediato (pauta, plenário, sanção) com score alto.",
        "teste": lambda p, ctx: ctx["estagio_decisorio"] and ctx["score"] >= 70,
    },
    {
        "acao": "Informar jurídico e compliance para análise interna",
        "quando": "Texto cria obrigações, vedações ou deveres de governança documentados no registro.",
        "teste": lambda p, ctx: bool(ctx["obrigacoes"]) or bool(ctx["proibicoes"]),
    },
    {
        "acao": "Revisar processo e mapear sistemas de IA enquadrados",
        "quando": "Matéria trata de sistemas de alto risco, auditoria, transparência algorítmica ou biometria.",
        "teste": lambda p, ctx: bool(ctx["cats"] & {26, 25, 24, 17, 18}),
    },
    {
        "acao": "Aguardar regulamentação e monitorar atos infralegais",
        "quando": "Norma já vigente ou matéria convertida em lei, com efeitos dependentes de regulamentação.",
        "teste": lambda p, ctx: ctx["virou_norma"],
    },
    {
        "acao": "Acompanhar e revisar posição quando houver relatório ou parecer",
        "quando": "Matéria relevante ainda sem parecer, em comissão ou apensada.",
        "teste": lambda p, ctx: ctx["score"] >= 55,
    },
    {
        "acao": "Acompanhar em cadência ordinária",
        "quando": "Matéria de baixa prioridade ou sem sinal de movimentação relevante.",
        "teste": lambda p, ctx: True,
    },
]

# Tipos de mudança (updates.json) → severidade comercial para o alerta.
SEVERIDADE_MUDANCA = {
    "sanção": "crítica",
    "aprovação": "crítica",
    "publicação": "alta",
    "parecer": "alta",
    "relatoria": "alta",
    "decisão judicial": "alta",
    "cronograma": "média",
    "fiscalização": "média",
    "tramitação": "média",
    "apensação": "média",
    "arquivamento": "média",
    "nova proposição": "baixa",
    "atualização cadastral": "baixa",
}

FONTES_OFICIAIS_DOMINIOS = (
    "camara.leg.br", "senado.leg.br", "congressonacional.leg.br", "planalto.gov.br",
    "in.gov.br", "tse.jus.br", "cnj.jus.br", "gov.br/anpd", "dadosabertos.camara.leg.br",
)


# ---------------------------------------------------------------------------
# Helpers de data
# ---------------------------------------------------------------------------

def _parse_date(s):
    if not s:
        return None
    s = str(s)[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_between(ref, s):
    d = _parse_date(s)
    if not d or not ref:
        return None
    return (ref - d).days


def _fmt(d):
    if isinstance(d, str):
        d = _parse_date(d)
    if not d:
        return "—"
    return d.strftime("%d/%m/%Y")


def _limpar(texto, limite=None):
    """Colapsa quebras de linha/espaços e trunca sem cortar palavra no meio."""
    if not texto:
        return None
    import re as _re
    t = _re.sub(r"\s+", " ", str(texto).replace("\r", " ")).strip()
    if limite and len(t) > limite:
        corte = t[:limite]
        espaco = corte.rfind(" ")
        if espaco > limite * 0.6:
            corte = corte[:espaco]
        t = corte.rstrip(" ,;:.") + " […]"
    return t


def ref_date(execution_date=None):
    d = _parse_date(execution_date)
    return d or date.today()


# ---------------------------------------------------------------------------
# Análise por proposição
# ---------------------------------------------------------------------------

def _is_oficial(url):
    return bool(url) and any(dom in url for dom in FONTES_OFICIAIS_DOMINIOS)


def analisar_proposicao(p, cats_by_id, ref, updates_by_prop=None):
    """Retorna o bloco {fato_oficial, analise, score} de uma proposição.

    `fato_oficial` só contém campos presentes no dataset. `analise` contém a
    interpretação derivada das regras públicas deste módulo, sempre com a base
    objetiva declarada em `base_da_analise` e o `status_interpretacao`.
    """
    imp = p.get("impacto") or {}
    score = imp.get("score", 0) or 0
    situacao = (p.get("situacao") or "").strip()
    sit_low = situacao.lower()
    estagio = (p.get("estagio") or "").strip()
    proxima = (p.get("proxima_etapa") or "").strip()
    obrigacoes = (p.get("obrigacoes_criadas") or "").strip()
    proibicoes = (p.get("proibicoes") or "").strip()
    orgaos = (p.get("orgaos_responsaveis") or "").strip()
    chance = (p.get("chance_impacto_regulatorio") or "").strip()
    cat_ids = set(p.get("categorias") or [])
    ultima = p.get("ultima_movimentacao") or {}

    estagio_decisorio = any(k in sit_low for k in (
        "pauta", "plenário", "plenario", "ordem do dia", "sanção", "sancao",
        "aprovado", "redação final", "redacao final", "promulgação"))
    virou_norma = any(k in sit_low for k in (
        "transformada em norma", "convertida", "sancionada", "lei nº", "lei n°")) or \
        "transformada em norma" in (estagio or "").lower()

    ctx = {
        "score": score,
        "cats": cat_ids,
        "obrigacoes": obrigacoes,
        "proibicoes": proibicoes,
        "orgaos": orgaos,
        "estagio_decisorio": estagio_decisorio,
        "virou_norma": virou_norma,
    }

    acao = ACAO_RECOMENDADA_REGRAS[-1]
    for regra in ACAO_RECOMENDADA_REGRAS:
        if regra["teste"](p, ctx):
            acao = regra
            break

    # Setores afetados: união determinística a partir das categorias temáticas.
    setores = []
    for cid in sorted(cat_ids):
        for s in CATEGORIA_PARA_SETORES.get(cid, []):
            if s not in setores:
                setores.append(s)

    # Por que importa: usa o enriquecimento curado quando existe; caso contrário
    # declara explicitamente que a leitura é automatizada (sem inventar texto).
    base_analise = []
    if obrigacoes:
        base_analise.append("obrigacoes_criadas")
    if proibicoes:
        base_analise.append("proibicoes")
    if orgaos:
        base_analise.append("orgaos_responsaveis")
    if chance:
        base_analise.append("chance_impacto_regulatorio")

    curado = bool(base_analise) and not p.get("revisao_pendente")

    if obrigacoes:
        por_que = f"O texto documentado cria obrigações: {obrigacoes}."
        if proibicoes:
            por_que += f" E vedações: {proibicoes}."
    elif proibicoes:
        por_que = f"O texto documentado estabelece vedações: {proibicoes}."
    elif virou_norma:
        por_que = ("Matéria já convertida em norma: o efeito sobre a operação depende dos "
                   "prazos e da regulamentação infralegal associados.")
    elif estagio_decisorio:
        por_que = ("Matéria em estágio decisório — mudanças de texto ou de calendário nesta "
                   "fase alteram diretamente o prazo de adaptação de quem é afetado.")
    else:
        por_que = ("Registro automático ainda sem curadoria editorial: o enquadramento "
                   "empresarial depende da análise do texto oficial.")

    if chance:
        por_que += f" Leitura registrada no monitor: {chance}"

    # Prazo provável: só declara quando há data/etapa explícita no dataset.
    prazo = None
    prazo_base = None
    if proxima:
        prazo = proxima
        prazo_base = "proxima_etapa"
    elif estagio_decisorio and (ultima.get("data")):
        prazo = f"Estágio decisório em curso (última movimentação oficial em {_fmt(ultima.get('data'))})."
        prazo_base = "situacao + ultima_movimentacao"

    fato = {
        "titulo": f"{p.get('tipo', '')} {p.get('numero', '')}/{p.get('ano', '')}",
        "nome": p.get("titulo") or "",
        "id": p.get("id"),
        "situacao": situacao or None,
        "estagio": estagio or None,
        "casa_atual": p.get("casa_atual"),
        "comissao_atual": p.get("comissao_atual"),
        "relator": (p.get("relator") or {}).get("nome"),
        "relator_partido": (p.get("relator") or {}).get("partido"),
        "ultima_movimentacao_data": ultima.get("data"),
        "ultima_movimentacao": ultima.get("descricao"),
        "proxima_etapa": proxima or None,
        "obrigacoes_criadas": obrigacoes or None,
        "proibicoes": proibicoes or None,
        "orgaos_responsaveis": orgaos or None,
        "url_oficial": p.get("url_oficial"),
        "url_oficial_eh_fonte_primaria": _is_oficial(p.get("url_oficial")),
        "aguardando_curadoria": bool(p.get("revisao_pendente")),
        "total_apensados": p.get("total_apensados"),
        "ementa": p.get("ementa"),
        "resumo": p.get("resumo"),
        "mudancas_registradas": updates_by_prop or [],
    }

    # Fatores do score: usa o detalhe da rúbrica quando o dataset o traz;
    # caso contrário lista os fatores observáveis que sustentam a faixa.
    detalhe = imp.get("detalhe") or {}
    fatores = []
    if detalhe:
        for k, v in detalhe.items():
            fatores.append({
                "criterio": k.replace("_", " ").title(),
                "pontos": v,
                "maximo": RUBRIC_MAX.get(k, v),
                "origem": "rúbrica pública aplicada no cálculo",
            })
        fatores.sort(key=lambda f: -f["pontos"])
    else:
        observados = []
        if estagio_decisorio:
            observados.append("estágio decisório (pauta/plenário/sanção)")
        if virou_norma:
            observados.append("matéria convertida em norma vigente")
        if cat_ids & {1, 24, 26, 30}:
            observados.append("abrangência regulatória ampla (marco geral / alto risco / soberania)")
        try:
            if int(p.get("total_apensados") or 0) >= 3:
                observados.append(f"{p.get('total_apensados')} proposições apensadas")
        except (TypeError, ValueError):
            pass
        if obrigacoes or proibicoes:
            observados.append("obrigações e vedações documentadas no texto")
        if orgaos:
            observados.append("criação/alteração de competências institucionais")
        if (p.get("regime_tramitacao") or "").lower().find("urg") >= 0 or \
           (p.get("regime_tramitacao") or "").lower().find("prior") >= 0:
            observados.append(f"regime: {p.get('regime_tramitacao')}")
        fatores = [{"criterio": o, "pontos": None, "maximo": None,
                    "origem": "fatores observados no registro oficial"} for o in observados]

    analise = {
        "por_que_importa": por_que,
        "setores_afetados": setores,
        "impacto_potencial": impacto_potencial(score),
        "prazo_provavel": prazo,
        "prazo_provavel_base": prazo_base,
        "obrigacao_potencial": obrigacoes or ("Não detalhada no registro público desta matéria."
                                              if not curado else None),
        "risco_operacional": ("Relevante: a matéria cria deveres de governança, transparência ou "
                              "auditoria sobre sistemas de IA." if (obrigacoes or cat_ids & {24, 25, 26})
                              else "Não identificado a partir do registro público."),
        "impacto_em_compliance": bool(cat_ids & {1, 24, 25, 26, 3, 22}),
        "impacto_em_dados": bool(cat_ids & {3, 17, 18}),
        "impacto_em_modelos_de_ia": bool(cat_ids & {1, 6, 23, 24, 25, 26}),
        "impacto_em_infraestrutura": bool(cat_ids & {28, 29, 30, 22}),
        "acao_recomendada": acao["acao"],
        "acao_recomendada_criterio": acao["quando"],
        "status_interpretacao": ("curadoria editorial" if curado else
                                 "interpretação automatizada (rúbrica pública) — sem curadoria"),
        "base_da_analise": base_analise or ["categorias", "situacao", "impacto.score"],
    }

    return {
        "fato_oficial": fato,
        "analise": analise,
        "score": {
            "valor": score,
            "classificacao": imp.get("classificacao") or "",
            "fatores": fatores,
            "rúbrica_publica": bool(detalhe),
        },
    }


# ---------------------------------------------------------------------------
# Montagem do brief
# ---------------------------------------------------------------------------

def _mudanca_bloco(m, by_id, cats_by_id, ref):
    prop = by_id.get(m.get("proposicao")) if m.get("proposicao") else None
    score = ((prop or {}).get("impacto") or {}).get("score", 0) if prop else 0
    tipo = (m.get("tipo") or "").strip()
    dias = _days_between(ref, m.get("data"))
    return {
        "data": m.get("data"),
        "data_fmt": _fmt(m.get("data")),
        "dias_atras": dias,
        "titulo": m.get("titulo"),
        "descricao": m.get("descricao"),
        "tipo": tipo,
        "severidade": SEVERIDADE_MUDANCA.get(tipo, "média"),
        "proposicao_id": m.get("proposicao"),
        "proposicao_rotulo": (f"{prop.get('tipo')} {prop.get('numero')}/{prop.get('ano')}"
                              if prop else None),
        "score": score,
        "impacto_potencial": impacto_potencial(score) if prop else None,
        "fonte_url": m.get("fonte_url"),
        "fonte_oficial": _is_oficial(m.get("fonte_url")),
    }


def build_brief(props, updates, events, laws, cats_by_id, execution_date=None,
                top_n=5, janela_dias=7):
    """Gera o payload completo do Executive Regulatory Brief."""
    ref = ref_date(execution_date)
    by_id = {p["id"]: p for p in props}

    mudancas = sorted(updates.get("mudancas", []), key=lambda m: (m.get("data") or ""), reverse=True)
    updates_by_prop = {}
    for m in mudancas:
        if m.get("proposicao"):
            updates_by_prop.setdefault(m["proposicao"], []).append(m)

    na_janela = [m for m in mudancas
                 if (_days_between(ref, m.get("data")) is not None
                     and 0 <= _days_between(ref, m.get("data")) <= janela_dias)]
    # Se não houver mudança na janela (semana sem movimentação), o brief mostra as
    # mais recentes disponíveis e declara o período real — nunca inventa mudança.
    periodo_usado = janela_dias
    base_mudancas = na_janela
    if not base_mudancas and mudancas:
        mais_recente = _parse_date(mudancas[0].get("data"))
        if mais_recente:
            periodo_usado = max((ref - mais_recente).days, 1)
            base_mudancas = [m for m in mudancas
                             if (_days_between(ref, m.get("data")) is not None
                                 and 0 <= _days_between(ref, m.get("data")) <= periodo_usado)]

    criticas = sorted(base_mudancas,
                      key=lambda m: (SEVERIDADE_MUDANCA.get((m.get("tipo") or ""), "média")
                                     not in ("crítica", "alta"),
                                     -(((by_id.get(m.get("proposicao")) or {}).get("impacto") or {}).get("score", 0))))
    criticas = [_mudanca_bloco(m, by_id, cats_by_id, ref) for m in criticas]

    # Contexto de 30 dias: usado quando a semana tem pouca movimentação (o brief
    # declara o volume real do período em vez de inflar a lista).
    contexto_30 = [_mudanca_bloco(m, by_id, cats_by_id, ref) for m in mudancas
                   if (_days_between(ref, m.get("data")) is not None
                       and 0 <= _days_between(ref, m.get("data")) <= 30)][:12]

    # Top matérias por impacto
    top = sorted(props, key=lambda p: -((p.get("impacto") or {}).get("score", 0)))[:top_n]
    top_blocos = [analisar_proposicao(
        p, cats_by_id, ref,
        updates_by_prop=[_mudanca_bloco(m, by_id, cats_by_id, ref)
                         for m in updates_by_prop.get(p["id"], [])][:3]) for p in top]

    # Mudanças desde o último relatório. Critério preferencial: execução anterior
    # do cron (log auditável). Se não houver mudança entre execuções (rodadas no
    # mesmo dia), usa a janela do briefing anterior (7 dias precedentes) — sempre
    # declarando qual critério foi aplicado.
    execucoes = updates.get("execucoes") or []
    ultima_exec = execucoes[0] if execucoes else {}
    exec_anterior = execucoes[1] if len(execucoes) > 1 else {}
    ref_anterior = _parse_date((exec_anterior.get("fim") or exec_anterior.get("data_hora") or ""))
    desde_ultimo = []
    criterio_desde = None
    if ref_anterior:
        desde_ultimo = [_mudanca_bloco(m, by_id, cats_by_id, ref) for m in mudancas
                        if _parse_date(m.get("data")) and _parse_date(m.get("data")) > ref_anterior]
        if desde_ultimo:
            criterio_desde = f"execução anterior do monitoramento ({_fmt(ref_anterior)})"
    if not desde_ultimo:
        ini = ref - timedelta(days=2 * janela_dias)
        fim = ref - timedelta(days=janela_dias)
        desde_ultimo = [_mudanca_bloco(m, by_id, cats_by_id, ref) for m in mudancas
                        if _parse_date(m.get("data")) and ini < _parse_date(m.get("data")) <= fim]
        criterio_desde = (f"janela do briefing anterior ({_fmt(ini)} a {_fmt(fim)}) — "
                          "sem mudança entre as duas últimas execuções do cron")

    # Agenda: próximos N dias + marcos sem data confirmada
    agenda = []
    for e in events.get("eventos", []):
        di = _parse_date(e.get("data_inicio"))
        df = _parse_date(e.get("data_fim"))
        if di and df and df < ref:
            continue  # evento já encerrado na data de referência do build
        if di and (di - ref).days <= janela_dias and (di - ref).days >= 0:
            janela = "proximos_%d_dias" % janela_dias
        elif di:
            janela = "alem_da_janela"
        else:
            janela = "sem_data_confirmada"
        agenda.append({
            "titulo": _limpar(e.get("titulo"), 150),
            "titulo_completo": _limpar(e.get("titulo"), 1000),
            "data_inicio": e.get("data_inicio"),
            "data_fim": e.get("data_fim"),
            "data_fmt": _fmt(e.get("data_inicio")) if e.get("data_inicio") else "sem data confirmada",
            "casa": e.get("casa"),
            "tipo": e.get("tipo"),
            "local": _limpar(e.get("local"), 120),
            "hora": e.get("hora"),
            "tema": _limpar(e.get("tema"), 320),
            "relacao_ia": _limpar(e.get("relacao_ia"), 300),
            "fonte_url": e.get("fonte_url"),
            "fonte_oficial": _is_oficial(e.get("fonte_url")),
            "janela": janela,
            "dias": (di - ref).days if di else None,
        })
    agenda_curta = [a for a in agenda if a["janela"] == "proximos_%d_dias" % janela_dias]
    agenda_sem_data = [a for a in agenda if a["janela"] == "sem_data_confirmada"]
    agenda_alem = sorted([a for a in agenda if a["janela"] == "alem_da_janela"],
                         key=lambda a: a["data_inicio"] or "9999")

    # Impactos possíveis por setor (agregação determinística)
    setores = {}
    for p in props:
        bloco = analisar_proposicao(p, cats_by_id, ref)
        sc = bloco["score"]["valor"]
        for s in bloco["analise"]["setores_afetados"]:
            reg = setores.setdefault(s, {"setor": s, "proposicoes": 0, "score_max": 0,
                                         "top": None, "criticos": 0, "mudancas_recentes": 0})
            reg["proposicoes"] += 1
            if sc > reg["score_max"]:
                reg["score_max"] = sc
                reg["top"] = {
                    "rotulo": bloco["fato_oficial"]["titulo"],
                    "nome": bloco["fato_oficial"]["nome"],
                    "id": p["id"],
                    "score": sc,
                    "impacto_potencial": bloco["analise"]["impacto_potencial"],
                }
            if sc >= 85:
                reg["criticos"] += 1
            if updates_by_prop.get(p["id"]):
                reg["mudancas_recentes"] += 1
    setores_lista = sorted(setores.values(), key=lambda s: (-s["score_max"], -s["proposicoes"]))

    # Pontos de atenção executiva: só afirmações sustentadas por campos do dataset
    atencao = []
    sancao = [p for p in props if "sanç" in (p.get("situacao") or "").lower()
              or "aguarda sanção" in (p.get("situacao") or "").lower()]
    if sancao:
        atencao.append({
            "ponto": "Matérias aguardando sanção presidencial",
            "detalhe": "; ".join(f"{p.get('tipo')} {p.get('numero')}/{p.get('ano')}" for p in sancao[:4]),
            "base": "campo situacao do dataset (fonte oficial)",
        })
    paradas = [p for p in props if ((p.get("impacto") or {}).get("score", 0) >= 80)
               and "parecer" in (p.get("situacao") or "").lower()]
    if paradas:
        atencao.append({
            "ponto": "Matérias de maior score dependentes de parecer do relator",
            "detalhe": "; ".join(f"{p.get('tipo')} {p.get('numero')}/{p.get('ano')} — "
                                 f"{(p.get('situacao') or '')[:90]}" for p in paradas[:3]),
            "base": "campo situacao + impacto.score",
        })
    if criticas:
        atencao.append({
            "ponto": f"{len(criticas)} mudança(s) registrada(s) no período do relatório",
            "detalhe": criticas[0]["titulo"],
            "base": "updates.json (mudancas)",
        })
    vigentes = [l for l in laws if "Vigente" in (l.get("status") or "")]
    if vigentes:
        atencao.append({
            "ponto": f"{len(vigentes)} normas vigentes mapeadas com relação direta a IA",
            "detalhe": "; ".join(f"{l.get('tipo')} {l.get('numero')}" for l in vigentes[:5] if l.get("numero")),
            "base": "laws.json",
        })
    if agenda_sem_data:
        atencao.append({
            "ponto": "Marcos previstos sem data oficial confirmada",
            "detalhe": "; ".join(a["titulo"] for a in agenda_sem_data[:3]),
            "base": "events.json (janela sem_data_confirmada)",
        })

    # Fontes oficiais citadas neste brief
    fontes = {}
    for b in top_blocos:
        u = b["fato_oficial"].get("url_oficial")
        if u:
            fontes[u] = b["fato_oficial"]["titulo"]
    for m in criticas:
        if m.get("fonte_url"):
            fontes[m["fonte_url"]] = m["titulo"]
    for l in vigentes[:8]:
        if l.get("url"):
            fontes[l["url"]] = f"{l.get('tipo')} {l.get('numero')} — {l.get('nome')}"

    return {
        "meta": {
            "modelo": "Executive Regulatory Brief",
            "referencia": ref.isoformat(),
            "referencia_fmt": _fmt(ref),
            "execucao": execution_date,
            "periodo_mudancas_dias": periodo_usado,
            "janela_solicitada_dias": janela_dias,
            "total_proposicoes": len(props),
            "total_normas": len(laws),
            "total_mudancas_no_periodo": len(criticas),
            "total_mudancas_30_dias": len(contexto_30),
            "score_minimo_destaque": 85,
            "proposicoes_score_80_mais": sum(1 for p in props
                                             if (p.get("impacto") or {}).get("score", 0) >= 80),
            "gerado_por": "brief.py — regras públicas em scripts/brief.py",
            "aviso": ("Inteligência regulatória e análise de impacto. Não constitui parecer, "
                      "aconselhamento jurídico ou garantia de conformidade."),
        },
        "mudancas_criticas": criticas,
        "mudancas_30_dias": contexto_30,
        "top_materias": top_blocos,
        "desde_ultimo_relatorio": desde_ultimo,
        "criterio_desde_ultimo_relatorio": criterio_desde,
        "execucoes": {"ultima": ultima_exec, "anterior": exec_anterior},
        "agenda": {
            "proximos_dias": agenda_curta,
            "sem_data_confirmada": agenda_sem_data,
            "alem_da_janela": agenda_alem[:8],
        },
        "setores": setores_lista,
        "atencao_executiva": atencao,
        "fontes_oficiais": [{"url": u, "referencia": r} for u, r in sorted(fontes.items())],
    }


def carregar_datasets(data_dir):
    """Conveniência: carrega os JSON do dataset a partir de um diretório."""
    import json
    import os

    def _load(nome):
        with open(os.path.join(data_dir, nome), encoding="utf-8") as f:
            return json.load(f)

    props = _load("propositions.json").get("proposicoes", [])
    updates = _load("updates.json")
    events = _load("events.json")
    laws = _load("laws.json").get("normas", [])
    cats = {c["id"]: c for c in _load("categories.json").get("categorias", [])}
    execucao = updates.get("meta", {}).get("execucao")
    return props, updates, events, laws, cats, execucao


if __name__ == "__main__":
    import json
    import os

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    props, updates, events, laws, cats, execucao = carregar_datasets(
        os.path.join(base, "data", "legislation"))
    brief = build_brief(props, updates, events, laws, cats, execucao)
    print(json.dumps(brief["meta"], ensure_ascii=False, indent=2))
    print("mudanças críticas:", len(brief["mudancas_criticas"]))
    print("top matérias:", [b["fato_oficial"]["titulo"] for b in brief["top_materias"]])
    print("setores:", len(brief["setores"]))
    print("fontes oficiais:", len(brief["fontes_oficiais"]))
