#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
commercial.py — Camada comercial B2B do Monitor Legislativo de IA.

Posicionamento obrigatório (não é um monitor legislativo genérico):
    Inteligência regulatória especializada em Inteligência Artificial, Dados,
    Infraestrutura Digital e tecnologias de alta consequência regulatória.

    A proposta não é "acompanhe N projetos de lei".
    É "saiba o que mudou, por que isso importa para sua operação, quem precisa
    agir e qual evidência oficial sustenta a conclusão".

Este módulo é a CONFIGURAÇÃO CENTRALIZADA + gerador das páginas comerciais:
    /solucoes/            4 formas de contratação (pricing em config)
    /diagnostico/         landing + captura de lead + lead scoring
    /briefing-executivo/  amostra do produto pago com dados REAIS do monitor
    /para-empresas/       página para o comprador corporativo

Princípios respeitados aqui:
  * o monitor público continua público (freemium demonstrativo) — nada de paywall;
  * nenhuma URL existente é alterada ou removida;
  * nenhuma prova social inventada (PROVA_SOCIAL_ENABLED = False até haver case real);
  * linguagem de inteligência regulatória, nunca de aconselhamento jurídico;
  * preço alterável por config (constante aqui ou variável de ambiente MONITOR_*).

Sem dependências externas (stdlib).
"""
import json
import os

import brief as _brief

_CORE = None  # referência ao gerador (build_site_core), definida em install()

# ---------------------------------------------------------------------------
# 1. CONFIGURAÇÃO CENTRAL — pricing, CTAs, contatos, analytics, captura de lead
# ---------------------------------------------------------------------------

# Contato comercial. Nada de inventar: são os canais reais do projeto.
CONTATO_EMAIL = os.environ.get("MONITOR_COMMERCIAL_EMAIL", "contato@lcfconsulting.com.br")
CONSULTING_URL = "https://lcfconsulting.com.br/"

# WhatsApp comercial (opcional). Vazio = o botão não é renderizado.
# Ex.: MONITOR_WHATSAPP=5511999999999
WHATSAPP = os.environ.get("MONITOR_WHATSAPP", "").strip()

# Endpoint de captura de lead (provider de formulário: Formspree, Web3Forms,
# Basin, Getform, função serverless própria...). Vazio = modo fallback
# (e-mail/WhatsApp com o payload estruturado), para a captura nunca quebrar.
# Ex.: MONITOR_LEAD_ENDPOINT=https://formspree.io/f/xxxxxxxx
LEAD_ENDPOINT = os.environ.get("MONITOR_LEAD_ENDPOINT", "").strip()
LEAD_PROVIDER = os.environ.get("MONITOR_LEAD_PROVIDER", "").strip() or (
    "endpoint-http" if LEAD_ENDPOINT else "fallback-email")

# Analytics (camada própria, agnóstica de fornecedor — ver assets/commercial.js).
ANALYTICS = {
    "ga4_id": os.environ.get("MONITOR_GA4_ID", "").strip(),
    "plausible_domain": os.environ.get("MONITOR_PLAUSIBLE_DOMAIN", "").strip(),
    "plausible_src": os.environ.get("MONITOR_PLAUSIBLE_SRC", "").strip(),
    "beacon_endpoint": os.environ.get("MONITOR_ANALYTICS_ENDPOINT", "").strip(),
    "debug": os.environ.get("MONITOR_ANALYTICS_DEBUG", "") == "1",
}


def _env_price(key, default_min, default_max):
    """Preço sobrescrevível por ambiente sem tocar no código."""
    lo = os.environ.get(f"MONITOR_PRICE_{key}_MIN", "").strip()
    hi = os.environ.get(f"MONITOR_PRICE_{key}_MAX", "").strip()
    try:
        lo = int(lo) if lo else default_min
    except ValueError:
        lo = default_min
    try:
        hi = int(hi) if hi else default_max
    except ValueError:
        hi = default_max
    return lo, hi


def _brl(v):
    return "R$ " + f"{v:,}".replace(",", ".")


# As 4 formas de contratação (item 4 do briefing comercial).
# `publico` controla se a faixa aparece no site (Inteligência Institucional = sob consulta).
_SOLUCAO_1 = _env_price("MONITOR_IA", 1500, 3000)
_SOLUCAO_2 = _env_price("RADAR_EXECUTIVO", 4000, 8000)
_SOLUCAO_3 = _env_price("INSTITUCIONAL", 10000, 20000)  # referência interna, não pública
_SOLUCAO_4 = _env_price("DIAGNOSTICO", 5000, 15000)

SOLUCOES = [
    {
        "id": "monitor-ia",
        "nome": "Monitor IA",
        "resumo": "A base proprietária do monitoramento, com score de impacto, histórico e fontes oficiais.",
        "para_quem": ["Startups e pequenas empresas", "Consultores", "Escritórios menores",
                      "Profissionais de regulação, compliance e RIG"],
        "entregas": [
            "Monitor legislativo de IA, dados e infraestrutura digital (acesso ao produto público + camadas de priorização)",
            "AI Legislative Impact Score por matéria, com fatores que sustentam a pontuação",
            "Histórico completo de movimentações e registro auditável de mudanças",
            "Fontes oficiais linkadas em cada afirmação",
            "Agenda legislativa de IA (audiências, votações, marcos normativos)",
            "Alertas por e-mail (imediato, diário ou semanal) por tema e score mínimo",
            "Relatório periódico do que mudou no seu recorte",
        ],
        "preco_min": _SOLUCAO_1[0],
        "preco_max": _SOLUCAO_1[1],
        "preco_unidade": "mês",
        "preco_publico": True,
        "usuarios": "Até 3 usuários",
        "destaque": False,
        "cta": "Começar com o Monitor IA",
    },
    {
        "id": "radar-executivo",
        "nome": "Radar Executivo de Regulação de IA",
        "resumo": "A oferta principal: tudo do Monitor IA traduzido para decisão executiva, toda semana.",
        "para_quem": ["Fintech e bancos", "Seguradoras", "Empresas de tecnologia",
                      "Healthtech e saúde", "Data centers e cloud providers",
                      "Empresas que usam IA de forma relevante", "Escritórios jurídicos"],
        "entregas": [
            "Tudo o que está incluído no Monitor IA",
            "Briefing executivo semanal (o modelo que você vê em /briefing-executivo/)",
            "Análise de impacto: o que a mudança significa para a operação",
            "Agenda prioritária dos próximos 7 e 30 dias",
            "Alertas críticos fora de ciclo quando algo muda de estágio ou de score",
            "Reunião executiva mensal de leitura do cenário",
            "Identificação do impacto da alteração legislativa no negócio, por área",
        ],
        "preco_min": _SOLUCAO_2[0],
        "preco_max": _SOLUCAO_2[1],
        "preco_unidade": "mês",
        "preco_publico": True,
        "usuarios": "Até 10 usuários",
        "destaque": True,
        "cta": "Solicitar proposta do Radar Executivo",
    },
    {
        "id": "inteligencia-institucional",
        "nome": "Inteligência Institucional",
        "resumo": "Monitoramento customizado, integração e SLA para estruturas reguladas e multiárea.",
        "para_quem": ["Grandes empresas", "Associações setoriais", "Consultorias",
                      "Grandes escritórios", "Empresas altamente reguladas"],
        "entregas": [
            "Monitoramento customizado por temas, órgãos e jurisdições definidos com você",
            "Múltiplos usuários e perfis de acesso por área",
            "Temas personalizados além do recorte padrão de IA e dados",
            "Alertas prioritários com regra própria de severidade",
            "API e webhook para integrar ao seu GRC, jurídico ou BI",
            "SLA contratual de atualização e resposta",
            "Reunião recorrente com curadoria especializada",
            "Relatórios customizados (comitê, conselho, regulador, associados)",
            "Possibilidade de white-label para consultorias e associações",
        ],
        "preco_min": _SOLUCAO_3[0],
        "preco_max": _SOLUCAO_3[1],
        "preco_unidade": "mês",
        "preco_publico": False,          # faixa interna de referência — não publicada
        "preco_rotulo": "Sob consulta",
        "usuarios": "Usuários e temas ilimitados conforme escopo",
        "destaque": False,
        "cta": "Falar sobre escopo institucional",
    },
    {
        "id": "diagnostico-exposicao",
        "nome": "Diagnóstico de Exposição Regulatória",
        "resumo": "Produto avulso, sem assinatura: onde sua operação está exposta à regulação de IA hoje.",
        "para_quem": ["Quem ainda não quer assumir uma assinatura",
                     "Times que precisam de um retrato objetivo para decidir",
                     "Comitês que vão definir orçamento de compliance em IA"],
        "entregas": [
            "Workshop de leitura do cenário regulatório com o seu time",
            "Levantamento de exposição por área, produto e processo",
            "Definição dos temas prioritários para a sua operação",
            "Mapeamento das proposições e normas relacionadas a cada tema",
            "Riscos identificados com a evidência oficial correspondente",
            "Relatório executivo com hierarquia de prioridade",
            "Recomendações de monitoramento (o que acompanhar, com que frequência e quem acionar)",
        ],
        "preco_min": _SOLUCAO_4[0],
        "preco_max": _SOLUCAO_4[1],
        "preco_unidade": "projeto",
        "preco_publico": True,
        "usuarios": "Time participante do workshop",
        "destaque": False,
        "cta": "Solicitar diagnóstico",
        "nota": "Funciona também como porta de entrada para uma assinatura recorrente: "
                "o plano de monitoramento sai do diagnóstico.",
    },
]

# CTA principal e secundário (item 3) — textos exatos do posicionamento.
CTA_PRINCIPAL = "Solicitar diagnóstico regulatório"
CTA_PRINCIPAL_SUB = ("Descubra quais projetos, normas e mudanças regulatórias relacionadas à IA "
                     "podem afetar sua organização.")
CTA_SECUNDARIO = "Ver exemplo de briefing executivo"
CTA_DEMO = "Solicitar demonstração contextualizada"
CTA_ALERTA = "Receber briefing regulatório por e-mail"

# Avisos obrigatórios (item 18): inteligência, não aconselhamento jurídico.
DISCLAIMER_COMERCIAL = (
    "O Monitor Legislativo de IA fornece inteligência regulatória, acompanhamento legislativo, "
    "análise de impacto e priorização com base em fontes oficiais. Não presta aconselhamento "
    "jurídico, não emite parecer e não garante conformidade nem interpretação legal. "
    "Decisões jurídicas devem ser tomadas com assessoria habilitada."
)
DISCLAIMER_COMERCIAL_CURTO = (
    "Inteligência regulatória, análise de impacto e priorização com fonte oficial. "
    "Não constitui parecer, aconselhamento jurídico nem garantia de conformidade."
)
DISCLAIMER_ANALISE = (
    "Análise / interpretação do Monitor — derivada de regras públicas e auditáveis, "
    "não é fato oficial."
)
DISCLAIMER_FATO = (
    "Fato oficial — campo registrado no monitoramento a partir de fonte oficial linkada."
)

# Prova social (item 13): estrutura pronta, DESATIVADA até existir evidência real.
PROVA_SOCIAL_ENABLED = False
PROVA_SOCIAL = {
    "logos": [],        # [{"nome": ..., "url_logo": ..., "autorizado_em": ...}]
    "depoimentos": [],  # [{"texto": ..., "autor": ..., "cargo": ..., "empresa": ...}]
    "cases": [],        # [{"empresa": ..., "desafio": ..., "resultado": ..., "url": ...}]
    "metricas": [],     # [{"rotulo": ..., "valor": ..., "fonte_interna": ...}]
}

# Setores do formulário (item 5) e base das futuras páginas setoriais (P1).
SETORES_FORM = ["Tecnologia", "Bancos", "Fintech", "Seguros", "Saúde", "Telecom", "Cloud",
                "Data Center", "Infraestrutura", "Jurídico", "Consultoria", "Associação",
                "Governo", "Outro"]

SETORES_PRIORITARIOS = {"Bancos", "Fintech", "Seguros", "Tecnologia", "Cloud", "Data Center"}

TAMANHOS = ["1 a 10", "11 a 50", "51 a 100", "101 a 500", "501 a 1.000", "Mais de 1.000"]
TAMANHOS_GRANDES = {"501 a 1.000", "Mais de 1.000"}
TAMANHOS_ACIMA_100 = {"101 a 500", "501 a 1.000", "Mais de 1.000"}

CARGOS = ["C-level (CEO, CTO, CCO, CRO, CFO)", "Diretor(a)", "Head / Gerente executivo(a)",
          "Sócio(a)", "Gerente", "Coordenador(a) / Supervisor(a)", "Analista / Especialista",
          "Consultor(a)", "Outro"]
CARGOS_SENIOR = {"C-level (CEO, CTO, CCO, CRO, CFO)", "Diretor(a)",
                 "Head / Gerente executivo(a)", "Sócio(a)"}

AREAS = ["Sim — Compliance", "Sim — Jurídico", "Sim — Relações governamentais (RIG)",
         "Sim — mais de uma dessas áreas", "Em estruturação", "Não temos"]

HORIZONTES = ["Imediata — próximos 3 meses", "Curto prazo — 6 a 12 meses",
              "Médio prazo — 1 a 2 anos", "Ainda avaliando se somos afetados"]

USO_IA = ["IA em processo crítico da operação", "IA em produtos e receita",
          "IA em suporte interno e produtividade", "Em avaliação / pilotos",
          "Ainda não usamos IA"]

PREOCUPACOES = ["Marco legal da IA (PL 2338/2023)", "Proteção de dados e atuação da ANPD",
                "Deepfakes, conteúdo sintético e eleições", "Responsabilidade civil por sistemas de IA",
                "Sistemas de alto risco, biometria e auditoria",
                "Infraestrutura digital e data centers (Redata)",
                "Direitos autorais e treinamento de modelos", "Trabalho e automação",
                "IA em saúde", "IA em serviços financeiros e seguros",
                "Compras públicas e uso de IA pelo governo", "Outra"]

ASSUNTOS = ["Diagnóstico de Exposição Regulatória", "Radar Executivo (briefing semanal)",
            "Monitor IA (assinatura)", "Inteligência Institucional",
            "Alertas por e-mail", "Demonstração contextualizada",
            "API / integração (webhook)", "Outro assunto"]

# Lead scoring (item 6) — pesos e faixas publicados na config para que o
# front-end aplique exatamente a mesma regra (fonte única).
LEAD_SCORING = {
    "regras": [
        {"id": "grande_empresa", "pontos": 20,
         "descricao": "Organização de grande porte (501+ funcionários)"},
        {"id": "setor_prioritario", "pontos": 20,
         "descricao": "Setor de alta consequência regulatória (banco, fintech, seguros, tecnologia, cloud, data center)"},
        {"id": "cargo_decisor", "pontos": 15,
         "descricao": "Cargo de decisão (C-level, diretoria, head ou sócio)"},
        {"id": "area_estruturada", "pontos": 15,
         "descricao": "Possui área de compliance, jurídico ou relações governamentais"},
        {"id": "preocupacao_imediata", "pontos": 15,
         "descricao": "Declara preocupação regulatória imediata (próximos 3 meses)"},
        {"id": "ia_critica", "pontos": 10,
         "descricao": "Usa IA em processo crítico da operação"},
        {"id": "mais_de_100", "pontos": 5,
         "descricao": "Mais de 100 funcionários"},
    ],
    "faixas": [
        {"min": 70, "classe": "prioridade_comercial", "rotulo": "Prioridade comercial"},
        {"min": 50, "classe": "alto", "rotulo": "Alto"},
        {"min": 30, "classe": "medio", "rotulo": "Médio"},
        {"min": 0, "classe": "baixo", "rotulo": "Baixo"},
    ],
    "maximo": sum(r["pontos"] for r in [
        {"pontos": 20}, {"pontos": 20}, {"pontos": 15}, {"pontos": 15},
        {"pontos": 15}, {"pontos": 10}, {"pontos": 5}]),
    "entradas": {
        "tamanho_grande": sorted(TAMANHOS_GRANDES),
        "tamanho_acima_100": sorted(TAMANHOS_ACIMA_100),
        "setores_prioritarios": sorted(SETORES_PRIORITARIOS),
        "cargos_senior": sorted(CARGOS_SENIOR),
        "areas_que_pontuam": ["Sim — Compliance", "Sim — Jurídico",
                              "Sim — Relações governamentais (RIG)",
                              "Sim — mais de uma dessas áreas"],
        "horizonte_imediato": HORIZONTES[0],
        "uso_ia_critico": USO_IA[0],
    },
}

# Domínios de e-mail gratuitos: o formulário pede e-mail corporativo e avisa
# (sem bloquear) quando o domínio é público.
EMAILS_GRATUITOS = ["gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.com.br",
                    "live.com", "icloud.com", "bol.com.br", "uol.com.br", "terra.com.br",
                    "proton.me", "protonmail.com", "gmx.com", "aol.com"]

# Diferenciação competitiva (item 17) — o que afirmamos e o que NÃO afirmamos.
DIFERENCIACAO = [
    {"titulo": "Especialização",
     "texto": "Recorte deliberado em IA, dados, infraestrutura digital e tecnologias de alta "
              "consequência regulatória. Não tentamos cobrir toda a agenda legislativa.",
     "evidencia": "30 categorias temáticas específicas, de regulação geral de IA a soberania digital."},
    {"titulo": "Priorização",
     "texto": "AI Legislative Impact Score proprietário, com rúbrica pública de 9 critérios e "
              "pontuação reproduzível — não é uma lista cronológica.",
     "evidencia": "Rúbrica publicada em /metodologia/ e fatores exibidos por matéria."},
    {"titulo": "Auditabilidade",
     "texto": "Cada afirmação aponta a fonte oficial e o histórico de mudanças fica registrado "
              "com data, tipo e link.",
     "evidencia": "Registro auditável de mudanças e log de execuções do monitoramento."},
    {"titulo": "Tradução empresarial",
     "texto": "Do evento legislativo para a consequência operacional: setores afetados, obrigação "
              "potencial, prazo provável e ação recomendada.",
     "evidencia": "Camada de análise separada visualmente do fato oficial."},
    {"titulo": "Velocidade",
     "texto": "Mudança detectada na fonte oficial → classificação por score → alerta → briefing.",
     "evidencia": "Coleta automática diária das APIs da Câmara e do Senado com orçamento e telemetria públicos."},
]

# O que NÃO dizemos (guard-rail editorial, verificado em validate_site.py).
TERMOS_PROIBIDOS = ["parecer jurídico", "aconselhamento jurídico", "garantia de conformidade",
                    "garantimos conformidade", "consultoria jurídica", "advocacia",
                    "interpretamos a lei para você"]

# Páginas comerciais → sitemap, links internos e eventos de analytics.
PAGINAS = [
    {"path": "solucoes/", "nome": "Soluções e planos", "evento": "pricing_view"},
    {"path": "diagnostico/", "nome": "Diagnóstico regulatório", "evento": "diagnostic_page_view"},
    {"path": "briefing-executivo/", "nome": "Exemplo de briefing executivo", "evento": "briefing_sample_view"},
    {"path": "para-empresas/", "nome": "Para empresas", "evento": "para_empresas_view"},
]

NAV_COMERCIAL = [("solucoes/", "Soluções"), ("para-empresas/", "Para empresas")]

EVENTOS_ANALYTICS = [
    "commercial_cta_click", "diagnostic_started", "diagnostic_submitted", "briefing_sample_view",
    "pricing_view", "sector_page_view", "high_impact_view", "alert_signup", "demo_request",
    "whatsapp_click",
]

FAQ_SOLUCOES = [
    {"q": "Isso é aconselhamento jurídico?",
     "a": "Não. Entregamos inteligência regulatória: acompanhamento legislativo, análise de impacto, "
          "priorização e evidência oficial. A decisão jurídica continua com a sua assessoria habilitada. "
          "Nenhum material do monitor constitui parecer ou garantia de conformidade."},
    {"q": "Vocês cobrem toda a agenda legislativa federal?",
     "a": "Não, e isso é deliberado. O recorte é IA, dados, infraestrutura digital e tecnologias de "
          "alta consequência regulatória. Para agenda legislativa generalista, um monitor amplo terá "
          "cobertura maior — a nossa diferença é priorização, tradução empresarial e auditabilidade "
          "nesse recorte."},
    {"q": "O monitor público sai do ar com a contratação?",
     "a": "Não. O monitor público continua gratuito e indexável. A contratação adiciona priorização, "
          "briefing, alertas configurados, análise de impacto por setor e reunião executiva."},
    {"q": "Como o preço é definido?",
     "a": "As faixas publicadas são referência para contratação mensal ou por projeto. A proposta formal "
          "sai depois do diagnóstico, conforme número de usuários, temas monitorados, frequência de "
          "briefing e necessidade de integração (API/webhook)."},
    {"q": "Existe período de piloto?",
     "a": "Sim. Estruturamos piloto comercial com temas customizados, alertas, briefing e limite de "
          "usuários por período inicial definido em contrato, com registro de uso para conversão."},
    {"q": "De onde vêm os dados?",
     "a": "Das fontes oficiais: APIs de dados abertos da Câmara dos Deputados e do Senado Federal, "
          "Congresso Nacional, Planalto, Diário Oficial da União, TSE, CNJ e ANPD. Cada registro traz "
          "o link da fonte e a metodologia é pública."},
    {"q": "Como meus dados são tratados?",
     "a": "Os dados enviados no formulário de diagnóstico são usados para contato comercial e "
          "qualificação do pedido, sob responsabilidade da LCF Consulting, nos termos da LGPD. "
          "Não são vendidos nem compartilhados para outra finalidade."},
]


# ---------------------------------------------------------------------------
# 2. Helpers de renderização
# ---------------------------------------------------------------------------

def is_installed():
    return _CORE is not None


def _url(path=""):
    return (_CORE.SITE_URL if _CORE else "") + "/" + path


def _esc(t):
    return _CORE.esc(t) if _CORE else str(t)


def _b(v):
    """Formata valor em BRL."""
    return _brl(v)


def preco_rotulo(s):
    if not s.get("preco_publico"):
        return s.get("preco_rotulo", "Sob consulta")
    if s["preco_min"] == s["preco_max"]:
        return _b(s["preco_min"])
    return f"{_b(s['preco_min'])} – {_b(s['preco_max'])}"


def preco_jsonld(s):
    """PriceSpecification honesta: faixa com minValue/maxValue, sem preço falso."""
    if not s.get("preco_publico"):
        return None
    return {
        "@type": "UnitPriceSpecification",
        "priceCurrency": "BRL",
        "minPrice": s["preco_min"],
        "maxPrice": s["preco_max"],
        "unitText": s["preco_unidade"],
    }


def link_diag(interesse=None, solucao=None, setor=None):
    q = []
    if interesse:
        q.append("interesse=" + interesse)
    if solucao:
        q.append("solucao=" + solucao)
    if setor:
        q.append("setor=" + setor)
    return _url("diagnostico/") + ("?" + "&".join(q) if q else "")


def whatsapp_link(texto="Olá! Vim do Monitor Legislativo de IA e quero falar sobre inteligência regulatória de IA."):
    if not WHATSAPP:
        return None
    from urllib.parse import quote
    return f"https://wa.me/{WHATSAPP}?text={quote(texto)}"


def form_attrs():
    """Atributos do <form> com degradação graciosa.

    Com provider configurado: POST para o endpoint (o JS envia JSON e trata a
    resposta). Sem provider: mailto com enctype text/plain — mesmo sem JavaScript
    o visitante consegue mandar o pedido pelo cliente de e-mail.
    """
    if LEAD_ENDPOINT:
        return f'action="{_esc(LEAD_ENDPOINT)}" method="POST"'
    return f'action="mailto:{_esc(CONTATO_EMAIL)}" method="POST" enctype="text/plain"'


def cta_principal(classe="cta-btn", interesse=None, rotulo=None, track="commercial_cta_click"):
    """CTA principal de alta visibilidade (item 3)."""
    return (f'<a class="{classe}" href="{link_diag(interesse)}" data-track="{track}" '
            f'data-cta="diagnostico">{rotulo or CTA_PRINCIPAL}</a>')


def cta_secundario(classe="btn-ghost", rotulo=None, track="briefing_sample_view"):
    return (f'<a class="{classe}" href="{_url("briefing-executivo/")}" data-track="{track}">'
            f'{rotulo or CTA_SECUNDARIO}</a>')


def faixa_cta(titulo=None, subtitulo=None, interesse=None, mostrar_secundario=True):
    """Bloco de CTA reutilizável em qualquer página."""
    wa = whatsapp_link()
    extra = ""
    if wa:
        extra = (f' <a class="btn-ghost wa" href="{wa}" target="_blank" rel="noopener" '
                 f'data-track="whatsapp_click">WhatsApp</a>')
    secundario = cta_secundario() if mostrar_secundario else ""
    return f"""
<section class="block cta-band"><div class="wrap">
  <div class="cta-box">
    <div>
      <h3>{_esc(titulo or CTA_PRINCIPAL)}</h3>
      <p>{_esc(subtitulo or CTA_PRINCIPAL_SUB)}</p>
    </div>
    <div class="cta-actions">
      {cta_principal(interesse=interesse)}
      {secundario}
      {extra}
    </div>
  </div>
</div></section>"""


def header_cta():
    """CTA compacto no cabeçalho de TODAS as páginas (alta visibilidade)."""
    return (f'<a class="nav-cta" href="{link_diag()}" data-track="commercial_cta_click" '
            f'data-cta="header">Solicitar diagnóstico</a>')


def nav_links():
    return "".join(f'<a href="{_url(p)}">{_esc(n)}</a>' for p, n in NAV_COMERCIAL)


def disclaimer_block(titulo="Aviso sobre o escopo do serviço"):
    return (f'<div class="note warn disclaimer-comercial"><b>{_esc(titulo)}.</b> '
            f'{_esc(DISCLAIMER_COMERCIAL)}</div>')


def prova_social_block():
    """Estrutura pronta para cases/logos/depoimentos — desativada sem evidência real.

    Retorna string vazia enquanto PROVA_SOCIAL_ENABLED for False, garantindo que
    nenhuma prova social inventada chegue ao HTML publicado.
    """
    if not PROVA_SOCIAL_ENABLED:
        return ""
    logos = "".join(
        f'<span class="logo-item"><img src="{_esc(l["url_logo"])}" alt="{_esc(l["nome"])}" loading="lazy"></span>'
        for l in PROVA_SOCIAL.get("logos", []))
    deps = "".join(
        f'<blockquote class="card"><p>{_esc(d["texto"])}</p>'
        f'<footer>{_esc(d["autor"])} — {_esc(d["cargo"])}, {_esc(d["empresa"])}</footer></blockquote>'
        for d in PROVA_SOCIAL.get("depoimentos", []))
    if not logos and not deps:
        return ""
    return f"""
<section class="block"><div class="wrap">
  <h2 class="section-title">Quem já usa</h2>
  <div class="logos">{logos}</div>
  <div class="grid cols-2">{deps}</div>
</div></section>"""


def config_script(caminho_pagina="", page_kind="", setor=""):
    """Config pública injetada no <head> (sem segredo nenhum) + camada de analytics."""
    cfg = {
        "siteUrl": _CORE.SITE_URL if _CORE else "",
        "siteName": _CORE.SITE_NAME if _CORE else "",
        "page": caminho_pagina,
        "pageKind": page_kind,
        "sector": setor,
        "leadEndpoint": LEAD_ENDPOINT,
        "leadProvider": LEAD_PROVIDER,
        "contactEmail": CONTATO_EMAIL,
        "whatsapp": WHATSAPP,
        "analytics": ANALYTICS,
        "leadScoring": LEAD_SCORING,
        "freeEmailDomains": EMAILS_GRATUITOS,
        "eventCatalog": EVENTOS_ANALYTICS,
        "buildDate": (_CORE.EXECUTION_DATE if _CORE else ""),
    }
    return ('<script id="monitor-commercial-config" type="application/json">'
            + json.dumps(cfg, ensure_ascii=False) + "</script>")


def analytics_tags():
    """Carrega o fornecedor de analytics somente se estiver configurado no build.

    Sem configuração, nenhuma tag de terceiro é injetada (a camada própria em
    assets/commercial.js continua registrando dataLayer + buffer local).
    """
    tags = []
    ga4 = ANALYTICS.get("ga4_id")
    if ga4:
        tags.append(
            f'<script async src="https://www.googletagmanager.com/gtag/js?id={_esc(ga4)}"></script>\n'
            "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
            f"gtag('js',new Date());gtag('config','{_esc(ga4)}',{{'send_page_view':true}});</script>")
    pl = ANALYTICS.get("plausible_domain")
    if pl:
        src = ANALYTICS.get("plausible_src") or "https://plausible.io/js/script.js"
        tags.append(f'<script defer data-domain="{_esc(pl)}" src="{_esc(src)}"></script>')
    return "\n".join(tags)


def head_extras(caminho_pagina="", page_kind="", setor=""):
    return (f'<link rel="stylesheet" href="{_url("assets/commercial.css")}">\n'
            + config_script(caminho_pagina, page_kind, setor) + "\n"
            + (analytics_tags() + "\n" if analytics_tags() else "")
            + '<script src="' + _url("assets/commercial.js") + '" defer></script>')


def footer_column():
    links = "".join(f'<a href="{_url(p["path"])}">{_esc(p["nome"])}</a><br>' for p in PAGINAS)
    wa = whatsapp_link()
    wa_html = f'<br><a href="{wa}" target="_blank" rel="noopener" data-track="whatsapp_click">WhatsApp comercial</a>' if wa else ""
    return f"""<div>
      <h4>Contratar</h4>
      <p>{links}
      <a href="{_esc(CONSULTING_URL)}">LCF Consulting</a>{wa_html}</p>
      <p class="cta-mini"><a href="{link_diag()}" data-track="commercial_cta_click" data-cta="footer">{CTA_PRINCIPAL} →</a></p>
      <p class="disclaimer" style="margin-top:8px">{_esc(DISCLAIMER_COMERCIAL_CURTO)}</p>
    </div>"""


def page_kind(caminho):
    """Classifica a página para o analytics (fonte única usada no config injetado)."""
    p = (caminho or "").strip("/")
    if not p:
        return "monitor_home"
    mapa = {
        "solucoes": "pricing",
        "diagnostico": "lead_form",
        "briefing-executivo": "briefing_sample",
        "para-empresas": "commercial",
        "proposicoes": "proposicoes_lista",
        "atualizacoes": "atualizacoes",
        "leis": "leis",
        "timeline": "timeline",
        "parlamentares": "parlamentares",
        "agenda": "agenda",
        "monitoramento": "monitoramento",
        "metodologia": "metodologia",
        "relatorio": "relatorio",
        "alto-impacto": "high_impact",
    }
    primeiro = p.split("/")[0]
    if primeiro == "setores":
        return "sector_page"
    if primeiro == "casos-de-uso":
        return "use_case"
    if primeiro == "proposicoes" and p.count("/") >= 1:
        return "proposicao_ficha"
    return mapa.get(primeiro, primeiro)


def faixa_comercial_home(props, laws, updates, met=None):
    """Faixa comercial na home: posicionamento + CTA principal + secundário.

    Usa apenas números reais do dataset (nada de métrica inventada).
    """
    n_props = len(props)
    n_laws = len(laws)
    mudancas_30 = sum(1 for m in updates.get("mudancas", [])
                      if m.get("dias_atras") is not None and m["dias_atras"] <= 30)
    score_80 = sum(1 for p in props if (p.get("impacto") or {}).get("score", 0) >= 80)
    return f"""
<section class="block commercial-band" id="contratar"><div class="wrap">
  <div class="kicker">Inteligência regulatória de IA · Dados · Infraestrutura digital</div>
  <h2 class="section-title">Saiba o que mudou, por que isso importa para a sua operação e quem precisa agir</h2>
  <p class="section-sub">Este monitor público é a demonstração da nossa capacidade técnica. Para empresas,
  transformamos o mesmo dataset em priorização, briefing executivo, alertas configurados e análise de impacto —
  sempre com a fonte oficial ao lado de cada conclusão.</p>
  <div class="grid cols-4 commercial-proof">
    <div class="metric blue"><div class="num">{n_props}</div><div class="lbl">Proposições monitoradas</div></div>
    <div class="metric"><div class="num">{score_80}</div><div class="lbl">Matérias com score 80+</div></div>
    <div class="metric green"><div class="num">{n_laws}</div><div class="lbl">Normas vigentes mapeadas</div></div>
    <div class="metric yellow"><div class="num">{mudancas_30}</div><div class="lbl">Mudanças nos últimos 30 dias</div></div>
  </div>
  <div class="cta-box commercial-cta">
    <div>
      <h3>{_esc(CTA_PRINCIPAL)}</h3>
      <p>{_esc(CTA_PRINCIPAL_SUB)}</p>
    </div>
    <div class="cta-actions">
      {cta_principal()}
      {cta_secundario()}
      <a class="btn-ghost" href="{_url('solucoes/')}" data-track="pricing_view">Ver soluções e faixas de preço</a>
    </div>
  </div>
  <p class="disclaimer">{_esc(DISCLAIMER_COMERCIAL)}</p>
</div></section>"""


# ---------------------------------------------------------------------------
# 3. /solucoes/
# ---------------------------------------------------------------------------

def _card_solucao(s):
    entregas = "".join(
        "<li>" + _esc(e).replace("/briefing-executivo/",
                                 f'<a href="{_url("briefing-executivo/")}">/briefing-executivo/</a>')
        + "</li>" for e in s["entregas"])
    quem = "".join(f'<span class="tag">{_esc(q)}</span>' for q in s["para_quem"])
    selo = '<div class="plan-flag">Oferta principal</div>' if s.get("destaque") else ""
    nota = f'<p class="plan-note">{_esc(s["nota"])}</p>' if s.get("nota") else ""
    unidade = f'/{s["preco_unidade"]}' if s.get("preco_publico") else ""
    faixa_hint = ""
    if s.get("preco_publico"):
        faixa_hint = f'<p class="plan-hint">Faixa de referência por {s["preco_unidade"]} · proposta formal após o diagnóstico</p>'
    else:
        faixa_hint = '<p class="plan-hint">Escopo, SLA e volume definidos em proposta</p>'
    return f"""
<article class="card plan {'plan-destaque' if s.get('destaque') else ''}" id="{s['id']}" data-plan="{s['id']}">
  {selo}
  <h3>{_esc(s['nome'])}</h3>
  <p class="plan-resumo">{_esc(s['resumo'])}</p>
  <div class="plan-price"><span class="valor">{preco_rotulo(s)}</span><span class="unidade">{unidade}</span></div>
  {faixa_hint}
  <p class="plan-users"><b>Usuários:</b> {_esc(s['usuarios'])}</p>
  <h4 class="plan-sub">Para quem é</h4>
  <div class="tag-row">{quem}</div>
  <h4 class="plan-sub">O que está incluído</h4>
  <ul class="plan-list">{entregas}</ul>
  {nota}
  <div class="plan-cta">
    <a class="cta-btn" href="{link_diag(solucao=s['id'])}" data-track="commercial_cta_click"
       data-cta="plan-{s['id']}" data-plan="{s['id']}">{_esc(s['cta'])}</a>
  </div>
</article>"""


def build_solucoes(core, props, laws, updates, met):
    cards = "".join(_card_solucao(s) for s in SOLUCOES)

    # Tabela comparativa
    linhas = []
    recursos = [
        ("Monitor público + histórico + fontes oficiais", [1, 1, 1, "—"]),
        ("AI Legislative Impact Score e fatores", [1, 1, 1, "—"]),
        ("Alertas por e-mail (tema, órgão, score mínimo)", [1, 1, 1, "—"]),
        ("Relatório periódico do seu recorte", [1, 1, 1, 1]),
        ("Briefing executivo semanal", [0, 1, 1, 0]),
        ("Análise de impacto para o negócio por setor", [0, 1, 1, 1]),
        ("Agenda prioritária 7 e 30 dias", [0, 1, 1, 1]),
        ("Reunião executiva", [0, "Mensal", "Recorrente", "Workshop"]),
        ("Temas e órgãos personalizados", [0, 0, 1, 1]),
        ("API / webhook", [0, 0, 1, 0]),
        ("SLA contratual", [0, 0, 1, 0]),
        ("Multiusuário avançado / white-label", [0, 0, 1, 0]),
        ("Usuários", ["Até 3", "Até 10", "Conforme escopo", "Time do workshop"]),
        ("Investimento", [preco_rotulo(SOLUCOES[0]) + "/mês", preco_rotulo(SOLUCOES[1]) + "/mês",
                          "Sob consulta", preco_rotulo(SOLUCOES[3]) + "/projeto"]),
    ]
    for nome, vals in recursos:
        tds = "".join(
            "<td>" + ('<span class="yes">incluído</span>' if v == 1 else
                      '<span class="no">—</span>' if v == 0 else _esc(str(v))) + "</td>"
            for v in vals)
        linhas.append(f"<tr><th scope=\"row\">{nome}</th>{tds}</tr>")
    cabecalho = "".join(f"<th>{_esc(s['nome'])}</th>" for s in SOLUCOES)
    tabela = f"""<div class="table-scroll"><table class="tbl compare">
<thead><tr><th scope="col">Recurso</th>{cabecalho}</tr></thead>
<tbody>{''.join(linhas)}</tbody></table></div>"""

    dif = "".join(
        f"""<div class="card diff-card"><h3>{_esc(d['titulo'])}</h3><p>{_esc(d['texto'])}</p>
        <p class="diff-ev"><b>Evidência no produto:</b> {_esc(d['evidencia'])}</p></div>"""
        for d in DIFERENCIACAO)

    faq = "".join(f"""<details class="faq-item"><summary>{_esc(f['q'])}</summary>
    <p>{_esc(f['a'])}</p></details>""" for f in FAQ_SOLUCOES)

    n_props = len(props)
    n_laws = len(laws)

    body = f"""
<div class="hero"><div class="wrap">
  <div class="kicker">Soluções comerciais · LCF Consulting</div>
  <h1>Inteligência regulatória especializada em IA, dados e infraestrutura digital</h1>
  <p class="lead">Não vendemos volume de projetos de lei. Vendemos a resposta a quatro perguntas:
  <b>o que mudou</b>, <b>por que isso importa para a sua operação</b>, <b>quem precisa agir</b> e
  <b>qual evidência oficial sustenta a conclusão</b>.</p>
  <div class="updated">Base atual do monitor: {n_props} proposições, {n_laws} normas vigentes mapeadas,
  verificação automática diária das fontes oficiais. <a href="{_url('')}">Ver o monitor público →</a></div>
  <div class="hero-cta">{cta_principal()} {cta_secundario()}</div>
</div></div>

<section class="block" id="planos"><div class="wrap">
  <h2 class="section-title">Quatro formas de contratação</h2>
  <p class="section-sub">Faixas de referência publicadas para você comparar antes de falar com a gente.
  A proposta formal considera número de usuários, temas monitorados, frequência de briefing e integrações.</p>
  <div class="grid cols-2 plans">{cards}</div>
</div></section>

<section class="block" id="comparativo"><div class="wrap">
  <h2 class="section-title">Comparativo detalhado</h2>
  <p class="section-sub">O que está incluído em cada formato.</p>
  {tabela}
</div></section>

<section class="block" id="diferencial"><div class="wrap">
  <h2 class="section-title">Por que contratar este monitor e não um generalista</h2>
  <p class="section-sub">Não afirmamos ter mais dados — monitores generalistas cobrem mais assuntos.
  A nossa diferença é o recorte e o que fazemos com ele.</p>
  <div class="grid cols-3">{dif}</div>
</div></section>

{prova_social_block()}

<section class="block" id="como-funciona"><div class="wrap">
  <h2 class="section-title">Como começa</h2>
  <div class="grid cols-4 steps">
    <div class="card step"><span class="step-n">1</span><h3>Diagnóstico</h3>
      <p>Você responde um formulário curto ou faz o workshop. Levantamos temas, áreas expostas e o que já acompanha hoje.</p></div>
    <div class="card step"><span class="step-n">2</span><h3>Recorte e priorização</h3>
      <p>Definimos os temas e o score mínimo que importam para a sua operação e o que entra no seu briefing.</p></div>
    <div class="card step"><span class="step-n">3</span><h3>Piloto</h3>
      <p>Período inicial com briefing, alertas e reunião executiva, com registro de uso para decidir a continuidade.</p></div>
    <div class="card step"><span class="step-n">4</span><h3>Contrato recorrente</h3>
      <p>Assinatura mensal com SLA, usuários e integrações conforme a solução escolhida.</p></div>
  </div>
</div></section>

<section class="block" id="faq"><div class="wrap">
  <h2 class="section-title">Perguntas frequentes</h2>
  <div class="faq">{faq}</div>
  {disclaimer_block()}
</div></section>

{faixa_cta(titulo="Quer saber quais matérias afetam a sua operação?",
           subtitulo=CTA_PRINCIPAL_SUB)}
"""

    jsonld = _CORE.combine_ld(
        _CORE.ld_website(),
        _CORE.ld_breadcrumbs([("Início", ""), ("Soluções", None)]),
        {
            "@type": "ItemList",
            "name": "Soluções de inteligência regulatória de IA",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "item": {
                    "@type": "Service",
                    "name": s["nome"],
                    "serviceType": "Inteligência regulatória e monitoramento legislativo de IA",
                    "description": s["resumo"],
                    "provider": {"@type": "Organization", "name": _CORE.AUTHOR_ORG,
                                 "url": CONSULTING_URL},
                    "url": _url("solucoes/") + "#" + s["id"],
                    "audience": {"@type": "BusinessAudience",
                                 "description": ", ".join(s["para_quem"])},
                    **({"offers": {"@type": "Offer", "priceSpecification": preco_jsonld(s),
                                   "availability": "https://schema.org/InStock"}}
                       if preco_jsonld(s) else {"offers": {"@type": "Offer",
                                                           "priceSpecification": {
                                                               "@type": "PriceSpecification",
                                                               "priceCurrency": "BRL",
                                                               "description": "Sob consulta"},
                                                           "availability": "https://schema.org/InStock"}}),
                }}
                for i, s in enumerate(SOLUCOES)
            ],
        },
        {
            "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": f["q"],
                            "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                           for f in FAQ_SOLUCOES],
        },
    )
    core.write("solucoes/index.html", core.page(
        "Soluções e preços — Inteligência regulatória de IA | Monitor Legislativo de IA",
        "Quatro formas de contratação: Monitor IA, Radar Executivo de Regulação de IA, Inteligência "
        "Institucional e Diagnóstico de Exposição Regulatória. Faixas de referência, comparativo, "
        "metodologia e fontes oficiais.",
        "solucoes/", body,
        jsonld=jsonld))


# ---------------------------------------------------------------------------
# 4. /diagnostico/ — landing + captura de lead + lead scoring
# ---------------------------------------------------------------------------

def _options(lista, placeholder="Selecione…"):
    opts = "".join(f'<option value="{_esc(v)}">{_esc(v)}</option>' for v in lista)
    return f'<option value="" selected>{_esc(placeholder)}</option>{opts}'


def _campo(rotulo, name, controle, ajuda="", obrigatorio=True):
    req = " required" if obrigatorio else ""
    aria = "" if obrigatorio else ' <span class="opt">(opcional)</span>'
    return f"""<div class="field" data-field="{name}">
  <label for="f-{name}">{_esc(rotulo)}{aria}</label>
  {controle.replace('name="' + name + '"', 'name="' + name + '" id="f-' + name + '"' + req)}
  {f'<p class="help">{_esc(ajuda)}</p>' if ajuda else ''}
</div>"""


def build_diagnostico(core, props, laws, updates, met):
    n_props = len(props)
    n_laws = len(laws)
    mudancas_30 = sum(1 for m in updates.get("mudancas", [])
                      if m.get("dias_atras") is not None and m["dias_atras"] <= 30)
    ultima_exec = (updates.get("execucoes") or [{}])[0]
    cobertura = ultima_exec.get("cobertura_pct")

    entregas = "".join(f"<li>{_esc(e)}</li>" for e in SOLUCOES[3]["entregas"])

    form = f"""
<form id="form-diagnostico" class="lead-form" novalidate
      data-form="diagnostico" {form_attrs()}>
  <div class="form-grid">
    {_campo('Nome completo', 'nome', '<input type="text" name="nome" autocomplete="name" placeholder="Como você se chama">')}
    {_campo('Empresa / organização', 'empresa', '<input type="text" name="empresa" autocomplete="organization" placeholder="Razão social ou nome fantasia">', obrigatorio=True)}
    {_campo('Cargo', 'cargo', f'<select name="cargo">{_options(CARGOS)}</select>')}
    {_campo('E-mail corporativo', 'email', '<input type="email" name="email" autocomplete="email" placeholder="nome@suaempresa.com.br">',
            ajuda='Use o e-mail da empresa: o diagnóstico é enviado para o endereço corporativo.', obrigatorio=True)}
    {_campo('Telefone / WhatsApp', 'telefone', '<input type="tel" name="telefone" autocomplete="tel" placeholder="+55 11 90000-0000">',
            ajuda='Opcional — acelera o contato se você preferir conversa rápida.', obrigatorio=False)}
    {_campo('Setor', 'setor', f'<select name="setor">{_options(SETORES_FORM)}</select>')}
    {_campo('Tamanho aproximado da organização', 'tamanho', f'<select name="tamanho">{_options(TAMANHOS)}</select>',
            ajuda='Número de funcionários.')}
    {_campo('Como sua organização usa IA hoje', 'uso_ia', f'<select name="uso_ia">{_options(USO_IA)}</select>')}
    {_campo('Sua organização possui área de compliance, jurídico ou relações governamentais?', 'area',
            f'<select name="area">{_options(AREAS)}</select>')}
    {_campo('Qual é o seu horizonte de preocupação regulatória', 'horizonte', f'<select name="horizonte">{_options(HORIZONTES)}</select>')}
    {_campo('Principal preocupação regulatória', 'preocupacao', f'<select name="preocupacao">{_options(PREOCUPACOES)}</select>')}
    {_campo('Assunto de interesse', 'interesse', f'<select name="interesse">{_options(ASSUNTOS)}</select>',
            ajuda='Usamos isso para encaminhar ao formato certo (diagnóstico, assinatura, briefing, alertas ou demo).')}
    {_campo('Solução de interesse (opcional)', 'solucao', '<input type="text" name="solucao" placeholder="Ex.: Radar Executivo">', obrigatorio=False)}
    {_campo('Contexto adicional', 'mensagem', '<textarea name="mensagem" rows="4" placeholder="Descreva em poucas linhas o que sua operação faz com IA, quais áreas seriam afetadas e o que você precisa decidir."></textarea>', obrigatorio=False)}
  </div>

  <div class="consent field">
    <label class="check"><input type="checkbox" name="consentimento" id="f-consentimento" required>
      <span>Autorizo o contato comercial da LCF Consulting e o tratamento dos dados enviados para
      resposta deste pedido, nos termos da LGPD.</span></label>
    <p class="help">Controlador: {_esc(_CORE.AUTHOR_ORG)} ({_esc(CONSULTING_URL)}). Finalidade: contato
    comercial e qualificação do pedido de diagnóstico. Base legal: consentimento e legítimo interesse
    comercial. Os dados não são vendidos nem compartilhados para outra finalidade. Para revogar,
    escreva para {_esc(CONTATO_EMAIL)}.</p>
  </div>

  <div class="form-actions">
    <button type="submit" class="cta-btn btn-submit" data-track="diagnostic_submit">Enviar e solicitar diagnóstico</button>
    <span class="form-status" data-form-status role="status" aria-live="polite"></span>
  </div>
  <p class="form-mode">Modo de captura: <code data-lead-mode>{_esc(LEAD_PROVIDER)}</code></p>
  <div class="lead-debug" data-lead-debug hidden>
    <h4>Qualificação calculada (visível apenas com ?debug=1)</h4>
    <pre data-lead-debug-out></pre>
  </div>
  <input type="hidden" name="lead_score" data-lead-score value="">
  <input type="hidden" name="lead_classificacao" data-lead-class value="">
  <input type="hidden" name="lead_score_fatores" data-lead-factors value="">
  <input type="hidden" name="lead_payload" data-lead-payload value="">
  <input type="hidden" name="pagina_origem" data-lead-origin value="diagnostico">
  <input type="hidden" name="timestamp_envio" data-lead-ts value="">
  <input type="text" name="_gotcha" class="gotcha" tabindex="-1" autocomplete="off" aria-hidden="true">
</form>"""

    body = f"""
<div class="hero hero-diag"><div class="wrap">
  <div class="kicker">Diagnóstico de Exposição Regulatória · produto avulso, sem assinatura</div>
  <h1>Sua empresa sabe quais mudanças na regulação de IA podem afetá-la nos próximos meses?</h1>
  <p class="lead">O diagnóstico cruza a sua operação com o que está efetivamente tramitando e vigente
  hoje no Brasil — e devolve um retrato objetivo: temas prioritários, proposições relacionadas, riscos
  identificados e o que passar a monitorar, com a fonte oficial de cada afirmação.</p>
  <div class="updated">Base usada no diagnóstico: {n_props} proposições monitoradas · {n_laws} normas vigentes ·
  {mudancas_30} mudanças registradas nos últimos 30 dias · última verificação automática das fontes oficiais em
  <b>{_esc(str(ultima_exec.get('data_hora') or _CORE.EXECUTION_DATE))}</b>{f' · cobertura de {cobertura}%' if cobertura is not None else ''}.</div>
  <div class="hero-cta">{cta_principal(rotulo='Preencher o diagnóstico')} {cta_secundario()}</div>
</div></div>

<section class="block"><div class="wrap diag-layout">
  <div class="diag-form-col" id="formulario">
    <h2 class="section-title">Solicitar diagnóstico regulatório</h2>
    <p class="section-sub">Leva cerca de 2 minutos. Você recebe a proposta de diagnóstico e a leitura
    inicial do seu recorte — sem compromisso de assinatura.</p>
    <div class="alert-inline" data-lead-alert hidden></div>
    {form}
  </div>
  <aside class="diag-side">
    <div class="card">
      <h3>O que você recebe</h3>
      <ul class="plan-list">{entregas}</ul>
      <p class="plan-hint">Faixa de referência: {preco_rotulo(SOLUCOES[3])} por projeto.</p>
      <a class="btn-ghost" href="{_url('solucoes/')}#diagnostico-exposicao" data-track="pricing_view">Ver todas as soluções</a>
    </div>
    <div class="card">
      <h3>Como qualificamos o seu pedido</h3>
      <p>Cada envio recebe uma pontuação interna de prioridade comercial, calculada por regras fixas e
      auditáveis (porte, setor, cargo, área estruturada, horizonte declarado, uso de IA em processo
      crítico). Isso serve para responder primeiro quem tem decisão em andamento — e para encaminhar ao
      formato certo de contratação.</p>
      <p class="plan-hint">Regras: {len(LEAD_SCORING['regras'])} critérios · pontuação máxima
      {LEAD_SCORING['maximo']} · faixas: {', '.join(f['rotulo'] for f in reversed(LEAD_SCORING['faixas']))}.</p>
    </div>
    <div class="card">
      <h3>Prefere ver antes?</h3>
      <p>Publicamos uma amostra real do briefing executivo que um cliente recebe, gerada a partir dos
      mesmos dados que alimentam este formulário.</p>
      <a class="btn-ghost" href="{_url('briefing-executivo/')}" data-track="briefing_sample_view">{_esc(CTA_SECUNDARIO)}</a>
    </div>
    {_card_contato_direto()}
  </aside>
</div></section>

<section class="block"><div class="wrap">
  <h2 class="section-title">O que acontece depois do envio</h2>
  <div class="grid cols-3 steps">
    <div class="card step"><span class="step-n">1</span><h3>Qualificação e confirmação</h3>
      <p>Recebemos o pedido com a pontuação de prioridade e confirmamos por e-mail em até 1 dia útil.</p></div>
    <div class="card step"><span class="step-n">2</span><h3>Leitura inicial do seu recorte</h3>
      <p>Cruzamos setor, uso de IA e preocupação declarada com as matérias monitoradas de maior score.</p></div>
    <div class="card step"><span class="step-n">3</span><h3>Proposta de diagnóstico</h3>
      <p>Escopo, prazo, participantes do workshop e investimento — com a opção de seguir para assinatura.</p></div>
  </div>
  {disclaimer_block()}
</div></section>

{faixa_cta(titulo='Precisa de um recorte setorial específico?',
           subtitulo='Diga o setor e o tema: montamos o levantamento de exposição a partir das matérias já monitoradas.')}
"""

    jsonld = _CORE.combine_ld(
        _CORE.ld_website(),
        _CORE.ld_breadcrumbs([("Início", ""), ("Diagnóstico", None)]),
        {
            "@type": "Service",
            "name": "Diagnóstico de Exposição Regulatória em IA",
            "serviceType": "Inteligência regulatória — levantamento de exposição e priorização",
            "description": "Workshop, levantamento de exposição regulatória em IA, temas prioritários, "
                           "proposições relacionadas, riscos identificados, relatório executivo e "
                           "recomendações de monitoramento.",
            "provider": {"@type": "Organization", "name": _CORE.AUTHOR_ORG, "url": CONSULTING_URL},
            "areaServed": {"@type": "Country", "name": "Brasil"},
            "url": _url("diagnostico/"),
            "offers": {"@type": "Offer", "priceSpecification": preco_jsonld(SOLUCOES[3]),
                       "availability": "https://schema.org/InStock"},
        },
    )
    core.write("diagnostico/index.html", core.page(
        "Diagnóstico de Exposição Regulatória em IA — Solicitar diagnóstico | Monitor Legislativo de IA",
        "Sua empresa sabe quais mudanças na regulação de IA podem afetá-la nos próximos meses? "
        "Solicite o diagnóstico de exposição regulatória: temas prioritários, proposições relacionadas, "
        "riscos e recomendações de monitoramento, com fonte oficial.",
        "diagnostico/", body,
        jsonld=jsonld))


def _card_contato_direto():
    wa = whatsapp_link()
    wa_html = (f'<a class="btn-ghost wa" href="{wa}" target="_blank" rel="noopener" '
               f'data-track="whatsapp_click">Falar no WhatsApp</a>') if wa else ""
    return f"""<div class="card">
      <h3>Contato direto</h3>
      <p>Se preferir, fale diretamente com a {_esc(_CORE.AUTHOR_ORG)}.</p>
      <p class="plan-hint"><a href="mailto:{_esc(CONTATO_EMAIL)}?subject=Diagn%C3%B3stico%20regulat%C3%B3rio%20de%20IA"
      data-track="commercial_cta_click" data-cta="email">{_esc(CONTATO_EMAIL)}</a></p>
      {wa_html}
      <a class="btn-ghost" href="{_esc(CONSULTING_URL)}" data-track="commercial_cta_click"
         data-cta="lcf-site">lcfconsulting.com.br</a>
    </div>"""


# ---------------------------------------------------------------------------
# 5. /briefing-executivo/ — amostra do produto pago com dados REAIS
# ---------------------------------------------------------------------------

def _fato_analise_blocos(b):
    f = b["fato_oficial"]
    a = b["analise"]
    sc = b["score"]

    def linha(rotulo, valor):
        if not valor:
            return ""
        return f'<div class="kv-row"><span class="k">{_esc(rotulo)}</span><span class="v">{_esc(str(valor))}</span></div>'

    fato_rows = "".join([
        linha("Situação oficial", f.get("situacao")),
        linha("Estágio", f.get("estagio")),
        linha("Casa / órgão atual", f.get("casa_atual")),
        linha("Comissão", f.get("comissao_atual")),
        linha("Relatoria", (f"{f.get('relator')} ({f.get('relator_partido')})"
                            if f.get("relator") and f.get("relator_partido") else f.get("relator"))),
        linha("Última movimentação oficial",
              (f"{_brief._fmt(f.get('ultima_movimentacao_data'))} — {f.get('ultima_movimentacao')}"
               if f.get("ultima_movimentacao") else None)),
        linha("Próxima etapa registrada", f.get("proxima_etapa")),
        linha("Obrigações criadas pelo texto", f.get("obrigacoes_criadas")),
        linha("Vedações do texto", f.get("proibicoes")),
        linha("Órgãos responsáveis", f.get("orgaos_responsaveis")),
        linha("Apensados", f.get("total_apensados")),
    ])
    if f.get("aguardando_curadoria"):
        fato_rows += '<div class="kv-row"><span class="k">Curadoria</span><span class="v">' \
                     '<span class="tag review">registro automático aguardando curadoria editorial</span></span></div>'

    selos = []
    if a["impacto_em_compliance"]:
        selos.append("Compliance")
    if a["impacto_em_dados"]:
        selos.append("Dados pessoais")
    if a["impacto_em_modelos_de_ia"]:
        selos.append("Modelos de IA")
    if a["impacto_em_infraestrutura"]:
        selos.append("Infraestrutura")
    setores_html = "".join(f'<span class="tag">{_esc(s)}</span>' for s in a["setores_afetados"][:10])
    selos_html = "".join(f'<span class="tag impact">{_esc(s)}</span>' for s in selos) or \
        '<span class="tag">Não identificado no registro público</span>'

    fonte = ""
    if f.get("url_oficial"):
        oficial = "fonte primária oficial" if f.get("url_oficial_eh_fonte_primaria") else "fonte registrada"
        fonte = (f'<a href="{_esc(f["url_oficial"])}" target="_blank" rel="noopener">'
                 f'Abrir {_esc(oficial)} ↗</a>')

    fatores = sc.get("fatores") or []
    if fatores and fatores[0].get("pontos") is not None:
        fat_html = "".join(
            f'<li><b>{_esc(x["criterio"])}</b> — {x["pontos"]}/{x["maximo"]} pontos</li>'
            for x in fatores)
        fat_titulo = "Como o score foi composto (rúbrica pública de 9 critérios)"
    else:
        fat_html = "".join(f'<li>{_esc(x["criterio"])}</li>' for x in fatores) or \
            "<li>Sem detalhamento adicional no registro público.</li>"
        fat_titulo = "Fatores observados que sustentam esta faixa de score"

    mudancas = f.get("mudancas_registradas") or []
    mud_html = "".join(
        f'<li><b>{_esc(m["data_fmt"])}</b> · {_esc(m["tipo"] or "mudança")} — {_esc(m["titulo"])}</li>'
        for m in mudancas[:3]) or "<li>Nenhuma mudança registrada para esta matéria no histórico recente.</li>"

    return f"""
<article class="brief-item" data-score="{sc['valor']}" data-impacto="{_esc(a['impacto_potencial'])}">
  <header class="brief-head">
    <div>
      <h3>{_esc(f['titulo'])} — {_esc(f['nome'])}</h3>
      <p class="brief-sub">{_esc((f.get('resumo') or f.get('ementa') or '')[:300])}</p>
    </div>
    <div class="brief-score">
      <span class="score-badge {_CORE.score_class(sc['valor'])}">Score {sc['valor']}/100 · {_esc(sc['classificacao'].split(' (')[0])}</span>
      <span class="impact-pill impact-{_esc(a['impacto_potencial'].lower())}">Impacto potencial: {_esc(a['impacto_potencial'])}</span>
    </div>
  </header>

  <div class="brief-cols">
    <div class="brief-col fato">
      <h4><span class="col-tag tag-fato">Fato oficial</span></h4>
      <p class="col-note">{_esc(DISCLAIMER_FATO)}</p>
      <div class="kv">{fato_rows or '<div class="kv-row"><span class="v">Sem campos adicionais registrados.</span></div>'}</div>
      <p class="fonte"><b>Fonte oficial:</b> {fonte or '—'}</p>
    </div>
    <div class="brief-col analise">
      <h4><span class="col-tag tag-analise">Análise / interpretação</span></h4>
      <p class="col-note">{_esc(DISCLAIMER_ANALISE)}</p>
      <div class="kv">
        <div class="kv-row"><span class="k">Por que importa</span><span class="v">{_esc(a['por_que_importa'])}</span></div>
        <div class="kv-row"><span class="k">Ação recomendada</span><span class="v"><b>{_esc(a['acao_recomendada'])}</b>
          <small>(critério: {_esc(a['acao_recomendada_criterio'])})</small></span></div>
        <div class="kv-row"><span class="k">Prazo provável</span><span class="v">{_esc(a['prazo_provavel'] or 'Não informado na fonte oficial')}</span></div>
        <div class="kv-row"><span class="k">Obrigação potencial</span><span class="v">{_esc(a['obrigacao_potencial'] or 'Não detalhada no registro público')}</span></div>
        <div class="kv-row"><span class="k">Risco operacional</span><span class="v">{_esc(a['risco_operacional'])}</span></div>
        <div class="kv-row"><span class="k">Áreas de impacto</span><span class="v">{selos_html}</span></div>
        <div class="kv-row"><span class="k">Status da interpretação</span><span class="v">{_esc(a['status_interpretacao'])}</span></div>
        <div class="kv-row"><span class="k">Base da análise</span><span class="v"><code>{_esc(', '.join(a['base_da_analise']))}</code></span></div>
      </div>
      <p class="quem"><b>Quem pode ser afetado:</b></p>
      <div class="tag-row">{setores_html}</div>
    </div>
  </div>

  <details class="brief-more">
    <summary>Por que esta matéria recebeu score {sc['valor']}?</summary>
    <p class="col-note">{_esc(fat_titulo)}</p>
    <ul class="fatores">{fat_html}</ul>
    <p class="col-note">Rúbrica completa e faixas em <a href="{_url('metodologia/')}">metodologia</a>.</p>
  </details>

  <details class="brief-more">
    <summary>Histórico de mudanças registradas</summary>
    <ul class="mudancas">{mud_html}</ul>
  </details>

  <p class="brief-link"><a href="{_url('proposicoes/')}{_slug(f['id'])}/">Ver ficha completa no monitor público →</a></p>
</article>"""


def _slug(pid):
    return _CORE.slugify_prop(pid) if _CORE else pid


def build_briefing_executivo(core, props, laws, events, updates, cats):
    execucao = updates.get("meta", {}).get("execucao") or _CORE.EXECUTION_DATE
    b = _brief.build_brief(props, updates, events, laws, cats, execucao)
    meta = b["meta"]

    # Mudanças críticas do período
    if b["mudancas_criticas"]:
        crit = "".join(_card_mudanca(m) for m in b["mudancas_criticas"])
        if len(b["mudancas_criticas"]) <= 2:
            crit = ('<div class="note">Semana com pouca movimentação oficial no recorte monitorado '
                    f'({len(b["mudancas_criticas"])} registro). O monitor não infla a lista: o contexto '
                    'completo dos últimos 30 dias está na seção 7.</div>') + crit
    else:
        crit = ('<div class="note">Nenhuma mudança com data de evento registrada neste período. '
                'O monitoramento seguiu ativo: a verificação está registrada no '
                f'<a href="{_url("monitoramento/")}">painel de monitoramento</a>.</div>')

    ctx = "".join(_card_mudanca(m) for m in b["mudancas_30_dias"][:8]) or \
        '<div class="note">Sem mudanças registradas nos últimos 30 dias.</div>'

    desde = "".join(_card_mudanca(m) for m in b["desde_ultimo_relatorio"][:10]) or \
        ('<div class="note">Nenhuma mudança entre a execução anterior e a atual do monitoramento '
         '(ou histórico insuficiente para comparar).</div>')

    top_html = "".join(_fato_analise_blocos(x) for x in b["top_materias"])

    # Agenda
    agenda_html = "".join(_card_evento(e) for e in b["agenda"]["proximos_dias"]) or \
        '<div class="note">Nenhum evento oficial com data confirmada nos próximos 7 dias.</div>'
    sem_data = "".join(_card_evento(e) for e in b["agenda"]["sem_data_confirmada"])
    alem = "".join(_card_evento(e) for e in b["agenda"]["alem_da_janela"][:6])

    # Impactos por setor (top 8)
    setores_html = "".join(_card_setor(s) for s in b["setores"][:8])

    atencao_html = "".join(
        f"""<li><b>{_esc(a['ponto'])}</b> — {_esc(a['detalhe'])}
        <span class="base">base: {_esc(a['base'])}</span></li>"""
        for a in b["atencao_executiva"]) or "<li>Sem pontos de destaque nesta execução.</li>"

    fontes_html = "".join(
        f'<li><a href="{_esc(f["url"])}" target="_blank" rel="noopener">{_esc(f["url"])}</a>'
        f' <span class="base">({_esc(f["referencia"])})</span></li>'
        for f in b["fontes_oficiais"][:20])

    alerta_form = f"""
<form id="form-alerta" class="alert-form" data-form="alerta" {form_attrs()} novalidate>
  <h3>Receber este briefing por e-mail</h3>
  <p class="section-sub">Amostra pública é gerada a partir do dataset do monitor. Clientes recebem o
  briefing no seu recorte (temas, setores, órgãos e score mínimo), na frequência escolhida.</p>
  <div class="alert-grid">
    <div class="field"><label for="a-email">E-mail corporativo</label>
      <input type="email" id="a-email" name="email" required placeholder="nome@suaempresa.com.br"></div>
    <div class="field"><label for="a-setor">Setor</label>
      <select id="a-setor" name="setor">{_options(SETORES_FORM)}</select></div>
    <div class="field"><label for="a-freq">Frequência</label>
      <select id="a-freq" name="frequencia"><option value="imediato">Imediato (alerta crítico)</option>
      <option value="diario">Diário</option><option value="semanal" selected>Semanal</option></select></div>
    <div class="field"><label for="a-score">Score mínimo</label>
      <select id="a-score" name="score_minimo"><option value="0">Todas as matérias</option>
      <option value="60">Score 60+</option><option value="80" selected>Score 80+</option></select></div>
    <div class="field"><label for="a-tema">Tema prioritário<span class="opt"> (opcional)</span></label>
      <input type="text" id="a-tema" name="tema" placeholder="Ex.: data centers, biometria, PL 2338"></div>
  </div>
  <label class="check"><input type="checkbox" name="consentimento" required>
    <span>Autorizo o envio de alertas e o contato comercial (LGPD).</span></label>
  <div class="form-actions">
    <button type="submit" class="cta-btn" data-track="alert_signup">Ativar alertas</button>
    <span class="form-status" data-form-status role="status" aria-live="polite"></span>
  </div>
  <input type="hidden" name="interesse" value="Alertas por e-mail">
  <input type="hidden" name="pagina_origem" value="briefing-executivo">
  <input type="hidden" name="lead_payload" data-lead-payload value="">
  <input type="text" name="_gotcha" class="gotcha" tabindex="-1" autocomplete="off" aria-hidden="true">
</form>"""

    body = f"""
<div class="hero hero-brief"><div class="wrap">
  <div class="kicker">Amostra do produto · Executive Regulatory Brief</div>
  <h1>Exemplo de briefing executivo</h1>
  <p class="lead">Este é o formato que um cliente do Radar Executivo recebe. <b>Tudo aqui foi gerado a
  partir dos dados reais do monitor público</b> na execução de {_esc(str(meta['referencia_fmt']))} —
  nenhuma informação foi criada para a demonstração.</p>
  <div class="updated">Referência: {_esc(str(meta['referencia_fmt']))} · {meta['total_proposicoes']} proposições ·
  {meta['total_normas']} normas · {meta['total_mudancas_no_periodo']} mudança(s) nos últimos
  {meta['periodo_mudancas_dias']} dias · {meta['proposicoes_score_80_mais']} matérias com score 80+</div>
  <div class="hero-cta">
    <button class="btn-ghost" type="button" data-print-brief>Imprimir / salvar em PDF</button>
    {cta_principal(interesse='briefing', rotulo='Receber este briefing toda semana')}
  </div>
</div></div>

<section class="block brief-section" id="mudancas-criticas"><div class="wrap">
  <h2 class="section-title">1. Mudanças críticas do período</h2>
  <p class="section-sub">Janela de {meta['periodo_mudancas_dias']} dias até {_esc(str(meta['referencia_fmt']))}.
  Severidade derivada do tipo de movimentação e do score da matéria. Volume real:
  {meta['total_mudancas_no_periodo']} na janela · {meta['total_mudancas_30_dias']} em 30 dias.</p>
  {crit}
</div></section>

<section class="block brief-section" id="top-materias"><div class="wrap">
  <h2 class="section-title">2. Top {len(b['top_materias'])} matérias por impacto</h2>
  <p class="section-sub">Cada bloco separa explicitamente <span class="col-tag tag-fato">fato oficial</span>
  de <span class="col-tag tag-analise">análise</span>. A ação recomendada é uma sugestão de priorização
  operacional — não é aconselhamento jurídico.</p>
  {top_html}
</div></section>

<section class="block brief-section" id="desde-ultimo"><div class="wrap">
  <h2 class="section-title">3. Mudanças desde o último relatório</h2>
  <p class="section-sub">Critério aplicado: {_esc(str(b['criterio_desde_ultimo_relatorio'] or 'execução anterior do monitoramento'))}.
  Log auditável em <code>updates.json</code>.</p>
  {desde}
</div></section>

<section class="block brief-section" id="agenda"><div class="wrap">
  <h2 class="section-title">4. Agenda dos próximos 7 dias</h2>
  <p class="section-sub">Eventos oficiais e marcos normativos. Itens sem data confirmada são listados
  à parte, como fazem os clientes que precisam se programar.</p>
  <div class="grid cols-2">{agenda_html}</div>
  {f'<h3 class="mini-title">Marcos previstos sem data oficial confirmada</h3><div class="grid cols-2">{sem_data}</div>' if sem_data else ''}
  {f'<h3 class="mini-title">Além dos 7 dias</h3><div class="grid cols-2">{alem}</div>' if alem else ''}
</div></section>

<section class="block brief-section" id="setores"><div class="wrap">
  <h2 class="section-title">5. Possíveis impactos por setor</h2>
  <p class="section-sub">Agregação determinística: categorias temáticas das matérias monitoradas mapeadas
  para setores (tabela pública em <code>scripts/brief.py</code>).</p>
  <div class="grid cols-3">{setores_html}</div>
</div></section>

<section class="block brief-section" id="atencao"><div class="wrap">
  <h2 class="section-title">6. Pontos que merecem atenção executiva</h2>
  <ul class="atencao">{atencao_html}</ul>
</div></section>

<section class="block brief-section" id="contexto-30"><div class="wrap">
  <h2 class="section-title">7. Contexto dos últimos 30 dias</h2>
  <p class="section-sub">Para quando a semana é silenciosa: o que se moveu no mês.</p>
  {ctx}
</div></section>

<section class="block brief-section" id="fontes"><div class="wrap">
  <h2 class="section-title">8. Fontes oficiais citadas</h2>
  <ul class="fontes">{fontes_html}</ul>
</div></section>

<section class="block brief-section" id="metodologia-brief"><div class="wrap">
  <h2 class="section-title">9. Metodologia deste briefing</h2>
  <div class="grid cols-2">
    <div class="card"><h3>Como é gerado</h3>
      <p>Conteúdo montado por <code>scripts/brief.py</code> a partir exclusivamente de
      <code>data/legislation/*.json</code>: proposições, mudanças, agenda, normas e categorias.
      O AI Legislative Impact Score segue a rúbrica pública de 9 critérios descrita em
      <a href="{_url('metodologia/')}">metodologia</a>.</p>
      <p><b>Periodicidade:</b> semanal para clientes, com alertas críticos fora de ciclo quando uma
      matéria muda de estágio, de relatoria, entra em pauta ou tem alteração relevante de score.</p></div>
    <div class="card"><h3>Limite do que afirmamos</h3>
      <p>Fatos vêm de campos do dataset com fonte oficial linkada. Análise é interpretação derivada de
      regras públicas e aparece sempre sinalizada, com a base objetiva declarada e o status da
      interpretação (curadoria editorial ou leitura automatizada).</p>
      <p>Nada aqui é parecer, aconselhamento jurídico ou garantia de conformidade.</p></div>
  </div>
  {disclaimer_block()}
</div></section>

<section class="block" id="alertas"><div class="wrap">
  {alerta_form}
</div></section>

{faixa_cta(titulo='Quer este briefing no seu recorte?',
           subtitulo='Temas, setores, órgãos e score mínimo definidos com você — semanal, com reunião executiva mensal.')}
"""

    jsonld = _CORE.combine_ld(
        _CORE.ld_website(),
        _CORE.ld_breadcrumbs([("Início", ""), ("Exemplo de briefing executivo", None)]),
        {
            "@type": "Report",
            "name": f"Executive Regulatory Brief — amostra de {_esc(str(meta['referencia_fmt']))}",
            "description": "Amostra pública do briefing executivo de regulação de IA gerada a partir "
                           "dos dados reais do monitor legislativo.",
            "datePublished": meta["referencia"],
            "inLanguage": "pt-BR",
            "creator": {"@type": "Organization", "name": _CORE.AUTHOR_ORG, "url": CONSULTING_URL},
            "about": {"@type": "Thing", "name": "Regulação de Inteligência Artificial no Brasil"},
            "url": _url("briefing-executivo/"),
        },
    )
    core.write("briefing-executivo/index.html", core.page(
        "Exemplo de briefing executivo de regulação de IA — amostra real | Monitor Legislativo de IA",
        "Amostra real do briefing executivo de inteligência regulatória de IA: o que mudou, por que "
        "importa, quem pode ser afetado, impacto potencial, próxima decisão relevante, fonte oficial, "
        "AI Legislative Impact Score e ação recomendada.",
        "briefing-executivo/", body,
        jsonld=jsonld))


def _slug_setor(nome):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(nome)).encode("ascii", "ignore").decode("ascii")
    return t.lower().replace(" ", "-").replace("/", "-")


def _card_setor(s):
    """Card de impacto por setor na amostra do briefing (base das páginas P1)."""
    top = s.get("top")
    if top:
        href = _url("proposicoes/") + _slug(top["id"]) + "/"
        maior = (f'<p>Maior exposição: <a href="{href}">{_esc(top["rotulo"])}</a> '
                 f'(score {top["score"]} · impacto {_esc(top["impacto_potencial"])})</p>')
    else:
        maior = ""
    diag = link_diag(setor=_slug_setor(s["setor"]), interesse="briefing-setorial")
    return f"""<div class="card setor-card" data-setor="{_esc(s['setor'])}">
      <h3>{_esc(s['setor'])}</h3>
      <p><b>{s['proposicoes']}</b> matérias monitoradas · <b>{s['criticos']}</b> com score 85+</p>
      {maior}
      <a class="btn-mini" href="{diag}" data-track="sector_page_view"
         data-setor="{_esc(s['setor'])}">Receber briefing deste setor</a>
    </div>"""


def _card_mudanca(m):
    href = (_url("proposicoes/") + _slug(m["proposicao_id"]) + "/") if m.get("proposicao_id") else None
    titulo = _esc(m["titulo"] or "")
    if href:
        titulo = f'<a href="{href}">{titulo}</a>'
    fonte = ""
    if m.get("fonte_url"):
        rotulo = "Fonte oficial ↗" if m.get("fonte_oficial") else "Fonte registrada ↗"
        fonte = (f'<a class="fonte-link" href="{_esc(m["fonte_url"])}" target="_blank" '
                 f'rel="noopener">{rotulo}</a>')
    score_html = ""
    if m.get("score"):
        score_html = (f'<span class="score-badge {_CORE.score_class(m["score"])}">Score {m["score"]}</span>')
        if m.get("impacto_potencial"):
            score_html += f'<span class="tag impact">Impacto {m["impacto_potencial"]}</span>'
    return f"""
<div class="card change-brief sev-{_esc(m['severidade'])}">
  <div class="change-top">
    <span class="when">{_esc(m['data_fmt'])} · {_esc(m['tipo'] or 'mudança')}</span>
    <span class="sev">Severidade comercial: {_esc(m['severidade'])}</span>
  </div>
  <h3>{titulo}</h3>
  <p>{_esc(m['descricao'] or '')}</p>
  <div class="meta">{score_html}{fonte}</div>
</div>"""


def _card_evento(e):
    fonte = ""
    if e.get("fonte_url"):
        rotulo = "Fonte oficial ↗" if e.get("fonte_oficial") else "Fonte registrada ↗"
        fonte = (f'<a class="fonte-link" href="{_esc(e["fonte_url"])}" target="_blank" rel="noopener">{rotulo}</a>')
    quando = e["data_fmt"]
    if e.get("dias") is not None and e["dias"] >= 0:
        quando += f" (em {e['dias']} dia{'s' if e['dias'] != 1 else ''})"
    completo = ""
    if e.get("titulo_completo") and e.get("titulo_completo") != e.get("titulo"):
        completo = (f'<details class="brief-more"><summary>Programação registrada na fonte</summary>'
                    f'<p>{_esc(e["titulo_completo"])}</p></details>')
    return f"""
<div class="card agenda-brief">
  <h3>{_esc(e['titulo'])}</h3>
  <p class="when">{_esc(quando)} · {_esc(e.get('casa') or '—')} · {_esc(e.get('tipo') or '—')}</p>
  {f'<p>{_esc(e.get("hora"))} · {_esc(e.get("local"))}</p>' if e.get('local') and e.get('local') != '—' else ''}
  {f'<p>{_esc(e.get("tema"))}</p>' if e.get('tema') else ''}
  {f'<p class="rel"><b>Relação com IA:</b> {_esc(e.get("relacao_ia"))}</p>' if e.get('relacao_ia') else ''}
  {completo}
  <div class="meta">{fonte}</div>
</div>"""


# ---------------------------------------------------------------------------
# 6. /para-empresas/
# ---------------------------------------------------------------------------

def build_para_empresas(core, props, laws, events, updates, met):
    n_props = len(props)
    n_laws = len(laws)
    n_events = len(events.get("eventos", []))
    mudancas = updates.get("mudancas", [])
    mud_30 = sum(1 for m in mudancas if m.get("dias_atras") is not None and m["dias_atras"] <= 30)
    score_80 = sum(1 for p in props if (p.get("impacto") or {}).get("score", 0) >= 80)
    execucoes = updates.get("execucoes") or []
    n_exec = len(execucoes)
    ultima = execucoes[0] if execucoes else {}
    cobertura = ultima.get("cobertura_pct")

    problemas = [
        ("A mudança aparece tarde", "Quando a matéria já está em pauta ou sancionada, o custo de adaptação "
         "deixa de ser uma escolha e vira um prazo."),
        ("Existe volume, não priorização", "Monitores generalistas entregam muitas matérias e nenhuma "
         "hierarquia. O time não sabe o que exige atuação agora."),
        ("Falta tradução para o negócio", "O evento legislativo chega em linguagem de tramitação; a "
         "decisão precisa de consequência operacional, área responsável e prazo."),
        ("Sem evidência auditável", "Conclusões sem link para a fonte oficial não sustentam decisão de "
         "comitê, conselho ou regulador."),
    ]
    prob_html = "".join(f"""<div class="card"><h3>{_esc(t)}</h3><p>{_esc(x)}</p></div>"""
                        for t, x in problemas)

    pilares = [
        ("Monitoramento especializado", "Recorte em IA, dados, infraestrutura digital e tecnologias de alta "
         f"consequência regulatória: {n_props} proposições, {n_laws} normas vigentes e {n_events} eventos de agenda.",
         "proposicoes/"),
        ("AI Legislative Impact Score", f"Rúbrica pública de 9 critérios. Hoje {score_80} matérias estão na "
         "faixa 80+, e cada ficha mostra os fatores que sustentam a pontuação.", "metodologia/"),
        ("Histórico e auditabilidade", "Cada mudança fica registrada com data, tipo, descrição e link da fonte. "
         "O log de execuções do cron é público.", "atualizacoes/"),
        ("Análise de impacto para o negócio", "Setores afetados, obrigação potencial, prazo provável, risco "
         "operacional e ação recomendada — separados do fato oficial.", "briefing-executivo/"),
        ("Alertas configuráveis", "Por tema, proposição, órgão, score mínimo e frequência (imediato, diário ou "
         "semanal). Arquitetura preparada para webhook, Slack e Teams.", "diagnostico/"),
        ("Briefing executivo e reunião", "Briefing semanal no formato publicado como amostra e reunião mensal "
         "de leitura do cenário com o seu time.", "briefing-executivo/"),
    ]
    pil_html = "".join(f"""<div class="card"><h3>{_esc(t)}</h3><p>{_esc(x)}</p>
    <p><a href="{_url(l)}">Ver no produto →</a></p></div>""" for t, x, l in pilares)

    seguranca = [
        ("Dados versionados", "O dataset é versionado em Git: cada alteração tem commit, data e diff "
         "recuperável — não há edição silenciosa."),
        ("Fonte oficial por afirmação", "Fatos legislativos apontam para Câmara, Senado, Congresso, "
         "Planalto, DOU, TSE, CNJ ou ANPD."),
        ("Separação fato × análise", "A camada de interpretação é rotulada e traz a base objetiva usada, "
         "inclusive o status de curadoria."),
        ("Correções registradas", "Correções entram como registro novo, preservando o histórico anterior."),
        ("Telemetria do monitoramento", f"Cobertura, latência e status da última execução publicados "
         f"(última: {_esc(str(ultima.get('data_hora') or '—'))}{f', cobertura de {cobertura}%' if cobertura is not None else ''})."),
        ("LGPD no comercial", "Dados de formulário usados só para contato e qualificação do pedido, sob "
         "responsabilidade da LCF Consulting, com consentimento explícito."),
    ]
    seg_html = "".join(f"""<div class="card"><h3>{_esc(t)}</h3><p>{_esc(x)}</p></div>""" for t, x in seguranca)

    personas = [
        ("Relações governamentais", "Priorize quais matérias exigem atuação nesta semana e em qual estágio."),
        ("Jurídico regulatório", "Identifique alterações regulatórias antes que virem obrigação vigente."),
        ("Compliance", "Receba o recorte de deveres, prazos e áreas afetadas para atualizar o programa."),
        ("Diretoria executiva", "Receba apenas mudanças com impacto potencial relevante, em uma página."),
    ]
    per_html = "".join(f"""<div class="card persona"><h3>{_esc(t)}</h3><p>{_esc(x)}</p>
    <a class="btn-mini" href="{link_diag(interesse='persona')}">Receber diagnóstico para esta área</a></div>"""
                       for t, x in personas)

    wa = whatsapp_link()
    demo_wa = ""
    if wa:
        demo_wa = (f'<a class="btn-ghost wa" href="{wa}" target="_blank" rel="noopener" '
                   f'data-track="whatsapp_click">WhatsApp</a>')

    body = f"""
<div class="hero"><div class="wrap">
  <div class="kicker">Para empresas · comprador corporativo</div>
  <h1>Inteligência regulatória de IA para quem não pode descobrir mudanças legislativas tarde demais</h1>
  <p class="lead">Transformamos o monitoramento legislativo de IA, dados e infraestrutura digital em
  priorização executiva: o que mudou, por que importa para a sua operação, quem precisa agir e qual
  evidência oficial sustenta a conclusão.</p>
  <div class="hero-cta">
    {cta_principal()}
    <a class="btn-ghost" href="{link_diag(interesse='demo')}" data-track="demo_request">{_esc(CTA_DEMO)}</a>
    {cta_secundario()}
  </div>
</div></div>

<section class="block" id="problema"><div class="wrap">
  <h2 class="section-title">O problema</h2>
  <p class="section-sub">O custo de descobrir tarde não é a informação perdida — é o prazo de adaptação.</p>
  <div class="grid cols-2">{prob_html}</div>
</div></section>

<section class="block" id="solucao"><div class="wrap">
  <h2 class="section-title">A solução</h2>
  <p class="section-sub">Seis camadas sobre o mesmo dataset público — você pode verificar cada uma antes
  de contratar.</p>
  <div class="grid cols-3">{pil_html}</div>
</div></section>

<section class="block" id="metodo"><div class="wrap">
  <h2 class="section-title">Metodologia e fontes oficiais</h2>
  <div class="grid cols-2">
    <div class="card"><h3>Coleta</h3>
      <p>Verificação automática diária nas APIs de dados abertos da Câmara dos Deputados e do Senado
      Federal, complementada por Congresso Nacional, Planalto, Diário Oficial da União, TSE, CNJ e ANPD.
      O comparador de estado detecta mudança de relatoria, parecer, pauta, votação, apensação, sanção e
      arquivamento.</p>
      <p><a href="{_url('metodologia/')}">Metodologia completa →</a> ·
      <a href="{_url('monitoramento/')}">Telemetria do cron →</a></p></div>
    <div class="card"><h3>Classificação</h3>
      <p>Cada matéria recebe o AI Legislative Impact Score por rúbrica pública e reproduzível:
      abrangência regulatória, estágio de tramitação, proximidade de votação, urgência, apensados,
      impacto econômico, impacto sobre direitos, alcance setorial e relevância institucional.</p>
      <p><a href="{_url('proposicoes/')}">Ver matérias com filtros de score →</a></p></div>
    <div class="card"><h3>Tradução empresarial</h3>
      <p>Camada de análise converte o evento legislativo em consequência operacional: setores afetados,
      tipo de impacto, prazo provável, obrigação potencial, risco operacional e ação recomendada — com a
      base objetiva declarada.</p>
      <p><a href="{_url('briefing-executivo/')}">Ver a amostra do briefing →</a></p></div>
    <div class="card"><h3>Velocidade</h3>
      <p>Fluxo: mudança detectada na fonte oficial → classificação por score → alerta → briefing.
      A latência do ciclo é medida e publicada no painel de monitoramento.</p>
      <p><a href="{_url('relatorio/')}">Relatório da execução →</a></p></div>
  </div>
</div></section>

<section class="block" id="seguranca"><div class="wrap">
  <h2 class="section-title">Segurança e auditabilidade</h2>
  <p class="section-sub">O que é verificável hoje, sem exigir confiança prévia.</p>
  <div class="grid cols-3">{seg_html}</div>
</div></section>

<section class="block" id="personas"><div class="wrap">
  <h2 class="section-title">Quem usa dentro da empresa</h2>
  <p class="section-sub">O mesmo dado, com recorte e linguagem diferentes por área.</p>
  <div class="grid cols-4">{per_html}</div>
  <p class="plan-hint">Páginas dedicadas por caso de uso e por setor entram no próximo ciclo de
  desenvolvimento (P1).</p>
</div></section>

{prova_social_block()}

<section class="block" id="numeros"><div class="wrap">
  <h2 class="section-title">Números reais da base (nada de métrica inventada)</h2>
  <div class="grid cols-4">
    <div class="metric blue"><div class="num">{n_props}</div><div class="lbl">Proposições monitoradas</div></div>
    <div class="metric"><div class="num">{score_80}</div><div class="lbl">Matérias com score 80+</div></div>
    <div class="metric green"><div class="num">{n_laws}</div><div class="lbl">Normas vigentes mapeadas</div></div>
    <div class="metric yellow"><div class="num">{mud_30}</div><div class="lbl">Mudanças nos últimos 30 dias</div></div>
    <div class="metric"><div class="num">{n_exec}</div><div class="lbl">Execuções registradas no log público</div></div>
    <div class="metric"><div class="num">{len(mudancas)}</div><div class="lbl">Mudanças no histórico total</div></div>
    <div class="metric"><div class="num">{n_events}</div><div class="lbl">Eventos e marcos na agenda</div></div>
    <div class="metric">{f'<div class="num">{cobertura}%</div>' if cobertura is not None else '<div class="num">—</div>'}<div class="lbl">Cobertura da última verificação</div></div>
  </div>
  <p class="disclaimer">Métricas calculadas no build a partir do dataset versionado. Não publicamos
  números de clientes, contratos ou resultados que não existam.</p>
</div></section>

<section class="block" id="contratar-empresa"><div class="wrap">
  <h2 class="section-title">Formatos de contratação</h2>
  <p class="section-sub">Faixas de referência publicadas. Detalhe em <a href="{_url('solucoes/')}">soluções</a>.</p>
  <div class="grid cols-4">
    {''.join(f'''<div class="card mini-plan"><h3>{_esc(s['nome'])}</h3>
      <p class="plan-price"><span class="valor">{preco_rotulo(s)}</span></p>
      <p>{_esc(s['resumo'])}</p>
      <a class="btn-mini" href="{link_diag(solucao=s['id'])}" data-track="commercial_cta_click">{_esc(s['cta'])}</a></div>'''
             for s in SOLUCOES)}
  </div>
</div></section>

{faixa_cta(titulo=CTA_PRINCIPAL, subtitulo=CTA_PRINCIPAL_SUB)}

<section class="block"><div class="wrap">
  <div class="cta-box">
    <div><h3>{_esc(CTA_DEMO)}</h3>
    <p>Demonstração contextualizada com o seu setor e os seus temas, usando dados reais do monitor.</p></div>
    <div class="cta-actions">
      <a class="cta-btn" href="{link_diag(interesse='demo')}" data-track="demo_request">Agendar demonstração</a>
      {demo_wa}
      <a class="btn-ghost" href="mailto:{_esc(CONTATO_EMAIL)}?subject=Demonstra%C3%A7%C3%A3o%20-%20intelig%C3%AAncia%20regulat%C3%B3ria%20de%20IA"
         data-track="commercial_cta_click" data-cta="email-demo">{_esc(CONTATO_EMAIL)}</a>
    </div>
  </div>
  {disclaimer_block()}
</div></section>
"""

    jsonld = _CORE.combine_ld(
        _CORE.ld_website(),
        _CORE.ld_breadcrumbs([("Início", ""), ("Para empresas", None)]),
        {
            "@type": "ProfessionalService",
            "name": "Inteligência regulatória de IA para empresas — LCF Consulting",
            "description": "Monitoramento legislativo especializado em IA, dados e infraestrutura digital, "
                           "com AI Legislative Impact Score, análise de impacto para o negócio, alertas e "
                           "briefing executivo.",
            "provider": {"@type": "Organization", "name": _CORE.AUTHOR_ORG, "url": CONSULTING_URL},
            "areaServed": {"@type": "Country", "name": "Brasil"},
            "url": _url("para-empresas/"),
            "makesOffer": [{"@type": "Offer", "itemOffered": {"@type": "Service", "name": s["nome"]},
                            **({"priceSpecification": preco_jsonld(s)} if preco_jsonld(s) else {})}
                           for s in SOLUCOES],
        },
    )
    core.write("para-empresas/index.html", core.page(
        "Inteligência regulatória de IA para empresas — Monitor Legislativo de IA | LCF Consulting",
        "Para empresas que não podem descobrir mudanças legislativas tarde demais: monitoramento "
        "especializado em IA, dados e infraestrutura digital, AI Legislative Impact Score, análise de "
        "impacto, alertas, briefing executivo e fontes oficiais auditáveis.",
        "para-empresas/", body,
        jsonld=jsonld))


# ---------------------------------------------------------------------------
# 7. Config pública gerada (troca de preço sem rebuild de código)
# ---------------------------------------------------------------------------

def escrever_config_publica(core):
    """Grava docs/data/commercial.json — config pública da camada comercial.

    Contém apenas o que já é publicado no HTML (nenhum segredo): soluções, faixas,
    CTAs, regras de lead scoring, canais e eventos de analytics. Permite trocar
    preço/copy por variável de ambiente no build e dá ao front-end uma fonte única.
    """
    cfg = {
        "meta": {
            "descricao": "Configuração pública da camada comercial do Monitor Legislativo de IA",
            "gerado_em": _CORE.EXECUTION_DATE if _CORE else "",
            "fonte": "scripts/commercial.py (configuração centralizada)",
            "aviso": DISCLAIMER_COMERCIAL,
        },
        "contato": {"email": CONTATO_EMAIL, "site": CONSULTING_URL,
                    "whatsapp_disponivel": bool(WHATSAPP)},
        "ctas": {"principal": CTA_PRINCIPAL, "principal_sub": CTA_PRINCIPAL_SUB,
                 "secundario": CTA_SECUNDARIO, "demo": CTA_DEMO, "alerta": CTA_ALERTA,
                 "url_principal": link_diag()},
        "solucoes": [
            {
                "id": s["id"], "nome": s["nome"], "resumo": s["resumo"],
                "para_quem": s["para_quem"], "entregas": s["entregas"],
                "preco_publico": s.get("preco_publico", True),
                "preco_rotulo": preco_rotulo(s),
                "preco_min": s["preco_min"] if s.get("preco_publico") else None,
                "preco_max": s["preco_max"] if s.get("preco_publico") else None,
                "unidade": s["preco_unidade"], "usuarios": s["usuarios"],
                "destaque": bool(s.get("destaque")),
                "url": _url("solucoes/") + "#" + s["id"],
            }
            for s in SOLUCOES
        ],
        "lead_scoring": LEAD_SCORING,
        "captura": {"endpoint_configurado": bool(LEAD_ENDPOINT), "provider": LEAD_PROVIDER,
                    "campos": ["nome", "empresa", "cargo", "email", "telefone", "setor", "tamanho",
                               "uso_ia", "area", "horizonte", "preocupacao", "interesse", "solucao",
                               "mensagem", "consentimento"]},
        "setores": SETORES_FORM,
        "analytics": {"eventos": EVENTOS_ANALYTICS,
                      "ga4_configurado": bool(ANALYTICS["ga4_id"]),
                      "plausible_configurado": bool(ANALYTICS["plausible_domain"]),
                      "beacon_configurado": bool(ANALYTICS["beacon_endpoint"])},
        "prova_social": {"habilitada": PROVA_SOCIAL_ENABLED,
                         "nota": "Estrutura pronta; desativada até existirem cases, logos e "
                                 "depoimentos reais autorizados."},
        "paginas": [{"path": p["path"], "nome": p["nome"], "evento": p["evento"]} for p in PAGINAS],
    }
    core.write("data/commercial.json", json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    return cfg


# ---------------------------------------------------------------------------
# 8. install(): integra a camada comercial ao gerador sem tocar nas páginas atuais
# ---------------------------------------------------------------------------

def build_all(core, props, laws, events, updates, timeline, cats):
    """Gera as páginas comerciais e devolve os paths para o sitemap."""
    met = None
    build_solucoes(core, props, laws, updates, met)
    build_diagnostico(core, props, laws, updates, met)
    build_briefing_executivo(core, props, laws, events, updates, cats)
    build_para_empresas(core, props, laws, events, updates, met)
    escrever_config_publica(core)
    return [p["path"] for p in PAGINAS]


def install(core):
    """Guarda a referência do gerador para os helpers de renderização."""
    global _CORE
    _CORE = core
    # Garante que o sitemap inclua as páginas comerciais mesmo se outro módulo
    # (ai_visibility) chamar build_sitemap depois.
    original_sitemap = core.build_sitemap

    def sitemap_com_comerciais(paths):
        extra = [p["path"] for p in PAGINAS]
        combined = list(paths) + [e for e in extra if e not in paths]
        return original_sitemap(combined)

    core.build_sitemap = sitemap_com_comerciais
    return core
