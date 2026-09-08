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
  build_site.py              # Gera o site estático a partir do dataset → /docs
  assets/                    # CSS e JS do site

docs/                        # SITE GERADO (não editar manualmente)
  index.html                 # Página principal (dashboard, o que mudou, top matérias)
  proposicoes/               # Lista filtrável + ficha individual de cada proposição
  leis/                      # Leis e normas vigentes
  timeline/                  # Linha do tempo da regulação de IA
  parlamentares/             # Mapa de parlamentares
  agenda/                    # Agenda legislativa de IA
  relatorio/                 # Relatório da execução + metodologia
  data/                      # Cópia pública do dataset (JSON)
  sitemap.xml · robots.txt   # SEO
```

## Como executar

```bash
python3 scripts/build_site.py   # regenera /docs a partir de /data
```

Publicação: ativar o GitHub Pages do repositório apontando para `main` / `/docs`.
Se o domínio for outro, ajustar `SITE_URL` em `scripts/build_site.py`.

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

Detalhes completos: página [Relatório](docs/relatorio/index.html).
