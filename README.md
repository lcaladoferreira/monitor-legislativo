# Monitor Legislativo de IA no Brasil

**Sistema de inteligência legislativa** — monitoramento público, documentado e auditável de toda a atividade legislativa federal brasileira relacionada à Inteligência Artificial.

O ativo principal é o **dataset legislativo histórico** (`/data/legislation`), estruturado e continuamente atualizado. O site em `/docs` é a interface pública desse dataset.

- **Site oficial:** https://monitor.lcfconsulting.com.br (publicado a partir de `/docs`, compatível com GitHub Pages *e* Vercel)
- **Dados:** `/data/legislation/*.json` (fonte única da verdade, versionada no Git)
- **Build:** `python3 scripts/build_site.py` (stdlib apenas)
- **Domínio legado bloqueado no build:** o build e a validação reprovam qualquer artefato crítico (HTML, JSON, XML, `robots.txt`, sitemap) que ainda aponte para o antigo domínio do GitHub Pages ou para a app Vercel legada. Os endereços exatos ficam na constante `OLD_DOMAIN` de `scripts/validate_site.py` e em `OLD_SITE_URL` de `scripts/build_site.py` — não são reescritos aqui de propósito, porque qualquer menção literal ao domínio antigo em `.md` derrubava a validação e, com ela, a publicação automática (incidente 2026-09-30).

---

## Índice

- [O que este repositório monitora](#o-que-este-repositório-monitora)
- [Arquitetura e fluxo de dados](#arquitetura-e-fluxo-de-dados)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Dataset — fonte única da verdade](#dataset--fonte-única-da-verdade)
  - [propositions.json](#propositionsjson)
  - [laws.json](#lawsjson)
  - [timeline.json](#timelinejson)
  - [parliamentarians.json](#parliamentariansjson)
  - [events.json](#eventsjson)
  - [updates.json](#updatesjson)
  - [atos.json](#atosjson)
  - [categories.json](#categoriesjson)
  - [data/articles/](#dataarticles)
- [Pipeline de execução (ciclo completo)](#pipeline-de-execução-ciclo-completo)
- [Orçamento de tempo e robustez](#orçamento-de-tempo-e-robustez)
- [Módulo frescor.py — cadência e limiares de frescor](#módulo-frescorpy--cadência-e-limiares-de-frescor-fonte-única)
- [Módulo scoring.py — AI Legislative Impact Score](#módulo-scoringpy--ai-legislative-impact-score)
- [Módulo update_legislation.py — Coletor Câmara/Senado](#módulo-update_legislationpy--coletor-câmarasenado)
- [Módulo sources/ — Coletores multiórgão](#módulo-sources--coletores-multiórgão)
  - [sources/base.py](#sourcesbasepy)
  - [sources/anpd.py, cnj.py, tse.py, dou.py, planalto.py, mcti.py](#sourcesanpdpy-cnjpy-tsepy-doupy-planaltopy-mctipy)
  - [update_sources.py](#update_sourcespy)
- [Módulo generate_articles.py — Camada editorial](#módulo-generate_articlespy--camada-editorial)
- [Módulo build_site_core.py / build_site.py — Gerador do site](#módulo-build_site_corepy--build_sitepy--gerador-do-site)
- [Módulo build_articles.py — Renderização de /artigos/](#módulo-build_articlespy--renderização-de-artigos)
- [Módulo dataviz.py — Gráficos SVG](#módulo-datavizpy--gráficos-svg)
- [Módulos ai_visibility.py, google_ai_citation.py, commercial_pages.py](#módulos-ai_visibilitypy-google_ai_citationpy-commercial_pagespy)
- [Camada comercial B2B](#camada-comercial-b2b)
  - [commercial/store.py](#commercialstorepy)
  - [commercial/service.py](#commercialservicepy)
  - [commercial/intelligence.py](#commercialintelligencepy)
  - [commercial/alerts.py](#commercialalertspy)
  - [api/index.py](#apiindexpy)
  - [scripts/commercial_admin.py, serve_commercial.py, send_alerts.py, generate_briefing.py](#scripts-comerciais-auxiliares)
- [Validação e auditoria](#validação-e-auditoria)
- [Workflows GitHub Actions](#workflows-github-actions)
- [Metodologia e política de qualidade](#metodologia-e-política-de-qualidade)
- [Como executar localmente](#como-executar-localmente)
- [SEO / AEO / Agentic](#seo--aeo--agentic)
- [Autoria e licença de uso](#autoria-e-licença-de-uso)

---

## O que este repositório monitora

- **Proposições federais:** PL, PLP, PLC, PLS, PEC, PDL, PLN, MP/MPV, substitutivos, emendas, requerimentos (REQ/RIC/RQS/RMA com match forte) e pareceres relacionados a IA.
- **Normas vigentes e históricas:** leis sancionadas, vetos, decretos, resoluções e atos regulatórios de TSE, CNJ, ANPD, MCTI, Planalto/Presidência e DOU.
- **Mudanças de estado:** relatoria, parecer, pauta, votação, apensação, desapensação, arquivamento, desarquivamento, sanção, veto, redação final.
- **Relações:** proposições apensadas, clusters temáticos, sucessão histórica (PL principal).
- **Parlamentares:** autores, relatores, presidentes de comissões com atuação documentada em IA.
- **Agenda:** eventos futuros (Câmara) e marcos normativos previstos.
- **Artigos editoriais automáticos:** camada que transforma mudanças detectadas em artigos públicos com SEO completo, sem inventar fatos.

---

## Arquitetura e fluxo de dados

```
Fontes oficiais (8 órgãos obrigatórios)
  ├─ Câmara (API Dados Abertos v2) ─┐
  ├─ Senado (API Dados Abertos v7) ─┤
  ├─ ANPD (plone.restapi gov.br) ───┤
  ├─ CNJ (atos.cnj.jus.br + WP) ────┤
  ├─ TSE (portal JSON + DOU) ───────┼─► update_legislation.py + update_sources.py
  ├─ DOU (busca in.gov.br) ─────────┤         │
  ├─ Planalto (DOU + RSS) ──────────┤         ▼
  └─ MCTI (DOU + portal) ───────────┘   data/legislation/*.json  (dataset)
                                              │
                                              ├─► generate_articles.py ─► data/articles/
                                              │                                    │
                                              └──────────────┬─────────────────────┘
                                                             ▼
                                              build_site_core.py (+ camadas)
                                                             │
                                                             ▼
                                                      docs/ (site estático)
                                                        ├─ index.html, proposicoes/, leis/, etc.
                                                        ├─ artigos/ (SEO + JSON-LD NewsArticle)
                                                        ├─ data/ (cópia pública do dataset)
                                                        ├─ sitemap.xml, robots.txt
                                                        └─ llms.txt, ai-content.md, mcp-actions.json
```

**Princípio:** nenhuma etapa posterior inventa dado legislativo. Tudo vem de resposta oficial com URL registrada. Falha de uma fonte nunca gera dado estimado — é marcada como `falha/parcial` e exibida no painel `/monitoramento/`.

---

## Estrutura de pastas

```
data/legislation/            # DATASET (fonte única da verdade)
  propositions.json          # Banco de proposições (chave lógica: casa_tipo_numero_ano)
  laws.json                  # Leis, decretos, resoluções e atos vigentes/históricos
  atos.json                  # Atos multiórgão (ANPD, CNJ, TSE, DOU, Planalto, MCTI)
  timeline.json              # Timeline histórica documentada (2019–2026)
  parliamentarians.json      # Mapa de parlamentares com atuação documentada
  events.json                # Agenda legislativa de IA (eventos futuros)
  updates.json               # "O que mudou" + log de execuções (execucoes + mudancas)
  updates_arquivo.json       # Histórico arquivado (rotação quando > LIMITE_MUDANCAS)
  categories.json            # 30 categorias temáticas

data/articles/
  articles.json              # Artigos editoriais (conteúdo, datas, fontes, revisões)
  editorial_state.json       # Log auditável: change_id → ação editorial (new_article / article_update / ignored)

scripts/
  update_legislation.py      # Coletor Câmara/Senado + orquestra fontes multiórgão
  update_sources.py          # Orquestrador multiórgão (subprocesso isolado por fonte)
  sources/                   # Conectores por órgão
    base.py                  # Cliente HTTP, parsers (RSS, JSON, HTML, DOU), filtro temático
    anpd.py, cnj.py, tse.py, dou.py, planalto.py, mcti.py
  scoring.py                 # Rúbrica pública do AI Legislative Impact Score (reproduzível)
  generate_articles.py       # Camada editorial: classifica mudanças → cria/atualiza artigos
  build_articles.py          # Renderiza /artigos/ (SEO, AEO, JSON-LD NewsArticle)
  build_site_core.py         # Gera o site estático a partir do dataset → /docs
  build_site.py              # Wrapper: força domínio oficial + instala camadas visibilidade/comercial
  dataviz.py                 # Gráficos SVG inline (stdlib, sem JS)
  ai_visibility.py           # Camada AEO: llms.txt, ai-content.md, agent-permissions.json, robots.txt
  google_ai_citation.py      # Bloco entidade/Organization + citação Google AI Overviews
  commercial_pages.py        # Páginas comerciais (soluções, setores, casos de uso, alertas, app)
  validate_site.py           # Validações: JSON, duplicatas, links, SEO, domínio, editorial
  check_collection.py        # Falha o job se coleta não for do dia, cobertura <100% ou fontes com falha
  probe_sources.py           # Sonda manuais de fontes (debug)
  selftest_offline.py        # Testes offline: orçamento, persistência e métricas
  recover_audit_history.py   # Recupera lacuna histórica de auditoria (watchlist)
  assets/                    # CSS e JS (style.css, site.js, commercial.css, commercial.js)

commercial/
  __init__.py                # Marcador de pacote privado
  store.py                   # Store transacional (PostgreSQL prod, SQLite só em MONITOR_DEV=1)
  service.py                 # Lead capture, auth, rate-limit, preferências, pilot briefing
  intelligence.py            # Modelo de briefing evidence-led (sem inventar fatos)
  alerts.py                  # Snapshot/diff, fila filtrada, transporte SMTP opt-in

api/
  index.py                   # Vercel Python Function: API JSON same-origin (health, leads, alerts, login, app)

config/
  commercial.json            # Ofertas B2B, setores, personas, WhatsApp, prova social

docs/                        # SITE GERADO (não editar manualmente)
  index.html, proposicoes/, atualizacoes/, leis/, timeline/, parlamentares/, agenda/
  metodologia/, monitoramento/, relatorio/, artigos/, data/, assets/
  sitemap.xml, robots.txt, llms.txt, llms-full.txt, ai-content.md, mcp-actions.json

.github/workflows/
  update-legislation.yml     # Cron horário (minuto 17) + push paths + dispatch manual
  commercial.yml             # CI comercial
  probe-sources.yml          # Sonda de fontes

tests/
  test_audit_*.py, test_collection_*.py, test_commercial.py, test_editorial.py, etc.

vercel.json                  # Build = build_site.py, output = docs/, rewrites /api/:path*
```

---

## Dataset — fonte única da verdade

Todos os JSON em `data/legislation/` seguem o contrato:

```json
{
  "meta": { "descricao": "...", "execucao": "YYYY-MM-DD", ... },
  "proposicoes": [ ... ] // ou "normas", "eventos", "mudancas", etc.
}
```

### propositions.json

Campo chave: `id` = `casa_tipo_numero_ano` (ex.: `camara_pl_2338_2023`). Nunca duplicado.

**Campos principais por proposição:**

- `id`, `tipo`, `numero`, `ano`, `titulo`, `ementa`, `resumo`
- `casa_origem`, `casa_atual`, `comissao_atual`, `url_oficial`
- `autor: {nome, partido, estado, cargo}`, `relator`, `relator_camara`, `relator_senado`
- `situacao` (texto oficial), `regime_tramitacao`, `forma_apreciacao`
- `ultima_movimentacao: {data, descricao}`, `proxima_etapa`
- `categorias: [int]` (ids 1..30), `impacto: {score, classificacao, detalhe?}`
- `documentos: [{titulo, url}]`, `fontes_adicionais`, `timeline: [{data, evento, fonte}]`
- `relacionamentos`, `apensados_principais`, `total_apensados`, `proposicao_principal`
- `obrigacoes_criadas`, `proibicoes`, `orgaos_responsaveis`, `chance_impacto_regulatorio`
- `origem: "descoberta_automatica"` quando veio da descoberta, `revisao_pendente: true` (score conservador, nunca CRÍTICO automático)
- `api_camara: {id_proposicao, verificado_em, status_datahora, descricao_situacao, descricao_tramitacao, despacho, sigla_orgao, regime, apreciacao, uri_prop_principal, keywords, url_inteiro_teor, ementa_api, ultima_tramitacao, relator_api, votacoes_total, proposicao_principal_api}`
- `api_senado: {codigo_materia, verificado_em, tramitando, ementa_api, apelido, autor_api, decisao, situacao_senado, ultimo_informe_senado, relatoria_senado_atual}`

### laws.json

- `id`, `tipo`, `numero`, `nome`, `data`, `status`, `orgao`, `url`, `ementa_sintese`, `relacao_ia`, `categorias`

### timeline.json

- `data`, `casa`, `titulo`, `descricao`, `ator`, `fonte_titulo`, `fonte_url`

### parliamentarians.json

- `nome`, `casa`, `partido`, `estado`, `papel`, `atuacao_ia: [str]`, `proposicoes_relacionadas: [id]`, `fontes: [{titulo, url}]`

### events.json

- `id`, `titulo`, `casa`, `tipo`, `data_inicio`, `data_fim`, `hora`, `local`, `tema`, `relacao_ia`, `janela: proximos_7_dias|proximos_30_dias|sem_data_confirmada`, `fonte_titulo`, `fonte_url`, `origem`
- `verificacao: {data, fontes_consultadas, resultado}`

### updates.json

- `mudancas: [{data, titulo, descricao, tipo, proposicao?, item?, orgao?, fonte, fonte_url, url_oficial, campo_alterado, valor_anterior, valor_novo, data_deteccao, relevancia?, revisao_pendente?, timestamp_execucao, id_execucao}]`
- `execucoes: [{id, data_hora, fim, tipo, status: concluida|parcial|falha|em_andamento, duracao_segundos, orcamento_segundos, orcamento_restante_segundos, cobertura_pct, proposicoes_verificadas, proposicoes_monitoradas, proposicoes_pendentes, proposicoes_distintas_verificadas, novas_proposicoes, mudancas_detectadas, eventos_adicionados, fontes_consultadas, erros, observacao, fases_segundos, http: {chamadas, cache, falhas, tempo_total, por_endpoint}, snapshot_dataset, fontes_monitoradas: {orgao: {nome, status: ok|parcial|falha, ultima_tentativa, ultima_execucao_ok, itens_consultados, novidades, erros, endpoints, canais_ok, canais_falhos, erro_detalhe}}, status_global: OK|PARCIAL|FALHA, fontes_falha, fontes_parciais, http_fontes, descoberta_candidatos, descoberta_adiada}]`

### atos.json

- `atos: [{id, orgao, tipo, titulo, descricao, data, url_oficial, fonte, canais, relevancia: forte|revisar, revisao_pendente, situacao, tipo_ato, hierarquia, texto_hash, primeira_deteccao, ultima_verificacao, historico: [{data_deteccao, id_execucao, campo, anterior, novo}]}]`
- `indice: {orgao: {id: {h: hash, s: situacao, d: primeira_deteccao, v: ultima_verificacao}}}`
- `meta: {total, por_orgao, indice_total, execucao}`

### categories.json

- `categorias: [{id, nome, descricao}]` — 30 categorias (1=Marco legal geral, 2=Direitos fundamentais, 3=Dados pessoais, 4=Responsabilidade civil, 5=Penal/deepfake, 6=Direitos autorais, 7=Trabalho, 8=Educação, 9=Saúde, 10=Segurança pública, 11=Defesa, 12=Judiciário, 13=Eleições, 14=Deepfake, 15=Desinformação, 16=Plataformas, 17=Biometria, 18=Reconhecimento facial, 19=Adm. pública, 20=Financeiro, 21=Consumidor, 22=Cibersegurança, 23=Agentes autônomos, 24=Transparência/rotulagem, 25=Auditoria/risco, 26=Alto risco, 27=P&D, 28=Incentivo fiscal, 29=Data center/infra, 30=Soberania digital)

### data/articles/

- **articles.json:** `meta: {total, atualizado_em}`, `artigos: [{id, editorial_topic_id, slug, title, description, summary, assunto, published_at, modified_at, source_change_ids, source_entity_ids, related_propositions, related_acts, related_laws, related_organs, related_parliamentarians, categories, keywords, official_sources: [{titulo, url, orgao}], url, status: published, selection_reason, revision_count, last_revision_reason, content: {lead, o_que_mudou: [html], situacao_atual: html, por_que_importa: html, o_que_acontece_agora: html, historico: [{data, evento, fonte}], quem_atinge: html}, revisions: [{date, source_change_ids, reason, fields_changed, summary, change_count}], editorial_hash}]`
- **editorial_state.json:** `meta`, `processadas: {change_id: {change_id, processed, editorial_action: new_article|article_update|ignored, article_id, editorial_topic_id, selection_reason, processed_at, run_id}}`, `pendentes: {change_id: {reason: cota_diaria_atingida|sem_cota_no_dia, since, editorial_topic_id, prioridade}}`, `execucoes: [{executado_em, dia, mudancas_novas, novos_artigos, artigos_atualizados, ignoradas, adiadas, stale, aguardando_curadoria, run_id, bootstrap}]`

---

## Pipeline de execução (ciclo completo)

1. **Carregar estado anterior** — lê `data/legislation/*.json` e `data/articles/`.
2. **Consultar fontes oficiais** — `update_legislation.py`:
   - Câmara: `/proposicoes` (detalhe, tramitações, autores, votações, eventos, deputados)
   - Senado: `/materia/{codigo}` (detalhe, movimentações, relatorias)
   - Multiórgão via `update_sources.py` em subprocessos isolados (timeout próprio).
3. **Comparar estado** — compara snapshot anterior vs. atual; detecta alterações de campo.
4. **Registrar mudanças** — cada alteração vira registro em `updates.json` com `proposicao`/`item`, `campo_alterado`, `valor_anterior/novo`, `data` do evento, `data_deteccao`, `fonte_url`, `timestamp_execucao`, `id_execucao`.
5. **Descobrir novas proposições** — busca incremental (desde última execução, com 1 dia de sobreposição) + keywords (`inteligência artificial`, `deepfake`, `reconhecimento facial`, etc.). Watchlist de auditoria (`PL 2688/2025`, `PL 1884/2025`, `PL 370/2024`, `PL 3592/2023`) validada diretamente na API oficial.
6. **Atualizar agenda** — eventos futuros da Câmara (60 dias).
7. **Camada editorial** — `generate_articles.py` classifica cada mudança nova por `change_id` estável:
   - `NEW_ARTICLE_CANDIDATE` → no máximo 1 artigo novo por dia (maior prioridade; demais adiados).
   - `ARTICLE_UPDATE_CANDIDATE` → atualiza artigo existente na mesma URL (preserva `published_at`, novo `modified_at`, `revision_count++`, histórico).
   - `NO_EDITORIAL_ACTION` → ruído administrativo, eco de protocolo, aguardando curadoria.
8. **Build do site** — `build_site.py` → `build_site_core.py` regenera `/docs` + camadas `ai_visibility` + `commercial_pages` + `google_ai_citation`.
9. **Validação** — `validate_site.py` + `test_audit_watchlist.py` + `check_collection.py`.
10. **Commit** — somente se `docs/` ou `data/` mudaram e validações passaram; mensagem inclui status (`concluida|parcial|falha`) e resumo editorial.

Se nada relevante mudou, apenas registra-se a verificação — **nada de conteúdo artificial**.

---

## Módulo frescor.py — cadência e limiares de frescor (fonte única)

**Problema de 2026-09-30:** o site congelou com o último estado verificado de 29/09 12:54 BRT, enquanto o cron horário (`17 * * * *`) continuava rodando e coletando. Duas falhas independentes se somaram:

1. **Publicação bloqueada.** `validate_site.py` reprovava com `README.md:10: contém referência ao domínio antigo` — o README explicava a regra do domínio legado citando o domínio legado, e a varredura tratava a documentação como artefato crítico. Como o workflow só commita com `steps.validate.outcome == 'success'`, nenhuma execução publicava. O commit era pulado **em silêncio**: o histórico do Actions mostrava a coleta terminando em poucos minutos e nenhuma data nova no dataset.
2. **Frescor mentiroso.** Limiares fixos de 30 h (ok) e 54 h (atenção) — pensados para 4 coletas/dia — classificavam 23 h de silêncio como "Monitoramento em dia", enquanto o painel e o `site.js` anunciavam um "cron diário às 07:17 BRT" que não existe. O cartão "Desde a última execução" mostrava o valor congelado do build (`0.0 h`) ao lado do selo, recalculado ao vivo (`há 23 h`).

**O que o módulo faz** (`scripts/frescor.py`, stdlib):

| Função | Retorna |
|---|---|
| `crons()` | expressões `cron` do bloco `schedule:` de `.github/workflows/update-legislation.yml` |
| `intervalo_horas()` | menor intervalo entre execuções, em horas (`17 * * * *` → `1.0`) |
| `descricao()` | texto do agendamento em português, com horários UTC e BRT |
| `limiares()` | `(ok_h, atencao_h)` derivados do intervalo (piso 3 h / 8 h) |
| `estado(idade_h)` | `"ok"` / `"atencao"` / `"critico"` / `"sem_dados"` |

**Contrato:** nenhum número de frescor é fixado à mão em página alguma. O build lê `frescor.resumo()` uma vez e:

- escreve os limiares em `data-fresh-ok` / `data-fresh-warn` (selo e painel) e `data-age-ok` / `data-age-warn` (cartões) — o `site.js` classifica com **os mesmos números**, em vez de manter uma cópia;
- escreve a cadência em `data-fresh-cron`, usada no texto do alerta do painel;
- usa `estado()` em Python (`build_site_core.metricas_monitoramento`, faixa de saúde da home) **e** em `check_collection.problems()`, para que o gate do workflow e o selo do site nunca discordem;
- joga a descrição nos textos de `/monitoramento/` e `/metodologia/`.

Com o cron horário os limiares ficam em **3 h / 8 h**: 23 h parado é crítico, e o selo aparece vermelho mesmo sem JavaScript (`data-estado` inicial sai correto do build).

**Demais correções do mesmo incidente:**

- `build_site_core._ultima_execucao()` escolhe a execução mais nova **por timestamp**, não por posição na lista (o selo usava `execucoes[0]`).
- `run_summary()` e `/relatorio/` usam `fim` (e não `data_hora`) — a hora anunciada é a mesma do selo, sem divergência de até 25 min.
- `ref_date()` usa o **dia real em Brasília** para "Hoje"/"Ontem"/"N dias atrás" e para os filtros `data-days`. Com o dataset parado, um item de hoje continua sendo "hoje"; quem avisa que ele ainda não foi coletado é o selo.
- O cartão "Desde a última execução" carrega `data-age-from` e é recalculado no navegador a cada visita (número e cor), igual ao selo.
- O bloco "Últimas 24 horas" vazio diz a verdade: com o dataset atrasado, a mensagem explica que a janela **ainda não foi coletada** em vez de "o monitoramento segue ativo".
- `validate_site.py`: menção ao domínio legado em `.md` é **aviso**; em código e artefatos continua **erro**. `README.md` não cita mais o endereço literal.
- Workflow: nova etapa "Sinalizar publicação bloqueada" falha o job com `::error::PUBLICAÇÃO BLOQUEADA` quando build/validação/auditoria reprovam, para que o congelamento nunca mais seja silencioso; `recover_audit_history.py` ganhou `continue-on-error` para não abortar a coleta.
- `tests/test_frescor.py` (16 casos) trava o contrato: cadência lida do workflow, `estado(23 h) == "critico"`, monoticidade dos estados, limiares iguais entre build e navegador, instante único no painel, ausência de números fixos no código do site, `.md` como aviso e validação verde na árvore atual.

---

## Orçamento de tempo e robustez

Problema histórico: dataset cresce → mais fichas → mais HTTP → job de 45 min no GitHub Actions era cancelado **durante a coleta**, sem rebuild/commit — site congelava.

Soluções implementadas em `update_legislation.py`:

- **Classe `Budget`:** relógio monotônico compartilhado por threads. `limite` (padrão 25 min via `MONITOR_BUDGET_SEGUNDOS`), `margem` final 90s para persistir. Métodos:
  - `decorrido()`, `restante()`, `expirado(folga)`, `checar(folga)` (levanta `BudgetExceeded`), `pausa(segundos)` (encurtada se orçamento no fim).
- **Cache de execução:** `_HTTP_CACHE` (url → payload) evita reconsultar mesma ficha; `_HTTP_HOST_FAILURES` + `HTTP_FAILURE_LIMIT` = circuit breaker por host; `_HTTP_STATS` + `por_endpoint` = telemetria.
- **Prioridade:** `_prioridade(p)` = maior score primeiro, empate → mais tempo sem verificação. `_prioridade_candidato` = relevância temática (`forte>media>infra`) > tipo (`PL/PEC > REQ`) > recência.
- **Paralelismo:** `ThreadPoolExecutor` com `WORKERS` (padrão 5) e semáforo `HTTP_CONCORRENCIA` (padrão 4). Cada thread toca só seu dict + estruturas com lock.
- **Checkpoint intermediário:** após atualizar proposições monitoradas, grava dataset antes da descoberta — se job morrer, verificação já feita não se perde.
- **Teto de fichas novas:** `MAX_NOVAS` (25) por execução, priorizado por relevância; excedente adiado.
- **Subprocesso por fonte multiórgão:** `update_sources.py` roda cada órgão com timeout próprio (`MONITOR_FONTES_TIMEOUT_S` 75s) e teto total (`MONITOR_FONTES_LIMITE_TOTAL_S` 480s). Falha de uma fonte não derruba as outras.
- **Status global:** `OK` (todas obrigatórias OK), `PARCIAL` (alguma falha/parcial), `FALHA` (nenhuma consultada ou Câmara+Senado falharam). Se `FALHA`, workflow não publica.
- **Workflow `if: always()`:** build, validação e commit rodam mesmo se coleta falhar; resumo do job e painel sinalizam parcial/falha.

---

## Módulo scoring.py — AI Legislative Impact Score

**Função pública:** `compute_impact_score(prop) -> {score:int, classificacao:str, detalhe:dict}`

**Rúbrica (soma máxima 100):**

| Critério | Máx | Como pontuar |
|---|---|---|
| `abrangencia_regulatoria` | 20 | Marco geral/nacional 20, setorial amplo 12, tema pontual 6, simbólico/arquivado 0-2 |
| `estagio_tramitacao` | 15 | À sanção/convertida 15, plenário/pronta pauta 12, comissão com parecer 9, comissão sem parecer 6, apresentação 3, arquivada 0 |
| `proximidade_votacao` | 10 | Pauta/votação iminente 10, urgência 8, prioridade 5, ordinária 2, parada 0 |
| `urgencia_regime` | 10 | Urgência constitucional/MP 10, urgência aprovada 8, prioridade 5, ordinária 2 |
| `apensados` | 5 | Principal 10+ =5, 3-9=3, 1-2=1, apensada/sem=0 |
| `impacto_economico` | 15 | Fiscal bilionário/setor inteiro 15, custos relevantes 9, moderado 5, baixo 0-2 |
| `impacto_direitos` | 10 | Direitos fundamentais/dados/penal 10, consumidor/trabalho 6, indireto 3, nenhum 0 |
| `alcance_setorial` | 5 | Multissetorial 5, 2-3 setores 3, 1 setor 1 |
| `relevancia_institucional` | 10 | Cria/governa autoridade nacional 10, altera competências 6, pontual 3, nenhum 0 |

**Funções:**

- `classify(score)`: 90-100 CRÍTICO, 75-89 MUITO RELEVANTE, 60-74 RELEVANTE, 40-59 MONITORAR, 0-39 BAIXA PRIORIDADE.
- `_norm(t)`: NFKD → ascii → lower, para matching conservador.
- `rubric_table_html()`: tabela HTML da rúbrica para metodologia.

**Regras:**

- Critério conservador: na dúvida, pontua para baixo.
- Registros recém-descobertos (`revisao_pendente`) nunca entram como CRÍTICO automático: se score ≥90, trava em 89.
- Scores do bootstrap (08/09/2026) são preservados manualmente e nunca recalculados para manchete.

---

## Módulo update_legislation.py — Coletor Câmara/Senado

**Constantes globais:**

- `CAMARA`, `SENADO`, `BRT`, `UA`, `TIPOS_INCLUIR`, `TIPOS_REQUERIMENTO`
- `STRONG_PATTERNS`, `MEDIUM_PATTERNS`, `INFRA_ONLY` → regex `STRONG_RE`, `MEDIUM_RE`, `INFRA_RE`
- `FONTES_CAMARA`, `FONTES_SENADO` (rótulos para auditoria)
- `_env_int(nome, padrao)` — lê env com fallback.

**Funções HTTP e utilitárias:**

- `endpoint_label(url)`: rótulo estável sem IDs (ex.: `camara:proposicoes/{id}/tramitacoes`).
- `_stat_endpoint(url, campo, valor)`: incrementa telemetria por endpoint.
- `http_stats()`: retorna `{chamadas, cache, falhas, tempo_total, por_endpoint}`.
- `_http_urllib(url, timeout)` / `_http_curl(url, timeout)`: usa curl se disponível (handshake mais robusto), senão urllib stdlib.
- `http_get_json(url, timeout, retries, cache)`: GET com orçamento, cache, retry, circuit breaker, telemetria. Levanta `BudgetExceeded` quando orçamento acaba.
- `polite_pause()`: `Budget.pausa(0.3)`.
- `relevance(text)`: classifica `forte|media|infra|None` sobre texto normalizado.
- `load(name)`, `save(name, obj)`, `today_brt()`, `parse_run_date(s)`, `date_only(dt_str)`, `as_list(x)`.

**APIs Câmara:**

- `camara_find_id(tipo, numero, ano)`: busca `/proposicoes?siglaTipo=&numero=&ano=`.
- `camara_detail(pid)`: `/proposicoes/{id}`.
- `camara_tramitacoes(pid)`: `/proposicoes/{id}/tramitacoes`.
- `camara_autores(pid)`: `/proposicoes/{id}/autores`.
- `camara_votacoes(pid)`: `/proposicoes/{id}/votacoes` (melhor esforço, timeout 12s).
- `camara_deputado(uri_or_id)`: `/deputados/{id}`.
- `camara_id_from_prop(p)`: extrai id de URLs.

**APIs Senado:**

- `senado_detail(codigo)`: `/materia/{codigo}.json`.
- `senado_movimentacoes(codigo)`: `/materia/movimentacoes/{codigo}.json`.
- `senado_relatorias(codigo)`: `/materia/relatorias/{codigo}.json`.
- `senado_search(sigla, numero, ano, palavra_chave)`: `/materia/pesquisa/lista`.
- `senado_codes_from_prop(p)`: extrai códigos de URLs.

**Tipos e categorias:**

- `infer_change_type(text)`: apensação, desapensação, arquivamento, sanção, veto, parecer, votação, pauta, relatoria, etc. via keywords normalizadas.
- `infer_categories(ementa, titulo)`: mapeia keywords → ids de categorias (0..30).
- `CATEGORY_KEYWORDS`: lista de ([keywords], [ids]).

**Classe Collector:**

Atributos: `now`, `run_id`, `run_iso`, `today`, `changes`, `errors`, `verified`, `updated`, `new_props`, `fontes_ok`, `nao_verificadas`, `verificadas_ids`, `verificadas_casa`, `fases`, `_changes_gravadas`, `_lock`.

Métodos:

- `fase(nome)`: context manager que mede duração e acumula em `fases`.
- `_resumo_execucao()`: retorna métricas de execução + http.
- `_bump(attr)`, `_marca_verificada(prop_id)`, `_add_fonte(fonte)`, `_add_fontes(fontes)` (thread-safe).
- `add_change(*, data_evento, titulo, descricao, tipo, proposicao, fonte, fonte_url, campo, anterior, novo)`: adiciona mudança ao buffer.
- `update_camara_prop(p, last_run)`: atualiza ficha Câmara (regime, movimentação, principal, relator, autores, votações). Chama `_record_movimentacao`, `_situacao_from_tram`, `_detect_apensacoes`, `_resolve_principal`.
- `_record_movimentacao(p, last, last_date, last_text, last_sigla, stored, ficha_url, last_run)`: registra mudança de movimentação (distingue alinhamento de texto vs. nova movimentação, detecta se já constava antes).
- `_situacao_from_tram(last, p)`: deriva situação preservando estado terminal curado (arquivada, transformada) e contexto de apensação.
- `_detect_apensacoes(trams, p, ficha_url, last_run)`: detecta novas apensações no pacote da principal.
- `_resolve_principal(detail, p)`: resolve proposição principal via `uriPropPrincipal`.
- `update_senado_refs(p, last_run)`: atualiza refs Senado (decisão, informes, relatoria).
- `discover_camara(known_keys, last_run)`: descoberta incremental (desde última execução) + keywords + watchlist auditoria. Retorna lista de (item, relevancia, via).
- `build_new_camara_record(item, rel, via)`: constrói registro preliminar para nova proposição Câmara.
- `discover_senado(known_keys)`: busca Senado por palavra-chave + watchlist.
- `build_new_senado_record(m)`: constrói registro preliminar Senado.
- `update_events(events)`: atualiza agenda Câmara (60 dias, filtro relevância).
- `_ordinal(data_iso)`, `_prioridade(p)`, `_prioridade_candidato(cand)` (ordenação).
- `_snapshot_dataset(props_all, laws_f, ev_f, up_f)`: fotografia do banco ao fim da execução.
- `_status_casa(verificadas, falhas)`, `_saude_casas()`: saúde por casa.
- `_atualizar_registro(rec, n_ev)`, `_gravar(props_f, up_f, ev_f, laws_f, tl_f, pm_f, props, exec_record, status, atos_f)`.
- `run(dry_run)`: orquestra tudo (fases, threads, checkpoint, descoberta, agenda, sugestões de conversão em lei, saúde multiórgão, persistência).

**CLI:** `--dry-run`, `--budget-min`, `--max-novas`, `--limite`, `--workers` (env: `MONITOR_BUDGET_SEGUNDOS`, `MONITOR_MAX_NOVAS`, `MONITOR_MAX_PROPS`, `MONITOR_WORKERS`, `MONITOR_HTTP_*`, `MONITOR_SEM_FONTES`).

---

## Módulo sources/ — Coletores multiórgão

### sources/base.py

**Exceções:** `FonteIndisponivel`, `OrcamentoEsgotado`.

**Constantes:** `TOPICOS_BUSCA` (10 termos), `FORTE_PATTERNS` (60+), `REVISAR_PATTERNS`, regex compilados.

**Funções puras:**

- `normalizar(texto)`: NFKD lower sem acento.
- `classificar_relevancia(*textos)`: `forte|revisar|None` — sem sinal claro, descarta.
- `limpar_texto(valor, limite)`: HTML → texto plano, unescape, trim.
- `url_canonica(url)`: chave de identidade sem esquema/query/fragmento.
- `hash_texto(*partes)`: sha1 dos textos normalizados.
- `data_iso(valor, formatos)`: extrai YYYY-MM-DD de RSS/JSON/HTML.

**HTTP:**

- `Resposta`: `url, status, content_type, texto, segundos, erro, url_final`, prop `ok`.
- `Cliente`: timeout, retries, orçamento, UA, logger, cache, stats. Métodos:
  - `rotulo_endpoint(url)`, `_stat()`, `resumo_stats()`
  - `get(url, accept, timeout, cache, headers, retry_403)`: retry com backoff, 403 com espera 20s se `retry_403`, cache, telemetria.
  - `get_json()`, `get_texto()`, `get_rss()` (levanta `FonteIndisponivel` se vazio).

**Parsers:**

- `parse_rss(xml, base_url)`: RSS 2.0 e Atom → `{titulo, link, data, descricao}`.
- `parse_html_links(html, base_url, padrao_href, limite, descricao_apos)`: listagem Plone gov.br.
- `parse_dou_json(dados)`: envelope DOU JSON (`jsonArray` etc.) → itens com `titulo, link, data, descricao, tipo_ato, secao`.
- `parse_plone_search(dados)`: `@search` gov.br → `@id, title, description, effective`.
- `parse_cnj_atos(dados)`: API CNJ `{data:[{id, tipo, numero, ementa, ...}]}`.
- `parse_dou_embutido(html)`: extrai JSON embutido `<script id="BuscaDouPortlet_params">`.
- `html_para_texto_blocos(html, padrao_href, base_url, limite)`: fallback DOU HTML.

**Modelo de canal/fonte:**

- `Canal(rotulo, url, formato, parser, padrao_href, paginas, passo, accept, obrigatorio, extrai, topicos, url_template, tipo_padrao, opcoes, filtro_tema, dias)`: gera `urls()` com `{topico}`, `{from}`, `{to}` (DD-MM-AAAA) e paginação `b_start:int`.
- `ResultadoFonte(orgao, nome)`: `itens, tentativa_em, duracao, canais_ok, canais_falhos, canais_falhos_obrigatorios, canais_opcionais_falhos, endpoints, erros, itens_consultados, itens_relevantes, itens_descartados, itens_duplicados, revisao_pendente, parcial_por_orcamento, canais_detalhe`. Prop `status` (ok/parcial/falha), `erro_resumo()`, `como_dict(novidades)`.
- `ContextoFonte(orgao, timeout_s, orcamento, dry_run, ua, logger, timeout_http, retries)`: `restante()`, `expirado()`, `checar()`, `cliente`.
- `Fonte`: base para conectores. `orgao, nome, obrigatoria, canais, repetir_403`, `coletar(ctx, resultado)`, `_marca_falha`, `_absorver(resultado, itens, canal)` (deduplicação por `url_canonica`, classificação relevância, id estável, hash), `id_item(item)` (slug da URL), `_coletar_canal`, `_coletar_rss/json/html`, `_parser_json`, `_parse_wp_json`, `_parse_ckan`, `_parse_lista_json`, `_pos_processar`.

**Registro:**

- `registrar(classe)`: decorador que registra fonte em `_REGISTRO`.
- `fontes_disponiveis()`, `instanciar(orgao, logger)`.

### sources/anpd.py, cnj.py, tse.py, dou.py, planalto.py, mcti.py

Cada arquivo declara uma classe `@registrar` com `orgao`, `nome`, `obrigatoria`, `repetir_403` e `canais: [Canal(...)]`.

- **anpd.py — ANPD:** API `https://www.gov.br/anpd/++api++/@search` (plone.restapi). Canais: notícias recentes (News Item, sort effective desc), notícias por tema (SearchableText=TOPICOS_BUSCA), regulação/normas (path regulacao), consultas públicas, tomada de subsídios, atos normativos (File + resolução), fiscalização e agenda regulatória (pastas oficiais). Parser `plone_search`.

- **cnj.py — CNJ:** API `https://atos.cnj.jus.br/api/atos` + WP REST `https://www.cnj.jus.br/wp-json/wp/v2/posts`. Canais: atos normativos por tema (API oficial com `tipo, numero, data_publicacao`), notícias oficiais (WP), busca temática (SearchableText). Parser `cnj_atos` + `wp_json`.

- **tse.py — TSE:** Portal JSON `https://www.tse.jus.br/++api++/@search` + DOU busca `https://www.in.gov.br/consulta/-/buscar/dou`. Canais: atos normativos (portal, path /legislacao), notícias (portal, portal_type Noticia), atos por tema (portal), atos DOU por tema (filtro hierarquia TSE/Justiça Eleitoral), resoluções DOU (orgPrin Poder Judiciário + orgSub TSE). `repetir_403=True` (WAF do TSE bloqueia rajadas, volta após 20s). Filtros `_filtro_tse`, `_filtro_resolucao_tse`.

- **dou.py — DOU:** Busca oficial `https://www.in.gov.br/consulta/-/buscar/dou`. Canais: busca por tema (TOPICOS_BUSCA, dias 30, filtro por hierarquia relevante — ANPD, CNJ, TSE, Planalto, MCTI, etc.), busca por tipo (resolução, portaria, decreto, lei). Parser `dou_embutido` + fallback HTML. Filtro `ESCOPO_HIERARQUIA`.

- **planalto.py — Planalto:** DOU busca + RSS `https://www.gov.br/planalto/.../noticias/RSS`. Canais: atos do Poder Legislativo (leis, vetos, filtro `Atos do Poder Legislativo` + tipo Lei/Decreto Legislativo/Mensagem), atos da Presidência (decretos, MPs, filtro `Presidência da República`), notícias RSS (opcional), notícias página (opcional). Dias 90 (atos presidenciais raros). Filtros `_filtro_presidencia_legislativo`, `_filtro_presidencia_direta`, `_hierarquia_ok`, `_tipo_ok`.

- **mcti.py — MCTI:** DOU busca + portal `https://www.gov.br/mcti/...`. Canais: atos MCTI no DOU (orgPrin MCTI, temas), notícias portal (RSS ou HTML), programas (portarias, editais). Parser `dou_embutido` + `plone_search`.

### update_sources.py

**Funções principais:**

- `agora_brt()`, `ts_iso()`, `load(nome, padrao)`, `save(nome, obj)`, `inferir_tipo_evento(item)` (mapeia texto → tipo evento: revogação, sanção, veto, regulamentação, etc.).
- `executar_fonte(orgao, timeout_s, orcamento, dry_run, logger) -> {orgao, nome, obrigatoria, itens, saude, http, erro_fatal}`: executa conector no processo atual.
- `_resultado_falha(orgao, motivo, duracao, erros)`: fábrica de falha explícita.
- `executar_fonte_subprocesso(orgao, timeout_s, logger)`: roda fonte em subprocesso com timeout rígido (kill se estourar), lê JSON temporário.
- `executar_todas(orgaos, timeout_s, usar_subprocesso, logger, orcamento, limite_total_s) -> {orgao: resultado}`: loop com teto total, marca não executadas como falha explícita ("não executada por orçamento").
- `_atos_vazios()`: esqueleto `atos.json`.
- `_historico_padrao(atos_f, execucoes_anteriores, orgao, status_atual, agora)`: última execução OK (nunca estimado).
- `mesclar(atos_f, up_f, resultados, exec_info, execucoes_anteriores, logger) -> {fontes_monitoradas, mudancas, novidades, novos, alterados, status_global, fontes_falha, fontes_parciais, fontes_ok, http_fontes}`: compara coleta vs. estado anterior, detecta novos e alterações (texto_hash, situacao), registra histórico por item, aplica retenção (`LIMITE_ATOS_POR_FONTE` 400 por fonte, `RETENCAO_DIAS` 180), limpa índice antigo.
- `_mudanca(registro, exec_info, tipo, campo, de, para)`: fábrica de mudança.
- `_somar_http(resultados)`: soma telemetria.
- `calcular_status_global(fontes_monitoradas, camara_senado)`: OK|PARCIAL|FALHA.
- `registrar_mudancas(up_f, mudancas, exec_info, logger) -> n`: adiciona ao log, deduplica por `(id_execucao, titulo, data)`, rotaciona excedente para `updates_arquivo.json`.
- `relatorio_compacto(resultados, limite_amostras)`: relatório enxuto saúde+amostras para CI.
- `_resumo_texto(dados)`: imprime resumo no log.
- `main(argv)`: CLI `--fonte, --todas, --listar, --timeout, --json, --relatorio, --limite-amostras, --dry-run, --gravar, --sem-subprocesso`.

---

## Módulo generate_articles.py — Camada editorial

**Princípios:** criação e atualização são ações diferentes; identidade de assunto estável (`editorial_topic_id`) derivada de IDs do dataset; idempotente por `change_id`; máx. 1 novo artigo/dia; tolerante a ausência de novidades; falha nunca corrompe dataset legislativo.

**Constantes:**

- `MAX_NEW_PER_DAY=1`, `STALE_DAYS=30`, `MIN_SCORE_NOVO_ASSUNTO=75`, `NEW_MIN_SCORE=12`, `UPDATE_MIN_SCORE=5`, `MAX_REVISIONS_LOG=200`
- `ACTION_NEW="new_article"`, `ACTION_UPDATE="article_update"`, `ACTION_IGNORED="ignored"`
- `TIPO_PESO`: peso por `tipo` de mudança (nova lei 9, sanção 8, parecer 6, tramitação 2, etc.)
- `TITULO_BONUS`: regex → bônus (transformação em norma 8, aprovado 6, parecer 5, pauta 5, etc.)
- `ECO_PROTOCOLO`: `(registro incorporado)|(alinhamento de texto à ficha oficial)` — marcador mecânico do coletor.
- `TITULO_PROTOCOLO`: `PL 123/2024: apresentação/publicação/recebimento` — sem valor editorial.
- `RUIDO_TITULO`: extrato, edital, pregão, ata, credenciamento, etc. — nunca gera artigo.
- `ATO_TIPO_PESO`, `ATO_ORGAO_PESO`, `ESCOPO_HIERARQUIA`: pesos multiórgão.

**Funções utilitárias:**

- `_slug(texto, limite)`: NFKD → slug.
- `_date_only(s)`: extrai YYYY-MM-DD.
- `hoje_brt()`, `agora_iso()`.
- `change_id(m)`: ID estável reprodutível (sha1 de campos de identidade: id_execucao, timestamp, tipo, titulo, data, proposicao, item, url, campo, valor_novo).
- `dia_editorial(m, fallback)`: dia editorial = data_deteccao registrada (nunca hoje presumido).
- `fmt_data(d)`, `_trim(texto, n)`.
- `load_json(path, padrao)`, `load_artigos(base_art)`, `load_state(base_art)`, `save_artigos(artigos_f, base_art)`, `save_state(state, base_art)`.

**Classe Contexto:**

- Carrega `propositions.json`, `atos.json`, `laws.json`, `categories.json`, `parliamentarians.json`, `updates.json`.
- `props_por_id`, `atos_por_id`, `_principal_cache`.
- `principal_de(p)`: resolve proposição principal (apensadas compartilham tópico), segue cadeia `proposicao_principal` ou regex `Apensado ao PL X/YYYY`.

**Identidade editorial:**

- `prop_topic_id(p)`: `tipo-numero-ano-slug(titulo)` (ex.: `pl-2338-2023-marco-legal-ia`).
- `ato_topic_id(a)`: `ato-orgao-slug-titulo-hash`.
- `topico_da_mudanca(m, ctx) -> (tipo_entidade, entidade, editorial_topic_id)`: mapeia mudança para tópico via IDs oficiais, agregando apensadas ao principal.

**Classificação:**

- `_titulo_limpo(m)`: remove marcadores mecânicos do coletor.
- `_peso_titulo(m)`: bônus por regex no título/descrição.
- `_ruidosa(m)`, `_eco_protocolo(m)`, `_peso_ato(a)`.
- `classify_change(m, topico, artigo, ctx, cfg) -> (acao, prioridade, motivo)`: regras determinísticas auditáveis. Retorna `NEW_ARTICLE_CANDIDATE` (sem artigo, peso ≥ NEW_MIN_SCORE e fato autônomo), `ARTICLE_UPDATE_CANDIDATE` (com artigo, peso ≥ UPDATE_MIN_SCORE), `NO_EDITORIAL_ACTION` (sem entidade, aguardando curadoria, sem título, ruído, eco protocolo, abaixo limiar).
- `find_existing_article(artigos, topic_id)`: busca por identidade, não texto.
- `should_create_new_article(candidatos, artigos, cfg, dia) -> (vencedor, motivo)`: cota diária considera só `new_article`.
- `should_update_article(artigo, m, decisao)`.

**Conteúdo:**

- `_rotulo_orgao(orgao)`: ANPD, CNJ, TSE, DOU, etc.
- `_bulks_mudanca(m, ctx)`: balaústre factual HTML de uma mudança (data, título limpo, descrição trim, campo alterado, órgão, fonte oficial).
- `esc_html(t)`.
- `_conteudo_prop(p, mudancas, ctx, motivo) -> {lead, o_que_mudou, situacao_atual, por_que_importa, o_que_acontece_agora, historico, quem_atinge}`: 100% do dataset.
- `_conteudo_ato(a, mudancas, ctx, motivo)`: idem para ato multiórgão.

**Criação/atualização:**

- `_parlamentares_relacionados(ctx, p)`, `_slug_unico(base, artigos_f)`.
- `create_article(topico, mudancas_topico, ctx, artigos_f, cfg, dia, decisao, change_ids, motivo)`: cria novo artigo (URL nova, slug único, selection_reason, revisions).
- `_hash_artigo(a)`: hash do conteúdo efetivo (detecta edição real).
- `update_article(artigo, topico, mudanca, ctx, cfg, dia, motivo) -> (artigo, mudou, fields_changed)`: atualiza snapshots, insere balaústre, coalescência de movimentações do mesmo dia (uma revisão por dia por assunto).
- `mudancas_do_topico(topico, mudancas, ctx, dia_max)`: todas mudanças do tópico até dia editorial.

**Pipeline:**

- `run_editorial(cfg, logger) -> resumo`: carrega contexto, lista mudanças não processadas, varredura stale (candidatos adiados > STALE_DAYS viram ignored), agrupa por dia editorial, classifica, aplica atualizações primeiro, cria 1 novo artigo (maior prioridade), reclassifica candidatos do mesmo dia que agora pertencem ao artigo criado, adia demais candidatos, registra ignorados, persiste só se houve ação (sem commit vazio).
- `_aplicar_update(d, ctx, artigos_f, cfg, dia)`, `_registrar(state, d, artigo, acao, motivo, cfg, extra)`.
- `_cfg_padrao()`: lê env `MONITOR_ARTIGOS_MAX_NOVOS_DIA`, `MONITOR_ARTIGOS_STALE_DIAS`.
- `main(argv)`: CLI `--dry-run, --bootstrap, --max-new-per-day, --stale-days, --run-id, --legislation-dir, --articles-dir, --strict`.

---

## Módulo build_site_core.py / build_site.py — Gerador do site

`build_site.py` é wrapper fino que:

- Define `SITE_URL="https://monitor.lcfconsulting.com.br"` e `OLD_SITE_URL="https://monitor-legislativo-five.vercel.app"`.
- Força `core.SITE_URL = SITE_URL`.
- Instala camadas: `ai_visibility.install(core)`, `commercial_pages.install(core)`, `google_ai_citation.install(core)`.
- Expõe todos símbolos de `core` no módulo para compatibilidade.
- `_assert_domain_migration()`: falha build se `sitemap.xml, robots.txt, llms.txt, llms-full.txt, ai-content.md, agent-permissions.json, mcp-actions.json, index.html` ainda contiverem domínio antigo, ou se sitemap não usar domínio oficial.

`build_site_core.py` (2095 linhas) é o gerador real:

**Globals:** `BASE, DATA, ASSETS, OUT=docs/, SITE_URL, OLD_DOMAIN, SITE_NAME, TAGLINE, AUTHOR_NAME, AUTHOR_ORG, AUTHOR_URLS, CONSULTING_URL, DISCLAIMER, CTA_TEXT, CTA_SUB, EXECUTION_DATE, EXECUTION_RUN, EXECUTION_TS, _SLUGS`.

**Funções base:**

- `_freshness_badge()`: selo no topo de todas páginas com `data-freshness=EXECUTION_TS` (idade recalculada no navegador; se cron parar, fica vermelho).
- `load(name)`, `esc(t)`, `build_slugs(props)`, `slugify_prop(pid)`, `prop_fs_path(pid)`, `fmt_date(d)`, `ref_date()`, `days_ago(d)`, `rel_label(d)`, `score_class(s)`, `score_label(s)`, `status_group(p)`, `cat_map()`, `prop_link(p)`, `prop_link_by_id(pid, by_id)`, `changes_for_prop(pid, updates)`, `guess_principal_id(p)`, `fonte_label(url)` (só domínios oficiais = "Fonte oficial"), `near_vote(p)` (heurística honesta: sanção, pauta, plenário, redação final), `change_prop_href(m, by_id)`.
- JSON-LD: `ld_website()`, `ld_breadcrumbs(items)`, `ld_collection(name, desc, path)`, `combine_ld(*blocks)`.
- Layout: `_atos_footer_link()`, `_artigos_footer_link()`, `page(title, desc, path, body, extra_head, og_type, jsonld)` (canonical, OG, nav ativa, freshness badge, footer com links dados/metodologia/aviso, CTA LCF, `site.js`), `write(path, content)`, `tags_for_prop(p, cats)`, `change_card(m, by_id)`, `run_summary()`.

**Builders de páginas:**

- `build_home(props, laws, events, updates, timeline, cats, artigos)`: hero, verify block (data/hora/verificadas/mudanças/novas + fontes), health strip (idade, cobertura, pendentes, status), o que mudou (24h, 7d), dashboard (8 métricas), matérias maior impacto (top 6 por score), próximas de votação (near_vote), novas (30d), normas recentes, artigos recentes (3), agenda, categorias, CTA.
- `build_propositions(props, cats)`: lista filtrável (JS) com filtros casa, ano, status, categoria, score, busca textual; rows com `data-prop, data-casa, data-ano, data-statusgroup, data-cats, data-score, data-search`.
- `seo_title_prop(p)`, `seo_desc_prop(p)`, `build_prop_pages(props, cats, updates, artigos)`: ficha individual por proposição (identificação, resumo, score box com detalhe, mudanças recentes, documentos, relacionadas, timeline, fontes, artigo relacionado, review note, business_html).
- `build_updates(props, updates)`: histórico cronológico com filtros Hoje/7d/30d/Todas.
- `build_laws(laws)`, `build_timeline(timeline)`, `build_parliamentarians(parms, props)`, `build_agenda(events)`, `build_metodologia(props, laws, updates)` (tabela rúbrica, fontes, frequência, critérios, limitações, correção, automação/orçamento, status por fonte), `build_report(props, laws, updates, events)` (resumo executivo fatos vs. interpretação, top 5 desenvolvimentos).
- **DataViz:** `_date_only(s)`, `_parse_ts(s)`, `_status_run(ex, agora)`, `_status_run_label(st)`, `_latencia_media(latencias, limite)`, `metricas_monitoramento(props, laws, events, updates) -> {gerado_em, execucoes, ultima, frescor, kpis, series, dataset, mudancas, http_por_endpoint, alertas}`, `build_monitoramento(props, laws, events, updates, met)`: painel com alertas, KPIs, quadro por órgão (8 fontes obrigatórias, status, última tentativa/OK, itens, novidades, erros, endpoints), séries temporais (cobertura, duração×orçamento, monitoradas, HTTP, mudanças, novas), composição dataset (status, faixa score, ano, categoria, curadoria), atividade (calendário heatmap 26 semanas, por mês, por tipo), histórico execuções (tabela 15 últimas), custo por endpoint e tempos por fase.
- `build_sitemap(paths)`: `sitemap.xml` + `robots.txt` (preserva lastmod por URL via `_SITEMAP_LASTMOD` global).
- `main()`: carrega datasets, `build_slugs`, limpa `OUT`, copia `data/legislation` → `docs/data`, `assets` → `docs/assets`, chama todos builders, gera `data/monitoramento.json`, chama `build_articles.build` se existir dataset editorial, monta sitemap.
- `self_module()`: retorna módulo atual para `build_articles`.

---

## Módulo build_articles.py — Renderização de /artigos/

- `carregar_artigos(base)`: lê `articles.json` ou None.
- `artigos_publicados(artigos_f)`, `artigos_para_prop(artigos_f, pid)`, `_url(core, a)`.
- `article_jsonld(SITE_URL, a)`: NewsArticle com `headline, description, url, mainEntityOfPage, datePublished, dateModified, inLanguage, isAccessibleForFree, author (Leandro Calado), publisher (LCF), keywords, articleSection, about (Legislation), mentions (GovernmentOrganization, Person)`.
- `_fmt(d)`, `_resolver_site(html, site_url)`, `_secao(titulo, corpo, id_ancora)`, `_bullets_o_que_mudou(conteudo, limite)`.
- `render_article(core, a, artigos_f)`: HTML completo com breadcrumbs, dateline (publicado/atualizado/revisão/autoria), lead, seções O que mudou (com <details> se > limite), Situação atual, Por que importa, O que acontece agora, Histórico, Quem pode ser afetado, Relacionados (fichas monitor, atos, parlamentares, artigos relacionados por categoria/proposição), Fontes oficiais, Revisões (<details>), disclaimer. SEO: `article:published_time, article:modified_time, author`, JSON-LD combinado com breadcrumbs.
- `render_index(core, artigos_f)`: índice /artigos/ com cards ordenados por `modified_at`, datas, assunto, categorias, revisão.
- `build(core, artigos_f) -> n`: gera `artigos/index.html` + `artigos/<slug>/index.html`, preenche `_SITEMAP_LASTMOD`, copia `articles.json` e `editorial_state.json` para `docs/data/`.

---

## Módulo dataviz.py — Gráficos SVG

Sem dependências externas, sem JS, usa variáveis CSS do site.

- `PALETA`, `CORES`, `esc(t)`, `_fmt(v)`.
- `bar_chart(items, width, height, color, unidade, mostrar_valores, rotulo_max)`: barras verticais (últimas 14), grade, valores, rótulos truncados, `<title>` acessibilidade.
- `bar_chart_h(items, width, bar_height, gap, color, rotulo_max)`: barras horizontais (ranking), largura proporcional, valor bold.
- `line_chart(labels, series, width, height, y_max, unidade)`: `series=[{nome, valores, cor, area}]`, área opcional, pontos com `<circle><title>`, eixo X com até 6 rótulos.
- `legenda(series)`, `stacked_bar(items, width, altura)` (barra única empilhada), `stacked_legenda(items)`, `heatmap(dias, width, cell, gap, semanas, fim)`: calendário intensidade (últimas N semanas até `fim`, meses no topo, dias da semana à esquerda, opacidade por valor).

---

## Módulos ai_visibility.py, google_ai_citation.py, commercial_pages.py

### ai_visibility.py

`install(core)` patcha `core.page` e `core.main`:

- `enhanced_page`: injeta `<link rel="alternate" llms.txt>`, `<link rel="mcp-actions">`, JSON-LD Organization (LCF + founder Leandro), `data-mcp-action="contact-lcf-consulting"` no CTA.
- `write_ai_files()`:
  - `_artigos_para_descoberta`, `_ordenar_por_frescor`, `secao_artigos_llms`, `secao_artigos_llms_full`.
  - `llms.txt`: Key Pages, Structured Data, Artigos, AI Discovery, Commercial.
  - `llms-full.txt`: llms.txt + High-impact proposições (top 20) + Source policy + artigos detalhados.
  - `ai-content.md`: índice legível por IA com canonical, coleções, artigos, feeds.
  - `agent-permissions.json`: `{version, site, updated, public_access:{crawl, read_html, read_structured_feeds, citation}, write_actions:false, authentication_required:false, high_stakes_notice, commercial_contact}`.
  - `mcp-actions.json`: `{version, site, actions:[contact-lcf-consulting (declarative), read-legislative-updates (GET /data/updates.json), read-articles, read-propositions]}`.
  - `AGENTS.md`: propósito, preferred sources, rules (fonte oficial autoridade, não inferir voto, etc.).
  - `robots.txt`: AI crawler policy (Allow * exceto Bytespider Disallow), Sitemap oficial.

### google_ai_citation.py

`install(core)`:

- `enhanced_page`: só na home (`path==""`), injeta bloco `#sobre-o-monitor` (FONTE PRIMÁRIA, o que é o monitor, fontes, como citar, entidade responsável) antes de `#verificacao`. Adiciona JSON-LD graph com Organization (LCF), WebSite (Monitor, alternateNames, publisher, creator, about), Dataset (distributions para 3 JSONs, isAccessibleForFree).

### commercial_pages.py

Funções:

- `cta(label, sector, kind)`: link `/diagnostico/?setor=&interesse=` com `data-commercial-cta`.
- `strip()`: aside comercial fixo no topo (exceto login/app) com CTA diagnóstico + briefing.
- `input_field(name, label, kind, required, options)`: factory de inputs (text, email, tel, password, select, textarea) com autocomplete.
- `diagnostics()`: grid com card explicativo + form `#diagnostic-form` (nome, empresa, cargo, email, telefone, setor, tamanho, uso_ia, area_controle, urgencia, preocupacao textarea, interesse) + honeypot website + consent + status + noscript.
- `business_html(p)`: seção Impacto empresarial (FATO OFICIAL + ANÁLISE, setores afetados, dimensões, disclaimer, watchlist button, CTA).
- `prop_card(p, core, full)`: card com score, fato oficial (descrição, datas, fonte), interpretação (por que importa, setores, impacto, próxima decisão, ação), por que score (detalhe ou nota curadoria), watchlist.
- `briefing_body(model, core)`: corpo briefing executivo (nota amostra, mudanças críticas, top 5 full, mudanças período, agenda 7d, pontos atenção, metodologia, CTA).
- `alert_form(core)`: form `#alert-form` (email, frequencia, score_min, temas multi, proposicoes multi, orgaos multi, consent, honeypot, status).
- `build(core) -> paths`: emite páginas via `emit(path, title, desc, body, private)`:
  - `solucoes`: cards ofertas de `CONFIG['offers']` (preço BRL, audience, features, CTA).
  - `diagnostico`: `diagnostics()`.
  - `para-empresas`: grid + dimensões + segurança.
  - `briefing-executivo`: amostra `briefing(as_of=EXECUTION_DATE)`.
  - `alto-impacto`: filtro score + todos props ordenados por score.
  - `setores/<slug>`: por setor (focus, projetos relacionados top 8, mudanças recentes, eventos, CTA setorial).
  - `casos-de-uso` e `casos-de-uso/<slug>`: personas.
  - `alertas`: `alert_form`.
  - `watchlist`: lista local + sync button.
  - `login` (private, noindex), `app` (private), `privacidade`.
  - Retorna lista de paths indexáveis.
- `install(core)`: patcha `page` (injeta `commercial.css`, `commercial.js`, `commercial-nav` com links Para empresas, Soluções, Briefing, Alto impacto, Casos de uso, Alertas, Watchlist, Área cliente; injeta `strip()` após header; injeta `sector-links` antes de footer; trim lines) e `main` (chama `old_main()`, `build(core)`, reescreve sitemap com novas URLs, preserva robots.txt).

---

## Camada comercial B2B

As páginas públicas permanecem como demonstração. Ofertas em `config/commercial.json`; geração em `scripts/commercial_pages.py`; API em `api/index.py`; dados comerciais privados via PostgreSQL.

**config/commercial.json:**

- `currency: BRL`, `pricing_note`, `offers: [{id, name, min, max, period, featured, users, audience, features}]` (monitor-ia 1500-3000/mês, radar-executivo 4000-8000/mês featured 5 users, institucional sob consulta, diagnostico 5000-15000/projeto), `social_proof:{enabled, cases, logos, testimonials, results}`, `whatsapp`, `sectors: {fintech, bancos, seguros, saude, data-centers, cloud, tecnologia, escritorios-advocacia, associacoes: {name, categories, focus}}`, `personas: {relacoes-governamentais, juridico-regulatorio, compliance, public-affairs, diretoria-executiva, escritorios-advocacia, associacoes-empresariais: {name, value}}`.

### commercial/store.py

Store transacional privado:

- `SCHEMA`: `commercial_records(kind TEXT, id TEXT, account_id TEXT, payload TEXT, created_at BIGINT, updated_at BIGINT, PRIMARY KEY(kind,id))`.
- `Store(conn, postgres)`: `execute(sql, args)` (troca ? por %s se postgres), `get(kind, key) -> dict|None`, `put(kind, key, data, account)`, `insert(kind, key, data, account) -> bool` (ON CONFLICT DO NOTHING), `list(kind, account, limit) -> [(id, payload)]`, `delete(kind, key)`, `lock(key)` (pg_advisory_xact_lock se postgres), `commit()`.
- `connect()`: context manager; se `DATABASE_URL` → psycopg; elif `MONITOR_DEV=1` e não Vercel → SQLite em `COMMERCIAL_SQLITE` ou `/tmp/monitor-commercial.sqlite3` com `BEGIN IMMEDIATE`; else RuntimeError. Yield store, commit/rollback, close.
- `migrate()`: cria tabela + índice `commercial_account_idx(kind,account_id)`.

### commercial/service.py

Lead capture, alertas consentidos e operações piloto isoladas por conta.

- `EVENTS`: 10 eventos (commercial_cta_click, diagnostic_started, diagnostic_submitted, briefing_sample_view, pricing_view, sector_page_view, high_impact_view, alert_signup, demo_request, whatsapp_click).
- `SECTORS`, `FREQUENCIES`.
- `Problem(status, message)`: exceção HTTP.
- `clean(value, limit)`, `email(value)`, `digest(value)` (sha256), `token_record(s, kind, key, record, account, days)` (token urlsafe 32, payload com expires, put com digest).
- `attribution(raw)`: filtra page, cta, sector, source, campaign, utm_* (≤160 chars, sem @<>?\r\n) + timestamp.
- `lead_score(d) -> {score, classificacao, fatores, versao}`: fatores grande_empresa 20 (501+), setor_prioritario 20 (Bancos/Fintech/Seguros/Tecnologia/Cloud/Data Center), decisor 15 (diretor/head/socio/partner/ceo/cto/cio/cfo), area_controle 15 (sim), urgencia_imediata 15, ia_critica 10, mais_100_pessoas 5; classificação prioridade comercial ≥70, alto ≥50, médio ≥30, baixo.
- `queue(s, key, to, subject, text, account)`: insere outbox pending.
- `rate_limit(s, identity, bucket, maximum)`: HMAC sha256 com `RATE_LIMIT_SECRET` + `identity:bucket:hour`, lock, conta por hora, 429 se exceder.
- `capture_lead(s, d) -> {ok, request_id, message}`: honeypot website, consent true obrigatório, clean campos, email válido, obrigatórios (nome, empresa, cargo, preocupacao, interesse), valida enums setor/tamanho/uso_ia/area_controle/urgencia/interesse, request_id regex `[a-zA-Z0-9-]{16,64}`, lead_score, attribution, consent_at, consent_version, stage lead, fingerprint estável (hash de campos estáveis sem timestamps) para idempotência de retry, lock `lead:key`, verifica fingerprint divergente → 409, insert lead + event (demo_request → também diagnostic_submitted), queue email para `LEAD_NOTIFY_EMAIL` se configurado.
- `preferences(d) -> {temas, proposicoes, orgaos, score_min, frequencia}`: valida contra dataset (ids proposições e categorias), orgãos enum, score 0..100 int, frequencia enum.
- `subscribe(s, d, user) -> {ok, message}`: honeypot, consent true, SMTP_HOST obrigatório (exceto dev), email, prefs, cria subscription inactive, token confirm (7 dias), queue email confirmação com link `/alertas/#confirm=token`.
- `subscription_action(s, d, action)`: token → digest → grant (confirm/unsubscribe), verifica expiração, row subscription, se confirm desativa outras ativas do mesmo email, active=true/false, confirmed_at, delete grant, insert event alert_signup.
- `password_hash(password, salt)`: 12+ chars, pbkdf2_hmac sha256 600k.
- `login(s, d) -> token`: email+password, constant-time compare, check_account, token session 1 dia, usage login.
- `check_account(account)`: status inactive ou ends_on < hoje → 403.
- `authenticated(s, token) -> (user, account)`: verifica session expiração, user account match, check_account.
- `pilot(s, user, account) -> {account:{name,status,ends_on,user_limit}, email, preferences, briefing:{title,as_of,since,sector,top:[{id,title,score,fact,analysis}], changes, events, critical_changes, coverage, coverage_pct, source_errors}, subscriptions}`: prefs do user ou account.themes default, briefing filtrado, top 5 com official_fact e business_impact, usage dashboard_view.

### commercial/intelligence.py

Evidence-led briefing model, sem inventar fatos.

- `ROOT, CONFIG (commercial.json), OFFICIAL (domínios oficiais)`.
- `official(url)`: https + host oficial.
- `load(name)`: lê `data/legislation/name.json`.
- `score(p)`: impacto score.
- `sectors_for(p)`: setores cujo categories intersectam ou categoria 1 (marco geral).
- `business_impact(p) -> {setores_afetados, tipo_de_impacto, prazo_provavel, obrigacao_potencial, risco_operacional, impacto_financeiro_potencial, impacto_em_compliance/dados/modelos_ia/infraestrutura, status_da_interpretacao, por_que_importa, acao_recomendada, metodo, fonte}`: triagem temática conservadora, nada quantificado sem base.
- `official_fact(p) -> {descricao, data_evento, verificado_em, situacao, orgao, fonte}`: prefere `api_camara.ultima_tramitacao` sobre editorial.
- `briefing(as_of, since, sector, themes, watchlist, score_min, organs) -> model`: filtra props com url oficial, sector/themes/watchlist/score/organs, changes desde `since` até `as_of` com fonte oficial, events próximos 7 dias com vínculo setorial explícito (setores ou proposições intersectam), critical_changes score≥80, coverage e source_errors do log.
- `email_briefing(model) -> HTML`: standalone HTML escapado, sem URL privada, seções mudanças críticas, top 5 com fato oficial + análise, mudanças período, agenda 7d, pontos atenção, metodologia.

### commercial/alerts.py

Baseline/diff, fila filtrada, transporte SMTP opt-in.

- `CHANNELS`: email implemented, outros future.
- `snapshots() -> {key: record}`: varre propositions, laws, events com url oficial → record com id, entity, title, source, themes, org, score, status, movement, rapporteur, votes, date, propositions.
- `classify(previous, current) -> [kinds]`: novo projeto/norma/evento, alteração relatoria, votação, alteração score ≥5, inclusão em pauta vs. mudança legislativa, status, date event.
- `capture(s, records, now)`: lock alert-snapshot, se previous existe compara cada record, classifica, hash change_id sha256, insert alert_change (detected_at, types, record, before), put system alert-snapshot.
- `matches(sub, change) -> bool`: filtra por confirmed_at, score_min, temas intersect, proposicoes, orgãos (igual ou substring).
- `prepare(s, now)`: lista alert_change (10k), para cada subscription active verifica account status, intervalo frequencia (imediato 0, diario 86400, semanal 604800), lock subscription, seleciona changes que matches e não entregues (alert_delivery), se semanal e sem selected continua (weekly digest), token unsubscribe 10 anos, monta linhas texto (título, tipos, score, source), queue outbox, se weekly monta `email_briefing` filtrado por prefs, subject "Executive Regulatory Brief — seu recorte semanal", put outbox, insert alert_delivery, update last_queued_at.
- `send_smtp(mail, key)`: EmailMessage, From SMTP_FROM, To, Subject, Message-ID sha256 key, set_content text + html opcional, SMTP com STARTTLS, login se SMTP_USER.
- `deliver(connect, transport, limit) -> sent`: lista outbox, para cada lock outbox, verifica status sent/cancelled/next_attempt, verifica subscription active e account não expirada → cancela se inválida, marca sending next_attempt +300s attempts++, chama transport, em exceção marca retry next_attempt min(86400, 60*2^attempts), em sucesso marca sent.

### api/index.py

Vercel Python Function, same-origin JSON API, sem exportar dados/PII.

- `handler(BaseHTTPRequestHandler)`: `log_message` no-op (não loga payloads/tokens/email), `send_json(status, payload, cookie)`, `cookie(token, delete)` (Secure exceto dev, HttpOnly SameSite Lax Max-Age 86400/0), `do_GET/POST/PUT/DELETE` → `dispatch`.
- `dispatch(method)`:
  - Parse route: `/api/index` ou `/api` → `/api/` + `route` query (trusted rewrite); direct não seleciona rota privada via dados não confiáveis.
  - `GET /api/health`: SELECT 1.
  - POST: valida Origin contra `SITE_URL` + `VERCEL_URL` + dev localhost, Content-Type application/json, Content-Length 0<≤16384, json dict.
  - Cookie `monitor_session` → token.
  - Rate limit: `x-vercel-forwarded-for` se Vercel else client_address, bucket 300 para /api/events else 20.
  - Rotas:
    - `POST /api/leads`: `capture_lead`.
    - `POST /api/events`: valida name in EVENTS e não em {diagnostic_submitted, alert_signup, demo_request}, insert event token_hex 16 + attribution.
    - `POST /api/alerts`: user opcional, `subscribe`.
    - `POST /api/alerts/confirm|unsubscribe`: `subscription_action`.
    - `POST /api/login`: `login` → cookie.
    - `POST /api/logout`: delete session, cookie delete.
    - `GET /api/app`: `authenticated` → `pilot`.
    - `POST /api/preferences`: `authenticated`, `preferences`, put preferences.
  - Erros: `Problem` → status+error, ValueError/TypeError/JSON → 400, Exception → 503 genérico.

### Scripts comerciais auxiliares

- **commercial_admin.py:** CLI operador (migrate, provision --account --name --email --status trial/pilot/active/inactive --ends-on --users 1-100 --themes ids, leads, lead-stage id stage, account-status id status, purge). `provision` valida status, user limit, ends_on, themes contra categories, lock account, digest email, password_hash, revoga sessions do user, usage event.
- **serve_commercial.py:** preview local full-stack `MONITOR_DEV=1 python3 scripts/serve_commercial.py` → ThreadingHTTPServer 127.0.0.1:8765, handler herda API + SimpleHTTPRequestHandler com `docs/` como directory, migrate.
- **send_alerts.py:** `--capture` → capture, sempre `prepare`, `--send` → `deliver(connect)` else "Queues prepared. No e-mail sent".
- **generate_briefing.py:** gera briefing privado HTML+TXT fora de `docs/` (protege contra escrita em output). Args --since --as-of --sector --output default `.private/briefing.html`. Usa `briefing()` + `briefing_body()` + core `build_slugs`.

---

## Validação e auditoria

### validate_site.py

- `site_url()`: lê SITE_URL de build_site.py.
- `Report`: errors, warnings, err(), warn().
- `load_json(path, rep, label)`, `band(score)`.
- `check_data(rep)`: JSON válido, ids duplicados, chave lógica duplicada (casa,tipo,numero,ano), campos obrigatórios, url_oficial válida, score 0..100 int, classificação compatível com band, documentos URL, mudanças referenciam proposição existente, fonte_url presente, execucoes não vazio, leis/parlamentares/eventos ids únicos, timeline fonte_url, categories ids únicos.
- `local_path_for_url(url, site)`: mapeia URL interna → arquivo docs/.
- `check_docs(rep, site)`: docs/ existe, HTMLs têm <title> e canonical no domínio oficial, sem OLD_DOMAIN, sem noindex exceto app/login, links internos existentes, robots.txt com Sitemap oficial sem domínio antigo, sitemap.xml URLs no domínio oficial, arquivos correspondem, sem duplicatas, XML válido.
- `check_artigos(rep, site)`: se `articles.json` existe valida schema (obrigatórios, id/slug únicos, slug padrão, modified≥published, revision_count == len(revisions), primeira revisão = published_at), estado editorial ações válidas, nenhuma change processada E pendente, cota diária new_article ≤1, sitemap uma URL por artigo lastmod=modified_at canonical estável, páginas geradas existem com canonical correto, JSON-LD datePublished/dateModified NewsArticle, "Atualizado em" quando modificado, autoria Leandro/LCF, feed docs/data/articles.json espelhado igual, llms.txt/ai-content.md citam /artigos/ quando há artigos.
- Varredura domínio antigo em arquivos-fonte (exceto docs/ e .git, ignora linha definição OLD_DOMAIN).

### check_collection.py

- `AUDIT_WATCHLIST`: 4 fichas documentadas (PL 2688/2025, PL 1884/2025, PL 370/2024 Câmara, PL 3592/2023 Senado) com URL oficial.
- `audit_coverage(props)`: verifica presença e url_oficial igual.
- `problems(record, now)`: data coleta é do dia corrente BRT, não futura, status concluida, cobertura 100%, sem erros/pendentes, status_global OK/concluida, sem fontes_falha/parciais, cada fonte status ok, sem erros, sem canais_falhos. Retorna lista erros.
- `main()`: lê updates.json + propositions.json, imprime ::error::, exit 1 se houver problema.

### Outros testes (tests/)

- `test_audit_coverage.py`, `test_audit_discovery.py`, `test_audit_watchlist.py`: garantem watchlist presente.
- `test_collection_health.py`, `test_collection_multisource.py`: saúde coleta.
- `test_commercial.py`: store/service.
- `test_editorial.py`: regras editoriais.
- `test_fontes_multiorgao.py`: fontes.
- `test_site_contract.py`: contrato site.
- `test_source_budget.py`: orçamento.
- `test_workflows.py`: workflows.
- `browser_smoke.cjs`: smoke browser.

---

## Workflows GitHub Actions

### update-legislation.yml

- **Triggers:** push em main com paths `scripts/update_legislation.py`, `scripts/update_sources.py`, `scripts/check_collection.py`, `scripts/sources/**`, `.github/workflows/update-legislation.yml`; cron `17 * * * *` (todo início de hora minuto 17 UTC → ~a cada hora, best effort GitHub); `workflow_dispatch` com input `orcamento_minutos`.
- **Permissions:** contents write.
- **Concurrency:** `update-legislation-${{ github.ref }}` cancel-in-progress false.
- **Env:** `PYTHONUNBUFFERED=1`, `MONITOR_BUDGET_SEGUNDOS=1500` (25 min), `MONITOR_MAX_NOVAS=25`.
- **Jobs update:** runs-on ubuntu-latest, timeout 55 min.
  - Checkout ref atual, setup Python 3.13.
  - `Recuperar lacuna histórica`: `recover_audit_history.py`.
  - `Coletar dados oficiais` (id coleta, continue-on-error, timeout 40 min): args `--budget-min` se input, `python3 scripts/update_legislation.py`.
  - `Editorial` (if always, continue-on-error): `generate_articles.py` — falha nunca corrompe dataset.
  - `Rebuild do site` (if always): `build_site.py`.
  - `Validar dataset e páginas` (if always): `validate_site.py`.
  - `Verificar regressões da auditoria` (if always): `tests/test_audit_watchlist.py`.
  - `Resumo da execução` (if always): Python inline lê updates.json + editorial_state.json, gera markdown para GITHUB_STEP_SUMMARY (status, duração, verificadas/monitoradas/cobertura/pendentes, mudanças/novas/eventos, HTTP chamadas/cache/falhas/tempo, erros, status_global, editorial novos/atualizados/ignoradas/curadoria, tabela fontes orgão/status/itens/novidades/erros, fontes falha).
  - `Detectar mudanças reais`: `git status --porcelain`.
  - `Commit e push` (if always e changed e build/validate/audit success): config user bot, `git add -A data docs`, evita commit vazio, commit message `chore: atualização automática do monitoramento ($DATA) [$STATUS]` com corpo execução+editorial+referências, `git push`.
  - `Conferir saúde da coleta publicada` (if build/validate/audit success): `check_collection.py`.
  - `Preservar dados coletados em caso de falha` (if failure): upload-artifact `data/legislation/*.json` 14 dias.
  - `Sinalizar coleta incompleta`: se coleta failure, ::error:: e exit 1 após tentar publicar.

### Outros workflows

- **commercial.yml:** CI comercial (testes, lint).
- **probe-sources.yml:** sonda fontes (debug).

---

## Metodologia e política de qualidade

- **Fontes primárias obrigatórias:** cada fato relevante cita URL oficial (Câmara, Senado, Congresso, Planalto, DOU, TSE, CNJ, ANPD). Imprensa apenas descoberta/contexto.
- **Chave primária:** `casa_tipo_numero_ano` — nenhuma duplicata.
- **AI Legislative Impact Score (0–100):** faixas 90–100 crítico · 75–89 muito relevante · 60–74 relevante · 40–59 monitorar · 0–39 baixa prioridade. Critérios: abrangência, estágio, proximidade votação, regime, apensados, impacto econômico, direitos, alcance setorial, relevância institucional. Nunca manipulado. Implementado em `scoring.py`, preservado para bootstrap.
- **Proibido:** inventar proposições, tramitações, datas, autores, pareceres, probabilidades ou posições políticas sem evidência documental. Campos não confirmados ficam ausentes.
- **Controle de alterações:** dataset versionado no Git; mudanças geram registro em `updates.json` com anterior/novo/data/fonte. Histórico rotacionado para `updates_arquivo.json` preservado.
- **Correção:** erro corrigido no dataset com registro da correção, nunca sobrescrita silenciosa.
- **Automação, orçamento e auditoria:** coleta diária com orçamento, prioridade por score, cobertura publicada em `/monitoramento/` + `data/monitoramento.json`. Frescor recalculado no navegador — se cron parar, painel fica vermelho.
- **Multiórgão:** 8 fontes obrigatórias, cada com timestamp última tentativa e última OK, status, itens consultados, novidades, erros, endpoints, canais OK/falhos. Status global OK/PARCIAL/FALHA. FALHA não publica.

---

## Como executar localmente

```bash
# Coleta (Câmara/Senado + multiórgão)
python3 scripts/update_legislation.py
python3 scripts/update_legislation.py --dry-run
python3 scripts/update_legislation.py --budget-min 25 --max-novas 25 --workers 5 --limite 60

# Apenas multiórgão
python3 scripts/update_sources.py --listar
python3 scripts/update_sources.py --fonte anpd --dry-run
python3 scripts/update_sources.py --todos --dry-run
python3 scripts/update_sources.py --todos --gravar

# Camada editorial
python3 scripts/generate_articles.py
python3 scripts/generate_articles.py --dry-run
python3 scripts/generate_articles.py --bootstrap  # backfill histórico ≤1 artigo/dia

# Build site
python3 scripts/build_site.py

# Validação
python3 scripts/validate_site.py
python3 scripts/check_collection.py
python3 scripts/selftest_offline.py

# Testes
python3 -m unittest discover -s tests -v

# Preview comercial local (PostgreSQL ou SQLite dev)
# .env: DATABASE_URL=, RATE_LIMIT_SECRET=, SITE_URL=, SMTP_*, LEAD_NOTIFY_EMAIL=, MONITOR_DEV=1, COMMERCIAL_SQLITE=/tmp/...
python3 -m commercial.store migrate  # via commercial_admin.py migrate
MONITOR_DEV=1 python3 scripts/serve_commercial.py
# Preview: http://127.0.0.1:8765

# Admin comercial
python3 scripts/commercial_admin.py migrate
python3 scripts/commercial_admin.py provision --account acme --name "Acme" --email admin@acme.com --status pilot --ends-on 2026-12-31 --users 5 --themes 1 3 20
python3 scripts/commercial_admin.py leads
python3 scripts/commercial_admin.py purge

# Alertas
python3 scripts/send_alerts.py --capture
python3 scripts/send_alerts.py --send

# Briefing privado (fora de docs/)
python3 scripts/generate_briefing.py --sector fintech --output .private/briefing.html
```

**Variáveis de ambiente (ver .env.example):**

- `DATABASE_URL` (PostgreSQL prod, obrigatório em prod), `RATE_LIMIT_SECRET` (obrigatório), `SITE_URL` (default https://monitor.lcfconsulting.com.br), `SMTP_HOST/PORT/USER/PASSWORD/FROM`, `LEAD_NOTIFY_EMAIL`
- `MONITOR_DEV=1` (só local, SQLite permitido), `COMMERCIAL_SQLITE=/tmp/monitor-commercial.sqlite3`
- `MONITOR_BUDGET_SEGUNDOS` (1500), `MONITOR_MAX_NOVAS` (25), `MONITOR_MAX_PROPS` (0=sem limite), `MONITOR_WORKERS` (5), `MONITOR_HTTP_CONCORRENCIA` (4), `MONITOR_HTTP_TIMEOUT` (8), `MONITOR_HTTP_RETRIES` (1), `MONITOR_HTTP_FAILURE_LIMIT` (5)
- `MONITOR_FONTES_TIMEOUT_S` (150), `MONITOR_FONTES_LIMITE_TOTAL_S` (900), `MONITOR_ATOS_POR_FONTE` (400), `MONITOR_LIMITE_MUDANCAS` (800), `MONITOR_RETENCAO_DIAS` (180)
- `MONITOR_ARTIGOS_MAX_NOVOS_DIA` (1), `MONITOR_ARTIGOS_STALE_DIAS` (30), `MONITOR_SEM_FONTES` (desativa multiórgão)

---

## SEO / AEO / Agentic

- **robots.txt:** gerado por `ai_visibility.py`, lista crawlers AI (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, Applebot-Extended Allow; Bytespider Disallow) + Sitemap oficial.
- **llms.txt:** índice curto para LLMs (Key Pages, Structured Data, Artigos, AI Discovery, Commercial).
- **llms-full.txt:** llms.txt + top 20 proposições high-impact + source policy + artigos detalhados.
- **ai-content.md:** índice legível por IA com coleções, artigos, feeds.
- **agent-permissions.json:** permissões públicas (crawl, read_html, read_structured_feeds, citation true; write false; auth false).
- **mcp-actions.json:** ações MCP declarativas (contact-lcf-consulting, read-legislative-updates, read-articles, read-propositions).
- **AGENTS.md:** canonical, propósito, preferred sources, rules.
- **JSON-LD:** WebSite, Organization, Dataset, CollectionPage, BreadcrumbList, Article, NewsArticle (com datePublished/dateModified, author Leandro Calado, publisher LCF, about Legislation, mentions GovernmentOrganization/Person), DataDownload.
- **Sitemap:** 1 URL por proposição + 1 por artigo (lastmod = modified_at real), validado contra domínio oficial.
- **Frescor:** selo `data-freshness` recalculado no navegador via `site.js`.

---

## Camada comercial — detalhes adicionais

- **Site comercial:** `/para-empresas/`, `/solucoes/`, `/briefing-executivo/`, `/alto-impacto/`, `/setores/<slug>/`, `/casos-de-uso/`, `/alertas/`, `/watchlist/`, `/login/`, `/app/`, `/privacidade/`, `/diagnostico/`.
- **Ofertas:** Monitor IA, Radar Executivo (featured), Inteligência Institucional (sob consulta), Diagnóstico de Exposição Regulatória (projeto). Preços experimentais em `commercial.json`.
- **Segurança:** rate-limit por HMAC hour bucket, honeypot, consent obrigatório, fingerprint idempotente, token digest sha256, password pbkdf2 600k, session HttpOnly Secure SameSite Lax, lock advisory postgres, account isolation (account_id), ends_on, user_limit, status inactive bloqueia, purge retenção (rate/session/confirm/unsubscribe expira, event/usage 90d, lead 180d exceto pilot/contract, outbox 30d, alert_change/delivery 90d, subscription inactive 7d).
- **Vercel:** `vercel.json` → buildCommand `python3 scripts/build_site.py`, outputDirectory `docs`, function `api/index.py` maxDuration 30 exclude reports/tests/.git, rewrites `/api/:path*` → `/api?route=:path*`, headers Cache-Control no-store + X-Robots-Tag noindex para /api, X-Content-Type-Options nosniff + Referrer-Policy + X-Frame-Options DENY para resto.

---

## Estado atual (referência 08/09/2026 bootstrap)

- 32 proposições monitoradas (incluindo pacote 37 apensados ao PL 2338/2023)
- 14 normas vigentes/históricas (LGPD, ECA Digital, Lei 15.487/2026, Res. TSE 23.748/2026, Res. CNJ 615/2025, Decretos 12.975-12.976/2026, EBIA, PBIA…)
- 35 eventos timeline 2019–2026
- 15 parlamentares documentados
- Situação-síntese: marco legal PL 2338/2023 parado 16 meses comissão especial Câmara, votação adiada pós-eleições 10/2026; Redata PL 278/2026 aprovado Congresso à sanção; Lei 15.487/2026 deepfakes em vigor 07/08/2026.

Detalhes: [Relatório](docs/relatorio/index.html) · [Painel monitoramento](docs/monitoramento/index.html)

---

## Autoria

Projeto desenvolvido por [Leandro Calado](https://leandrocaladoferreira.com/) / [LCF Consulting](https://lcfconsulting.com.br/).

**Disclaimer:** Dados legislativos devem sempre ser conferidos nas fontes oficiais. Inteligência regulatória e análise de impacto de caráter informativo. Não constitui parecer ou aconselhamento jurídico.

---

## Anexos técnicos — lista completa de funções por arquivo

### scoring.py

- `classify(score)`: faixa textual.
- `_norm(t)`: normalização ascii lower.
- `compute_impact_score(prop)`: calcula 9 critérios, trava revisao_pendente, retorna dict.
- `rubric_table_html()`: HTML tabela rúbrica.

### update_legislation.py

- `_env_int`, `Budget`, `BudgetExceeded`, `endpoint_label`, `_stat_endpoint`, `http_stats`, `_http_urllib`, `_http_curl`, `http_get_json`, `polite_pause`, `relevance`, `load`, `save`, `today_brt`, `parse_run_date`, `date_only`, `as_list`, `camara_find_id`, `camara_detail`, `camara_tramitacoes`, `camara_autores`, `camara_votacoes`, `camara_deputado`, `camara_id_from_prop`, `senado_detail`, `senado_movimentacoes`, `senado_relatorias`, `senado_search`, `senado_codes_from_prop`, `infer_change_type`, `infer_categories`, `Collector` (fase, _resumo_execucao, _bump, _marca_verificada, _add_fonte, _add_fontes, add_change, update_camara_prop, _record_movimentacao, _situacao_from_tram, _detect_apensacoes, _resolve_principal, update_senado_refs, discover_camara, build_new_camara_record, discover_senado, build_new_senado_record, update_events, _ordinal, _prioridade, _prioridade_candidato, _snapshot_dataset, _status_casa, _saude_casas, _atualizar_registro, _gravar, run), `parse_args`, `main`.

### sources/base.py

- `FonteIndisponivel`, `OrcamentoEsgotado`, `normalizar`, `classificar_relevancia`, `limpar_texto`, `url_canonica`, `hash_texto`, `data_iso`, `Resposta`, `Cliente` (rotulo_endpoint, _stat, resumo_stats, get, get_json, get_texto, get_rss), `parse_rss`, `parse_html_links`, `parse_dou_json`, `parse_plone_search`, `parse_cnj_atos`, `parse_dou_embutido`, `html_para_texto_blocos`, `Canal` (_com_params, urls), `ResultadoFonte` (status, erro_resumo, como_dict), `ContextoFonte` (restante, expirado, checar), `Fonte` (coletar, _marca_falha, _absorver, id_item, _coletar_canal, _coletar_rss, _coletar_json, _parser_json, _parse_wp_json, _parse_ckan, _parse_lista_json, _coletar_html, _pos_processar), `registrar`, `fontes_disponiveis`, `instanciar`.

### update_sources.py

- `agora_brt`, `ts_iso`, `load`, `save`, `inferir_tipo_evento`, `executar_fonte`, `_resultado_falha`, `executar_fonte_subprocesso`, `executar_todas`, `_atos_vazios`, `_historico_padrao`, `mesclar`, `_mudanca`, `_somar_http`, `calcular_status_global`, `registrar_mudancas`, `relatorio_compacto`, `_resumo_texto`, `main`.

### generate_articles.py

- `_slug`, `_date_only`, `hoje_brt`, `agora_iso`, `change_id`, `dia_editorial`, `fmt_data`, `_trim`, `load_json`, `load_artigos`, `load_state`, `save_artigos`, `save_state`, `Contexto` (principal_de), `prop_topic_id`, `ato_topic_id`, `topico_da_mudanca`, `_titulo_limpo`, `_peso_titulo`, `_ruidosa`, `_eco_protocolo`, `_peso_ato`, `classify_change`, `find_existing_article`, `should_create_new_article`, `should_update_article`, `_rotulo_orgao`, `_bulks_mudanca`, `esc_html`, `_conteudo_prop`, `_conteudo_ato`, `_parlamentares_relacionados`, `_slug_unico`, `create_article`, `_hash_artigo`, `update_article`, `mudancas_do_topico`, `run_editorial`, `_aplicar_update`, `_registrar`, `_cfg_padrao`, `main`.

### build_site_core.py

- `_freshness_badge`, `load`, `esc`, `build_slugs`, `slugify_prop`, `prop_fs_path`, `fmt_date`, `ref_date`, `days_ago`, `rel_label`, `score_class`, `score_label`, `status_group`, `cat_map`, `prop_link`, `prop_link_by_id`, `changes_for_prop`, `guess_principal_id`, `fonte_label`, `near_vote`, `change_prop_href`, `ld_website`, `ld_breadcrumbs`, `ld_collection`, `combine_ld`, `_atos_footer_link`, `_artigos_footer_link`, `page`, `write`, `tags_for_prop`, `change_card`, `run_summary`, `build_home`, `build_propositions`, `seo_title_prop`, `seo_desc_prop`, `build_prop_pages`, `build_updates`, `build_metodologia`, `build_laws`, `build_timeline`, `build_parliamentarians`, `build_agenda`, `build_report`, `_date_only`, `_parse_ts`, `_status_run`, `_status_run_label`, `_latencia_media`, `metricas_monitoramento`, `build_monitoramento`, `build_sitemap`, `main`, `self_module`.

### build_site.py

- `_assert_domain_migration`, `main` wrapper.

### build_articles.py

- `carregar_artigos`, `artigos_publicados`, `artigos_para_prop`, `_url`, `article_jsonld`, `_fmt`, `_resolver_site`, `_secao`, `_bullets_o_que_mudou`, `render_article`, `render_index`, `build`.

### dataviz.py

- `esc`, `_fmt`, `bar_chart`, `bar_chart_h`, `line_chart`, `legenda`, `stacked_bar`, `stacked_legenda`, `heatmap`.

### ai_visibility.py

- `_artigos_para_descoberta`, `_ordenar_por_frescor`, `secao_artigos_llms`, `secao_artigos_llms_full`, `install`.

### google_ai_citation.py

- `install`.

### commercial_pages.py

- `cta`, `strip`, `input_field`, `diagnostics`, `business_html`, `prop_card`, `briefing_body`, `alert_form`, `build`, `install`.

### commercial/store.py

- `Store` (execute, get, put, insert, list, delete, lock, commit), `connect`, `migrate`.

### commercial/service.py

- `Problem`, `clean`, `email`, `digest`, `token_record`, `attribution`, `lead_score`, `queue`, `rate_limit`, `capture_lead`, `preferences`, `subscribe`, `subscription_action`, `password_hash`, `login`, `check_account`, `authenticated`, `pilot`.

### commercial/intelligence.py

- `official`, `load`, `score`, `sectors_for`, `business_impact`, `official_fact`, `briefing`, `email_briefing`.

### commercial/alerts.py

- `snapshots`, `classify`, `capture`, `matches`, `prepare`, `send_smtp`, `deliver`.

### api/index.py

- `handler` (log_message, send_json, cookie, do_GET, do_POST, do_PUT, do_DELETE, dispatch).

### validate_site.py

- `site_url`, `Report`, `load_json`, `band`, `check_data`, `local_path_for_url`, `check_docs`, `check_artigos`, `main`.

### check_collection.py

- `audit_coverage`, `problems`, `main`.

### Outros

- `probe_sources.py`: sondas manuais, lista canais, testa filtros.
- `selftest_offline.py`: testes orçamento, persistência, métricas.
- `recover_audit_history.py`: recupera histórico lacuna Senado.
- `generate_briefing.py`: gera briefing privado HTML/TXT.
- `serve_commercial.py`: preview local full-stack.
- `commercial_admin.py`: provision, leads, purge.
- `send_alerts.py`: capture/prepare/deliver.
- `vercel.json`: build, output, functions, rewrites, headers.
- `AGENTS.md`: canonical, purpose, preferred sources, rules.
- `config/commercial.json`: ofertas, setores, personas.

---

**Fim da documentação completa.** Para dúvidas operacionais, consulte `docs/metodologia/`, `docs/monitoramento/` e `docs/relatorio/` no site gerado, ou os arquivos de descoberta `llms.txt` e `ai-content.md`.
