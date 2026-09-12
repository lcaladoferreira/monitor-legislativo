#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_alert_email.py — Alertas por e-mail + Executive Regulatory Brief automatizável.

Gera, a partir do MESMO dataset do site (data/legislation), a saída de alerta ou
o relatório executivo semanal em HTML (estilos inline, pronto para e-mail),
texto simples e JSON (payload para canais futuros).

Canais
------
  e-mail     → implementado (envio SMTP opcional via variáveis de ambiente)
  webhook    → payload JSON pronto (basta POSTar o arquivo .json)
  WhatsApp / Telegram / Slack / Teams → arquitetura declarada em CANAIS com o
               campo `implementado: False`; o formato de mensagem já é gerado
               (texto curto + link), faltando apenas o conector de envio.

Seleção (item 8 do briefing comercial)
--------------------------------------
  temas         → categorias (id ou slug)
  proposições   → ids explícitos (sempre entram, ignorando score mínimo)
  órgãos        → filtro textual sobre orgaos_responsaveis / casa / comissão
  score mínimo  → 0, 60 ou 80
  frequência    → imediato | diario | semanal (muda a janela de mudanças)

Nenhum dado é inventado: tipos de alerta sem cobertura no dataset atual são
declarados como indisponíveis (ver TIPOS_ALERTA).

Uso
---
  python3 scripts/build_alert_email.py                      # semanal, score 0
  python3 scripts/build_alert_email.py --modelo alerta --score-minimo 80 --frequencia imediato
  python3 scripts/build_alert_email.py --modelo brief --temas infraestrutura-de-ia,protecao-de-dados
  python3 scripts/build_alert_email.py --destinatarios a@x.com,b@y.com --send
  python3 scripts/build_alert_email.py --out-dir build/alertas --json-only

Saída padrão: build/alertas/ (não versionado).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brief as _brief  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data", "legislation")
SITE_URL = "https://monitor.lcfconsulting.com.br"

# ---------------------------------------------------------------------------
# Catálogo de tipos de alerta (item 8) — o que o dataset atual sustenta
# ---------------------------------------------------------------------------
TIPOS_ALERTA = [
    {"id": "mudanca_legislativa", "rotulo": "Mudança legislativa",
     "tipos_dataset": ["tramitação", "apensação", "parecer", "atualização cadastral"],
     "implementado": True},
    {"id": "novo_projeto", "rotulo": "Novo projeto",
     "tipos_dataset": ["nova proposição"], "implementado": True},
    {"id": "votacao", "rotulo": "Votação",
     "tipos_dataset": ["aprovação", "sanção"], "implementado": True},
    {"id": "inclusao_pauta", "rotulo": "Inclusão em pauta",
     "tipos_dataset": ["cronograma"], "implementado": True,
     "nota": "Detectado também por situação oficial com 'pauta'/'ordem do dia'."},
    {"id": "alteracao_relatoria", "rotulo": "Alteração de relatoria",
     "tipos_dataset": ["relatoria"], "implementado": True},
    {"id": "nova_norma", "rotulo": "Nova norma",
     "tipos_dataset": ["publicação"], "implementado": True,
     "nota": "Normas vigentes também são lidas de laws.json."},
    {"id": "evento", "rotulo": "Evento (audiência, reunião, marco)",
     "tipos_dataset": [], "implementado": True,
     "nota": "Vem de events.json, não de updates.json."},
    {"id": "alteracao_score", "rotulo": "Alteração relevante de score",
     "tipos_dataset": [], "implementado": False,
     "nota": "Requer histórico versionado de score por execução (P1): o dataset "
             "atual guarda o score corrente, não a série temporal."},
]

CANAIS = [
    {"id": "email", "rotulo": "E-mail", "implementado": True,
     "saida": "HTML inline + texto simples", "envio": "SMTP (variáveis MONITOR_SMTP_*)"},
    {"id": "webhook", "rotulo": "Webhook / API", "implementado": True,
     "saida": "JSON", "envio": "POST pelo consumidor (ou --webhook-url)"},
    {"id": "whatsapp", "rotulo": "WhatsApp", "implementado": False,
     "saida": "texto curto + link", "envio": "conector a definir (Cloud API)"},
    {"id": "telegram", "rotulo": "Telegram", "implementado": False,
     "saida": "texto curto + link", "envio": "conector a definir (Bot API)"},
    {"id": "slack", "rotulo": "Slack", "implementado": False,
     "saida": "blocks JSON", "envio": "conector a definir (incoming webhook)"},
    {"id": "teams", "rotulo": "Microsoft Teams", "implementado": False,
     "saida": "message card", "envio": "conector a definir (workflows)"},
]

FREQUENCIA_JANELA = {"imediato": 1, "diario": 1, "semanal": 7}

PERFIL_PADRAO = {
    "id": "radar-executivo-semanal",
    "nome": "Radar Executivo — semanal",
    "frequencia": "semanal",
    "score_minimo": 0,
    "temas": [],          # slugs ou ids de categoria; vazio = todos
    "orgaos": [],         # texto livre; vazio = todos
    "proposicoes": [],    # ids fixos que sempre entram
    "tipos": [t["id"] for t in TIPOS_ALERTA if t["implementado"]],
    "canais": ["email", "webhook"],
}


# ---------------------------------------------------------------------------
# Seleção
# ---------------------------------------------------------------------------

def _tipos_permitidos(perfil):
    permitidos = set()
    for t in TIPOS_ALERTA:
        if t["id"] in perfil.get("tipos", []):
            permitidos.update(t["tipos_dataset"])
    return permitidos


def _slugify(texto):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return t.lower().replace(" ", "-")


def selecionar(b, perfil, cats):
    """Aplica os filtros do perfil ao payload do brief. Retorna seleção + motivo."""
    score_min = int(perfil.get("score_minimo") or 0)
    permitidos = _tipos_permitidos(perfil)
    temas = [str(t).lower() for t in (perfil.get("temas") or [])]
    orgaos = [str(o).lower() for o in (perfil.get("orgaos") or [])]
    fixas = set(perfil.get("proposicoes") or [])

    slugs_tema = set()
    ids_tema = set()
    for t in temas:
        achou = False
        for c in cats.values():
            if t in (str(c.get("slug", "")).lower(), str(c.get("nome", "")).lower(), str(c.get("id"))):
                slugs_tema.add(str(c.get("slug", "")).lower())
                ids_tema.add(c.get("id"))
                achou = True
        if not achou:
            slugs_tema.add(t)

    def tema_ok(bloco):
        if not temas:
            return True
        fato = bloco.get("fato_oficial", {})
        texto = _slugify(fato.get("nome")) + " " + _slugify(fato.get("situacao")) + " " + \
            _slugify(fato.get("ementa"))
        if any(s and s in texto for s in slugs_tema):
            return True
        return bool(ids_tema & set(bloco.get("_categorias") or []))

    def orgao_ok(bloco):
        if not orgaos:
            return True
        fato = bloco.get("fato_oficial", {})
        alvo = " ".join(str(fato.get(k) or "").lower()
                        for k in ("orgaos_responsaveis", "comissao_atual", "casa_atual"))
        return any(o in alvo for o in orgaos)

    mudancas = []
    for m in b.get("mudancas_criticas", []) + b.get("mudancas_30_dias", []):
        if m in mudancas:
            continue
        tipo_dataset = (m.get("tipo") or "")
        if permitidos and tipo_dataset not in permitidos:
            continue
        if m.get("score") and score_min and m["score"] < score_min and not fixas:
            continue
        mudancas.append(m)

    materias = []
    for bloco in b.get("top_materias", []):
        bloco = dict(bloco)
        fato = bloco.get("fato_oficial", {})
        if fato.get("id") in fixas:
            materias.append(bloco)
            continue
        if score_min and (bloco.get("score", {}).get("valor") or 0) < score_min:
            continue
        if not tema_ok(bloco) or not orgao_ok(bloco):
            continue
        materias.append(bloco)

    janela = FREQUENCIA_JANELA.get(perfil.get("frequencia", "semanal"), 7)
    agenda = [e for e in b.get("agenda", {}).get("proximos_dias", [])
              if (e.get("dias") is None or e["dias"] <= janela + 3)]
    agenda += b.get("agenda", {}).get("sem_data_confirmada", [])

    return {
        "mudancas": mudancas,
        "materias": materias,
        "agenda": agenda,
        "desde_ultimo_relatorio": b.get("desde_ultimo_relatorio", []),
        "setores": b.get("setores", [])[:8],
        "atencao_executiva": b.get("atencao_executiva", []),
        "fontes_oficiais": b.get("fontes_oficiais", []),
        "filtros_aplicados": {
            "frequencia": perfil.get("frequencia"),
            "janela_dias": janela,
            "score_minimo": score_min,
            "temas": temas,
            "orgaos": orgaos,
            "proposicoes_fixas": sorted(fixas),
            "tipos": perfil.get("tipos"),
            "tipos_indisponiveis": [t["id"] for t in TIPOS_ALERTA
                                    if not t["implementado"] and t["id"] in perfil.get("tipos", [])],
        },
    }


# ---------------------------------------------------------------------------
# Renderização (e-mail: estilos inline, sem CSS externo, sem JavaScript)
# ---------------------------------------------------------------------------

_ESTILOS = {
    "bg": "#ffffff", "ink": "#10161d", "muted": "#5b6773", "line": "#e3e8ee",
    "accent": "#0f8f63", "fact": "#1f5fa8", "analysis": "#9a6b00",
    "crit": "#b42318", "warn": "#9a6b00",
}


def _e(t):
    return (str(t) if t is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _link(url, rotulo):
    if not url:
        return ""
    return f'<a href="{_e(url)}" style="color:{_ESTILOS["fact"]};text-decoration:underline">{_e(rotulo)}</a>'


def render_html(modelo, b, sel, perfil, gerado_em):
    meta = b["meta"]
    s = _ESTILOS
    titulo = ("Executive Regulatory Brief" if modelo == "brief"
              else f"Alerta regulatório de IA — {perfil.get('frequencia', 'semanal')}")
    linhas = []

    linhas.append(f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(titulo)}</title></head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;color:{s['ink']}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:22px 0">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:{s['bg']};border:1px solid {s['line']};border-radius:10px;overflow:hidden">
<tr><td style="padding:22px 24px;border-bottom:1px solid {s['line']}">
  <div style="font-size:11px;letter-spacing:1.6px;text-transform:uppercase;color:{s['accent']};font-weight:700">
    Monitor Legislativo de IA · LCF Consulting</div>
  <h1 style="margin:8px 0 6px;font-size:22px;line-height:1.25">{_e(titulo)}</h1>
  <p style="margin:0;font-size:13px;color:{s['muted']}">Referência {_e(meta['referencia_fmt'])} ·
  {_e(meta['total_proposicoes'])} proposições monitoradas · {_e(meta['total_normas'])} normas vigentes ·
  perfil <b>{_e(perfil.get('nome') or perfil.get('id'))}</b></p>
</td></tr>""")

    def secao(numero, titulo_sec, subtitulo=""):
        linhas.append(f"""<tr><td style="padding:20px 24px 6px">
  <h2 style="margin:0;font-size:16px">{_e(numero)}. {_e(titulo_sec)}</h2>
  {f'<p style="margin:4px 0 0;font-size:12.5px;color:{s["muted"]}">{_e(subtitulo)}</p>' if subtitulo else ''}
</td></tr>""")

    def bloco_mudanca(m):
        cor = {"crítica": s["crit"], "alta": s["warn"]}.get(m.get("severidade"), s["muted"])
        return f"""<tr><td style="padding:10px 24px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
   style="border:1px solid {s['line']};border-left:3px solid {cor};border-radius:8px">
   <tr><td style="padding:12px 14px">
     <div style="font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:{s['muted']}">
       {_e(m['data_fmt'])} · {_e(m.get('tipo') or 'mudança')} · severidade {_e(m.get('severidade'))}
       {f" · score {m['score']}" if m.get('score') else ''}</div>
     <div style="font-size:14.5px;font-weight:600;margin:6px 0 4px">{_e(m.get('titulo'))}</div>
     <div style="font-size:13px;color:{s['muted']}">{_e(m.get('descricao'))}</div>
     <div style="margin-top:8px;font-size:12.5px">{_link(m.get('fonte_url'), 'Fonte oficial ↗')}</div>
   </td></tr></table>
</td></tr>"""

    # 1. Mudanças
    secao(1, "Mudanças no período",
          f"Janela de {sel['filtros_aplicados']['janela_dias']} dia(s) · "
          f"{len(sel['mudancas'])} registro(s) após os filtros do perfil")
    if sel["mudancas"]:
        for m in sel["mudancas"][:12]:
            linhas.append(bloco_mudanca(m))
    else:
        linhas.append(f"""<tr><td style="padding:10px 24px;font-size:13px;color:{s['muted']}">
Nenhuma mudança no recorte deste perfil no período. O monitoramento seguiu ativo — a verificação
está registrada em {_link(SITE_URL + '/monitoramento/', 'painel de monitoramento')}.</td></tr>""")

    # 2. Matérias prioritárias (fato × análise)
    secao(2, "Matérias prioritárias por impacto",
          "Fato oficial e análise separados. A ação recomendada é priorização operacional, não aconselhamento jurídico.")
    for bloco in sel["materias"][:5]:
        f_ = bloco["fato_oficial"]
        a_ = bloco["analise"]
        sc = bloco["score"]
        linhas.append(f"""<tr><td style="padding:10px 24px">
 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid {s['line']};border-radius:8px">
  <tr><td style="padding:12px 14px;background:#fafbfc;border-bottom:1px solid {s['line']}">
    <div style="font-size:15px;font-weight:700">{_e(f_['titulo'])} — {_e(f_['nome'])}</div>
    <div style="font-size:12px;color:{s['muted']};margin-top:4px">Score {sc['valor']}/100 · {_e(sc['classificacao'])} ·
    impacto potencial <b>{_e(a_['impacto_potencial'])}</b> · ação recomendada: <b>{_e(a_['acao_recomendada'])}</b></div>
  </td></tr>
  <tr><td style="padding:12px 14px">
    <div style="font-size:10.5px;text-transform:uppercase;letter-spacing:1px;color:{s['fact']};font-weight:700">Fato oficial</div>
    <div style="font-size:13px;margin-top:4px">Situação: {_e(f_.get('situacao') or '—')}</div>
    {f'<div style="font-size:13px">Próxima etapa: {_e(f_.get("proxima_etapa"))}</div>' if f_.get('proxima_etapa') else ''}
    {f'<div style="font-size:13px">Obrigações criadas: {_e(f_.get("obrigacoes_criadas"))}</div>' if f_.get('obrigacoes_criadas') else ''}
    {f'<div style="font-size:13px">Órgãos: {_e(f_.get("orgaos_responsaveis"))}</div>' if f_.get('orgaos_responsaveis') else ''}
    <div style="font-size:12.5px;margin-top:6px">{_link(f_.get('url_oficial'), 'Fonte oficial ↗')} ·
      {_link(SITE_URL + '/proposicoes/', 'ficha completa')}</div>
  </td></tr>
  <tr><td style="padding:12px 14px;background:#fffdf6;border-top:1px solid {s['line']}">
    <div style="font-size:10.5px;text-transform:uppercase;letter-spacing:1px;color:{s['analysis']};font-weight:700">Análise / interpretação</div>
    <div style="font-size:13px;margin-top:4px">{_e(a_['por_que_importa'])}</div>
    <div style="font-size:12.5px;color:{s['muted']};margin-top:6px">Setores potencialmente afetados:
      {_e(', '.join(a_['setores_afetados'][:8]) or '—')} · prazo provável: {_e(a_.get('prazo_provavel') or 'não informado na fonte oficial')} ·
      status da interpretação: {_e(a_['status_interpretacao'])}</div>
  </td></tr>
 </table>
</td></tr>""")

    # 3. Desde o último relatório
    secao(3, "Mudanças desde o último relatório", b.get("criterio_desde_ultimo_relatorio") or "")
    for m in sel["desde_ultimo_relatorio"][:8]:
        linhas.append(bloco_mudanca(m))
    if not sel["desde_ultimo_relatorio"]:
        linhas.append(f'<tr><td style="padding:6px 24px;font-size:13px;color:{s["muted"]}">Nenhuma.</td></tr>')

    # 4. Agenda
    secao(4, "Agenda e próximos passos", "Eventos oficiais e marcos sem data confirmada")
    for e_ in sel["agenda"][:8]:
        linhas.append(f"""<tr><td style="padding:6px 24px;font-size:13px">
  <b>{_e(e_['data_fmt'])}</b> · {_e(e_.get('titulo'))} <span style="color:{s['muted']}">— {_e(e_.get('casa'))}</span>
  {_link(e_.get('fonte_url'), '↗')}
</td></tr>""")
    if not sel["agenda"]:
        linhas.append(f'<tr><td style="padding:6px 24px;font-size:13px;color:{s["muted"]}">Nenhum evento no período.</td></tr>')

    # 5. Setores (só no brief)
    if modelo == "brief":
        secao(5, "Possíveis impactos por setor", "Agregação determinística das categorias monitoradas")
        for st in sel["setores"][:8]:
            top = st.get("top") or {}
            linhas.append(f"""<tr><td style="padding:6px 24px;font-size:13px">
  <b>{_e(st['setor'])}</b> — {st['proposicoes']} matérias, {st['criticos']} com score 85+
  {f"· maior exposição: {_e(top.get('rotulo'))} (score {top.get('score')})" if top.get('rotulo') else ''}
</td></tr>""")
        secao(6, "Pontos de atenção executiva", "")
        for a_ in sel["atencao_executiva"]:
            linhas.append(f"""<tr><td style="padding:6px 24px;font-size:13px">
  • <b>{_e(a_['ponto'])}</b> — {_e(a_['detalhe'])}
  <span style="color:{s['muted']};font-size:11.5px">(base: {_e(a_['base'])})</span></td></tr>""")
        secao(7, "Fontes oficiais", "")
        for fo in sel["fontes_oficiais"][:12]:
            linhas.append(f'<tr><td style="padding:4px 24px;font-size:12.5px">{_link(fo["url"], fo["url"][:90])}</td></tr>')

    # Rodapé
    linhas.append(f"""<tr><td style="padding:18px 24px;border-top:1px solid {s['line']};font-size:11.5px;color:{s['muted']}">
  <p style="margin:0 0 6px"><b>Metodologia:</b> gerado automaticamente por <code>scripts/build_alert_email.py</code>
  a partir de <code>data/legislation/*.json</code> em {_e(gerado_em)}. AI Legislative Impact Score conforme
  rúbrica pública de 9 critérios.</p>
  <p style="margin:0 0 6px"><b>Filtros deste envio:</b> {_e(json.dumps(sel['filtros_aplicados'], ensure_ascii=False))}</p>
  <p style="margin:0 0 10px">{_e(meta['aviso'])}</p>
  <p style="margin:0">
   {_link(SITE_URL + '/solucoes/', 'Soluções e planos')} ·
   {_link(SITE_URL + '/diagnostico/', 'Solicitar diagnóstico regulatório')} ·
   {_link(SITE_URL + '/briefing-executivo/', 'Amostra pública do briefing')} ·
   {_link(SITE_URL + '/', 'Monitor público')}
  </p>
  <p style="margin:10px 0 0">Para alterar temas, score mínimo, frequência ou cancelar o envio,
  responda a este e-mail ou use o link de diagnóstico acima.</p>
</td></tr>
</table>
</td></tr></table></body></html>""")
    return "".join(linhas)


def render_text(modelo, b, sel, perfil):
    meta = b["meta"]
    L = []
    L.append("MONITOR LEGISLATIVO DE IA — " + ("EXECUTIVE REGULATORY BRIEF" if modelo == "brief" else "ALERTA"))
    L.append(f"Referência: {meta['referencia_fmt']} · perfil: {perfil.get('nome') or perfil.get('id')}")
    L.append(f"Filtros: {json.dumps(sel['filtros_aplicados'], ensure_ascii=False)}")
    L.append("")
    L.append(f"1) MUDANÇAS NO PERÍODO ({len(sel['mudancas'])})")
    for m in sel["mudancas"][:12]:
        L.append(f"- [{m['data_fmt']}] ({m.get('tipo')}) {m.get('titulo')}")
        if m.get("fonte_url"):
            L.append(f"  fonte: {m['fonte_url']}")
    L.append("")
    L.append(f"2) MATÉRIAS PRIORITÁRIAS ({len(sel['materias'])})")
    for bloco in sel["materias"][:5]:
        f_, a_, sc = bloco["fato_oficial"], bloco["analise"], bloco["score"]
        L.append(f"- {f_['titulo']} — {f_['nome']} | score {sc['valor']}/100 | impacto {a_['impacto_potencial']}")
        L.append(f"  FATO: {f_.get('situacao') or '—'}")
        if f_.get("proxima_etapa"):
            L.append(f"  PRÓXIMA ETAPA: {f_['proxima_etapa']}")
        L.append(f"  ANÁLISE: {a_['por_que_importa']}")
        L.append(f"  AÇÃO RECOMENDADA: {a_['acao_recomendada']}")
        L.append(f"  SETORES: {', '.join(a_['setores_afetados'][:8]) or '—'}")
        L.append(f"  FONTE: {f_.get('url_oficial') or '—'}")
    L.append("")
    L.append(f"3) AGENDA ({len(sel['agenda'])})")
    for e_ in sel["agenda"][:8]:
        L.append(f"- {e_['data_fmt']} · {e_.get('titulo')} · {e_.get('casa')}")
    L.append("")
    L.append(meta["aviso"])
    L.append(f"{SITE_URL}/diagnostico/ · {SITE_URL}/solucoes/")
    return "\n".join(L)


def render_mensagem_curta(sel):
    """Formato pronto para WhatsApp/Telegram/Slack/Teams (conector é P2)."""
    n = len(sel["mudancas"])
    top = sel["materias"][0] if sel["materias"] else None
    txt = f"Monitor Legislativo de IA — {n} mudança(s) no período."
    if top:
        f_ = top["fato_oficial"]
        txt += (f" Prioridade: {f_['titulo']} (score {top['score']['valor']}/100, "
                f"impacto {top['analise']['impacto_potencial']}).")
    txt += f" Detalhes: {SITE_URL}/briefing-executivo/"
    return txt


def enviar_smtp(destinatarios, assunto, html, texto):
    """Envio opcional. Credenciais SOMENTE por variáveis de ambiente."""
    import smtplib
    from email.message import EmailMessage

    host = os.environ.get("MONITOR_SMTP_HOST", "").strip()
    if not host:
        return False, "MONITOR_SMTP_HOST não configurado (envio pulado)"
    porta = int(os.environ.get("MONITOR_SMTP_PORT", "587"))
    usuario = os.environ.get("MONITOR_SMTP_USER", "").strip()
    senha = os.environ.get("MONITOR_SMTP_PASS", "")
    remetente = os.environ.get("MONITOR_SMTP_FROM", usuario or "monitor@lcfconsulting.com.br")

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP(host, porta, timeout=30) as srv:
            srv.starttls()
            if usuario and senha:
                srv.login(usuario, senha)
            srv.send_message(msg)
        return True, f"enviado para {len(destinatarios)} destinatário(s) via {host}:{porta}"
    except Exception as exc:  # nunca derruba o build/CI
        return False, f"falha no envio SMTP: {exc}"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gera alerta/relatório executivo a partir do dataset.")
    ap.add_argument("--modelo", choices=["alerta", "brief"], default="brief")
    ap.add_argument("--perfil", default="", help="JSON de perfil (sobrescreve o padrão)")
    ap.add_argument("--frequencia", choices=["imediato", "diario", "semanal"], default=None)
    ap.add_argument("--score-minimo", type=int, default=None)
    ap.add_argument("--temas", default="", help="slugs/ids de categorias separados por vírgula")
    ap.add_argument("--orgaos", default="")
    ap.add_argument("--proposicoes", default="")
    ap.add_argument("--destinatarios", default=os.environ.get("MONITOR_ALERT_TO", ""))
    ap.add_argument("--assunto", default="")
    ap.add_argument("--send", action="store_true", help="envia por SMTP se MONITOR_SMTP_* estiver configurado")
    ap.add_argument("--webhook-url", default="", help="se informado, faz POST do payload JSON")
    ap.add_argument("--out-dir", default=os.path.join(BASE, "build", "alertas"))
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--print", dest="imprimir", action="store_true", help="imprime o HTML no stdout")
    args = ap.parse_args(argv)

    props, updates, events, laws, cats, execucao = _brief.carregar_datasets(DATA)
    janela = FREQUENCIA_JANELA.get(args.frequencia or "semanal", 7)
    b = _brief.build_brief(props, updates, events, laws, cats, execucao, top_n=5, janela_dias=janela)

    perfil = dict(PERFIL_PADRAO)
    if args.perfil and os.path.isfile(args.perfil):
        with open(args.perfil, encoding="utf-8") as f:
            perfil.update(json.load(f))
    if args.frequencia:
        perfil["frequencia"] = args.frequencia
    if args.score_minimo is not None:
        perfil["score_minimo"] = args.score_minimo
    if args.temas:
        perfil["temas"] = [t.strip() for t in args.temas.split(",") if t.strip()]
    if args.orgaos:
        perfil["orgaos"] = [o.strip() for o in args.orgaos.split(",") if o.strip()]
    if args.proposicoes:
        perfil["proposicoes"] = [p.strip() for p in args.proposicoes.split(",") if p.strip()]

    if any([args.frequencia, args.score_minimo is not None, args.temas, args.orgaos, args.proposicoes]):
        perfil["id"] = "perfil-customizado"
        perfil["nome"] = f"Perfil customizado ({perfil.get('frequencia')}, score mínimo {perfil.get('score_minimo')})"

    # enriquece os blocos com as categorias (para filtro por tema)
    by_id = {p["id"]: p for p in props}
    for bloco in b["top_materias"]:
        bloco["_categorias"] = (by_id.get(bloco["fato_oficial"].get("id")) or {}).get("categorias") or []

    sel = selecionar(b, perfil, cats)
    gerado_em = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    html = render_html(args.modelo, b, sel, perfil, gerado_em)
    texto = render_text(args.modelo, b, sel, perfil)
    curta = render_mensagem_curta(sel)

    payload = {
        "modelo": args.modelo,
        "gerado_em": gerado_em,
        "canal": "email",
        "canais_disponiveis": CANAIS,
        "tipos_alerta": TIPOS_ALERTA,
        "perfil": perfil,
        "assunto": args.assunto or (
            f"[Monitor IA] {'Executive Regulatory Brief' if args.modelo == 'brief' else 'Alerta'} — "
            f"{b['meta']['referencia_fmt']} · {len(sel['mudancas'])} mudança(s) · "
            f"{len(sel['materias'])} matéria(s) prioritária(s)"),
        "destinatarios": [d.strip() for d in args.destinatarios.split(",") if d.strip()],
        "html": None if args.json_only else html,
        "texto": texto,
        "mensagem_curta": curta,
        "selecao": sel,
        "meta_brief": b["meta"],
    }

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = b["meta"]["referencia"]
    base_nome = f"{args.modelo}-{perfil.get('frequencia', 'semanal')}-{stamp}"
    caminho_json = os.path.join(args.out_dir, base_nome + ".json")
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    caminhos = [caminho_json]
    if not args.json_only:
        caminho_html = os.path.join(args.out_dir, base_nome + ".html")
        caminho_txt = os.path.join(args.out_dir, base_nome + ".txt")
        with open(caminho_html, "w", encoding="utf-8") as f:
            f.write(html)
        with open(caminho_txt, "w", encoding="utf-8") as f:
            f.write(texto)
        caminhos += [caminho_html, caminho_txt]

    if args.webhook_url:
        try:
            import urllib.request
            req = urllib.request.Request(
                args.webhook_url, data=json.dumps(sel, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=20) as resp:
                print(f"OK: webhook {args.webhook_url} → HTTP {resp.status}")
        except Exception as exc:
            print(f"AVISO: webhook não entregue ({exc})")

    if args.send:
        dests = payload["destinatarios"]
        if not dests:
            print("AVISO: --send sem destinatários (use --destinatarios ou MONITOR_ALERT_TO)")
        else:
            ok, msg = enviar_smtp(dests, payload["assunto"], html, texto)
            print(("OK: " if ok else "AVISO: ") + msg)

    for c in caminhos:
        relativo = os.path.relpath(c, BASE)
        print("OK: gerado " + (relativo if not relativo.startswith("..") else c))
    print(f"Resumo: {len(sel['mudancas'])} mudança(s) · {len(sel['materias'])} matéria(s) · "
          f"{len(sel['agenda'])} evento(s) · perfil {perfil.get('id')} · "
          f"tipos indisponíveis: {sel['filtros_aplicados']['tipos_indisponiveis'] or 'nenhum'}")
    if args.imprimir:
        print(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
