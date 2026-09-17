## Monitoramento multiórgão — o que foi implementado, testado e corrigido

Esta entrega amplia o monitoramento automático diário (antes só Câmara/Senado) para **ANPD, CNJ, TSE, DOU, Planalto e MCTI**, seguindo a missão. Câmara e Senado seguem exatamente como estavam (caminho aditivo, desligável por `MONITOR_SEM_FONTES`).

---

### 1) Órgãos automatizados

| órgão | automatizado | observação |
|---|---|---|
| ANPD | ✅ | 6 canais (notícias, temas, regulação, consultas, subsídios, atos) |
| CNJ | ✅ | API de atos normativos (páginas 1–3) + API de conteúdo do portal |
| TSE | ✅ | atos/notícias do portal (API do próprio site) + DOU (órgão/subórgão) |
| DOU | ✅ | busca oficial por tema (7 dias), normalização para a URL do ato |
| Planalto | ✅ | DOU (Atos do Poder Legislativo + Presidência da República) + notícias oficiais |
| MCTI | ✅ | DOU (atos do MCTI) + notícias institucionais + planos/programas (PBIA, semicondutores) |

### 2) Arquivo/coletor por órgão

| órgão | coletor | registro/orquestração |
|---|---|---|
| ANPD | `scripts/sources/anpd.py` | `scripts/sources/__init__.py` + `scripts/update_sources.py` |
| CNJ | `scripts/sources/cnj.py` | idem |
| TSE | `scripts/sources/tse.py` | idem |
| DOU | `scripts/sources/dou.py` | idem |
| Planalto | `scripts/sources/planalto.py` | idem |
| MCTI | `scripts/sources/mcti.py` | idem |
| (núcleo) | `scripts/sources/base.py` | dedup por URL oficial, saúde por canal, filtro temático conservador |
| (integração) | `scripts/update_legislation.py` (fase 3.5) | roda os 6 coletores em subprocesso com timeout próprio e mescla no dataset |
| (painel/dados) | `scripts/build_site_core.py`, `data/legislation/atos.json`, `data/legislation/updates.json` | `fontes_monitoradas`, `status_global` OK/PARCIAL/FALHA |
| (testes) | `tests/test_fontes_multiorgao.py` | 14 testes offline dos 6 coletores (parse, dedup, contratos) |

### 3) URLs/endpoints oficiais usados

- **ANPD** — `https://www.gov.br/anpd/++api++/@search` (plone.restapi do próprio portal; `portal_type=News Item`, `SearchableText=…`, `path=/pt-br/assuntos/regulacao`, `participacao-social`, `portal_type=File`)
- **CNJ** — `https://atos.cnj.jus.br/api/atos` (Sistema de Atos Normativos; `page=1..3`) e `https://www.cnj.jus.br/wp-json/wp/v2/posts` (API de conteúdo do portal)
- **TSE** — `https://www.tse.jus.br/++api++/@search` (API do portal: `portal_type=Noticia`, `path=/legislacao` → atos) e DOU `https://www.in.gov.br/consulta/-/buscar/dou?orgPrin=Poder Judiciário` (+ `orgSub=Tribunal Superior Eleitoral` para resoluções)
- **DOU** — `https://www.in.gov.br/consulta/-/buscar/dou` (busca oficial por tema; ato → `https://www.in.gov.br/web/dou/-/<urlTitle>`)
- **Planalto** — DOU com `orgPrin=Atos do Poder Legislativo` e `orgPrin=Presidência da República`; notícias oficiais `https://www.gov.br/planalto/pt-br/acompanhe-o-planalto/noticias` (+ `/RSS`)
- **MCTI** — DOU com `orgPrin=Ministério da Ciência, Tecnologia e Inovação`; portal `https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/noticias`, `/acesso-a-informacao/legislacao/portarias` e `/acompanhe-o-mcti` (PBIA, Semicondutores, Tecnologias Habilitadoras)

Toda URL de item gravada no dataset é a URL oficial da fonte (nada é inventado; item sem sinal temático claro é descartado, item duvidoso entra marcado para revisão).

### 4) Resultado de teste real por fonte (ensaio na CI, execução `35273642869`, 17/09/2026)

Ensaio real (`scripts/update_sources.py --todas --dry-run`) com os coletores deste PR rodando na CI, sem gravar dados: **`status_global: OK` — 6/6 fontes consultadas**.

| órgão | status | itens consultados | relevantes | descartados (tema) | duplicados entre canais | erros | tempo |
|---|---|---|---|---|---|---|---|
| ANPD | ok | 281 | 58 | 142 | 81 | 0 | 7,7s |
| CNJ | ok | 130 | 16 | 95 | 2 | 0 | 3,7s |
| TSE | ok | 6 | 1 | 5 | 0 | 3 | 12,5s |
| DOU | ok | 150 | 102 | 34 | 14 | 0 | 11,0s |
| Planalto | ok | 68 | 11 | 24 | 33 | 0 | 34,1s |
| MCTI | ok | 103 | 34 | 26 | 36 | 1 | 26,2s |

- **ANPD**: 6/6 canais responderam (notícias recentes, por tema, regulação, consultas, subsídios, atos normativos).
- **CNJ**: 5/5 canais (atos pág. 1/2/3 + notícias pág. 1/2); a dedup por URL oficial mostra 2 itens repetidos entre páginas.
- **TSE**: DOU respondeu (atos por tema + resoluções por órgão/subórgão); os 3 canais do *portal* ficaram bloqueados pelo WAF do TSE nesta execução (ver observação abaixo) — o DOU é a fonte oficial de publicação dos atos do TSE.
- **DOU**: canal único por tema respondeu; 102 itens relevantes.
- **Planalto**: 4/4 canais (atos do Legislativo, atos da Presidência, RSS e página de notícias).
- **MCTI**: DOU + notícias + planos/programas responderam; o canal "portarias publicadas" falhou (desafio anti-bot F5 do gov.br) e aparece como falho no painel — a cobertura de portarias do MCTI continua pelo DOU.
- **Testes automatizados**: `tests/test_fontes_multiorgao.py` (14 testes de parse/dedup/contrato) e `scripts/validate_site.py` → **VALIDAÇÃO OK (0 erros)**; build do site OK.

Observação de transparência (TSE): o WAF do portal TSE responde 200 e depois bloqueia rajadas do mesmo IP de runner (medido em 3 execuções: as sondas recebem 200 JSON, o ensaio seguinte recebe bloqueio). Por isso os canais do portal são opcionais (best-effort, com uma repetição após 20s), o DOU é o canal obrigatório do TSE e, quando o portal é bloqueado, a falha aparece explicitamente em `canais_falhos`/`canais_opcionais_falhos` no painel — nada é preenchido no lugar.

### 5) O workflow diário funciona com todos eles?

Sim. A integração entra na **fase 3.5 do `update_legislation.py`** (mesmo workflow `.github/workflows/update-legislation.yml`, mesmos horários diários):

- cada fonte roda em **subprocesso** com timeout próprio (`MONITOR_FONTES_TIMEOUT_S`, padrão 150s) e teto total (`limite_total` calculado sobre o orçamento restante);
- uma fonte que falha/trava **não interrompe** as outras nem o build do site; o resultado parcial é preservado;
- o dataset ganha `data/legislation/atos.json` e cada execução registra `fontes_monitoradas` (última tentativa, última execução ok, status, itens consultados, novidades, erros, endpoints) e `status_global` — **OK** (todas consultadas), **PARCIAL** (≥1 fonte falhou), **FALHA**;
- o resumo do job mostra a tabela por órgão e a lista de fontes com falha; o painel `/monitoramento/` exibe os mesmos dados;
- build e validação precisam passar para o commit de `data/`+`docs/` acontecer (Câmara/Senado inalterados);
- o modo diagnóstico (`probe-sources.yml`) roda o ensaio real + sondas de endpoints e publica evidência em `out/` a cada push que mexe nos coletores.

Correções feitas nesta entrega: URL do DOU com acentos/percent-encoding, dedup por URL oficial (paginação ignorada por servidor não duplica mais item), CNJ sem canais que repetiam página, TSE com resoluções por órgão/subórgão no DOU, MCTI sem canal RSS inexistente, rodapé do site só linka `atos.json` quando o arquivo existe (validação de links de volta a 0 erros).
