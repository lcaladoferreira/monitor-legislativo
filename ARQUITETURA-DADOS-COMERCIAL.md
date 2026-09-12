# Arquitetura de dados, comercial e alertas — Monitor Legislativo de IA

Documento de referência da camada comercial B2B (P0) e do plano técnico dos itens
seguintes. Complementa o `README.md` (que descreve o monitor) e o
`RELATORIO-ENTREGA-P0.md` (que registra o que foi entregue).

Posicionamento que orienta toda decisão técnica aqui:

> Inteligência regulatória especializada em **IA, dados, infraestrutura digital e
> tecnologias de alta consequência regulatória**.
> A entrega não é "acompanhe N projetos de lei" — é **o que mudou, por que isso
> importa para a sua operação, quem precisa agir e qual evidência oficial sustenta
> a conclusão**.

---

## 1. Decisão sobre a exposição do ativo de dados (item 19)

### Diagnóstico

`docs/data/` publica cópia integral dos datasets tratados, incluindo
`propositions.json` (≈ 630 KB) com os campos proprietários de enriquecimento
(`impacto`, `obrigacoes_criadas`, `proibicoes`, `orgaos_responsaveis`,
`proxima_etapa`, `chance_impacto_regulatorio`) e `updates.json` (≈ 190 KB) com o
histórico completo de mudanças.

Resposta à pergunta obrigatória — *alguém poderia reconstruir grande parte do
produto sem pagar?* — **sim, parcialmente**: consegue-se replicar o *banco de
dados tratado*. Não se replica o que sustenta a assinatura:

| Ativo | Está no JSON público? | Observação |
|---|---|---|
| Banco de proposições + score corrente | Sim | rúbrica do score já é pública por decisão editorial |
| Histórico de mudanças | Sim | `updates.json` |
| Regras de tradução empresarial (setores, ação recomendada, impacto potencial) | Não | `scripts/brief.py` gera sob demanda; o resultado só aparece em páginas/e-mails |
| Recorte por cliente (temas, órgãos, score mínimo, frequência) | Não | perfil de assinatura, não existe no repositório |
| Briefing executivo montado | Não | gerado por execução, entregue ao cliente |
| Alertas, SLA, reunião executiva, white-label, API | Não | serviço, não dado |
| Série temporal de score por matéria | Não | não existe ainda (ver P1) |

### Decisão aplicada nesta fase

**Manter os dados públicos** (decisão do proprietário) e **não criar paywall**,
porque:

1. o JSON público é a prova de capacidade técnica que vende — é o freemium
   demonstrativo exigido no item 2;
2. `llms.txt`, `ai-content.md`, `agent-permissions.json`, `mcp-actions.json` e o
   `AGENTS.md` publicado dependem desses feeds; fechá-los quebraria a estratégia
   de visibilidade em IA/busca já implementada;
3. o `sitemap.xml`, o canonical e as 147 URLs indexadas não podem ser
   prejudicados (item 23).

Contrapartida implementada: **todo o valor comercial novo nasce fora do dump
público** — `scripts/brief.py` (regras de tradução empresarial),
`scripts/build_alert_email.py` (seleção por perfil e canais),
`docs/data/commercial.json` (config comercial, sem dado legislativo novo).

### Plano de acesso controlado (quando houver área de cliente — P2)

Camada pública (permanece como está):

* dados necessários à renderização das páginas públicas;
* amostras demonstrativas (`/briefing-executivo/`);
* fontes oficiais linkadas;
* feeds para agentes de IA (`llms.txt`, `ai-content.md`).

Camada privada (a criar, sem remover nada do que é público hoje):

* **série histórica de score** por matéria e por cliente (novo dado, não derivável
  do JSON público) — habilita o tipo de alerta `alteracao_score`;
* **enriquecimento empresarial completo** (campos de `impacto_empresarial` por
  setor, prazo, obrigação, risco financeiro) quando passar de amostra a base;
* **relatórios e exportações** por cliente (PDF/CSV/XLSX);
* **API comercial** (`/api/v1/...`) com token por contrato, rate limit e escopo
  por temas — nunca exposta em `docs/`;
* **webhooks** com assinatura HMAC;
* **watchlist e alertas configurados** por usuário.

Implementação sugerida (não aplicada ainda, para não quebrar o deploy estático):

* manter o site estático em `docs/` (público, indexável, barato);
* expor a camada privada em serviço separado (função serverless ou serviço
  próprio) com autenticação; o front-end autenticado consome a API e nunca
  recebe o dump consolidado;
* se em algum momento for preciso reduzir o dump público, fazer por *campo*
  (view pública × view privada do mesmo dataset) e nunca por URL já indexada,
  preservando em `propositions.json` os campos que as páginas públicas
  renderizam — mudança desse tipo exige redirect/compatibilidade e aviso no
  `AGENTS.md` publicado.

---

## 2. Configuração centralizada da camada comercial

Fonte única: **`scripts/commercial.py`** (seção 1 do arquivo).

| O que mudar | Onde | Sem rebuild de código |
|---|---|---|
| Faixas de preço | `SOLUCOES[].preco_min/preco_max` ou `MONITOR_PRICE_<ID>_MIN/MAX` | env no build |
| Rótulo "Sob consulta" | `SOLUCOES[].preco_rotulo` + `preco_publico` | — |
| Copy dos CTAs | `CTA_PRINCIPAL`, `CTA_PRINCIPAL_SUB`, `CTA_SECUNDARIO`, `CTA_DEMO` | — |
| Entregas por solução | `SOLUCOES[].entregas` | — |
| Endpoint de captura de lead | `MONITOR_LEAD_ENDPOINT` (+ `MONITOR_LEAD_PROVIDER`) | env no build |
| WhatsApp comercial | `MONITOR_WHATSAPP` (dígitos, ex. `5511999999999`) | env no build |
| E-mail comercial | `MONITOR_COMMERCIAL_EMAIL` | env no build |
| GA4 / Plausible / beacon | `MONITOR_GA4_ID`, `MONITOR_PLAUSIBLE_DOMAIN` (+ `_SRC`), `MONITOR_ANALYTICS_ENDPOINT` | env no build |
| Debug de analytics/lead | `MONITOR_ANALYTICS_DEBUG=1` (ou `?debug=1` no navegador) | runtime |
| Regras de lead scoring | `LEAD_SCORING` (pesos, faixas e entradas) | — |
| Prova social | `PROVA_SOCIAL_ENABLED` + `PROVA_SOCIAL` | — |

Todo valor configurado é republicado em **`docs/data/commercial.json`**, que é a
fonte usada pelo front-end (`assets/commercial.js`). Nenhuma chave, token ou
segredo entra nesse arquivo — `validate_site.py` falha o build se aparecer algo
parecido (`access_key`, `api_key`, `secret`, `password`, `token`).

### Captura de lead: modos

1. **`endpoint` (recomendado para operar)** — definir `MONITOR_LEAD_ENDPOINT` no
   build (Formspree, Web3Forms, Basin, Getform ou função serverless própria). O
   JS envia `POST` JSON com `Accept: application/json`; se o provider responder
   mal, tenta o submit nativo como último recurso.
2. **`fallback-email` (padrão atual, sem configuração)** — o formulário usa
   `action="mailto:..."` com `enctype="text/plain"`, o JS abre o cliente de
   e-mail com o payload completo (inclusive score) e mostra o painel de
   confirmação. Funciona sem nenhum serviço externo; a captura não fica perdida.

Em ambos os modos o lead é gravado estruturadamente no navegador
(`localStorage.monitor_leads_local`) para auditoria do funil durante o piloto.

Campos enviados: `nome, empresa, cargo, email, telefone, setor, tamanho, uso_ia,
area, horizonte, preocupacao, interesse, solucao, mensagem, consentimento` +
`lead_score, lead_classificacao, lead_score_fatores, lead_payload, pagina_origem,
url_origem, timestamp_envio, utm_* (first e last touch), origem, campanha,
form_tipo, _subject`.

Honeypot `_gotcha` descarta envio de bot (evento `lead_bot_blocked`).

---

## 3. Lead scoring (item 6)

Regras fixas, publicadas em `docs/data/commercial.json` e aplicadas no
front-end (fonte única — não há duplicação de regra em Python e JS):

| Critério | Pontos | Gatilho |
|---|---|---|
| Grande empresa | +20 | 501+ funcionários |
| Setor prioritário | +20 | Bancos, Fintech, Seguros, Tecnologia, Cloud, Data Center |
| Cargo decisor | +15 | C-level, Diretor(a), Head/Gerente executivo(a), Sócio(a) |
| Área estruturada | +15 | Compliance, Jurídico, RIG ou mais de uma |
| Preocupação imediata | +15 | horizonte "próximos 3 meses" |
| IA em processo crítico | +10 | uso de IA declarado como crítico |
| Mais de 100 funcionários | +5 | porte 101+ |

Faixas: **0–29 baixo · 30–49 médio · 50–69 alto · 70+ prioridade comercial**.
Máximo possível: 100. O score nunca é exibido ao visitante (é qualificação
interna); aparece no payload, no assunto do e-mail e em `?debug=1`.

---

## 4. Analytics comercial (item 14)

Camada própria em `scripts/assets/commercial.js`, agnóstica de fornecedor.

Cada evento carrega: `event, timestamp, page, page_kind, sector, title, url,
origem, campanha, utm_source/medium/campaign/term/content (+ first_*)`.

| Evento | Disparo | Onde |
|---|---|---|
| `page_view` | carga de qualquer página | todas |
| `commercial_cta_click` | clique em CTA comercial | header, home, planos, rodapé, e-mail |
| `diagnostic_page_view` | visita à landing | `/diagnostico/` |
| `diagnostic_started` | primeira interação com o formulário | `/diagnostico/` |
| `diagnostic_submitted` | lead enviado (com `modo`, `lead_score`, `setor`) | `/diagnostico/` |
| `diagnostic_submit_error` | falha de envio | `/diagnostico/` |
| `diagnostic_validation_error` | envio bloqueado por validação | `/diagnostico/` |
| `briefing_sample_view` | visita à amostra | `/briefing-executivo/` |
| `briefing_print` | imprimir/salvar PDF da amostra | `/briefing-executivo/` |
| `pricing_view` | visita a soluções ou clique em preço/plano | `/solucoes/` |
| `sector_page_view` | clique/visita setorial | briefing (base do P1) |
| `high_impact_view` | página de alto impacto | gancho pronto (P1) |
| `alert_signup` | ativação de alertas por e-mail | `/briefing-executivo/` |
| `alert_signup_error` | falha na ativação | `/briefing-executivo/` |
| `demo_request` | pedido de demonstração | `/para-empresas/` |
| `whatsapp_click` | clique em canal WhatsApp | todas (se configurado) |
| `para_empresas_view` | visita à página corporativa | `/para-empresas/` |
| `lead_bot_blocked` | honeypot preenchido | formulários |

Destinos: `window.dataLayer` (GTM/GA4), `gtag()` se `MONITOR_GA4_ID`,
`plausible()` se `MONITOR_PLAUSIBLE_DOMAIN`, `sendBeacon` se
`MONITOR_ANALYTICS_ENDPOINT`, e buffer local `localStorage.monitor_eventos`
(últimos 200) para auditoria do funil sem ferramenta externa.

---

## 5. Sistema de alertas (item 8) e relatório executivo (item 21)

Motor compartilhado: **`scripts/brief.py`** → payload `Executive Regulatory Brief`
com `mudancas_criticas`, `mudancas_30_dias`, `top_materias`,
`desde_ultimo_relatorio` (+ critério aplicado), `agenda` (próximos dias, sem data
confirmada, além da janela), `setores`, `atencao_executiva`, `fontes_oficiais`.

Consumidores:

* `scripts/commercial.py` → página pública `/briefing-executivo/` (amostra);
* `scripts/build_alert_email.py` → e-mail (HTML inline + texto), webhook (JSON) e
  mensagem curta pronta para WhatsApp/Telegram/Slack/Teams.

```bash
python3 scripts/build_alert_email.py                                   # brief semanal
python3 scripts/build_alert_email.py --modelo alerta --frequencia imediato --score-minimo 80
python3 scripts/build_alert_email.py --temas infraestrutura-de-ia,protecao-de-dados --orgaos ANPD
python3 scripts/build_alert_email.py --proposicoes camara_pl_2338_2023 --destinatarios cliente@empresa.com.br --send
python3 scripts/build_alert_email.py --webhook-url https://hooks.exemplo.com/xyz --json-only
```

Saída em `build/alertas/` (não versionado): `.html`, `.txt`, `.json`.

**Envio SMTP** somente por variáveis de ambiente (nunca em código):
`MONITOR_SMTP_HOST`, `MONITOR_SMTP_PORT`, `MONITOR_SMTP_USER`,
`MONITOR_SMTP_PASS`, `MONITOR_SMTP_FROM`, `MONITOR_ALERT_TO`. Sem host
configurado, o script gera os arquivos e informa que o envio foi pulado — o que
permite rodar no CI sem segredos.

**Perfis de seleção** (o que o cliente escolhe): `frequencia`
(imediato/diário/semanal → janela de 1/1/7 dias), `score_minimo` (0/60/80),
`temas` (categorias por slug, nome ou id), `orgaos` (texto sobre
`orgaos_responsaveis`, comissão e casa), `proposicoes` (ids que sempre entram),
`tipos` (catálogo abaixo), `canais`.

**Tipos de alerta:**

| Tipo | Status | Origem no dataset |
|---|---|---|
| Mudança legislativa | implementado | `updates.mudancas` (tramitação, apensação, parecer, cadastral) |
| Novo projeto | implementado | `updates.mudancas` (`nova proposição`) |
| Votação | implementado | `updates.mudancas` (aprovação, sanção) |
| Inclusão em pauta | implementado | `updates.mudancas` (cronograma) + situação oficial com "pauta"/"ordem do dia" |
| Alteração de relatoria | implementado | `updates.mudancas` (relatoria) |
| Nova norma | implementado | `updates.mudancas` (publicação) + `laws.json` |
| Evento | implementado | `events.json` |
| Alteração relevante de score | **pendente (P1)** | exige série histórica de score por execução |

**Canais:** e-mail (implementado) e webhook (payload pronto); WhatsApp, Telegram,
Slack e Teams declarados em `CANAIS` com `implementado: false` e a mensagem curta
já gerada — falta apenas o conector de envio (P2).

---

## 6. Fato oficial × análise (item 9)

Obrigatório em toda superfície comercial. Implementado em `brief.py`:

* `fato_oficial` só recebe campos existentes no dataset (`situacao`, `estagio`,
  `comissao_atual`, `relator`, `ultima_movimentacao`, `proxima_etapa`,
  `obrigacoes_criadas`, `proibicoes`, `orgaos_responsaveis`, `url_oficial`,
  `total_apensados`, `aguardando_curadoria`). Campo ausente → `None` e a
  interface mostra "não informado na fonte oficial".
* `analise` recebe a interpretação derivada de tabelas públicas do próprio
  módulo (`CATEGORIA_PARA_SETORES`, `impacto_potencial`,
  `ACAO_RECOMENDADA_REGRAS`) e declara sempre `base_da_analise` e
  `status_interpretacao` (`curadoria editorial` × `interpretação automatizada
  (rúbrica pública) — sem curadoria`).

Campos de impacto empresarial já gerados: `setores_afetados`,
`impacto_potencial` (Baixo/Médio/Alto/Crítico), `prazo_provável` (+ base),
`obrigacao_potencial`, `risco_operacional`, `impacto_em_compliance`,
`impacto_em_dados`, `impacto_em_modelos_de_ia`, `impacto_em_infraestrutura`,
`acao_recomendada` (+ critério), `status_interpretacao`.

Visualmente: bloco azul "Fato oficial" × bloco âmbar "Análise / interpretação",
com o aviso de escopo ao lado de cada um. `validate_site.py` falha se qualquer
página usar linguagem de aconselhamento jurídico fora de contexto de
aviso/negação.

---

## 7. Infraestrutura preparada para área de cliente (item 20)

Não construído nesta fase (P2), mas os pontos de acoplamento já existem:

* `docs/data/commercial.json` — contrato público de soluções, faixas e regras;
* payload do lead (`lead_payload`) — estrutura pronta para virar registro de conta;
* `PERFIL_PADRAO` em `build_alert_email.py` — formato do perfil de alertas que
  vira "temas monitorados" e "watchlist" na área do cliente;
* `CANAIS` — contrato de canais por assinatura;
* eventos de analytics — base para "registro de uso" do piloto (item 22).

Estrutura futura de rotas: `/login`, `/app` (Dashboard, Alertas, Temas
monitorados, Watchlist, Briefings, Relatórios, Agenda, Exportações,
Configurações), `/api/v1/*`, webhooks com HMAC. Conta com estado
`trial | pilot | active | inactive`.

---

## 8. Backlog (o que NÃO foi feito nesta fase)

### P1 — conversão

9. páginas setoriais `/setores/*` (a base já existe: `CATEGORIA_PARA_SETORES`,
   agregação por setor no brief e evento `sector_page_view` instrumentado);
10. camada "impacto para o negócio" nas fichas de proposição (o motor já existe
    em `brief.py`; falta renderizar em `/proposicoes/<slug>/`);
11. filtros de alto impacto + página `/alto-impacto/` (evento `high_impact_view`
    já instrumentado; o filtro atual do monitor tem faixas 60/75/90 — o pedido é
    80+/60–79/<60);
12. watchlist (precisa de estado por visitante: `localStorage` primeiro, conta
    depois);
13. relatório executivo em PDF (o HTML de e-mail já é imprimível; falta gerador
    de PDF no CI);
14. configuração de alertas pelo próprio cliente (hoje o perfil é definido em
    contrato/CLI).

### P2 — retenção / enterprise

15. `/login`; 16. `/app` (área do cliente); 17. multiusuário e papéis;
18. API privada com token; 19. webhooks com HMAC; 20. SLA contratual;
21. white-label. Pendências de dados: série histórica de score (habilita alerta
`alteracao_score`) e persistência server-side de leads (hoje: provider ou
fallback de e-mail).

### Regra de priorização aplicada

Cada item foi avaliado por "como isso aumenta a chance de receita?". P0 saiu
primeiro porque é o que gera lead e proposta; P1 aumenta conversão sobre o mesmo
tráfego; P2 só se justifica com piloto assinado.

---

## 9. Como validar

```bash
python3 scripts/build_site.py            # gera 147 páginas (143 do monitor + 4 comerciais)
python3 scripts/validate_site.py         # SEO, links, domínio, JSON + regras comerciais
python3 scripts/selftest_comercial.py    # 121 verificações da camada comercial
python3 scripts/selftest_offline.py      # testes do coletor (não afetados)
npm install --no-save jsdom              # opcional: habilita o teste de front-end
node scripts/tests/commercial_front.test.js
```

`validate_site.py` ganhou o bloco `check_commercial`, que falha o build se:
faltar CTA no cabeçalho de qualquer página; faltar config de analytics; alguma
página comercial perder elemento obrigatório; um evento do catálogo deixar de ser
instrumentado; a faixa interna de preço vazar para o HTML; prova social for
renderizada sem evidência; a amostra de briefing perder a separação fato ×
análise; ou aparecer linguagem de aconselhamento jurídico fora de aviso/negação.
