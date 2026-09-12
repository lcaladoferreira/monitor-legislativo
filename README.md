# Monitor Legislativo de IA no Brasil

**Sistema de inteligência legislativa** — monitoramento público, documentado e auditável de toda a atividade legislativa federal brasileira relacionada à Inteligência Artificial.

O ativo principal é o **dataset legislativo histórico** (`/data/legislation`), estruturado e continuamente atualizado. O site em `/docs` é a interface pública desse dataset.

- **Site:** publicado a partir da pasta `/docs` (compatível com GitHub Pages — opção *Deploy from branch: `main` / `/docs`*)
- **Dados:** `/data/legislation/*.json` (fonte única da verdade, versionada no Git)
- **Build:** `python3 scripts/build_site.py` (sem dependências externas)

---

## O que este repositório monitora

- PL, PLC, PEC, PDL, PLN, MP, substitutivos, emendas, requerimentos e pareceres relacionados a IA
- Leis sancionadas, vetos, decretos e atos regulatórios (TSE, CNJ, ANPD, MCTI)
- **Mudanças de estado** de cada proposição (relatoria, parecer, pauta, votação, apensação, arquivamento)
- Relações entre proposições (apensados, clusters temáticos, sucessão histórica)
- Parlamentares com atuação documentada em IA
- Agenda de eventos futuros e marcos normativos

## Estrutura

```
data/legislation/            # DATASET (fonte única da verdade)
  propositions.json          # Banco de proposições (chave: casa_tipo_numero_ano)
  laws.json                  # Leis, decretos, resoluções e atos vigentes
  timeline.json              # Timeline histórica documentada (2019–2026)
  parliamentarians.json      # Mapa de parlamentares com atuação documentada
  events.json                # Agenda legislativa de IA (eventos futuros)
  updates.json               # "O que mudou" + log de execuções
  categories.json            # 30 categorias temáticas

scripts/
  update_legislation.py    # Coletor automático: APIs da Câmara/Senado → compara estado → atualiza dataset
  scoring.py               # Rúbrica pública do AI Legislative Impact Score (reproduzível)
  build_site.py            # Entry point do build (domínio oficial + camadas comercial e de visibilidade IA)
  build_site_core.py       # Gera o site estático a partir do dataset → /docs
  commercial.py            # CONFIGURAÇÃO CENTRAL da camada comercial B2B + páginas comerciais
  brief.py                 # Motor do Executive Regulatory Brief (fato oficial × análise)
  build_alert_email.py     # Alertas por e-mail/webhook + relatório executivo (HTML, TXT, JSON)
  dataviz.py               # Gráficos SVG (stdlib, sem JS) do painel de monitoramento
  ai_visibility.py         # SEO/AEO/agentic: llms.txt, ai-content.md, robots, mcp-actions
  validate_site.py         # Validações: JSON, duplicadas, links, SEO, domínio + regras comerciais
  selftest_offline.py      # Testes offline: orçamento de tempo, persistência e métricas do coletor
  selftest_comercial.py    # Testes offline da camada comercial (config, scoring, brief, HTML, alertas)
  assets/                  # CSS e JS do site (style.css/site.js) + comerciais (commercial.css/js)
  tests/                   # Teste de front-end em jsdom (dev; opcional)

.github/workflows/
  update-legislation.yml   # Action diária: coleta → build → valida → commit se houver mudança
  briefing-comercial.yml   # Action semanal/manual: gera o Executive Regulatory Brief (e envia se houver SMTP)

docs/                        # SITE GERADO (não editar manualmente)
  index.html                 # Página principal (verificação, o que mudou, dashboard, top matérias)
  proposicoes/               # Lista filtrável + ficha individual de cada proposição
  atualizacoes/              # Histórico cronológico das mudanças detectadas
  leis/                      # Leis e normas vigentes
  timeline/                  # Linha do tempo da regulação de IA
  parlamentares/             # Mapa de parlamentares
  agenda/                    # Agenda legislativa de IA
  metodologia/               # Fontes, critérios, score, limitações e correções
  monitoramento/             # Painel de métricas do cron (frescor, cobertura, mudanças, custo HTTP)
  relatorio/                 # Relatório da execução + síntese editorial
  solucoes/                  # COMERCIAL: 4 formas de contratação + comparativo + FAQ
  diagnostico/               # COMERCIAL: landing de captura de lead + lead scoring
  briefing-executivo/        # COMERCIAL: amostra real do briefing pago (imprimível)
  para-empresas/             # COMERCIAL: página do comprador corporativo
  data/                      # Cópia pública do dataset (JSON) + commercial.json (config comercial)
  sitemap.xml · robots.txt   # SEO
```

## Como executar

```bash
python3 scripts/update_legislation.py   # coleta das fontes oficiais → atualiza /data
python3 scripts/build_site.py           # regenera /docs a partir de /data
python3 scripts/validate_site.py        # valida dataset, páginas, links e domínio
python3 scripts/selftest_offline.py     # testes offline do coletor (orçamento, persistência, métricas)
python3 scripts/selftest_comercial.py   # testes offline da camada comercial (build + validação inclusos)
python3 scripts/build_alert_email.py    # gera o Executive Regulatory Brief em build/alertas/
```

O coletor aceita limites explícitos (todos com equivalente em variável de ambiente
`MONITOR_*`), usados pela automação para nunca estourar o tempo do job:

```bash
python3 scripts/update_legislation.py --budget-min 25 --max-novas 25 --workers 5
```

Publicação: a Vercel executa `python3 scripts/build_site.py` e publica a pasta `/docs`.
O domínio oficial (`SITE_URL` em `scripts/build_site.py`) é
`https://monitor-legislativo-five.vercel.app`.

## Ciclo de execução do monitoramento (execuções futuras)

1. Carregar o estado anterior (`data/legislation/*.json`)
2. Consultar as fontes oficiais (APIs de Dados Abertos da Câmara e do Senado, fichas de tramitação, DOU)
3. Identificar novas proposições e novas movimentações
4. Comparar estado antigo × atual; detectar alterações
5. Atualizar os registros (nunca sobrescrever silenciosamente: registrar em `updates.json` status anterior, novo, data e fonte)
6. Regenerar o site e validar (`python3 scripts/build_site.py` + checagem de links)
7. Commit na branch de trabalho e PR para revisão

Se nada relevante mudou, apenas registra-se a verificação — **nada de conteúdo artificial**.

## Metodologia e política de qualidade

- **Fontes primárias obrigatórias:** cada fato relevante cita a URL oficial (Câmara, Senado, Congresso, Planalto, DOU, TSE, CNJ, ANPD). Imprensa apenas para descoberta/contexto.
- **Chave primária:** `casa_tipo_numero_ano` (ex.: `camara_pl_2338_2023`) — nenhuma duplicata.
- **AI Legislative Impact Score (0–100):** faixas 90–100 crítico · 75–89 muito relevante · 60–74 relevante · 40–59 monitorar · 0–39 baixa prioridade. Critérios: abrangência, estágio, proximidade de votação, regime de tramitação, apensados, impactos econômico e sobre direitos. Nunca manipulado.
- **Proibido:** inventar proposições, tramitações, datas, autores, pareceres, probabilidades ou posições políticas sem evidência documental.
- Campos não confirmados em fonte oficial ficam **ausentes**, nunca preenchidos.

## Estado atual (execução de 08/09/2026 — bootstrap)

- **32 proposições** monitoradas (incluindo o pacote de 37 apensados ao PL 2338/2023)
- **14 normas** vigentes ou históricas mapeadas (LGPD, ECA Digital, Lei 15.487/2026, Res. TSE 23.748/2026, Res. CNJ 615/2025, Decretos 12.975-12.976/2026, EBIA, PBIA…)
- **35 eventos** na timeline histórica (2019–2026)
- **15 parlamentares** com atuação documentada
- Situação-síntese: marco legal (PL 2338/2023) parado há 16 meses na comissão especial da Câmara, com votação adiada para depois das eleições de outubro/2026; Redata (PL 278/2026) aprovado pelo Congresso e à sanção; Lei 15.487/2026 (deepfakes) em vigor desde 07/08/2026.

Detalhes completos: página [Relatório](docs/relatorio/index.html) ·
saúde da automação: [Painel de monitoramento](docs/monitoramento/index.html).

## Automação

O workflow `.github/workflows/update-legislation.yml` executa diariamente (07:17 BRT):
coleta → rebuild → validação → commit somente se houver alteração real no dataset
ou nas páginas. Sem commits vazios. O histórico de cada execução fica em
`data/legislation/updates.json` (bloco `execucoes`) e as mudanças em `mudancas`.

**Orçamento de tempo (por que existe).** O dataset cresce a cada dia e cada
proposição monitorada custa consultas às APIs oficiais. Em 10/09/2026 o job foi
cancelado pelo timeout de 45 min **durante a coleta** — rebuild, validação e
commit não rodaram e o site ficou congelado na execução anterior. Correções
aplicadas:

- a coleta tem **teto de duração** (`MONITOR_BUDGET_SEGUNDOS`, padrão 25 min);
  ao se aproximar do teto ela para de iniciar consultas, grava o que verificou e
  registra a execução como `parcial` (nunca mais perde o trabalho feito);
- verificação em **ordem de prioridade** (maior impacto primeiro; empate → mais
  tempo sem verificação), de modo que o que fica pendente são as matérias de
  menor score — e elas são as primeiras da execução seguinte;
- **teto de fichas novas por execução** (`MONITOR_MAX_NOVAS`, padrão 25), com
  prioridade por relevância temática, tipo de proposição e recência;
- **cache de execução** por URL + telemetria de rede (chamadas, cache, falhas,
  tempo por endpoint), evitando consultas repetidas;
- rebuild, validação e commit rodam **mesmo se a coleta falhar** (`if: always()`),
  e a execução é sinalizada no resumo do job e no painel.

### Painel de monitoramento (DataViz)

A página [`/monitoramento/`](docs/monitoramento/index.html) é reconstruída a cada
execução do site e mostra, a partir do log auditável do cron: frescor da última
execução (recalculado no navegador — se o cron parar, o painel fica vermelho),
cobertura da verificação, proposições pendentes, mudanças por dia/mês/tipo,
latência de detecção, evolução do banco, curadoria pendente, custo em chamadas
HTTP por endpoint e o histórico completo de execuções. As mesmas métricas são
publicadas em `docs/data/monitoramento.json` para uso externo (BI, planilhas).

## Camada comercial B2B

O monitor público continua **público, indexável e sem login** — ele é a
demonstração da capacidade técnica. Sobre o mesmo dataset existe agora uma camada
comercial integrada ao site (não é um site separado):

| URL | Função no funil |
|---|---|
| [`/solucoes/`](docs/solucoes/index.html) | 4 formas de contratação com faixas de referência, comparativo, diferenciação e FAQ |
| [`/diagnostico/`](docs/diagnostico/index.html) | landing + captura de lead + qualificação por lead scoring |
| [`/briefing-executivo/`](docs/briefing-executivo/index.html) | amostra real do produto pago (Executive Regulatory Brief) gerada do dataset |
| [`/para-empresas/`](docs/para-empresas/index.html) | página do comprador corporativo + pedido de demonstração |

CTA principal em **todas** as páginas: *Solicitar diagnóstico regulatório*.
CTA secundário: *Ver exemplo de briefing executivo*.

Soluções: **Monitor IA** (R$ 1.500–3.000/mês) · **Radar Executivo de Regulação de
IA** (R$ 4.000–8.000/mês, oferta principal) · **Inteligência Institucional** (sob
consulta; faixa interna não publicada) · **Diagnóstico de Exposição
Regulatória** (R$ 5.000–15.000 por projeto).

Tudo é configuração centralizada em `scripts/commercial.py` (preço, CTAs,
endpoint de captura, WhatsApp, analytics, regras de lead scoring, prova social —
esta última desativada até existirem cases reais). O que é configurado volta
público em `docs/data/commercial.json`, consumido pelo front-end.

```bash
# captura de lead por provider de formulário (Formspree, Web3Forms, função própria...)
MONITOR_LEAD_ENDPOINT=https://formspree.io/f/xxxxxxxx python3 scripts/build_site.py

# sem provider: o formulário degrada para mailto com o payload completo (não perde lead)
python3 scripts/build_site.py

# preço, canal e analytics sem tocar em código
MONITOR_PRICE_RADAR_EXECUTIVO_MIN=5000 MONITOR_WHATSAPP=5511999999999 \
MONITOR_GA4_ID=G-XXXXXXXXXX python3 scripts/build_site.py
```

Alertas e relatório executivo (mesmo motor da amostra pública):

```bash
python3 scripts/build_alert_email.py                                  # brief semanal (HTML + TXT + JSON)
python3 scripts/build_alert_email.py --modelo alerta --frequencia imediato --score-minimo 80
python3 scripts/build_alert_email.py --destinatarios cliente@empresa.com.br --send   # SMTP via env
```

Testes da camada comercial (121 verificações + teste de front-end em jsdom quando
disponível):

```bash
python3 scripts/selftest_comercial.py
python3 scripts/validate_site.py     # inclui as regras comerciais (CTA, analytics,
                                     # faixa interna, prova social, fato × análise,
                                     # linguagem sem promessa jurídica)
```

Detalhes de arquitetura, plano público × privado dos dados, catálogo de eventos
de analytics e backlog P1/P2: [`ARQUITETURA-DADOS-COMERCIAL.md`](ARQUITETURA-DADOS-COMERCIAL.md).
Registro da entrega P0: [`RELATORIO-ENTREGA-P0.md`](RELATORIO-ENTREGA-P0.md).

**Escopo do serviço (obrigatório em qualquer peça comercial):** inteligência
regulatória, acompanhamento legislativo, análise de impacto e priorização com
fonte oficial. Não é parecer, aconselhamento jurídico ou garantia de conformidade.

## Autoria

Projeto desenvolvido por [Leandro Calado](https://leandrocaladoferreira.com/) /
[LCF Consulting](https://lcfconsulting.com.br/).
