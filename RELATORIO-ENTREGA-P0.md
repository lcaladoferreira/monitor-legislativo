# Entrega P0 — Monitor Legislativo de IA como produto B2B

Branch: `arena/01a097e7-monitor-legislativo` · base: `317bff6` (main)
Data: 12/09/2026 · escopo executado: **P0 completo (receita)**

Decisões do proprietário aplicadas: provider de formulário configurável para
captura · camada de analytics própria e agnóstica · dados públicos preservados
com plano público × privado documentado.

---

## A. Auditoria inicial

**Stack.** Python 3 puro (stdlib, sem framework, sem npm). Gerador estático:
`scripts/build_site.py` (entry point, trava de domínio) →
`scripts/build_site_core.py` (1.821 linhas) → publica `docs/` na Vercel /
GitHub Pages. Camada de visibilidade IA/AEO em `scripts/ai_visibility.py`
(patch do gerador + `llms.txt`, `ai-content.md`, `mcp-actions.json`,
`agent-permissions.json`, `AGENTS.md` publicado, robots).

**Rotas antes da mudança (143 páginas).** `/`, `/proposicoes/` + 133 fichas,
`/atualizacoes/`, `/leis/`, `/timeline/`, `/parlamentares/`, `/agenda/`,
`/metodologia/`, `/monitoramento/`, `/relatorio/`.

**Dados.** `data/legislation/*.json` é a fonte única da verdade:
`propositions.json` (628 KB, 133 proposições, 3 com score ≥ 80),
`updates.json` (190 KB, 142 mudanças + 5 execuções), `laws.json` (14 normas),
`events.json` (10 eventos), `timeline.json`, `parliamentarians.json`,
`categories.json` (30 categorias). Cópias públicas em `docs/data/`.

**Carregamento de dados.** Build-time (o gerador lê os JSON e escreve HTML
estático). Client-side só para filtros (`assets/site.js`) e frescor do cron.

**Pipeline.** `.github/workflows/update-legislation.yml` — cron diário 10:17 UTC:
coleta (Câmara/Senado, orçamento 25 min, máx. 25 fichas novas) → build →
validação → commit se houve mudança → deploy Vercel. Regra "sempre publicar".

**SEO/AEO.** `sitemap.xml` (143 URLs), `robots.txt` por user-agent (inclui
GPTBot/ClaudeBot/PerplexityBot), canonical, OG, JSON-LD (`WebSite`, `Dataset`,
`BreadcrumbList`, `CollectionPage`), `llms.txt`/`llms-full.txt`/`ai-content.md`.
O build falha se o domínio antigo aparecer em artefato crítico.

**Analytics antes:** **nenhum** (zero `gtag`, `dataLayer`, Plausible, Matomo).

**Camada comercial antes:** **nenhuma** — só uma linha no `AGENTS.md`
("Commercial requests go to lcfconsulting.com.br") e um CTA no rodapé/home
apontando para o site da consultoria.

**Risco identificado (item 19).** `docs/data/` expõe os datasets integrais,
inclusive o enriquecimento proprietário. Decisão: manter público (é a prova
técnica que vende e sustenta SEO/AEO) e fazer todo o valor comercial novo nascer
fora do dump — documentado em `ARQUITETURA-DADOS-COMERCIAL.md`.

**Baseline ANTES de qualquer modificação (exigência do item 1/11/12).**

| Comando | Resultado |
|---|---|
| `python3 scripts/build_site.py` | OK — 143 páginas, 143 URLs no sitemap |
| `python3 scripts/validate_site.py` | Erros: 0 · Avisos: 0 · VALIDAÇÃO OK |
| `python3 scripts/selftest_offline.py` | AUTOTESTE OK (coletor real: 116 mudanças, 2 erros de rede, status parcial por orçamento — comportamento já tratado) |

Nenhum erro pré-existente encontrado. `data/legislation/` não foi alterado em
nenhum momento desta entrega (`git diff data/` vazio).

---

## B. Alterações realizadas (arquivo por arquivo)

### Novos

| Arquivo | Linhas | O que faz |
|---|---|---|
| `scripts/commercial.py` | 1.748 | **Configuração central** da camada comercial (preço, CTAs, soluções, setores, lead scoring, analytics, contatos, prova social desativada) + gerador de `/solucoes/`, `/diagnostico/`, `/briefing-executivo/`, `/para-empresas/`, `docs/data/commercial.json`, CTA de cabeçalho, coluna de rodapé e faixa comercial da home |
| `scripts/brief.py` | 663 | Motor do *Executive Regulatory Brief*: payload com mudanças críticas, top matérias, desde o último relatório, agenda, impactos por setor, atenção executiva e fontes. Tabelas públicas `CATEGORIA_PARA_SETORES`, `ACAO_RECOMENDADA_REGRAS`, `SEVERIDADE_MUDANCA`; separação estrita `fato_oficial` × `analise` com `base_da_analise` e `status_interpretacao` |
| `scripts/build_alert_email.py` | 580 | Alertas e relatório executivo: seleção por perfil (frequência, score mínimo, temas, órgãos, proposições, tipos), saída HTML inline (e-mail), TXT e JSON (webhook), mensagem curta pronta para WhatsApp/Telegram/Slack/Teams, envio SMTP opcional só por env |
| `scripts/selftest_comercial.py` | 411 | 121 verificações offline da camada comercial (config, lead scoring, brief, HTML gerado, analytics, alertas) + roda o teste jsdom quando disponível |
| `scripts/assets/commercial.css` | 245 | Estilos da camada comercial em arquivo separado (`style.css` intacto): CTA de header, planos, comparativo, formulário, blocos fato × análise, print/PDF |
| `scripts/assets/commercial.js` | 516 | Analytics agnóstico (dataLayer/GA4/Plausible/beacon + buffer local), UTM first/last touch, catálogo de 18 eventos, lead scoring pela config, validação, honeypot, envio ao provider com fallback mailto, prefill por query, impressão |
| `scripts/tests/commercial_front.test.js` | 249 | Teste de front-end em jsdom sobre o HTML gerado (52 verificações) — dev only |
| `.github/workflows/briefing-comercial.yml` | 99 | Action aditiva (semanal + manual): gera o brief, envia por e-mail se houver segredos SMTP, publica artefato. Não toca o cron de coleta |
| `ARQUITETURA-DADOS-COMERCIAL.md` | 347 | Arquitetura pública × privada, config central, lead scoring, catálogo de analytics, alertas, fato × análise, base da área de cliente, backlog P1/P2 |
| `RELATORIO-ENTREGA-P0.md` | este arquivo | Registro da entrega |

### Modificados (aditivos — nenhuma funcionalidade removida)

| Arquivo | +/- | O que mudou |
|---|---|---|
| `scripts/build_site_core.py` | +43 / −3 | `import commercial`; `page()` injeta links comerciais no nav, CTA no cabeçalho, CSS/JS/config comercial no `<head>` e coluna "Contratar" no rodapé; home ganha faixa comercial após "O que mudou" e CTA de diagnóstico no bloco final; `main()` gera as páginas comerciais e as inclui no sitemap e na contagem |
| `scripts/build_site.py` | +7 / −1 | `_commercial.install(_core)` antes de `_ai_visibility.install(_core)` (as páginas comerciais também recebem discovery/Organization no `<head>`) |
| `scripts/ai_visibility.py` | +62 / −2 | `llms.txt`, `llms-full.txt`, `ai-content.md` e `AGENTS.md` publicado com a camada comercial; `mcp-actions.json` ganha `request-regulatory-diagnostic`, `read-executive-briefing-sample`, `read-commercial-config`; WebMCP declarativo no CTA de diagnóstico |
| `scripts/validate_site.py` | +134 | `check_commercial()`: CTA e config em todas as páginas, páginas comerciais completas, 10 eventos instrumentados, faixa interna de preço não publicada, ausência de segredo em `commercial.json`, prova social não renderizada, separação fato × análise na amostra, e linguagem jurídica só em contexto de aviso/negação |
| `README.md` | +82 / −4 | Seção "Camada comercial B2B" (URLs, soluções, config por env, alertas, testes) e estrutura de pastas atualizada |
| `AGENTS.md` | +10 / −2 | Camada comercial e regras de linguagem (não apresentar como aconselhamento jurídico) |
| `.gitignore` | +6 | `build/` (artefatos de alerta) e `node_modules/` (teste de front-end) |
| `docs/**` | gerado | 147 páginas (143 do monitor + 4 comerciais), `docs/data/commercial.json`, `docs/assets/commercial.{css,js}`, sitemap com 147 URLs, `llms.txt`/`ai-content.md`/`mcp-actions.json`/`AGENTS.md` atualizados |

As 313 linhas "removidas" em `docs/` são substituições de linha única (nav,
CTA do rodapé, métrica de frescor) — nenhuma seção, filtro, rota ou dado deixou
de existir.

---

## C. Novas URLs

| URL | Título | Evento principal |
|---|---|---|
| `https://monitor.lcfconsulting.com.br/solucoes/` | Soluções e preços — Inteligência regulatória de IA | `pricing_view` |
| `https://monitor.lcfconsulting.com.br/diagnostico/` | Diagnóstico de Exposição Regulatória em IA | `diagnostic_started` / `diagnostic_submitted` |
| `https://monitor.lcfconsulting.com.br/briefing-executivo/` | Exemplo de briefing executivo (amostra real) | `briefing_sample_view` / `alert_signup` |
| `https://monitor.lcfconsulting.com.br/para-empresas/` | Inteligência regulatória de IA para empresas | `para_empresas_view` / `demo_request` |
| `https://monitor.lcfconsulting.com.br/data/commercial.json` | Configuração pública da camada comercial | — |

Todas com `title`, `description`, `canonical`, OG, JSON-LD específico
(`ItemList`+`Service`+`Offer`+`FAQPage`, `Service`, `Report`,
`ProfessionalService`, `BreadcrumbList`), no `sitemap.xml` (147 URLs) e com links
internos a partir do cabeçalho, do rodapé, da home e entre si.

Nenhuma URL existente foi alterada, renomeada ou removida.

---

## D. Funil comercial implementado

```
Conteúdo / Google / LinkedIn / Outbound   → UTM capturado e preservado (first + last touch)
        ↓
Monitor público (143 páginas, sem login)  → page_view + CTA "Solicitar diagnóstico" no cabeçalho
        ↓                                    de TODAS as páginas
Faixa comercial na home                   → commercial_cta_click
        ↓
/solucoes/ (faixas, comparativo, FAQ)     → pricing_view
/briefing-executivo/ (amostra real)       → briefing_sample_view · briefing_print · alert_signup
/para-empresas/ (comprador corporativo)   → para_empresas_view · demo_request
        ↓
/diagnostico/ (formulário + qualificação) → diagnostic_started → diagnostic_submitted
        ↓                                    (payload com lead_score, classificação, fatores,
Lead estruturado                             UTM, página de origem, timestamp)
        ↓
Demo contextualizada → piloto → contrato recorrente
        (base pronta: perfis de alerta em build_alert_email.py, commercial.json,
         estado de conta trial/pilot/active/inactive previsto no backlog P2)
```

Rupturas evitadas: sem provider configurado o formulário **não falha** — degrada
para `mailto:` com o payload completo (incluindo score e UTM) e registra o lead
localmente; com provider, tenta `POST` JSON e, em último caso, submit nativo.

---

## E. Eventos de analytics

Camada própria (`assets/commercial.js`), sem fornecedor obrigatório. Todos os
eventos carregam: `event, timestamp, page, page_kind, sector, title, url, origem,
campanha, utm_source/medium/campaign/term/content` (+ versão `first_*`).

| Evento | Gatilho | Página | Propriedades extras |
|---|---|---|---|
| `page_view` | carga | todas | `page_kind` |
| `commercial_cta_click` | clique em CTA comercial | todas | `cta`, `destino`, `texto`, `plan` |
| `diagnostic_page_view` | visita | `/diagnostico/` | — |
| `diagnostic_started` | 1ª interação com o formulário | `/diagnostico/` | `page` |
| `diagnostic_submitted` | lead enviado | `/diagnostico/` | `modo`, `provider`, `lead_score`, `lead_class`, `setor`, `interesse` |
| `diagnostic_submit_error` | falha de envio | `/diagnostico/` | `lead_score`, `setor` |
| `diagnostic_validation_error` | envio bloqueado | `/diagnostico/` | — |
| `briefing_sample_view` | visita | `/briefing-executivo/` | — |
| `briefing_print` | imprimir/PDF | `/briefing-executivo/` | `page` |
| `pricing_view` | visita ou clique em plano/preço | `/solucoes/` | `plan`, `cta` |
| `sector_page_view` | clique setorial | briefing (base P1) | `setor` |
| `high_impact_view` | gancho pronto | (P1) | — |
| `alert_signup` | ativação de alertas | `/briefing-executivo/` | `modo`, `setor` |
| `alert_signup_error` | falha | `/briefing-executivo/` | — |
| `demo_request` | pedido de demo | `/para-empresas/` | `cta`, `destino` |
| `whatsapp_click` | clique em WhatsApp | todas (se configurado) | `canal`, `destino` |
| `para_empresas_view` | visita | `/para-empresas/` | — |
| `lead_bot_blocked` | honeypot preenchido | formulários | `form` |

Destinos: `window.dataLayer` (GTM), `gtag()` (se `MONITOR_GA4_ID`), `plausible()`
(se `MONITOR_PLAUSIBLE_DOMAIN`), `sendBeacon` (se `MONITOR_ANALYTICS_ENDPOINT`) e
`localStorage.monitor_eventos` (últimos 200) para auditoria do funil sem
ferramenta externa. Debug: `MONITOR_ANALYTICS_DEBUG=1` no build ou `?debug=1` na
URL (mostra também o cálculo do lead score).

---

## F. O que ainda NÃO foi implementado

### P1 — conversão
9. `/setores/fintech|bancos|seguros|saude|data-centers|cloud|tecnologia|escritorios-advocacia|associacoes` — base pronta (`CATEGORIA_PARA_SETORES`, agregação por setor no brief, evento `sector_page_view`, links "Receber briefing deste setor" já apontando para o diagnóstico com setor).
10. Camada "impacto para o negócio" nas fichas `/proposicoes/<slug>/` — motor pronto em `brief.py`; falta renderizar na ficha.
11. `/alto-impacto/` + filtros score 80+ / 60–79 / <60 — hoje o filtro existente é 60/75/90; evento `high_impact_view` já instrumentado.
12. Watchlist — exige estado por visitante.
13. PDF do relatório executivo — HTML de e-mail já é imprimível; falta gerador no CI.
14. Configuração de alertas pelo cliente — hoje o perfil é definido por contrato/CLI.

### P2 — retenção / enterprise
15. `/login` · 16. `/app` (Dashboard, Alertas, Temas, Watchlist, Briefings, Relatórios, Agenda, Exportações, Configurações) · 17. multiusuário/papéis · 18. API privada com token · 19. webhooks com HMAC · 20. SLA · 21. white-label · estado de conta `trial/pilot/active/inactive` (item 22) · série histórica de score (habilita o alerta `alteracao_score`, hoje declarado como não implementado) · persistência server-side de leads.

### Pendências operacionais (não são código)
* Definir `MONITOR_LEAD_ENDPOINT` (provider) e `MONITOR_WHATSAPP` no ambiente de build da Vercel — hoje o site opera em modo fallback de e-mail.
* Definir `MONITOR_GA4_ID` ou `MONITOR_PLAUSIBLE_DOMAIN` para dashboard de funil.
* Confirmar o e-mail comercial (`MONITOR_COMMERCIAL_EMAIL`; padrão atual `contato@lcfconsulting.com.br`).
* Prova social: estrutura pronta e **desativada** — só ativar com cases/logos/depoimentos reais autorizados.

---

## G. Evidências técnicas

**Build** (após as alterações):
```
OK: site gerado em docs/ — 147 páginas, 147 URLs no sitemap.
OK: camada comercial gerada — /solucoes/, /diagnostico/, /briefing-executivo/, /para-empresas/
OK: AEO/SEO/agentic discovery files generated.
OK: sitemap e arquivos críticos validados em https://monitor.lcfconsulting.com.br
```

**Validação** (`scripts/validate_site.py`, com o novo bloco comercial):
```
Erros: 0 · Avisos: 0
VALIDAÇÃO OK
```

**Testes do coletor** (não afetados): `AUTOTESTE OK — orçamento, persistência e
métricas funcionando.` (build passou a reportar 147 páginas dentro do teste).

**Testes da camada comercial** (`scripts/selftest_comercial.py`):
```
== 1) Configuração centralizada ==  == 2) Lead scoring ==  == 3) brief.py ==
== 4) HTML gerado ==  == 5) Analytics ==  == 6) Alerta/relatório ==  == 7) Front-end (jsdom) ==
RESULTADO: 121 ok · 0 falha(s)
SELFTEST COMERCIAL OK
```

**Teste de front-end** (jsdom sobre o HTML gerado, 52 verificações, 0 falhas) —
cobre: `page_view` + UTM preservado (source/campaign/origem/first touch),
`commercial_cta_click`, `diagnostic_started`, lead score = 100 com 7 fatores para
perfil de prioridade, payload com e-mail corporativo/origem/UTM/timestamp/assunto,
lead em buffer local, `diagnostic_submitted` nos modos *fallback* (sem fetch) e
*endpoint* (fetch ao provider + painel de sucesso), bloqueio de envio incompleto,
honeypot, `briefing_sample_view`, 5+ blocos fato × análise, impressão,
`alert_signup`, `pricing_view`, 4 planos, `demo_request`, faixa comercial e CTA na
home, e **filtro de score do monitor público intacto** (`site.js` inalterado).

**Configuração por ambiente verificada** (build de teste com env):
`MONITOR_PRICE_RADAR_EXECUTIVO_MIN/MAX` → "R$ 5.500 – R$ 9.000" no HTML;
`MONITOR_WHATSAPP` → `wa.me/...` nos CTAs; `MONITOR_GA4_ID` → tag gtag injetada;
`MONITOR_LEAD_ENDPOINT` → config pública e POST do formulário; `debug` ativo.

**Alertas/relatório gerados** (`build/alertas/`, não versionado):
`brief-semanal-2026-09-12.{html,txt,json}` (12 mudanças, 5 matérias, 7 eventos,
44 links de fonte oficial) e `alerta-imediato-2026-09-12.json` (score mínimo 80 +
temas `infraestrutura-de-ia,protecao-de-dados` → 3 matérias, janela de 1 dia).
HTML de e-mail sem CSS externo e sem JavaScript (estilos inline).

**Commits / branch.** Todo o trabalho na branch
`arena/01a097e7-monitor-legislativo` (base `317bff6`). `data/legislation/`
intacto.

---

## H. Próxima ação para gerar receita

**A próxima ação com maior probabilidade de gerar receita é:**

> Enviar hoje, para 20 contactos reais da sua rede (fintech, banco, seguradora,
> healthtech, data center/cloud e escritórios com prática de tecnologia), o link
> `https://monitor.lcfconsulting.com.br/briefing-executivo/?utm_source=outbound&utm_medium=linkedin&utm_campaign=radar_ia_set26`
> com uma mensagem de 3 linhas nomeando **uma matéria do próprio briefing que
> toca o sector do destinatário** (Redata/PL 278/2026 à sanção para data center e
> cloud; PL 2338/2023 com votação pós-eleições para quem usa IA em processo
> crítico; Lei 15.487/2026 e a janela do TSE para quem publica conteúdo), e
> fechar com o CTA já pronto na página: *"Solicitar diagnóstico regulatório"*.
> Cada envio chega ao formulário com UTM preservado e pontuação de prioridade
> (0–100), de modo que a agenda de demo da semana seguinte se monta sozinha a
> partir dos leads 70+ — sem gastar mais um minuto de desenvolvimento.

Pré-requisito operacional de 15 minutos para não perder nenhum lead: definir
`MONITOR_LEAD_ENDPOINT` (ex.: Formspree) e `MONITOR_COMMERCIAL_EMAIL`/
`MONITOR_WHATSAPP` no ambiente de build da Vercel. Enquanto isso o site já capta
em modo fallback (abre o e-mail do visitante com o pedido completo), então a
acção pode ser executada hoje mesmo.
