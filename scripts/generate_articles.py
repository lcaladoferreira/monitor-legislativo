#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_articles.py — Camada editorial do Monitor Legislativo de IA.

Transforma mudanças JÁ DETECTADAS pelo monitoramento (updates.json, atos.json,
propositions.json…) em artigos públicos em /artigos/, seguindo regras editoriais
explícitas e auditáveis. Nada é inventado: toda afirmação factual do artigo vem
do dataset do monitor ou de fonte oficial já registrada nele.

PRINCÍPIOS
  · CRIAÇÃO e ATUALIZAÇÃO são ações editoriais DIFERENTES e independentes:
      - novo assunto com valor editorial próprio → NOVO artigo (máx. 1/dia);
      - continuação de assunto já coberto → ATUALIZAÇÃO do artigo existente
        (mesma URL, published_at preservado, modified_at novo, revision_count++);
      - alteração trivial/duplicada/aguardando curadoria → NO_EDITORIAL_ACTION.
  · Identidade de assunto estável (editorial_topic_id) derivada de IDs do
    dataset (proposição, ato), nunca de comparação frágil por texto.
  · Processamento IDEMPOTENTE: cada mudança é identificada por change_id
    estável (hash dos campos de identidade) e processada no máximo uma vez.
  · Máximo de 1 NOVO artigo por dia (a cota diária considera somente
    `new_article`; atualizações não consomem a cota e não têm limite arbitrário).
  · Tolerante a ausência de novidades: sem mudanças novas, nenhuma ação.

USO
    python3 scripts/generate_articles.py                 # modo normal (cron)
    python3 scripts/generate_articles.py --dry-run       # relata, não grava
    python3 scripts/generate_articles.py --bootstrap     # backfill histórico:
                                                         # ≤1 artigo novo por
                                                         # dia JÁ DETECTADO
Saída: exit 0 mesmo sem novidades ou com falha contida (--strict força exit 1).

A falha desta etapa NUNCA corrompe o dataset legislativo: este script só grava
em data/articles/ (articles.json e editorial_state.json).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data", "legislation")
ART_DIR = os.path.join(BASE, "data", "articles")
ARTICLES_FILE = "articles.json"
STATE_FILE = "editorial_state.json"

# ---------------------------------------------------------------- regras
MAX_NEW_PER_DAY = 1     # cota diária de ARTIGO NOVO (atualizações não contam)
STALE_DAYS = 30         # candidato adiado há mais dias que isso é ignorado
MIN_SCORE_NOVO_ASSUNTO = 75  # score (rubrica pública) que justifica artigo-sujeito
NEW_MIN_SCORE = 12      # score mínimo de mudança para virar NEW_ARTICLE_CANDIDATE
UPDATE_MIN_SCORE = 5    # score mínimo de mudança para atualizar artigo existente
MAX_REVISIONS_LOG = 200

ACTION_NEW = "new_article"
ACTION_UPDATE = "article_update"
ACTION_IGNORED = "ignored"
ACTIONS_VALID = (ACTION_NEW, ACTION_UPDATE, ACTION_IGNORED)

# Pesos por tipo de mudança (campo `tipo` de updates.json). Documentado para
# auditoria: pesos baixos = movimentação administrativa/tramitação.
TIPO_PESO = {
    "nova lei": 9, "sanção": 8, "veto": 8, "aprovação": 8,
    "nova decisão": 7, "decisão judicial": 7, "nova consulta pública": 7,
    "regulamentação": 7, "novo ato normativo": 7, "alteração normativa": 6,
    "parecer": 6, "nova portaria": 5, "nova proposição": 5, "publicação": 4,
    "relatoria": 4, "nova notícia oficial": 3, "novo programa": 3,
    "tramitação": 2, "apensação": 2, "arquivamento": 2,
    "atualização cadastral": 1, "alteração de texto": 2, "cronograma": 3,
    "fiscalização": 3,
}

# Bônus por palavras-chave no título/descrição da mudança (fatos fortes).
TITULO_BONUS = [
    (r"transforma[çc][ãa]o em norma|transformada em norma|convertida em lei", 8),
    (r"\baprovad", 6), (r"sancion|\bsanção\b|convertida em norm", 6),
    (r"\bveto|\bvetad", 6), (r"\bparecer\b", 5),
    (r"pauta|ordem do dia|votação", 5), (r"\brelator", 4),
    (r"apensad", 3), (r"consulta p[úu]blica", 4),
    (r"regulament|resolu[çc][ãa]o", 3), (r"deepfake", 2),
]

# Marcadores do coletor de que a mudança é registro mecânico de protocolo
# (eco de movimentação já refletida no estado da ficha) — sem valor editorial.
ECO_PROTOCOLO = re.compile(
    r"\(\s*registro incorporado\s*\)|\(\s*alinhamento de texto à ficha oficial\s*\)", re.I)
# Títulos que repetem o protocolo da própria proposição (apresentação,
# publicação, recebimento): nunca acrescentam conteúdo ao leitor.
TITULO_PROTOCOLO = re.compile(
    r"^(pl|plc|pec|pdl|pln|mpv|mp|req)\s*\d+\s*/\s*\d+\s*:\s*"
    r"(apresenta[çc][ãa]o de proposi[çc][ãa]o|publica[çc][ãa]o de proposi[çc][ãa]o|recebimento)\b",
    re.I)

# Ruído administrativo (títulos): nunca geram nem artigo nem atualização.
RUIDO_TITULO = re.compile(
    r"^\s*(extrato|resultado de (julgamento|chamamento|licita)|edital de (concurso|licita)"
    r"|aviso de (licita|altera)|preg[ãa]o|ata de (julgamento|sess[ãa]o)|credenciamento"
    r"|carta comercial|comunicado|retifica[çc][ãa]o|homologa[çc][ãa]o|concorr[êe]ncia"
    r"|termo aditivo|ordem de compra|convite|concorr[êe]ncia p[úu]blica)",
    re.I,
)

# Pesos para atos multiórgão (atos.json): tipo do ato × órgão de origem.
ATO_TIPO_PESO = {
    "lei": 9, "decreto": 8, "medida provisória": 8, "resolução": 8,
    "emenda constitucional": 8, "instrução normativa": 6, "portaria": 5,
    "consulta pública": 7, "nota técnica": 4, "ação": 2, "despacho": 2,
}
ATO_ORGAO_PESO = {"anpd": 8, "cnj": 7, "tse": 7, "planalto": 8, "mcti": 5,
                  "congresso": 8, "presidencia": 8}
# Hierarquias do DOU que indicam órgão dentro do escopo do monitor.
ESCOPO_HIERARQUIA = re.compile(
    r"anpd|prote[çc][ãa]o de dados|conselho nacional de justi[çc]a|tribunal superior eleitoral"
    r"|presid[êe]ncia da rep[úu]blica|congresso nacional|c[âa]mara dos deputados|senado federal"
    r"|ci[êe]ncia,? tecnologia|minist[ée]rio da ci[êe]ncia|mcti", re.I)


# ------------------------------------------------------------- utilidades
def _slug(texto, limite=70):
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:limite].rstrip("-")


def _date_only(s):
    """Extrai YYYY-MM-DD de datas/ISO; inválida → None."""
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(s))
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date().isoformat()
    except ValueError:
        return None


def hoje_brt():
    return datetime.now(timezone(timedelta(hours=-3))).date().isoformat()


def agora_iso():
    return datetime.now(timezone(timedelta(hours=-3))).isoformat(timespec="seconds")


def change_id(m):
    """ID estável e reprodutível de uma mudança do dataset.

    Nunca depende da ordem do JSON nem de timestamps variáveis: usa apenas os
    campos de identidade registrados pelo coletor.
    """
    partes = [
        str(m.get("id_execucao") or ""),
        str(m.get("timestamp_execucao") or ""),
        str(m.get("tipo") or ""),
        str(m.get("titulo") or ""),
        str(m.get("data") or ""),
        str(m.get("proposicao") or ""),
        str(m.get("item") or ""),
        str(m.get("url_oficial") or m.get("fonte_url") or ""),
        str(m.get("campo_alterado") or ""),
        str(m.get("valor_novo") or ""),
    ]
    bruto = "|".join(partes)
    return "chg_" + hashlib.sha1(bruto.encode("utf-8")).hexdigest()[:16]


def dia_editorial(m, fallback):
    """Dia editorial de uma mudança = quando o monitor a DETECTOU.

    Nunca usamos 'a data de hoje' como heurística: a detecção está registrada
    no dataset (data_deteccao). Datas absurdas (<2020) caem para o fallback.
    """
    for campo in ("data_deteccao", "timestamp_execucao", "data"):
        d = _date_only(m.get(campo))
        if d and d >= "2020-01-01":
            return d
    return fallback


def fmt_data(d):
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(d or "—")


def _trim(texto, n):
    t = re.sub(r"\s+", " ", str(texto or "")).strip()
    return t if len(t) <= n else t[:n - 1].rstrip(" ,;:.") + "…"


# ------------------------------------------------------------ persistência
def load_json(path, padrao):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def load_artigos(base_art=ART_DIR):
    dados = load_json(os.path.join(base_art, ARTICLES_FILE), None)
    if not isinstance(dados, dict) or not isinstance(dados.get("artigos"), list):
        return {"meta": {}, "artigos": []}
    return dados


def load_state(base_art=ART_DIR):
    dados = load_json(os.path.join(base_art, STATE_FILE), None)
    if not isinstance(dados, dict) or not isinstance(dados.get("processadas"), dict):
        dados = {"meta": {"descricao": "Estado editorial: cada mudança do monitor e "
                                       "a ação editorial tomada (auditoria)"},
                 "processadas": {}, "pendentes": {}, "execucoes": []}
    dados.setdefault("processadas", {})
    dados.setdefault("pendentes", {})
    dados.setdefault("execucoes", [])
    return dados


def save_artigos(artigos_f, base_art=ART_DIR):
    os.makedirs(base_art, exist_ok=True)
    artigos_f["meta"]["total"] = len(artigos_f["artigos"])
    artigos_f["meta"]["atualizado_em"] = hoje_brt()
    path = os.path.join(base_art, ARTICLES_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(artigos_f, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def save_state(state, base_art=ART_DIR):
    os.makedirs(base_art, exist_ok=True)
    state["meta"]["atualizado_em"] = hoje_brt()
    state["execucoes"] = state["execucoes"][-50:]
    path = os.path.join(base_art, STATE_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


# ------------------------------------------------------- índice editorial
class Contexto:
    """Dataset carregado + índices derivados (imutável durante a execução)."""

    def __init__(self, data_dir=DATA):
        self.data_dir = data_dir
        leg = lambda n: load_json(os.path.join(data_dir, n), {})
        props_f = leg("propositions.json")
        self.props = props_f.get("proposicoes", []) or []
        self.props_por_id = {p["id"]: p for p in self.props}
        self.atos_f = leg("atos.json")
        self.atos = self.atos_f.get("atos", []) or []
        self.atos_por_id = {a["id"]: a for a in self.atos}
        self.laws = (leg("laws.json").get("normas", []) or [])
        self.cats = {c.get("id"): c for c in
                     (leg("categories.json").get("categorias", []) or [])}
        self.parlamentares = (leg("parliamentarians.json").get("parlamentares", []) or [])
        self.updates = leg("updates.json")
        self.mudancas = self.updates.get("mudancas", []) or []
        self._principal_cache = {}

    def principal_de(self, p):
        """Proposição principal do assunto (apensadas compartilham o tópico)."""
        pid = p["id"]
        if pid in self._principal_cache:
            return self._principal_cache[pid]
        alvo = p
        visto = {pid}
        while True:
            alvo_id = None
            m = re.search(r"Apensad[oa] ao ([A-Z]{2,4})\s*(\d{1,5})/(\d{4})",
                          alvo.get("situacao") or "")
            if alvo.get("proposicao_principal"):
                alvo_id = alvo["proposicao_principal"]
            elif m:
                alvo_id = f"camara_{m.group(1).lower()}_{m.group(2)}_{m.group(3)}"
            if (not alvo_id or alvo_id in visto or alvo_id not in self.props_por_id
                    or alvo_id == alvo["id"]):
                break
            alvo = self.props_por_id[alvo_id]
            visto.add(alvo["id"])
        self._principal_cache[pid] = alvo
        return alvo


def prop_topic_id(p):
    """Identidade estável do assunto de uma proposição (ex. do enunciado:
    pl-2338-2023-marco-legal-ia). Derivada de campos curados do dataset."""
    base = f"{str(p.get('tipo', '')).lower()}-{p.get('numero')}-{p.get('ano')}"
    return f"{base}-{_slug(p.get('titulo', ''), 60)}"


def ato_topic_id(a):
    chave = _slug(a.get("titulo", ""), 60) or "ato"
    h = hashlib.sha1(str(a.get("id", "")).encode()).hexdigest()[:8]
    return f"ato-{a.get('orgao', 'orgao')}-{chave}-{h}"


def topico_da_mudanca(m, ctx):
    """Mapeia a mudança para (tipo_entidade, entidade, editorial_topic_id).

    Usa IDs oficiais/estáveis do dataset — nunca comparação frágil por texto.
    Apensadas são agregadas ao tópico da proposição principal (evita URLs
    canibalizadas por microevento).
    """
    pid = m.get("proposicao")
    if pid and pid in ctx.props_por_id:
        p = ctx.principal_de(ctx.props_por_id[pid])
        return ("prop", p, prop_topic_id(p))
    aid = m.get("item")
    if aid and aid in ctx.atos_por_id:
        a = ctx.atos_por_id[aid]
        return ("ato", a, ato_topic_id(a))
    return (None, None, None)


# ------------------------------------------------------- classificação
def _titulo_limpo(m):
    """Título da mudança sem os marcadores mecânicos do coletor.

    "(registro incorporado)"/"(alinhamento de texto à ficha oficial)" são
    anotações de captura — o fato descrito no título permanece válido.
    """
    t = ECO_PROTOCOLO.sub(" ", m.get("titulo") or "")
    return re.sub(r"\s+", " ", t).strip()


def _peso_titulo(m):
    texto = f"{_titulo_limpo(m)} {m.get('descricao') or ''}"
    bonus = 0
    for padrao, peso in TITULO_BONUS:
        if re.search(padrao, texto, re.I):
            bonus = max(bonus, peso)
    return bonus


def _ruidosa(m):
    titulo = m.get("titulo") or ""
    if RUIDO_TITULO.search(titulo):
        return True
    desc = (m.get("descricao") or "").lower()
    if "resultado de chamamento público" in desc and m.get("orgao") == "dou":
        return True
    return False


def _eco_protocolo(m):
    """Eco de protocolo puro (apresentação/publicação/recebimento) após remover
    os marcadores mecânicos: sem valor editorial para o leitor."""
    return bool(TITULO_PROTOCOLO.match(_titulo_limpo(m)))


def _peso_ato(a):
    tipo_ato = _slug(a.get("tipo_ato") or a.get("tipo") or "")
    peso_tipo = next((p for pad, p in ATO_TIPO_PESO.items()
                      if tipo_ato.startswith(_slug(pad))), 2)
    orgao = str(a.get("orgao") or "")
    peso_orgao = ATO_ORGAO_PESO.get(orgao, 0)
    if orgao == "dou":
        hier = f"{a.get('hierarquia') or ''} {a.get('fonte') or ''}"
        peso_orgao = 8 if ESCOPO_HIERARQUIA.search(hier) else 0
    return peso_tipo, peso_orgao


def classify_change(m, topico, artigo, ctx, cfg):
    """Classifica UMA mudança editorialmente.

    Retorna (acao, prioridade, motivo) com acao em:
      NEW_ARTICLE_CANDIDATE | ARTICLE_UPDATE_CANDIDATE | NO_EDITORIAL_ACTION.
    Regras explícitas, determinísticas e auditáveis (motivo sempre preenchido).
    """
    if m.get("revisao_pendente") or m.get("relevancia") == "revisar":
        return ("NO_EDITORIAL_ACTION", 0, "aguardando_curadoria")
    if not (m.get("titulo") or "").strip():
        return ("NO_EDITORIAL_ACTION", 0, "sem_titulo_informativo")
    if _ruidosa(m):
        return ("NO_EDITORIAL_ACTION", 0, "ruido_administrativo")
    if topico is None:
        return ("NO_EDITORIAL_ACTION", 0, "sem_entidade_vinculada_no_dataset")

    tipo_ent, ent, topic_id = topico
    if tipo_ent is None or ent is None:
        return ("NO_EDITORIAL_ACTION", 0, "sem_entidade_vinculada_no_dataset")
    if tipo_ent == "prop":
        score_prop = (ent.get("impacto") or {}).get("score") or 0
        # Para proposição RECÉM-descoberta ('nova proposição'), a importância do
        # assunto é o próprio fato: o score pesa mais forte na prioridade.
        peso_score = score_prop // 2 if m.get("tipo") == "nova proposição" \
            else score_prop // 20
        peso = TIPO_PESO.get(m.get("tipo") or "", 1) + _peso_titulo(m) + peso_score
        base_motivo = f"tipo={m.get('tipo')} peso={peso} score_prop={score_prop}"
    else:
        peso_tipo, peso_orgao = _peso_ato(ent)
        peso = peso_tipo + peso_orgao
        base_motivo = f"ato tipo={ent.get('tipo_ato') or ent.get('tipo')} órgão={ent.get('orgao')} peso={peso}"

    if _eco_protocolo(m):
        return ("NO_EDITORIAL_ACTION", 0,
                base_motivo + " → registro de protocolo sem valor editorial")

    if artigo is not None:
        if peso < UPDATE_MIN_SCORE:
            return ("NO_EDITORIAL_ACTION", 0,
                    base_motivo + " → abaixo do limiar de atualização")
        return ("ARTICLE_UPDATE_CANDIDATE", peso,
                base_motivo + " → continuação de assunto já coberto")

    # Sem artigo ainda: vale assunto novo?
    novo_por_tipo = TIPO_PESO.get(m.get("tipo") or "", 0) >= 5
    novo_por_titulo = _peso_titulo(m) >= 5
    novo_por_score = (topico[0] == "prop"
                      and ((ent.get("impacto") or {}).get("score") or 0)
                      >= cfg["min_score_novo_assunto"])
    if not (novo_por_tipo or novo_por_titulo or novo_por_score):
        return ("NO_EDITORIAL_ACTION", 0,
                base_motivo + " → sem valor editorial independente")
    if peso < cfg["new_min_score"]:
        return ("NO_EDITORIAL_ACTION", 0,
                base_motivo + " → abaixo do limiar de novo artigo")
    gatilho = ("score da proposição ≥ %d" % cfg["min_score_novo_assunto"]
               if novo_por_score and not (novo_por_tipo or novo_por_titulo)
               else "fato editorialmente autônomo")
    return ("NEW_ARTICLE_CANDIDATE", peso, base_motivo + f" → {gatilho}")


def find_existing_article(artigos, topic_id):
    """Artigo publicado para o tópico (ou None). Por identidade, não por texto."""
    for a in artigos["artigos"]:
        if a.get("editorial_topic_id") == topic_id and a.get("status") == "published":
            return a
    return None


def should_create_new_article(candidatos, artigos, cfg, dia):
    """Decisão de criação: existe candidato e a cota do dia está aberta.

    A cota diária considera SOMENTE artigos criados (new_article) no dia.
    """
    if not candidatos:
        return None, "nenhum candidato a artigo novo"
    usados = sum(1 for a in artigos["artigos"]
                 if (a.get("published_at") or "")[:10] == dia)
    if usados >= cfg["max_new_per_day"]:
        return None, f"cota diária de novos artigos atingida ({usados})"
    ordenados = sorted(candidatos, key=lambda c: (-c["prioridade"], c["cid"]))
    return ordenados[0], "maior relevância editorial do dia"


def should_update_article(artigo, m, decisao):
    """Atualização só quando passa os portões e acrescenta fato real."""
    if artigo is None or decisao != "ARTICLE_UPDATE_CANDIDATE":
        return False, "sem artigo correspondente ou mudança irrelevante"
    if m.get("revisao_pendente"):
        return False, "mudança aguardando curadoria"
    return True, "fato relevante que continua o assunto"


# ------------------------------------------------------ conteúdo do artigo
def _rotulo_orgao(orgao):
    return {"anpd": "ANPD", "cnj": "CNJ", "tse": "TSE", "dou": "DOU",
            "planalto": "Planalto/Presidência da República",
            "mcti": "MCTI (Ministério da Ciência, Tecnologia e Inovação)",
            "camara": "Câmara dos Deputados", "senado": "Senado Federal",
            }.get(orgao, (orgao or "órgão oficial").upper())


def _bulks_mudanca(m, ctx):
    """Balaústre factual de uma mudança (tudo vem do registro do monitor)."""
    partes = [f"<b>{fmt_data(m.get('data'))}</b> — {esc_html(_titulo_limpo(m))}"]
    if m.get("descricao"):
        partes.append(f"<br>{esc_html(_trim(m['descricao'], 320))}")
    extra = []
    if m.get("campo_alterado") and (m.get("valor_novo") or m.get("valor_anterior")):
        extra.append(f"{esc_html(m['campo_alterado'])}: "
                     f"“{esc_html(_trim(m.get('valor_anterior'), 120) or '—')}” → "
                     f"“{esc_html(_trim(m.get('valor_novo'), 120) or '—')}”")
    if m.get("orgao"):
        extra.append(esc_html(_rotulo_orgao(m["orgao"])))
    if extra:
        partes.append(f'<span class="article-changemeta">({" · ".join(extra)})</span>')
    if m.get("url_oficial"):
        partes.append(f'<br><a href="{esc_html(m["url_oficial"])}" target="_blank" '
                      f'rel="noopener">Fonte oficial ↗</a>')
    return "<p>" + "".join(partes) + "</p>"


def esc_html(t):
    return (str(t or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _conteudo_prop(p, mudancas, ctx, motivo):
    """Conteúdo estruturado de artigo sobre proposição — 100% do dataset."""
    imp = p.get("impacto") or {}
    relator = p.get("relator") or p.get("relator_camara")
    situacao = p.get("situacao") or ""
    gatilho = (f"O Monitor Legislativo de IA registrou: {_trim(_titulo_limpo(mudancas[0]), 180)}. "
               if mudancas else "")
    lead = (gatilho
            + f"Trata-se do {p.get('tipo')} {p.get('numero')}/{p.get('ano')} — "
            + f"{_trim(p.get('titulo'), 120)} ({_trim(p.get('ementa'), 200)}). "
            + f"Situação oficial registrada: {_trim(situacao, 160)}. "
            + f"Fonte: {esc_html(p.get('url_oficial') or '')}.")
    situacao_atual = [f"<p><b>Situação oficial:</b> {esc_html(situacao or '—')}</p>"]
    if p.get("casa_atual"):
        situacao_atual.append(f"<p><b>Localização:</b> {esc_html(p['casa_atual'])}</p>")
    if p.get("comissao_atual"):
        situacao_atual.append(f"<p><b>Comissão:</b> {esc_html(p['comissao_atual'])}</p>")
    if relator:
        rel = f"{esc_html(relator.get('nome'))}"
        if relator.get("partido"):
            rel += f" ({esc_html(relator['partido'])}-{esc_html(relator.get('estado') or '—')})"
        situacao_atual.append(f"<p><b>Relator(a):</b> {rel}</p>")
    por_que = []
    if imp.get("score") is not None:
        por_que.append(
            f"<p>A proposição tem <b>AI Legislative Impact Score {imp.get('score')}/100</b> "
            f"({esc_html(imp.get('classificacao', ''))}) no monitoramento — rúbrica pública "
            f"que avalia abrangência regulatória, estágio de tramitação, impactos econômico e "
            f"sobre direitos e proximidade de decisão (critérios na "
            f'<a href="{{SITE_URL}}/metodologia/">metodologia</a>).</p>')
    if p.get("obrigacoes_criadas"):
        por_que.append(f"<p><b>Obrigações previstas no texto:</b> {esc_html(p['obrigacoes_criadas'])}</p>")
    if p.get("proibicoes"):
        por_que.append(f"<p><b>Proibições previstas:</b> {esc_html(p['proibicoes'])}</p>")
    cats_nome = [ctx.cats[c]["nome"] for c in p.get("categorias", []) if c in ctx.cats]
    if cats_nome:
        por_que.append(f"<p><b>Temas:</b> {esc_html(', '.join(cats_nome))}.</p>")
    agora = []
    if p.get("proxima_etapa"):
        agora.append(f"<p>Etapa seguinte registrada na ficha oficial: {esc_html(p['proxima_etapa'])}.</p>")
    if situacao:
        agora.append(f"<p>Enquanto a situação formal não mudar, a matéria segue "
                     f"“{esc_html(_trim(situacao, 140))}”. Este artigo é atualizado "
                     f"automaticamente quando o monitor detecta nova movimentação relevante "
                     f"deste assunto.</p>")
    historico = [{"data": t.get("data"), "evento": t.get("evento"), "fonte": t.get("fonte")}
                 for t in (p.get("timeline") or []) if t.get("evento")]
    quem = []
    if p.get("obrigacoes_criadas") or cats_nome:
        pedacos = [f"públicos e organizações atingidos pelos temas "
                    f"{esc_html(', '.join(cats_nome))}"]
        if p.get("obrigacoes_criadas"):
            pedacos.append("as obrigações listadas acima, quando o texto entrar em vigor")
        quem.append("<p>Este assunto interessa, no que consta do material monitorado, a: "
                    + "; ".join(pedacos) + ".</p>")
    return {
        "lead": lead,
        "o_que_mudou": [_bulks_mudanca(m, ctx) for m in mudancas],
        "situacao_atual": "".join(situacao_atual),
        "por_que_importa": "".join(por_que) or None,
        "o_que_acontece_agora": "".join(agora) or None,
        "historico": historico,
        "quem_atinge": "".join(quem) or None,
    }


def _conteudo_ato(a, mudancas, ctx, motivo):
    """Conteúdo de artigo sobre ato multiórgão — 100% do dataset."""
    orgao = _rotulo_orgao(a.get("orgao"))
    lead = (f"Foi registrada publicação/ato no {esc_html(orgao)}: "
            f"{esc_html(_trim(a.get('titulo'), 200))}. "
            + (f"Detalhe oficial: {_trim(a.get('descricao'), 260)}. " if a.get("descricao") else "")
            + f"Detectado pelo monitoramento em {fmt_data(mudancas[0].get('data_deteccao') or mudancas[0].get('data'))}.")
    situacao = [f"<p><b>Órgão:</b> {esc_html(orgao)}</p>"]
    if a.get("tipo_ato"):
        situacao.append(f"<p><b>Natureza do ato:</b> {esc_html(a['tipo_ato'])}</p>")
    if a.get("hierarquia"):
        situacao.append(f"<p><b>Unidade emissora:</b> {esc_html(a['hierarquia'])}</p>")
    situacao.append(f"<p><b>Canal oficial:</b> {esc_html(a.get('fonte') or '—')}</p>")
    por_que = [
        f"<p>O ato entrou no radar do monitor por ter sido publicado em fonte oficial "
        f"acompanhada no tema inteligência artificial, proteção de dados e infraestrutura "
        f"digital ({esc_html(a.get('fonte') or '')}). O acompanhamento é factual: este artigo "
        f"não antecipa efeitos jurídicos nem interpreta o mérito do ato.</p>"]
    if a.get("situacao"):
        por_que.append(f"<p><b>Situação registrada:</b> {esc_html(a['situacao'])}</p>")
    agora = [f"<p>O texto oficial está disponível na fonte citada. Este artigo é atualizado "
             f"quando o monitor detecta alteração relevante do mesmo ato "
             f"(por exemplo, nova versão do texto registrado por hash).</p>"]
    return {
        "lead": lead,
        "o_que_mudou": [_bulks_mudanca(m, ctx) for m in mudancas],
        "situacao_atual": "".join(situacao),
        "por_que_importa": "".join(por_que),
        "o_que_acontece_agora": "".join(agora),
        "historico": [],
        "quem_atinge": None,
    }


# ------------------------------------------------------- criar / atualizar
def _parlamentares_relacionados(ctx, p):
    saida = []
    for par in ctx.parlamentares:
        if p["id"] in (par.get("proposicoes_relacionadas") or []):
            saida.append(par.get("nome"))
        elif (p.get("relator") or {}).get("nome") == par.get("nome"):
            saida.append(par.get("nome"))
    return [n for n in saida if n]


def _slug_unico(base, artigos_f):
    usados = {a.get("slug") for a in artigos_f["artigos"]}
    slug, i = base, 2
    while slug in usados:
        slug, i = f"{base}-{i}", i + 1
    return slug


def create_article(topico, mudancas_topico, ctx, artigos_f, cfg, dia,
                   decisao, change_ids, motivo=""):
    """Cria um NOVO artigo (uma URL nova, justificada e registrada)."""
    tipo_ent, ent, topic_id = topico
    if tipo_ent == "prop":
        p = ent
        titulo = f"{p.get('titulo')} — {p.get('tipo')} {p.get('numero')}/{p.get('ano')}"
        desc = _trim(p.get("ementa") or p.get("titulo"), 180)
        assunto = f"{p.get('tipo')} {p.get('numero')}/{p.get('ano')}"
        conteudo = _conteudo_prop(p, mudancas_topico, ctx, decisao)
        official_sources = []
        if p.get("url_oficial"):
            official_sources.append({"titulo": f"Ficha de tramitação — {p.get('tipo')} {p.get('numero')}/{p.get('ano')}",
                                     "url": p["url_oficial"], "orgao": str(p.get("casa_origem") or "")})
        for m in mudancas_topico:
            u = m.get("url_oficial")
            if u and all(s["url"] != u for s in official_sources):
                official_sources.append({"titulo": _trim(m.get("titulo"), 90),
                                         "url": u, "orgao": _rotulo_orgao(m.get("orgao"))})
        relacionadas = sorted({p["id"]} | {q["id"] for q in [ctx.principal_de(p)] if q["id"] != p["id"]})
        related = {
            "related_propositions": relacionadas,
            "related_acts": [], "related_laws": [],
            "related_organs": sorted({str(p.get("casa_origem") or "")} -
                                     {""}),
            "related_parliamentarians": _parlamentares_relacionados(ctx, p),
        }
        cats = [ctx.cats[c]["nome"] for c in p.get("categorias", []) if c in ctx.cats]
        keywords = [assunto, p.get("titulo") or "", "regulação de IA",
                    "Congresso Nacional"] + cats
    else:
        a = ent
        titulo = _trim(a.get("titulo"), 120)
        desc = _trim(a.get("descricao") or a.get("titulo"), 180)
        assunto = _rotulo_orgao(a.get("orgao"))
        conteudo = _conteudo_ato(a, mudancas_topico, ctx, decisao)
        official_sources = [{"titulo": _trim(a.get("titulo"), 90),
                             "url": a.get("url_oficial"), "orgao": assunto}]
        related = {"related_propositions": [], "related_laws": [],
                   "related_acts": [a["id"]],
                   "related_organs": [a.get("orgao") or ""],
                   "related_parliamentarians": []}
        cats = []
        keywords = [titulo, assunto, "regulação de IA", "ato oficial"]

    slug = _slug_unico(_slug(titulo, 80), artigos_f)
    selection_reason = (f"{decisao} | gatilho: {_trim(_titulo_limpo(mudancas_topico[0]), 120)} | "
                        f"critério: {motivo}")
    artigo = {
        "id": f"art-{slug[:60]}",
        "editorial_topic_id": topic_id,
        "slug": slug,
        "title": titulo,
        "description": desc,
        "summary": _trim(conteudo["lead"], 320),
        "assunto": assunto,
        "published_at": dia,
        "modified_at": dia,
        "source_change_ids": list(change_ids),
        "source_entity_ids": [ent["id"]],
        **related,
        "categories": cats[:4],
        "keywords": [k for k in keywords if k][:10],
        "official_sources": official_sources,
        "url": f"artigos/{slug}/",
        "status": "published",
        "selection_reason": selection_reason,
        "revision_count": 1,
        "last_revision_reason": "Criação do artigo a partir de mudança detectada pelo monitor.",
        "content": conteudo,
        "revisions": [{
            "date": dia,
            "source_change_ids": list(change_ids),
            "reason": selection_reason,
            "fields_changed": ["*"],
            "summary": _trim(conteudo["lead"], 240),
        }],
    }
    artigo["editorial_hash"] = _hash_artigo(artigo)
    artigos_f["artigos"].append(artigo)
    artigos_f["artigos"].sort(key=lambda a: (a.get("published_at") or "", a.get("id")), reverse=True)
    return artigo


def _hash_artigo(a):
    """Hash do conteúdo efetivo do artigo (publicação/edição detectável)."""
    bruto = json.dumps({
        "title": a.get("title"), "description": a.get("description"),
        "content": a.get("content"), "sources": a.get("official_sources"),
        "related": [a.get("related_propositions"), a.get("related_acts"),
                    a.get("related_laws"), a.get("related_organs"),
                    a.get("related_parliamentarians")],
    }, ensure_ascii=False, sort_keys=True)
    return "sha1:" + hashlib.sha1(bruto.encode("utf-8")).hexdigest()[:16]


def update_article(artigo, topico, mudanca, ctx, cfg, dia, motivo):
    """ATUALIZA artigo existente: mesma URL, published_at preservado."""
    _, ent, topic_id = topico
    tipo_ent = "prop" if topic_id in {p and prop_topic_id(p) for p in [ent]} else "ato"
    fields_changed = []
    # 1) Incorpora o fato em "O que mudou" (cronologia preservada: mais recente primeiro)
    conteudo = dict(artigo.get("content") or {})
    bullets = list(conteudo.get("o_que_mudou") or [])
    bullets.insert(0, _bulks_mudanca(mudanca, ctx))
    bullets = bullets[:60]
    conteudo["o_que_mudou"] = bullets
    fields_changed.append("content.o_que_mudou")

    # 2) Atualiza snapshots de situação a partir do estado ATUAL do dataset
    if ent is not None:
        if isinstance(ent, dict) and "situacao" in ent and ent.get("ementa"):
            novo = _conteudo_prop(ent, [], ctx, "atualização")
            for campo in ("situacao_atual", "por_que_importa", "o_que_acontece_agora"):
                if novo.get(campo) and novo[campo] != conteudo.get(campo):
                    conteudo[campo] = novo[campo]
                    fields_changed.append(f"content.{campo}")
            tl = novo.get("historico") or []
            if tl and tl != conteudo.get("historico"):
                conteudo["historico"] = tl
                fields_changed.append("content.historico")
            # entidades relacionadas podem ter mudado (ex. novo relator)
            rel_atual = {
                "related_parliamentarians": _parlamentares_relacionados(ctx, ent),
            }
            if rel_atual["related_parliamentarians"] != artigo.get("related_parliamentarians"):
                artigo["related_parliamentarians"] = rel_atual["related_parliamentarians"]
                fields_changed.append("related_parliamentarians")
            if (ent.get("url_oficial")
                    and all(s.get("url") != ent["url_oficial"] for s in artigo.get("official_sources", []))):
                artigo["official_sources"].append({
                    "titulo": f"Ficha de tramitação — {ent.get('tipo')} {ent.get('numero')}/{ent.get('ano')}",
                    "url": ent["url_oficial"], "orgao": str(ent.get("casa_origem") or "")})
                fields_changed.append("official_sources")
        else:
            novo = _conteudo_ato(ent, [], ctx, "atualização")
            if novo["situacao_atual"] != conteudo.get("situacao_atual"):
                conteudo["situacao_atual"] = novo["situacao_atual"]
                fields_changed.append("content.situacao_atual")

    artigo["content"] = conteudo
    novo_hash = _hash_artigo(artigo)
    mudou = novo_hash != artigo.get("editorial_hash")
    artigo["source_change_ids"] = list(dict.fromkeys(
        list(artigo.get("source_change_ids") or []) + [change_id(mudanca)]))
    if mudou:
        artigo["editorial_hash"] = novo_hash
        artigo["modified_at"] = dia
        revisions = list(artigo.get("revisions") or [])
        cid = change_id(mudanca)
        gatilho = _titulo_limpo(mudanca)
        # Coalescência: movimentações do MESMO assunto no MESMO dia viram UMA
        # revisão (evita spam de revisões idênticas no histórico público).
        if revisions and revisions[-1].get("date") == dia and \
                "source_change_ids" in revisions[-1]:
            last = revisions[-1]
            last["source_change_ids"] = sorted(set(last.get("source_change_ids") or []) | {cid})
            last["fields_changed"] = sorted(set(last.get("fields_changed") or []) | set(fields_changed))
            last["change_count"] = int(last.get("change_count") or 1) + 1
            n = last["change_count"]
            last["summary"] = _trim(gatilho, 160) + (f" (+{n - 1} movimentação(ões) do mesmo dia)" if n > 1 else "")
            last["reason"] = _trim(motivo, 240)
            artigo["last_revision_reason"] = _trim(f"{motivo} | {n} mudança(s) incorporada(s) no dia", 240)
        else:
            artigo["revision_count"] = int(artigo.get("revision_count") or 0) + 1
            artigo["last_revision_reason"] = _trim(f"{motivo} | gatilho: {gatilho}", 240)
            revisions.append({
                "date": dia,
                "source_change_ids": [cid],
                "reason": _trim(motivo, 240),
                "fields_changed": fields_changed,
                "summary": _trim(gatilho, 200),
                "change_count": 1,
            })
        artigo["revisions"] = revisions[-MAX_REVISIONS_LOG:]
    return artigo, mudou, fields_changed


# ------------------------------------------------------------ processamento
def mudancas_do_topico(topico, mudancas, ctx, dia_max=None):
    """Todas as mudanças (opcionalmente até um dia editorial) do tópico."""
    _, ent, topic_id = topico
    saida = []
    for m in mudancas:
        t = topico_da_mudanca(m, ctx)
        if t[2] != topic_id:
            continue
        if dia_max and dia_editorial(m, dia_max) > dia_max:
            continue  # fato de dia posterior entra como atualização futura
        saida.append(m)
    # cronologia: evento mais recente primeiro (leitura editorial)
    return sorted(saida, key=lambda m: (m.get("data") or "", change_id(m)), reverse=True)


def run_editorial(cfg=None, logger=None):
    """Pipeline editorial completo. Retorna resumo (dict) — nunca lança."""
    log = logger or print
    cfg = {**_cfg_padrao(), **(cfg or {})}
    resumo = {
        "executado_em": agora_iso(), "dia_editorial": None,
        "mudancas_totais": 0, "mudancas_novas": 0,
        "novos_artigos": 0, "artigos_atualizados": 0, "ignoradas": 0,
        "adiadas": 0, "aguardando_curadoria": 0, "stale_ignoradas": 0,
        "acoes": [], "erro": None, "bootstrap": bool(cfg.get("bootstrap")),
    }
    try:
        ctx = Contexto(cfg["data_dir"])
        artigos_f = load_artigos(cfg["art_dir"])
        state = load_state(cfg["art_dir"])
        hoje = hoje_brt()
        resumo["dia_editorial"] = hoje
        resumo["mudancas_totais"] = len(ctx.mudancas)

        # 1) mudanças ainda não processadas
        novas = []
        for m in ctx.mudancas:
            cid = change_id(m)
            if cid in state["processadas"]:
                continue
            if (m.get("revisao_pendente") or m.get("relevancia") == "revisar"):
                resumo["aguardando_curadoria"] += 1
                continue  # fica pendente de curadoria — sem ação editorial
            novas.append((cid, m))
        resumo["mudancas_novas"] = len(novas)

        # 2) varredura stale de candidatos adiados em execuções anteriores
        for cid, pend in list(state["pendentes"].items()):
            since = _date_only(pend.get("since")) or hoje
            if (datetime.fromisoformat(hoje) - datetime.fromisoformat(since)).days > cfg["stale_days"]:
                state["processadas"][cid] = {
                    "change_id": cid, "processed": True,
                    "editorial_action": ACTION_IGNORED,
                    "article_id": None, "editorial_topic_id": pend.get("editorial_topic_id"),
                    "selection_reason": f"stale: candidato adiado há mais de {cfg['stale_days']} dias sem artigo",
                    "processed_at": agora_iso(), "run_id": cfg.get("run_id"),
                }
                del state["pendentes"][cid]
                resumo["stale_ignoradas"] += 1

        # 3) agrupamento por dia editorial (bootstrap percorre os dias passados;
        #    modo normal só tem o dia corrente — a data NUNCA é presumida: vem
        #    de data_deteccao registrada pelo coletor)
        por_dia = {}
        for cid, m in novas:
            d = dia_editorial(m, hoje)
            if not cfg["bootstrap"]:
                d = hoje
            if d > hoje:
                d = hoje  # nenhuma data futura
            por_dia.setdefault(d, []).append((cid, m))

        for dia in sorted(por_dia):
            grupo = por_dia[dia]
            # 3a) classificação contra o estado ATUAL dos artigos
            decisoes = []
            for cid, m in grupo:
                topico = topico_da_mudanca(m, ctx)
                artigo = find_existing_article(artigos_f, topico[2]) if topico[2] else None
                acao, prio, motivo = classify_change(m, topico, artigo, ctx, cfg)
                decisoes.append({"cid": cid, "m": m, "topico": topico,
                                 "artigo": artigo, "acao": acao,
                                 "prioridade": prio, "motivo": motivo})
            # 3b) atualizações primeiro (não consomem cota)
            for d in [x for x in decisoes if x["acao"] == "ARTICLE_UPDATE_CANDIDATE"]:
                mudou, campos = _aplicar_update(d, ctx, artigos_f, cfg, dia)
                if mudou:
                    resumo["artigos_atualizados"] += 1
                else:
                    resumo["ignoradas"] += 1
                _registrar(state, d, d["artigo"] if mudou else d["artigo"],
                           ACTION_UPDATE if mudou else ACTION_IGNORED,
                           motivo=d["motivo"], cfg=cfg,
                           extra="" if mudou else "conteúdo inalterado")
                if mudou:
                    resumo["acoes"].append({"change_id": d["cid"], "acao": ACTION_UPDATE,
                                            "article_id": d["artigo"]["id"],
                                            "topic": d["topico"][2]})
            # 3c) candidatos a artigo novo: apenas o de maior relevância do dia
            cands = [x for x in decisoes if x["acao"] == "NEW_ARTICLE_CANDIDATE"
                     and x["cid"] not in state["processadas"]]
            vencedor, motivo_sel = should_create_new_article(
                cands, artigos_f, cfg, dia) if cands else (None, "sem candidatos")
            if vencedor:
                topico = vencedor["topico"]
                # Só fatos até o dia editorial: o que vier depois entra como
                # ATUALIZAÇÃO futura (nunca antecipado na criação).
                do_topico = mudancas_do_topico(topico, [m for _, m in novas], ctx,
                                               dia_max=dia)
                cids = sorted({change_id(m) for m in do_topico})
                artigo = create_article(topico, do_topico, ctx, artigos_f, cfg,
                                        dia, "NEW_ARTICLE_CANDIDATE", cids,
                                        motivo=motivo_sel)
                resumo["novos_artigos"] += 1
                _registrar(state, vencedor, artigo, ACTION_NEW, motivo=motivo_sel,
                           cfg=cfg, extra=f"seleção: {motivo_sel}")
                # Registra TODAS as mudanças incorporadas na criação — nenhum
                # fato pode reaparecer depois como atualização (idempotência).
                for m_inc in do_topico:
                    cid_inc = change_id(m_inc)
                    if cid_inc == vencedor["cid"] or cid_inc in state["processadas"]:
                        continue
                    _registrar(state, {"cid": cid_inc, "topico": topico}, artigo,
                               ACTION_NEW, motivo="incorporado na criação do artigo",
                               cfg=cfg)
                resumo["acoes"].append({"change_id": vencedor["cid"], "acao": ACTION_NEW,
                                        "article_id": artigo["id"],
                                        "topic": topico[2]})
                log(f"  [+artigo] {artigo['title'][:70]} ({artigo['url']}) — {motivo_sel}")
                # 3d) candidatos do MESMO dia que agora pertencem ao artigo criado
                #     viram atualização (não é nova URL, não consome cota)
                for x in cands:
                    if x is vencedor or x["cid"] in state["processadas"]:
                        continue
                    if x["topico"][2] == topico[2]:
                        acao, prio, motivo2 = classify_change(
                            x["m"], x["topico"], artigo, ctx, cfg)
                        if acao == "ARTICLE_UPDATE_CANDIDATE":
                            x.update({"acao": acao, "artigo": artigo,
                                      "motivo": motivo2 + " (reclassificado após criação)"})
                            mudou, _ = _aplicar_update(x, ctx, artigos_f, cfg, dia)
                            if mudou:
                                resumo["artigos_atualizados"] += 1
                            else:
                                resumo["ignoradas"] += 1
                            _registrar(state, x, artigo,
                                       ACTION_UPDATE if mudou else ACTION_IGNORED,
                                       motivo=x["motivo"], cfg=cfg,
                                       extra="" if mudou else "conteúdo inalterado")
                            resumo["acoes"].append({
                                "change_id": x["cid"],
                                "acao": ACTION_UPDATE if mudou else ACTION_IGNORED,
                                "article_id": artigo["id"], "topic": topico[2]})
            # 3e) demais candidatos: adiados (ficam para outro dia, sem estourar
            #     cota). Quem JÁ estava pendente permanece intocado — execuções
            #     repetidas no mesmo dia não reescrevem o estado (sem commit vazio).
            for x in cands:
                if x["cid"] in state["processadas"]:
                    continue
                pend_anterior = state["pendentes"].get(x["cid"])
                if pend_anterior is not None:
                    continue  # já adiado anteriormente: nada a fazer nesta execução
                state["pendentes"][x["cid"]] = {
                    "reason": "cota_diaria_atingida" if vencedor else "sem_cota_no_dia",
                    "since": hoje,
                    "editorial_topic_id": x["topico"][2],
                    "prioridade": x["prioridade"],
                }
                resumo["adiadas"] += 1
            # 3f) sem ação editorial: registrado como ignorado (auditoria)
            for x in [y for y in decisoes
                      if y["acao"] == "NO_EDITORIAL_ACTION" and y["cid"] not in state["processadas"]]:
                _registrar(state, x, None, ACTION_IGNORED, motivo=x["motivo"], cfg=cfg)
                resumo["ignoradas"] += 1

        # Persistência somente com ação efetiva: execuções sem nenhuma novidade
        # não reescrevem os arquivos (sem commit vazio, saída byte-estável).
        houve_acao = bool(resumo["novos_artigos"] or resumo["artigos_atualizados"]
                          or resumo["ignoradas"] or resumo["adiadas"]
                          or resumo["stale_ignoradas"])
        if not cfg["dry_run"]:
            if houve_acao or not os.path.isdir(cfg["art_dir"]):
                save_artigos(artigos_f, cfg["art_dir"])
                state["execucoes"].append({
                    "executado_em": resumo["executado_em"], "dia": hoje,
                    "mudancas_novas": resumo["mudancas_novas"],
                    "novos_artigos": resumo["novos_artigos"],
                    "artigos_atualizados": resumo["artigos_atualizados"],
                    "ignoradas": resumo["ignoradas"], "adiadas": resumo["adiadas"],
                    "stale": resumo["stale_ignoradas"],
                    "aguardando_curadoria": resumo["aguardando_curadoria"],
                    "run_id": cfg.get("run_id"), "bootstrap": resumo["bootstrap"],
                })
                save_state(state, cfg["art_dir"])
            else:
                log("Editorial: nada novo desde a execução anterior — nada gravado.")
        else:
            log("DRY-RUN: nada foi gravado.")
        log(f"Editorial: {resumo['mudancas_novas']} mudança(s) nova(s) → "
            f"{resumo['novos_artigos']} novo(s) artigo(s), "
            f"{resumo['artigos_atualizados']} atualização(ões), "
            f"{resumo['ignoradas']} ignorada(s), {resumo['adiadas']} adiada(s).")
        return resumo
    except Exception as e:  # noqa: BLE001 — falha editorial nunca derruba o dataset
        import traceback
        resumo["erro"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()
        log(f"[erro editorial] {resumo['erro']}")
        return resumo


def _aplicar_update(d, ctx, artigos_f, cfg, dia):
    artigo, mudou, _ = update_article(
        d["artigo"], d["topico"], d["m"], ctx, cfg, dia, d["motivo"])
    return mudou, []


def _registrar(state, d, artigo, acao, motivo, cfg, extra=""):
    topico = d.get("topico") or (None, None, None)
    if acao not in ACTIONS_VALID:
        acao = ACTION_IGNORED
    state["processadas"][d["cid"]] = {
        "change_id": d["cid"],
        "processed": True,
        "editorial_action": acao,
        "article_id": (artigo or {}).get("id"),
        "editorial_topic_id": topico[2],
        "selection_reason": _trim(f"{motivo}{(' | ' + extra) if extra else ''}", 300),
        "processed_at": agora_iso(),
        "run_id": cfg.get("run_id"),
    }
    state["pendentes"].pop(d["cid"], None)


def _cfg_padrao():
    env = os.environ.get
    return {
        "data_dir": DATA,
        "art_dir": ART_DIR,
        "max_new_per_day": int(env("MONITOR_ARTIGOS_MAX_NOVOS_DIA", MAX_NEW_PER_DAY)),
        "stale_days": int(env("MONITOR_ARTIGOS_STALE_DIAS", STALE_DAYS)),
        "min_score_novo_assunto": MIN_SCORE_NOVO_ASSUNTO,
        "new_min_score": NEW_MIN_SCORE,
        "dry_run": False,
        "bootstrap": False,
        "run_id": None,
    }


# ------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="Camada editorial do Monitor Legislativo de IA.")
    ap.add_argument("--dry-run", action="store_true", help="relata sem gravar")
    ap.add_argument("--bootstrap", action="store_true",
                    help="backfill histórico: ≤1 artigo novo por dia já detectado no dataset")
    ap.add_argument("--max-new-per-day", type=int, default=None,
                    help=f"override da cota diária de novos artigos (padrão {MAX_NEW_PER_DAY})")
    ap.add_argument("--stale-days", type=int, default=None,
                    help=f"dias até candidato adiado virar ignorado (padrão {STALE_DAYS})")
    ap.add_argument("--run-id", default=None, help="id da execução (auditoria)")
    ap.add_argument("--legislation-dir", default=DATA)
    ap.add_argument("--articles-dir", default=ART_DIR)
    ap.add_argument("--strict", action="store_true",
                    help="retorna exit 1 se a execução editorial falhar")
    args = ap.parse_args(argv)

    cfg = _cfg_padrao()
    cfg.update({"data_dir": args.legislation_dir, "art_dir": args.articles_dir,
                "dry_run": args.dry_run, "bootstrap": args.bootstrap,
                "run_id": args.run_id})
    if args.max_new_per_day is not None:
        cfg["max_new_per_day"] = max(0, args.max_new_per_day)
    if args.stale_days is not None:
        cfg["stale_days"] = max(1, args.stale_days)
    print(f"Camada editorial: {'BOOTSTRAP' if args.bootstrap else 'modo normal'} · "
          f"cota {cfg['max_new_per_day']} novo(s)/dia · dataset {cfg['data_dir']}")
    resumo = run_editorial(cfg)
    if resumo.get("erro") and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
