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

## Fontes monitoradas

**Fontes legislativas.** Câmara dos Deputados e Senado Federal (APIs de Dados
Abertos, fichas de tramitação, eventos e votações) — a base do dataset de
proposições.

**Fontes regulatórias.** ANPD, CNJ, TSE, Planalto e MCTI, coletadas por
`scripts/update_sources.py` no mesmo ciclo horário, com saúde por fonte e
fallback independente: uma fonte que falha não impede as demais nem o build.

**Diários Oficiais.** O DOU é coletado de forma **integral e auditável**; os 27
entes estaduais (26 estados + DF) e os municípios estão cadastrados no registry
com o vocabulário de coleta pronto para implementação incremental. Detalhes de
arquitetura: [`reports/architecture-diarios.md`](reports/architecture-diarios.md)
(publicado também em `docs/architecture-diarios.md`).

### DOU integral

A coleta deixou de depender de busca por tema. A ordem é:

1. **XML oficial do INLABS** (estruturado): pacotes locais via
   `MONITOR_DOU_XML_DIR` ou download autenticado via `MONITOR_INLABS_USUARIO`/
   `MONITOR_INLABS_SENHA` (credencial vive no ambiente, nunca no repositório);
2. **edição integral** pela página oficial de leitura do jornal
   (`in.gov.br/leiturajornal`, seções do1/do2/do3, com as edições extra que a
   própria página declarar) — sem termo de busca: entra a edição inteira. O texto
   de cada ato que a listagem não trouxer é lido na página oficial do ato, com
   tetos explícitos de páginas e de bytes por edição
   (`MONITOR_DOU_TEXTOS_POR_EDICAO`, `MONITOR_DOU_TEXTO_MB_POR_EDICAO`) — o que
   não for capturado é registrado como pendente;
3. **busca temática** (`scripts/sources/dou.py`, preservado) como *fallback* e
   verificação complementar.

A classificação temática acontece **depois** da ingestão, com os mesmos padrões
publicados (30 grupos temáticos). Regra explícita: **ausência de match temático
não é erro de ingestão** — o item fica registrado no corpus e nos contadores
(`itens_coletados`, `itens_normalizados`, `itens_classificados`,
`itens_relevantes`, `itens_descartados`, `itens_revisao`, `duplicados`,
`falhas_parse`).

### Estados implementados e pendentes

| Nível | Cadastrados | Com coletor | Situação |
|---|---|---|---|
| Federal (DOU) | 3 | 3 | XML oficial + edição integral + busca temática |
| Judiciário (DJEN) | 1 | 0 | cadastrado, aguardando coletor |
| Estaduais | 27 | 0 | **todos cadastrados e explicitamente `nao_implementado`** |
| Municipais | 0 habilitados | 0 | arquitetura pronta (5 famílias de adapter) |

Os 27 entes são cadastrados mesmo sem coletor: a cobertura estadual aparece como
**pendência nominal**, nunca como cobertura. A ordem de implementação é
incremental, um ente por vez, com execução verificada antes de qualquer
mudança de status.

### Municípios

`config/diarios_municipios.json` (vazio por padrão) habilita municípios por
família de adapter: `querido_diario` (agregador), `diario_individual`,
`plataforma_compartilhada`, `api_municipal` e `pdf_listing`. Nenhum município é
declarado coberto enquanto não houver coletor e execução verificada.

### Cobertura (o que o número significa)

`data/legislation/diarios.json` publica o Coverage Monitor: por fonte
(`ultima_tentativa`, `ultima_coleta_ok`, `ultima_publicacao_detectada`,
`itens_coletados`, `erro`, `status`, `duracao`, `layout_changed`, modo de
ingestão e se houve cobertura integral) e os agregados `fontes_totais`,
`fontes_implementadas`, `fontes_ok`, `fontes_parciais`, `fontes_falha`,
`fontes_nao_implementadas` e `cobertura_tecnica_pct`.

`cobertura_tecnica_pct` mede **fontes cadastradas com coletor implementado** —
não é a fração de publicações cobertas, e nunca é 100% só porque os coletores
rodaram. Quebra de layout é reportada como `layout_changed` (status
parcial/falha) e **nunca** como "não houve publicação"; zero publicações
legítimo só é afirmado quando os marcadores da edição estão presentes e a lista
vem vazia.

### Visual fallback (planejado, desligado)

Fontes cujo texto extraído é ruim (`degraded`/`failed` no quality gate) podem,
no futuro, acionar o pipeline visual. Nesta etapa existe **somente a interface**
(`scripts/visual_fallback/`), com o stub do PixelRAG desligado: nenhum PyTorch,
Qwen, FAISS ou dependência pesada entra no repositório ou no GitHub Actions.

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
  diarios.json               # Coverage Monitor dos Diários Oficiais (cobertura real por fonte)
  atos.json                  # Atos/publicações coletados das fontes regulatórias (ANPD, CNJ, TSE, DOU…)

data/diarios/
  estado.json                # Estado versionado da dedup dos diários (histórico; corpus fica fora do Git)

var/raw/diarios/             # Payload bruto da ingestão (FORA do Git): <source_id>/<referência>/…

data/articles/
  articles.json            # Artigos editoriais (conteúdo, datas, fontes, histórico de revisões)
  editorial_state.json     # Log auditável: cada mudança → ação editorial (novo artigo / atualização / ignorada)

scripts/
  update_legislation.py    # Coletor automático: APIs da Câmara/Senado → compara estado → atualiza dataset
  update_sources.py        # Fontes multiórgão (ANPD, CNJ, TSE, DOU, Planalto, MCTI) → atos.json/updates.json
  update_diarios.py        # Ingestão dos Diários Oficiais (edição integral) → estado + snapshot de cobertura
  probe_diarios.py         # Sonda de estrutura das fontes de Diários (diagnóstico, não coleta)
  sources/                 # Conectores multiórgão + vocabulário de descoberta/classificação (base.py)
  diarios/                 # Camada de Diários Oficiais: registry, DOU integral, dedup, coverage, quality
  storage/                 # Abstração de armazenamento (RawStorage/MetadataStore) — implementações locais
  visual_fallback/         # Interface do fallback visual (stub PixelRAG; nenhuma dependência pesada)
  generate_articles.py     # Camada editorial: classifica mudanças → cria/atualiza artigos (máx. 1 novo/dia)
  build_articles.py        # Renderiza /artigos/ (SEO, AEO, JSON-LD NewsArticle, feeds para IA)
  scoring.py               # Rúbrica pública do AI Legislative Impact Score (reproduzível)
  build_site.py            # Gera o site estático a partir do dataset → /docs
  dataviz.py               # Gráficos SVG (stdlib, sem JS) do painel de monitoramento
  validate_site.py         # Validações: JSON, duplicadas, links, SEO, domínio
  selftest_offline.py      # Testes offline: orçamento de tempo, persistência e métricas do coletor
  assets/                  # CSS e JS do site

.github/workflows/
  update-legislation.yml   # Action diária: coleta → build → valida → commit se houver mudança

reports/architecture-diarios.md  # Arquitetura da ingestão de diários (documento de fonte; build copia para docs/)
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
  artigos/                   # Área editorial automática (artigos criados/atualizados pelo monitor)
  data/                      # Cópia pública do dataset (JSON) + articles.json/editorial_state.json
  sitemap.xml · robots.txt   # SEO
```

## Como executar

```bash
python3 scripts/update_legislation.py   # coleta das fontes oficiais → atualiza /data
python3 scripts/build_site.py           # regenera /docs a partir de /data
python3 scripts/validate_site.py        # valida dataset, páginas, links e domínio
python3 scripts/selftest_offline.py     # testes offline do coletor (orçamento, persistência, métricas)
python3 -m unittest discover -s tests -t tests   # suíte completa (offline, com fixtures)

# Diários Oficiais (edição integral)
python3 scripts/update_diarios.py --listar                  # registry: federal, judiciário, 27 estaduais, municípios
python3 scripts/update_diarios.py --cobertura               # snapshot de cobertura + pendências explícitas
python3 scripts/update_diarios.py --quality "Art. 1º ..."   # quality gate do texto extraído
python3 scripts/update_diarios.py --fonte dou --dry-run     # coleta sem gravar nada
python3 scripts/probe_diarios.py --fonte dou_inlabs_xml     # sonda da estrutura oficial (diagnóstico)
```

O coletor aceita limites explícitos (todos com equivalente em variável de ambiente
`MONITOR_*`), usados pela automação para nunca estourar o tempo do job:

```bash
python3 scripts/update_legislation.py --budget-min 25 --max-novas 25 --workers 5
```

Publicação: a Vercel executa `python3 scripts/build_site.py` e publica a pasta `/docs`.
O domínio oficial (`SITE_URL` em `scripts/build_site.py`) é
`https://monitor.lcfconsulting.com.br`.

## Área de artigos automática (/artigos/)

Uma **camada editorial** transforma as mudanças que o monitor já detecta em
artigos públicos — sem intervenção humana e sem inventar nada:

1. `update_legislation.py` coleta as fontes oficiais e registra mudanças em `updates.json`/`atos.json`;
2. `generate_articles.py` classifica **cada mudança nova** (por `change_id` estável, processada uma única vez):
   - `NEW_ARTICLE_CANDIDATE` — fato editorialmente autônomo → **no máximo 1 artigo novo por dia** (o mais relevante; os demais ficam adiados para o dia seguinte);
   - `ARTICLE_UPDATE_CANDIDATE` — continuação de assunto já coberto (mesmo `editorial_topic_id`) → **atualiza o artigo existente na mesma URL**, preservando `published_at`, com novo `modified_at`, `revision_count++` e histórico de revisões;
   - `NO_EDITORIAL_ACTION` — ruído administrativo, eco de protocolo, registro aguardando curadoria → registrado como `ignored` no log editorial;
3. `build_site.py` gera `/artigos/` com SEO completo (canonical estável, Open Graph de artigo, `NewsArticle` JSON-LD com `datePublished`/`dateModified`/autor/publisher/about/mentions), breadcrumbs, linkagem interna bidirecional com as fichas, entrada única no sitemap com `<lastmod>` real por artigo;
4. os arquivos de descoberta para IA (`llms.txt`, `llms-full.txt`, `ai-content.md`, `mcp-actions.json`, `data/articles.json`) passam a citar os artigos automaticamente.

Toda decisão editorial é auditável em `data/articles/editorial_state.json`
(`source_change_id`, `editorial_action`, `article_id`, `selection_reason`,
`processed_at`). A falha da camada editorial nunca corrompe o dataset
legislativo — ela grava apenas em `data/articles/`. Testes: `tests/test_editorial.py`.

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

## Limitações conhecidas

- **Cobertura estadual/municipal é 0% hoje** e isso é declarado: os 27 entes
  estão cadastrados como `nao_implementado` até existir coletor com execução
  verificada. Não há número de cobertura sem coletor por trás.
- O download autenticado do pacote XML do INLABS exige credencial fornecida pelo
  ambiente do runner; sem ela, o caminho XML fica `nao_configurado` e a coleta
  segue pelos caminhos públicos (edições integrais) ou pela busca temática.
- A página oficial de leitura do jornal é HTML; o parser aceita JSON embutido e
  a listagem com breadcrumb. Mudança de layout **não** é silenciada: vira
  `layout_changed` com status parcial/falha até o parser ser atualizado.
- O fallback visual é apenas interface: extração visual de PDF digitalizado
  ainda não roda (dependeria de autorização explícita e de dependências pesadas
  fora do Actions).
- O corpus integral (payload bruto) fica em `var/raw/` **fora do Git**, por
  tamanho e por ser reproduzível na fonte; o que é versionado é o estado
  auditável (`data/diarios/estado.json`) e o dataset público
  (`data/legislation/*.json`).
- A captura do texto integral de uma edição é **limitada por execução** (teto de
  páginas e de MB por edição, `MONITOR_DOU_TEXTOS_POR_EDICAO` /
  `MONITOR_DOU_TEXTO_MB_POR_EDICAO`): o texto que não couber fica pendente e
  aparece como tal — o item continua publicado, mas sem texto inferido.
- Os subprocessos de coleta rodam em grupo próprio e o timeout derruba o grupo
  inteiro: um coletor travado não deixa processos órfãos consumindo o runner.

## Autoria

Projeto desenvolvido por [Leandro Calado](https://leandrocaladoferreira.com/) /
[LCF Consulting](https://lcfconsulting.com.br/).


## Camada comercial B2B

As páginas públicas permanecem como demonstração. Ofertas em `config/commercial.json`; geração em `scripts/commercial_pages.py`; API em `api/index.py`; dados comerciais privados via PostgreSQL.

Veja [a entrega e o guia de ativação](reports/ENTREGA-B2B.md) e [a auditoria inicial](reports/AUDITORIA-INICIAL.md). A captura e o envio real dependem da configuração de banco/SMTP; o build estático não configura serviços externos.

```bash
python3 -m unittest discover -s tests -v
MONITOR_DEV=1 python3 scripts/serve_commercial.py
```
