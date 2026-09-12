#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest_comercial.py — Testes offline da camada comercial B2B.

Cobre (sem rede, sem dependências externas):
  1. configuração centralizada: soluções, faixas de preço, prova social desativada
  2. lead scoring: pesos, faixas e simulação de perfis
  3. brief.py: integridade do payload, separação fato × análise, nada inventado
  4. HTML gerado: páginas comerciais, CTA em todas as páginas, ausência de
     faixa interna publicada, ausência de prova social inventada
  5. analytics: catálogo Python × catálogo instrumentado no JS
  6. alerta/relatório: geração em HTML, TXT e JSON + payload de canais
  7. front-end (opcional): roda o teste jsdom se node + jsdom estiverem disponíveis

Uso: python3 scripts/selftest_comercial.py [--sem-build] [--front]
Saída: exit 0 se tudo passou.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(BASE, "docs")
sys.path.insert(0, os.path.join(BASE, "scripts"))

import brief  # noqa: E402
import commercial  # noqa: E402

_ok = 0
_falha = 0


def check(nome, cond, extra=""):
    global _ok, _falha
    if cond:
        _ok += 1
        print(f"  ok   · {nome}")
    else:
        _falha += 1
        print(f"  FALHA· {nome}" + (f" → {extra}" if extra else ""))


def carregar_dataset():
    d = os.path.join(BASE, "data", "legislation")
    with open(os.path.join(d, "propositions.json"), encoding="utf-8") as f:
        props = json.load(f)["proposicoes"]
    with open(os.path.join(d, "updates.json"), encoding="utf-8") as f:
        updates = json.load(f)
    with open(os.path.join(d, "events.json"), encoding="utf-8") as f:
        events = json.load(f)
    with open(os.path.join(d, "laws.json"), encoding="utf-8") as f:
        laws = json.load(f)["normas"]
    with open(os.path.join(d, "categories.json"), encoding="utf-8") as f:
        cats = {c["id"]: c for c in json.load(f)["categorias"]}
    return props, updates, events, laws, cats


# ---------------------------------------------------------------------------
def teste_config():
    print("\n== 1) Configuração centralizada (pricing, CTAs, prova social) ==")
    check("4 soluções configuradas", len(commercial.SOLUCOES) == 4,
          str(len(commercial.SOLUCOES)))
    ids = [s["id"] for s in commercial.SOLUCOES]
    check("ids esperados", ids == ["monitor-ia", "radar-executivo", "inteligencia-institucional",
                                   "diagnostico-exposicao"], str(ids))
    check("Radar Executivo marcado como oferta principal",
          commercial.SOLUCOES[1]["destaque"] is True)
    check("faixa Monitor IA dentro do recomendado (1.5k–3k)",
          commercial.SOLUCOES[0]["preco_min"] >= 1500 and commercial.SOLUCOES[0]["preco_max"] <= 3000,
          f'{commercial.SOLUCOES[0]["preco_min"]}–{commercial.SOLUCOES[0]["preco_max"]}')
    check("faixa Radar Executivo dentro do recomendado (4k–8k)",
          commercial.SOLUCOES[1]["preco_min"] >= 4000 and commercial.SOLUCOES[1]["preco_max"] <= 8000)
    check("faixa Diagnóstico dentro do recomendado (5k–15k por projeto)",
          commercial.SOLUCOES[3]["preco_min"] >= 5000 and commercial.SOLUCOES[3]["preco_max"] <= 15000
          and commercial.SOLUCOES[3]["preco_unidade"] == "projeto")
    check("Inteligência Institucional não publica faixa",
          commercial.SOLUCOES[2]["preco_publico"] is False
          and commercial.SOLUCOES[2].get("preco_rotulo") == "Sob consulta")
    check("preco_jsonld omite valores da solução sob consulta",
          commercial.preco_jsonld(commercial.SOLUCOES[2]) is None)
    check("prova social desativada (item 13)", commercial.PROVA_SOCIAL_ENABLED is False)
    check("estrutura de prova social pronta para o futuro",
          set(commercial.PROVA_SOCIAL) == {"logos", "depoimentos", "cases", "metricas"})
    check("CTA principal exato", commercial.CTA_PRINCIPAL == "Solicitar diagnóstico regulatório")
    check("CTA secundário exato", commercial.CTA_SECUNDARIO == "Ver exemplo de briefing executivo")
    check("CTAs vagos não usados",
          not any(t in (commercial.CTA_PRINCIPAL + commercial.CTA_SECUNDARIO).lower()
                  for t in ("saiba mais", "entre em contato", "conheça a plataforma")))
    check("disclaimer nega aconselhamento jurídico",
          "aconselhamento jurídico" in commercial.DISCLAIMER_COMERCIAL
          and "Não presta" in commercial.DISCLAIMER_COMERCIAL)
    check("14 setores no formulário", len(commercial.SETORES_FORM) == 14,
          str(len(commercial.SETORES_FORM)))


def teste_lead_scoring():
    print("\n== 2) Lead scoring (regras, faixas e simulação) ==")
    cfg = commercial.LEAD_SCORING
    pesos = {r["id"]: r["pontos"] for r in cfg["regras"]}
    check("7 critérios", len(cfg["regras"]) == 7, str(len(cfg["regras"])))
    check("pesos conforme especificação",
          pesos == {"grande_empresa": 20, "setor_prioritario": 20, "cargo_decisor": 15,
                    "area_estruturada": 15, "preocupacao_imediata": 15, "ia_critica": 10,
                    "mais_de_100": 5}, str(pesos))
    check("pontuação máxima = 100", cfg["maximo"] == 100, str(cfg["maximo"]))
    faixas = {f["classe"]: f["min"] for f in cfg["faixas"]}
    check("faixas 0-29/30-49/50-69/70+",
          faixas == {"baixo": 0, "medio": 30, "alto": 50, "prioridade_comercial": 70}, str(faixas))

    ent = cfg["entradas"]

    def pontuar(perfil):
        """Espelho determinístico da regra aplicada no front-end."""
        t = 0
        if perfil.get("tamanho") in ent["tamanho_grande"]:
            t += pesos["grande_empresa"]
        if perfil.get("tamanho") in ent["tamanho_acima_100"]:
            t += pesos["mais_de_100"]
        if perfil.get("setor") in ent["setores_prioritarios"]:
            t += pesos["setor_prioritario"]
        if perfil.get("cargo") in ent["cargos_senior"]:
            t += pesos["cargo_decisor"]
        if perfil.get("area") in ent["areas_que_pontuam"]:
            t += pesos["area_estruturada"]
        if perfil.get("horizonte") == ent["horizonte_imediato"]:
            t += pesos["preocupacao_imediata"]
        if perfil.get("uso_ia") == ent["uso_ia_critico"]:
            t += pesos["ia_critica"]
        return t

    def classe(score):
        for f in cfg["faixas"]:
            if score >= f["min"]:
                return f["classe"]
        return "baixo"

    # Perfis de referência com pontuação esperada derivada da especificação:
    # +20 grande empresa, +20 setor prioritário, +15 cargo decisor, +15 área
    # estruturada, +15 preocupação imediata, +10 IA crítica, +5 >100 funcionários.
    perfis = [
        ("prioridade comercial (todas as regras)", 100, "prioridade_comercial",
         {"tamanho": "Mais de 1.000", "setor": "Bancos", "cargo": "Diretor(a)",
          "area": "Sim — Compliance", "horizonte": ent["horizonte_imediato"],
          "uso_ia": ent["uso_ia_critico"]}),
        ("alto (setor + porte + área estruturada = 60)", 60, "alto",
         {"tamanho": "Mais de 1.000", "setor": "Fintech", "cargo": "Gerente",
          "area": "Sim — Jurídico", "horizonte": "Curto prazo — 6 a 12 meses",
          "uso_ia": "IA em produtos e receita"}),
        ("médio (setor + sócio + >100 = 40)", 40, "medio",
         {"tamanho": "101 a 500", "setor": "Tecnologia", "cargo": "Sócio(a)",
          "area": "Em estruturação", "horizonte": "Curto prazo — 6 a 12 meses",
          "uso_ia": "IA em produtos e receita"}),
        ("baixo (perfil sem gatilhos = 0)", 0, "baixo",
         {"tamanho": "1 a 10", "setor": "Outro", "cargo": "Analista / Especialista",
          "area": "Não temos", "horizonte": "Ainda avaliando se somos afetados",
          "uso_ia": "Ainda não usamos IA"}),
    ]
    for rotulo, esperado, classe_esperada, perfil in perfis:
        s = pontuar(perfil)
        check(f"perfil {rotulo}", s == esperado and classe(s) == classe_esperada,
              f"obtido {s}/{classe(s)}, esperado {esperado}/{classe_esperada}")
    check("setores prioritários = banco/seguro/tech/cloud/data center/fintech",
          set(ent["setores_prioritarios"]) == {"Bancos", "Fintech", "Seguros", "Tecnologia",
                                               "Cloud", "Data Center"}, str(ent["setores_prioritarios"]))


def teste_brief():
    print("\n== 3) brief.py — integridade do payload ==")
    props, updates, events, laws, cats = carregar_dataset()
    execucao = updates.get("meta", {}).get("execucao")
    b = brief.build_brief(props, updates, events, laws, cats, execucao)
    check("meta declara o modelo", b["meta"]["modelo"] == "Executive Regulatory Brief")
    check("meta declara aviso de não-aconselhamento", "aconselhamento jurídico" in b["meta"]["aviso"])
    check("top 5 matérias", len(b["top_materias"]) == 5, str(len(b["top_materias"])))
    check("top matérias ordenadas por score decrescente",
          [m["score"]["valor"] for m in b["top_materias"]] ==
          sorted([m["score"]["valor"] for m in b["top_materias"]], reverse=True))
    sem_fonte = [m["fato_oficial"]["titulo"] for m in b["top_materias"]
                 if not m["fato_oficial"].get("url_oficial")]
    check("toda matéria prioritária tem fonte oficial", not sem_fonte, str(sem_fonte))
    check("toda matéria tem ação recomendada + critério",
          all(m["analise"]["acao_recomendada"] and m["analise"]["acao_recomendada_criterio"]
              for m in b["top_materias"]))
    check("toda matéria declara status da interpretação",
          all(m["analise"]["status_interpretacao"] for m in b["top_materias"]))
    check("análise declara a base objetiva usada",
          all(m["analise"]["base_da_analise"] for m in b["top_materias"]))
    check("impacto potencial na escala Baixo/Médio/Alto/Crítico",
          {m["analise"]["impacto_potencial"] for m in b["top_materias"]} <=
          {"Baixo", "Médio", "Alto", "Crítico"})
    check("fato oficial não contém campo de análise",
          not any(k in b["top_materias"][0]["fato_oficial"] for k in
                  ("acao_recomendada", "impacto_potencial", "setores_afetados")))
    check("nenhum 'por que importa' vazio",
          all(m["analise"]["por_que_importa"] for m in b["top_materias"]))
    check("setores agregados a partir das categorias", len(b["setores"]) >= 5, str(len(b["setores"])))
    check("agenda não inclui evento já encerrado",
          all(not e.get("data_fim") or e["data_fim"] >= b["meta"]["referencia"]
              for e in b["agenda"]["proximos_dias"]))
    check("critério de 'desde o último relatório' declarado",
          bool(b["criterio_desde_ultimo_relatorio"]))
    check("fontes oficiais citadas", len(b["fontes_oficiais"]) >= 5, str(len(b["fontes_oficiais"])))
    # nada inventado: matéria sem curadoria não pode afirmar obrigação
    sem_curadoria = [m for m in b["top_materias"]
                     if m["fato_oficial"].get("aguardando_curadoria")]
    check("registros automáticos sinalizados como aguardando curadoria",
          all("automatizada" in m["analise"]["status_interpretacao"] for m in sem_curadoria)
          if sem_curadoria else True)


def teste_html():
    print("\n== 4) HTML gerado (docs/) ==")
    if not os.path.isdir(DOCS):
        check("docs/ existe (rode build_site.py)", False)
        return
    paginas = ["solucoes", "diagnostico", "briefing-executivo", "para-empresas"]
    for p in paginas:
        fp = os.path.join(DOCS, p, "index.html")
        check(f"/{p}/ gerada", os.path.isfile(fp))
        if not os.path.isfile(fp):
            continue
        h = open(fp, encoding="utf-8").read()
        check(f"/{p}/ tem canonical", f'<link rel="canonical"' in h and f"/{p}/" in h)
        check(f"/{p}/ tem og:title", 'property="og:title"' in h)
        check(f"/{p}/ tem JSON-LD", 'application/ld+json' in h)
        check(f"/{p}/ tem CTA principal", "Solicitar diagnóstico" in h)
        check(f"/{p}/ sem 'None' vazado no HTML visível",
              not re.search(r">\s*None\s*<", h))
    # CTA + analytics em todas as páginas
    sem_cta, sem_cfg = [], []
    n_html = 0
    for root, _, files in os.walk(DOCS):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            n_html += 1
            h = open(os.path.join(root, fn), encoding="utf-8").read()
            if "nav-cta" not in h:
                sem_cta.append(os.path.relpath(os.path.join(root, fn), DOCS))
            if 'id="monitor-commercial-config"' not in h:
                sem_cfg.append(os.path.relpath(os.path.join(root, fn), DOCS))
    check(f"CTA no cabeçalho em todas as {n_html} páginas", not sem_cta, str(sem_cta[:3]))
    check(f"config comercial/analytics em todas as {n_html} páginas", not sem_cfg, str(sem_cfg[:3]))
    # faixa interna não publicada
    sh = open(os.path.join(DOCS, "solucoes", "index.html"), encoding="utf-8").read()
    check("faixa interna da Inteligência Institucional não publicada",
          "R$ 10.000" not in sh and "R$ 20.000" not in sh)
    check("prova social não renderizada", 'class="logos"' not in sh and "Quem já usa" not in sh)
    # briefing
    bh = open(os.path.join(DOCS, "briefing-executivo", "index.html"), encoding="utf-8").read()
    check("briefing separa fato oficial × análise",
          bh.count("tag-fato") >= 5 and bh.count("tag-analise") >= 5)
    check("briefing explica o score", "Por que esta matéria recebeu score" in bh)
    check("briefing tem ação recomendada", "Ação recomendada" in bh)
    check("briefing tem fonte oficial", "Fonte oficial" in bh)
    check("briefing cita dados reais (PL 2338/2023)", "PL 2338/2023" in bh)
    check("briefing tem formulário de alerta", 'id="form-alerta"' in bh)
    check("briefing tem CSS de impressão", "@media print" in
          open(os.path.join(DOCS, "assets", "commercial.css"), encoding="utf-8").read())
    # config pública
    cfg = json.load(open(os.path.join(DOCS, "data", "commercial.json"), encoding="utf-8"))
    check("commercial.json publicado", bool(cfg.get("solucoes")))
    check("commercial.json traz lead scoring", len(cfg["lead_scoring"]["regras"]) == 7)
    raw = json.dumps(cfg, ensure_ascii=False).lower()
    check("commercial.json sem segredos",
          not any(s in raw for s in ("access_key", "apikey", "api_key", "secret", "password")))
    # sitemap
    sm = open(os.path.join(DOCS, "sitemap.xml"), encoding="utf-8").read()
    for p in paginas:
        check(f"/{p}/ no sitemap", f"/{p}/</loc>" in sm)


def teste_analytics():
    print("\n== 5) Analytics — catálogo Python × instrumentação JS ==")
    js_path = os.path.join(BASE, "scripts", "assets", "commercial.js")
    js = open(js_path, encoding="utf-8").read()
    for ev in commercial.EVENTOS_ANALYTICS:
        check(f"evento '{ev}' presente no JS", ev in js)
    catalogo = re.search(r"var EVENT_CATALOG = \[(.*?)\];", js, re.S)
    check("catálogo de eventos declarado no JS", bool(catalogo))
    if catalogo:
        itens = re.findall(r"'([a-z_]+)'", catalogo.group(1))
        faltando = [e for e in commercial.EVENTOS_ANALYTICS if e not in itens]
        check("catálogo JS cobre os 10 eventos obrigatórios", not faltando, str(faltando))
        check("catálogo tem ≥10 eventos", len(itens) >= 10, str(len(itens)))
    for recurso in ("dataLayer", "utm_source", "first_touch", "last_touch", "sendBeacon",
                    "plausible", "gtag", "localStorage"):
        check(f"JS implementa {recurso}", recurso in js)
    check("nenhum ID de analytics hardcoded no JS",
          not re.search(r"G-[A-Z0-9]{6,}", js))


def teste_alerta():
    print("\n== 6) Alerta / relatório executivo automatizável ==")
    tmp = tempfile.mkdtemp(prefix="alertas-")
    try:
        import build_alert_email as bae
        rc = bae.main(["--modelo", "brief", "--out-dir", tmp])
        check("gerador executa (exit 0)", rc == 0, str(rc))
        arquivos = sorted(os.listdir(tmp))
        check("gera HTML, TXT e JSON",
              any(a.endswith(".html") for a in arquivos) and any(a.endswith(".txt") for a in arquivos)
              and any(a.endswith(".json") for a in arquivos), str(arquivos))
        html = open(os.path.join(tmp, [a for a in arquivos if a.endswith('.html')][0]),
                    encoding="utf-8").read()
        check("HTML de e-mail não usa CSS externo", "<link rel=\"stylesheet\"" not in html)
        check("HTML de e-mail não usa JavaScript", "<script" not in html)
        check("HTML de e-mail usa estilos inline", html.count("style=\"") > 30)
        check("HTML separa fato oficial e análise", "Fato oficial" in html and "Análise / interpretação" in html)
        payload = json.load(open(os.path.join(tmp, [a for a in arquivos if a.endswith('.json')][0]),
                                encoding="utf-8"))
        check("payload declara canais (e-mail + futuros)",
              {c["id"] for c in payload["canais_disponiveis"]} >=
              {"email", "webhook", "whatsapp", "telegram", "slack", "teams"})
        check("e-mail marcado como implementado",
              [c for c in payload["canais_disponiveis"] if c["id"] == "email"][0]["implementado"] is True)
        check("tipos de alerta incluem alteração de score (declarado como pendente)",
              any(t["id"] == "alteracao_score" and t["implementado"] is False
                  for t in payload["tipos_alerta"]))
        check("tipos obrigatórios presentes",
              {t["id"] for t in payload["tipos_alerta"]} >=
              {"mudanca_legislativa", "novo_projeto", "votacao", "inclusao_pauta",
               "alteracao_relatoria", "nova_norma", "evento", "alteracao_score"})
        check("mensagem curta pronta para WhatsApp/Slack", bool(payload["mensagem_curta"]))
        check("filtros registrados no payload",
              set(payload["selecao"]["filtros_aplicados"]) >=
              {"frequencia", "score_minimo", "temas", "orgaos", "tipos"})
        # filtros funcionam
        tmp2 = tempfile.mkdtemp(prefix="alertas2-")
        bae.main(["--modelo", "alerta", "--score-minimo", "80", "--frequencia", "imediato",
                  "--out-dir", tmp2, "--json-only"])
        p2 = json.load(open(os.path.join(tmp2, os.listdir(tmp2)[0]), encoding="utf-8"))
        check("score mínimo 80 filtra matérias",
              all(m["score"]["valor"] >= 80 for m in p2["selecao"]["materias"]),
              str([m["score"]["valor"] for m in p2["selecao"]["materias"]]))
        check("frequência imediato reduz a janela",
              p2["selecao"]["filtros_aplicados"]["janela_dias"] == 1)
        shutil.rmtree(tmp2, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def teste_front(forcar=False):
    print("\n== 7) Front-end (jsdom) ==")
    node = shutil.which("node")
    if not node:
        print("  pulado · node não disponível")
        return
    script = os.path.join(BASE, "scripts", "tests", "commercial_front.test.js")
    if not os.path.isfile(script):
        print(f"  pulado · {os.path.relpath(script, BASE)} não encontrado")
        return
    # jsdom precisa estar resolvível: node_modules local ou NODE_PATH
    candidatos = [os.path.join(BASE, "node_modules"), os.environ.get("NODE_PATH", ""),
                  "/tmp/jstest/node_modules"]
    node_path = next((c for c in candidatos if c and os.path.isdir(os.path.join(c, "jsdom"))), None)
    if not node_path:
        print("  pulado · jsdom não instalado (npm i --no-save jsdom)")
        return
    env = dict(os.environ, NODE_PATH=node_path)
    # o modo (provider HTTP × fallback) é detectado a partir do build atual
    r = subprocess.run([node, script], cwd=BASE, env=env,
                       capture_output=True, text=True, timeout=240)
    linhas = r.stdout.strip().splitlines()
    resultado = [l for l in linhas if l.startswith("RESULTADO")]
    modo = next((l.split("(modo ")[-1].rstrip(") ==") for l in linhas if "(modo " in l), "?")
    check(f"teste jsdom (modo de captura: {modo})", r.returncode == 0,
          (resultado[-1] if resultado else (r.stdout[-400:] + r.stderr[-400:])))
    if resultado:
        print(f"         {resultado[-1].strip()}")
    falhas_js = [l for l in linhas if l.strip().startswith("FALHA")]
    for f in falhas_js[:8]:
        print("         " + f.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-build", action="store_true", help="não regenera o site antes de testar")
    ap.add_argument("--front", action="store_true", help="força tentativa do teste jsdom")
    args = ap.parse_args()

    if not args.sem_build:
        print("== 0) Build do site (pré-requisito) ==")
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts", "build_site.py")],
                           cwd=BASE, capture_output=True, text=True, timeout=600)
        check("build_site.py exit 0", r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts", "validate_site.py")],
                           cwd=BASE, capture_output=True, text=True, timeout=600)
        check("validate_site.py exit 0", r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])

    teste_config()
    teste_lead_scoring()
    teste_brief()
    teste_html()
    teste_analytics()
    teste_alerta()
    teste_front(args.front)

    print(f"\nRESULTADO: {_ok} ok · {_falha} falha(s)")
    print("SELFTEST COMERCIAL OK" if not _falha else "SELFTEST COMERCIAL FALHOU")
    return 1 if _falha else 0


if __name__ == "__main__":
    sys.exit(main())
