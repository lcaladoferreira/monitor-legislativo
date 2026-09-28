# Arquitetura da ingestão de Diários Oficiais

Documento de **fonte** (versionado, editável). O build copia este arquivo para
`docs/architecture-diarios.md` — a pasta `docs/` é saída gerada e nunca deve ser
editada à mão.

Escopo: como o Monitor Legislativo deixou de depender de **busca temática** no
Diário Oficial da União e passou a **ingerir a edição integral** de forma
auditável, com arquitetura pronta para os 27 entes estaduais e para os
municípios. A regra editorial que governa todo o desenho:

> **coletar primeiro, classificar depois** — e nada é inventado: campo que a
> fonte oficial não entrega fica `None` (ou ausente), nunca preenchido por
> inferência.

---

## 1. Pipeline

```
SOURCE → FETCH → RAW → PARSE → NORMALIZE → DEDUP → CLASSIFY → STORE → ALERT
```

| Etapa | Onde vive | O que acontece | O que é proibido |
|---|---|---|---|
| **SOURCE** | `scripts/diarios/registry.py` | Fonte cadastrada (source_id, jurisdição, tipo de acesso, formato, coletor, status) define *de onde* se coleta | Marcar fonte sem coletor como coberta |
| **FETCH** | `scripts/diarios/base.py::Cliente` (reuso do cliente do projeto: timeout, retry, cache, telemetria, orçamento) | Busca a **edição inteira** da data (todas as seções), sem filtro temático | Aplicar termo de busca na origem e chamar isso de cobertura |
| **RAW** | `scripts/storage/` (`RawStorage`, `LocalRawStorage`) | Payload bruto e arquivo-fonte vão para `var/raw/diarios/<source_id>/<referencia>/` (fora do Git) | Publicar HTML/XML bruto no dataset público |
| **PARSE** | `scripts/diarios/dou.py` (DOU), adapters por família (municipal) | Extrai os atos com os campos que existem no payload | Inventar campo ausente; engolir erro de parser |
| **NORMALIZE** | `scripts/diarios/base.py::normalizar_item` | Contrato comum: `id_publicacao`, `id_oficial`, título, texto, data, seção, edição, extraordinária, tipo de ato, órgão, hierarquia, URL oficial, arquivo-fonte, página, hash, timestamp | Substituir URL oficial por secundária |
| **DEDUP** | `scripts/diarios/dedup.py` | Identidade oficial (ou composta), hash de conteúdo, `primeira_deteccao`, `ultima_verificacao`, `ultima_alteracao`, `hash_anterior`/`hash_atual`, histórico | Sobrescrever registro quando o texto muda |
| **CLASSIFY** | `scripts/diarios/classificacao.py` + `scripts/sources/base.py` | `classificar_detalhado()` aplica os **mesmos padrões publicados** (30 grupos / 77 padrões) sobre o texto já ingerido | Tratar ausência de match temático como erro de ingestão |
| **STORE** | `MetadataStore` (índice local) + `data/diarios/estado.json` (versionado) + `data/legislation/diarios.json` (snapshot público) + `atos.json` via `update_sources.mesclar()` | Separa o corpus (grande, fora do Git) do estado auditável (pequeno, versionado) | Gravar todo o corpus no dataset público |
| **ALERT** | `scripts/diarios/coverage.py`, painel `/monitoramento/`, `updates.json` | Publica cobertura real, quebra de layout, zero publicações confirmado, modo de ingestão e fallback usado | Esconder falha de parser como "não houve publicação" |

Os contadores de ingestão são medidos **independentemente da classificação**
(`MetricasIngestao`): `itens_fonte`, `itens_normalizados`, `itens_classificados`,
`itens_relevantes`, `itens_descartados`, `itens_revisao`, `duplicados`,
`falhas_parse`.

---

## 2. Como o DOU passou a ser coletado

Ordem de tentativa por execução (`scripts/diarios/dou.py::ColetorDiarioDou`):

1. **XML oficial do INLABS** (`ColetorDouXMLINLABS`) — caminho estruturado
   prioritário. Duas origens possíveis:
   - `MONITOR_DOU_XML_DIR`: pacotes `.zip`/`.xml` oficiais já obtidos
     (download manual no INLABS/dados abertos ou cópia de arquivo do órgão);
   - `MONITOR_INLABS_USUARIO` + `MONITOR_INLABS_SENHA`: download autenticado
     (credenciais vivem no ambiente do runner, **nunca no repositório**).
   O parser lê o formato de `<article>` com os atributos oficiais
   (`id`, `name`, `pubName`, `artType`, `pubDate`, `editionNumber`,
   `hierarchyStr`/`hierarchyList`, `artCategory`, `numberPage`) e marca
   `cobertura_integral=true` **somente** depois de ler o pacote de verdade.
2. **Edição integral pela página oficial de leitura do jornal**
   (`ColetorDouIntegral`) — `https://www.in.gov.br/leiturajornal?data=DD-MM-AAAA&secao=do1|do2|do3`.
   Sem termo de busca: a página lista a edição inteira da seção. Dois níveis de
   parser, ambos sem invenção:
   - JSON embutido na página (`parse_dou_json_embutido`) — usado quando o portal
     entrega a lista estruturada (`classPK` → `id_oficial`, `urlTitle` → URL
     oficial);
   - HTML da listagem (`parse_dou_html_edicao`) — fallback estruturado com o
     breadcrumb institucional (até 5 níveis) e a referência
     `Edição Nº X de DD/MM/AAAA - Pág. N`.
   Edições **extra/especial/suplemento** só entram quando a própria página as
   declara (`extrair_edicoes_extras`).
3. **Busca temática** (`ColetorDouBuscaTematica`) — o coletor histórico
   `scripts/sources/dou.py`, **preservado**, agora como *fallback* e verificação
   complementar. Ele continua sendo acionado quando os caminhos integrais não
   respondem; nesse caso a fonte fica com `modo_ingestao="fallback"` e
   `cobertura_integral=false`, e o painel mostra exatamente isso.

`ColetorDiarioDou` agrega os sub-resultados (`_absorver_resultado`) e nunca
declara sucesso sem resposta verificável: se todos os caminhos falharem, a fonte
levanta `FonteIndisponivel`.

### Detecção de quebra de layout (FASE 12)

Uma resposta `200` com conteúdo substancial **não** é sucesso automático. O
método `FonteDiario.avaliar_layout()` compara os marcadores esperados da página
(breadcrumb, referência de edição, links `/web/dou/-/`) com o que foi
efetivamente encontrado:

| Situação | Interpretação | Efeito |
|---|---|---|
| Marcadores presentes + itens extraídos | edição lida | `status=ok` |
| Marcadores presentes + zero itens | **zero publicações legítimo** | `zero_publicacao_confirmado=true`, `status=ok` |
| Marcadores ausentes + conteúdo substancial | **layout mudou** | `layout_changed=true`, `canais_falhos`, `status=parcial`/`falha` |
| Resposta vazia / erro HTTP | fonte indisponível | `status=falha` (nada é inventado) |

Página com paginação detectada (`RE_PAGINACAO`) ou truncamento por teto de
itens (`MONITOR_DOU_MAX_ITENS_EDICAO`) impede `cobertura_integral=true`.

---

## 3. Source Registry

`scripts/diarios/registry.py` mantém o catálogo **versionado** (definição) e a
**saúde** operacional (snapshot). Campos: `source_id`, `nome`, `nivel`
(`federal|estadual|municipal|judiciario`), `uf`, `municipio`, `poder`, `url`,
`tipo_acesso` (`api|xml|json|rss|html|pdf|scraper|agregador|nao_definido`),
`formato`, `collector`, `ativo`, `obrigatorio`, `adapter_family`,
`ultima_tentativa`, `ultima_execucao_ok`, `ultima_publicacao`, `status`, `erro`.

Vocabulário de status (nunca "coberto" por otimismo):

| status | Significado |
|---|---|
| `nao_implementado` | fonte cadastrada, **sem coletor** — é pendência, não cobertura |
| `implementado` | existe coletor, ainda sem execução verificável |
| `funcionando` | última execução leu a fonte com resposta verificável |
| `parcial` | coletou com cobertura reduzida, layout mudou ou houve falha de canal |
| `falha` | nenhuma resposta utilizável na última tentativa |

Cadastro atual: **31 fontes** → 3 federais de DOU (`dou`, `dou_inlabs_xml`,
`dou_busca_tematica`), 1 judiciária (`djen`, aguardando coletor), **os 27 entes
estaduais** (26 estados + DF, todos `nao_implementado` com URL oficial) e as
famílias municipais (0 municípios habilitados por padrão).

### Estados

Os 27 entes estão cadastrados desde já (`estados/`) com o vocabulário e o
`adapter_family` previstos. Entram como `nao_implementado` — o painel mostra a
pendência nominal, sem nenhum percentual fictício. Implementar um estado é
preencher o coletor e mudar a saúde com uma execução real verificada.

### Municípios

`config/diarios_municipios.json` é a lista **vazia por padrão** e documenta como
habilitar cada município. As cinco famílias de adapter
(`scripts/diarios/municipal/`):

| família | Estratégia | Como habilitar |
|---|---|---|
| `querido_diario` | agregador de diários municipais | `MONITOR_QUERIDO_DIARIO_API` + entrada no config com `codigo_ibge` |
| `diario_individual` | site próprio do município (`html`/`pdf`) | coletor específico por município |
| `plataforma_compartilhada` | portais que hospedam vários municípios (ex.: plataformas estaduais de atos municipais) | parser por plataforma |
| `api_municipal` | API oficial do município | endpoint documentado pela prefeitura |
| `pdf_listing` | listagem de PDFs por data | parser de listagem + extração de texto (com quality gate) |

Regra: município só entra como `implementado` quando o registry tem
`tipo_acesso`, `formato`, URL oficial confirmada e uma execução verificada. A
estrutura já existe; a cobertura não é declarada antecipadamente.

---

## 4. Deduplicação e histórico

Chave de identidade (`base.chave_identidade`), em ordem:

1. identificador oficial da fonte (`id_oficial`, ex.: `dou:734499001`);
2. `source_id + data + url_oficial + titulo`;
3. `source_id + data + url_oficial`;
4. `source_id + hash_conteudo` (último recurso).

Estados por execução: `novo`, `inalterado`, `alterado`, `duplicado`
(intra-execução). Quando o conteúdo muda, o registro **preserva**
`hash_anterior`, `hash_atual`, `ultima_alteracao` e um `historico` (limite de 20
entradas) — nada é sobrescrito em silêncio. Digests de edição
(`hash_lista` das chaves ingeridas) ficam em `data/diarios/estado.json` e provam
que a edição foi lida por inteiro, mesmo quando nenhum item é temático.

---

## 5. Armazenamento (abstração local, pronta para escalar)

`scripts/storage/base.py` define os contratos:

- `RawStorage.save/exists/get/listar` — bruto + payload parseado + arquivo-fonte;
- `MetadataStore.upsert/find/exists/todos` — índice por chave estável.

Implementações **locais** (nenhuma infraestrutura paga é necessária):

- `LocalRawStorage` → `var/raw/diarios/<source_id>/<referencia>/` com
  `itens.jsonl.gz`, `meta.json` e `fonte/`;
- `LocalMetadataStore` → `var/raw/diarios/indice.json` (escrita atômica, teto de
  registros, decisão de dedup entre execuções).

`ObjectStorageRaw` existe como stub documentado para S3/MinIO/GCS; backends
futuros (Object Storage, PostgreSQL, OpenSearch) entram por
`MONITOR_RAW_STORAGE`/`obter_raw_storage()` sem tocar no pipeline. **O deploy na
Vercel continua lendo apenas `data/legislation/*.json`** — o corpus bruto fica
fora do Git e fora do build.

---

## 6. Quality gate do texto e fallback visual

`scripts/diarios/quality.py::evaluate_text_quality(texto)` devolve
`good | degraded | failed` com métricas e motivos auditáveis: texto vazio, razão
de caracteres inválidos, razão alfabética, fragmentação, páginas sem texto,
repetição anormal, corrupção de encoding (mojibake).

`scripts/visual_fallback/` traz **somente a interface** (FASE 9), sem PyTorch,
Qwen, FAISS ou qualquer dependência pesada:

- `VisualFallback` (contrato) + `PixelRAGFallback` (**stub**, `disponivel()`
  sempre `False` até autorização explícita);
- `decidir_pipeline()` → `estruturado | texto | visual | indisponivel`;
- regra: **só** `degraded`/`failed` podem acionar o pipeline visual, e nada é
  executado enquanto o backend não estiver habilitado
  (`MONITOR_VISUAL_FALLBACK`).

---

## 7. Coverage Monitor

`scripts/diarios/coverage.py` publica em `data/legislation/diarios.json` (e o
build copia para `docs/data/diarios.json`):

- por fonte: os `CAMPOS_COBERTURA` (`ultima_tentativa`, `ultima_coleta_ok`,
  `ultima_publicacao_detectada`, `itens_coletados`, `erro`, `status`, `duracao`,
  `layout_changed`) mais `modo_ingestao`, `cobertura_integral`, `fallback_usado`,
  `itens_normalizados`, `itens_relevantes`;
- agregados: `fontes_totais`, `fontes_implementadas`, `fontes_ok`,
  `fontes_parciais`, `fontes_falha`, `fontes_nao_implementadas`,
  `cobertura_tecnica_pct` e a **definição publicada** do percentual;
- `pendentes`: lista nominal do que não tem coletor.

`cobertura_tecnica_pct` é a fração de fontes **cadastradas** com coletor
implementado — jamais "100% de cobertura" porque os coletores rodaram. Fonte
`nao_implementado` e fonte `implementado` sem execução ficam fora do numerador.

---

## 8. Operação

```bash
python3 scripts/update_diarios.py --listar                  # registry completo
python3 scripts/update_diarios.py --cobertura               # snapshot + pendências
python3 scripts/update_diarios.py --quality "Art. 1º ..."   # quality gate do texto
python3 scripts/update_diarios.py --fonte dou --dry-run     # coleta sem gravar nada
python3 scripts/update_diarios.py --fonte dou               # grava estado + snapshot
python3 scripts/probe_diarios.py --fonte dou_inlabs_xml     # sonda de estrutura oficial
python3 -m unittest discover -s tests -t tests              # suíte (offline)
```

Variáveis de ambiente (todas opcionais):

| Variável | Efeito |
|---|---|
| `MONITOR_DOU_XML_DIR` | diretório com pacotes XML oficiais do INLABS |
| `MONITOR_INLABS_USUARIO` / `MONITOR_INLABS_SENHA` | download autenticado no INLABS (segredo de ambiente) |
| `MONITOR_DOU_XML=0` | desliga o caminho XML |
| `MONITOR_DOU_FALLBACK=0` | desliga a busca temática (fallback/complemento) |
| `MONITOR_DOU_DIARIOS=0` | volta a fonte `dou` ao coletor antigo (rollback seguro) |
| `MONITOR_DIARIOS_DATAS` | janela explícita de datas (backfill, `AAAA-MM-DD,AAAA-MM-DD`) |
| `MONITOR_DOU_DIAS` | tamanho da janela de datas |
| `MONITOR_DOU_MAX_ITENS_EDICAO` | teto de itens por edição (padrão 2000) |
| `MONITOR_DOU_TEXTOS_POR_EDICAO` | teto de páginas de ato abertas por edição para capturar o texto (padrão 25; `0` desliga) |
| `MONITOR_DOU_TEXTO_MB_POR_EDICAO` | teto de MB de texto integral por edição (padrão 12) |
| `MONITOR_ARQUIVO_FONTE_MB` | teto do arquivo-fonte guardado por página (padrão 4 MB; o corte é registrado em `avisos`) |
| `MONITOR_RAW_STORAGE` | backend de raw storage (`local` hoje) |
| `MONITOR_RAW_DIR` | raiz do raw storage |
| `MONITOR_QUERIDO_DIARIO_API` | base da API do agregador municipal |
| `MONITOR_VISUAL_FALLBACK` | habilita o fallback visual (stub desligado por padrão) |

Integração com o fluxo principal: `scripts/update_sources.py` executa o pipeline
em subprocesso (`update_diarios.py --fonte dou --json-legado …`), traduz o
payload para o contrato legado e **só então** `mesclar()` grava
`atos.json`/`updates.json`. Se o pipeline falhar, a busca temática assume
(`caminho_ingestao="busca_tematica_fallback"`) e a saúde registra o que
aconteceu. `MONITOR_DOU_DIARIOS=0` desliga a rota nova sem mexer em dado.

---

## 8.1 Limites de recurso (por que existem)

A primeira execução da rota integral em CI morreu com **exit code 137 (OOM)**. Três
causas foram corrigidas e ficaram cobertas por testes
(`tests/test_diarios_memoria.py`):

1. **arquivo-fonte liberado depois de gravar** — a página HTML de cada seção era
   mantida em memória até o fim da execução e nem chegava ao raw storage; agora é
   entregue a `RawStorage.save(..., arquivos=…)` e o dicionário é esvaziado em
   `finally` (inclusive em `--dry-run`, que não grava nada);
2. **tetos de captura de texto** — a captura do texto integral é limitada em
   número de páginas **e em bytes** por edição; ao estourar, a captura para, o
   motivo vai para `edicoes[].motivo_parada` e o restante para
   `textos_pendentes` (o item segue publicado com `texto` ausente — nada é
   inferido do título);
3. **sem processos órfãos** — os subprocessos rodam em grupo próprio
   (`start_new_session=True`) e o timeout mata o grupo inteiro
   (`os.killpg`), então netos não continuam consumindo rede/memória depois do
   estouro. O fallback também não reentra no pipeline: o subprocesso do coletor
   histórico recebe `MONITOR_DOU_DIARIOS=0`, evitando reexecutar a ingestão
   integral inteira só para chegar à mesma resposta.

Nada disso muda o que é publicado: os limites só restringem **quanto texto** é
capturado por execução, e o que ficou de fora aparece explicitamente.

## 9. Testes

`tests/test_diarios_dou.py`, `tests/test_diarios_pipeline.py`,
`tests/test_diarios_registry.py`, `tests/test_diarios_quality.py` cobrem parser
XML/JSON/HTML, normalização, dedup, alteração de conteúdo, fonte indisponível,
quebra de layout, zero publicações legítimo, registry (27 UFs),
métricas de cobertura, fallback por busca, stub do fallback visual e quality
gate — **sem dependência de rede**, com fixtures mínimas em
`tests/fixtures/diarios/`.

---

## 10. Limitações conhecidas

1. O download autenticado do pacote XML do INLABS depende de credencial do
   ambiente; sem ela, o caminho XML fica `nao_configurado` (**nunca** declarado
   como coberto).
2. `leiturajornal` é a via pública do DOU integral; o parser aceita os dois
   formatos que a página oferece e marca `layout_changed` quando nenhum é
   reconhecido — nesse caso a coleta do dia fica explicitamente parcial.
3. Os 27 estaduais e os municípios estão **cadastrados, não implementados**: a
   cobertura técnica estadual é 0% por decisão de honestidade, não por falta de
   cadastro.
4. O fallback visual está implementado apenas como interface; nenhuma extração
   visual roda nesta etapa.
5. Sem índice local (`MetadataStore`), itens não relevantes voltam a ser
   tratados como "novo" entre execuções — comportamento documentado e testado,
   evitado no uso normal porque `update_diarios.py` mantém o índice em `var/`.
