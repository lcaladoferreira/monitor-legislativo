# Monitor LCF — intervenção GSC 28/10/2026: parlamentares

## Origem e escopo
- Google Search Console via Windsor.ai gratuito, conector `searchconsole`, propriedade `sc-domain:lcfconsulting.com.br`.
- Filtro obrigatório: `page contains https://monitor.lcfconsulting.com.br/`. Dados exclusivamente do Monitor, busca web.
- Dados consolidados até **25/10/2026** (margem de 3 dias).
- Métricas do site: soma de cliques/impressões de linhas por página, CTR recalculado e posição ponderada por impressões. Consultas do GSC são parcialmente omitidas por privacidade e não devem ser somadas para obter o total.

| Janela | Cliques | Impressões | CTR | Posição média |
| --- | ---: | ---: | ---: | ---: |
| 28d 28/09–25/10 | 12 | 1.294 | 0,93% | 7,68 |
| 28d anteriores 31/08–27/09 | 6 | 871 | 0,69% | 7,37 |
| 7d 19/10–25/10 | 5 | 329 | 1,52% | 8,90 |
| 7d anteriores 12/10–18/10 | 1 | 217 | 0,46% | 8,75 |

## Oportunidade priorizada
**URL:** https://monitor.lcfconsulting.com.br/parlamentares/

| Janela da URL | Cliques | Impressões | CTR | Posição |
| --- | ---: | ---: | ---: | ---: |
| 28d atual | 1 | 73 | 1,37% | 7,42 |
| 28d anterior | 1 | 41 | 2,44% | 10,98 |
| 7d atual | 0 | 13 | 0,00% | 14,62 |
| 7d anterior | 0 | 11 | 0,00% | 5,27 |

A URL tem posição útil no recorte de 28 dias, impressões crescentes e CTR baixo. A queda de posição em 7 dias exige acompanhamento, sem atribuição causal a qualquer mudança. Não foram retornadas consultas específicas para esta URL no conjunto de queries por página; portanto, **não há palavra-chave atribuída artificialmente**. A intervenção alinha a página à intenção documental de localizar autores, relatores, deputados, senadores e comissões da legislação de IA, preservando o escopo distinto da ficha do PL 2338/2023.

## Antes e depois
- **Title anterior:** `Parlamentares envolvidos com a legislação de IA no Brasil`.
- **Title novo:** `Parlamentares da IA: autores e relatores no Congresso`.
- **Meta anterior:** `Autores, relatores e presidentes de comissões das principais matérias de inteligência artificial no Congresso Nacional, com atuação documentada.`.
- **Meta nova:** `Deputados e senadores ligados à regulação de IA: autoria, relatoria e comissões do PL 2338/2023 e de outros projetos, com fontes oficiais.`.
- **H1 anterior:** `Parlamentares na legislação de IA`.
- **H1 novo:** `Parlamentares da regulação de IA: autores e relatores`.
- Introdução esclarece os papéis documentados, sem presumir posicionamento político.
- Links úteis na primeira dobra: ficha do PL 2338/2023, linha do tempo da regulação de IA e composição oficial da comissão especial na Câmara.
- Cartões: links de matérias agora separados visualmente; fontes formatadas como listas HTML válidas em vez de `<li>` dentro de `<p>`.
- Preservados dados parlamentares, canonical, BreadcrumbList, CollectionPage, navegação e funcionalidades.

## Fontes oficiais e verificação
- Composição da comissão especial da Câmara (relator e presidência): https://www.camara.leg.br/internet/comissao/composicao/57PL233823.htm
- Ficha do PL 2338/2023: https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2487262
- Código: `scripts/build_site_core.py`; HTML: `docs/parlamentares/index.html`.
- Commits da intervenção: `a0fbdbded354d27af5d64aebb121f4b7b660392d` (gerador) e `6dcf49b7249677358485edbf9916a7020a2679e1` (HTML).
- Verificar build, suíte de testes, Vercel READY e resposta pública após deploy. Não declarar HTTP 200 sem checagem independente.

## Medição futura
Comparar cliques, CTR, impressões e posição da URL em 14–28 dias **consolidados posteriores à publicação**. Não atribuir a mudança de tráfego ao experimento antes de acumular dados. Evitar reescrever o título antes de haver janela de observação suficiente.
