#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarios/base.py — vocabulário e contrato da camada de Diários Oficiais.

Arquitetura (FASE 1–2, 4, 7, 12):

    FONTE OFICIAL → FETCH → RAW → PARSE → NORMALIZE → DEDUP → CLASSIFY → STORE → ALERT
                     └────────────── ingestão ──────────────┘   └── classificação ──┘

Regra central: **coletar primeiro; classificar depois**. O coletor de um Diário
Oficial recebe a edição inteira (ou o pacote estruturado oficial) e devolve itens
brutos; a decisão temática acontece em outra etapa (`diarios/classificacao.py`),
depois de o item já ter sido persistido e deduplicado. Assim, uma publicação
relevante que não contenha nenhum termo de busca **não se perde**, e a ausência
de correspondência temática nunca conta como erro de ingestão.

Nada é inventado. Todo campo sem dado oficial na fonte fica `None` (ou ausente) —
nunca preenchido por estimativa. O módulo também concentra os vocabulários
fechados de nível, tipo de acesso, formato, família de adapter e status, para que
o registry, o monitor de cobertura e o painel falem a mesma língua.
"""
from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone

try:  # executado com scripts/ no sys.path (coleta)
    from sources.base import BRT, Cliente, limpar_texto, url_canonica
except ImportError:  # executado a partir da raiz do repositório (testes/import)
    from scripts.sources.base import BRT, Cliente, limpar_texto, url_canonica

# ------------------------------------------------------------------- caminhos
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE, "data")
DIARIOS_DIR = os.path.join(DATA_DIR, "diarios")
ARQUIVO_ESTADO = os.path.join(DIARIOS_DIR, "estado.json")
ARQUIVO_SNAPSHOT = os.path.join(DATA_DIR, "legislation", "diarios.json")

# ----------------------------------------------------------------- vocabulário
NIVEIS = ("federal", "estadual", "municipal", "judiciario")
TIPOS_ACESSO = ("api", "xml", "json", "rss", "html", "pdf", "scraper", "agregador",
                "nao_definido")
FORMATOS = ("xml", "json", "html", "pdf", "misto", "nao_definido")
ADAPTER_FAMILIES = ("querido_diario", "diario_individual", "plataforma_compartilhada",
                    "api_municipal", "pdf_listing", "nao_aplicavel")
STATUS_FONTES = ("nao_implementado", "implementado", "funcionando", "parcial", "falha")
PODERES = ("executivo", "legislativo", "judiciario", "todos", "nao_aplicavel")

# UFs oficiais do Brasil (27 entes: 26 estados + Distrito Federal).
UFS = ("AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
       "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
       "SP", "SE", "TO")

# Campos de um item bruto (o que a fonte oficial entregou; nada além disso).
CAMPOS_ITEM = (
    "id_publicacao",        # identificador da publicação na fonte
    "id_oficial",           # identificador oficial (ex.: classPK do DOU / id do XML)
    "titulo",
    "texto",                # texto integral (ou o conteúdo textual disponível)
    "data",                 # YYYY-MM-DD de publicação (None se a fonte não informa)
    "secao",                # ex.: "Seção 1" / do1
    "edicao",               # número da edição
    "edicao_extraordinaria", # True/False/None — só quando identificável
    "tipo_ato",             # Lei, Decreto, Portaria, Resolução…
    "orgao",                # órgão emissor (artCategory/hierarquia principal)
    "hierarquia",           # lista de níveis institucionais, do maior para o menor
    "url_oficial",          # URL oficial da publicação (obrigatória para entrar)
    "arquivo_fonte",        # nome do arquivo de origem (zip/xml/pdf/html)
    "pagina",               # página na edição, quando publicada
    "hash_conteudo",
    "coletado_em",
)


def agora_brt():
    return datetime.now(BRT)


def ts_iso():
    return agora_brt().isoformat(timespec="seconds")


def normalizar(texto):
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = t.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", t).strip().lower()


def sha1(*partes):
    base = normalizar(" | ".join(str(p or "") for p in partes))
    return "sha1:" + hashlib.sha1(base.encode("utf-8")).hexdigest()


def hash_conteudo(*partes, limite_texto=200000):
    """Hash do conteúdo do item (título + texto) — detecta alteração de texto.

    O texto é limitado para manter o hash barato em edições grandes; o limite é
    alto o suficiente para que qualquer alteração editorial relevante o mude.
    """
    return sha1(*[str(p or "")[:limite_texto] for p in partes])


def chave_identidade(source_id, item_normalizado):
    """Chave de deduplicação de um item (FASE 8).

    Ordem de precedência:
      1. identificador oficial da fonte (`id_oficial`), quando existe;
      2. `source_id + data + url_oficial + titulo`;
      3. `source_id + data + url_oficial` (sem título — quando a fonte não dá título);
      4. `source_id + hash_conteudo` ( último recurso, quando não há URL nem título).

    Diferença consciente em relação à formulação "source_id + data + url + titulo +
    hash": o hash **não** entra na identidade quando existe URL/título. Se
    entrasse, uma correção de texto criaria um item novo e o monitor perderia
    exatamente o que a FASE 8 exige preservar — `hash_anterior`/`hash_atual` e o
    `historico` da alteração. Os dois requisitos são compatíveis assim: a
    identidade é estável, o hash detecta a mudança. Ver docs/architecture-diarios.md.
    """
    id_oficial = (item_normalizado.get("id_oficial") or "").strip()
    if id_oficial:
        return f"{source_id}:oficial:{id_oficial}"
    url = url_canonica(item_normalizado.get("url_oficial"))
    titulo = normalizar(item_normalizado.get("titulo"))
    data = item_normalizado.get("data") or ""
    if url and titulo:
        return sha1(source_id, data, url, titulo)
    if url:
        return sha1(source_id, data, url)
    return sha1(source_id, item_normalizado.get("hash_conteudo"))


def normalizar_item(bruto, fonte, coletado_em=None):
    """Normaliza um item bruto para o contrato comum (FASE 2).

    Preenche apenas o que existe. `unidade_territorial`/`nivel`/`uf`/`municipio`
    vêm da fonte (registry), nunca deduzidos do texto. O item normalizado recebe
    `chave` (identidade de dedup), `id` (id estável de publicação no dataset) e
    `modo_ingestao`/`origem`.
    """
    item = {}
    for campo in CAMPOS_ITEM:
        valor = bruto.get(campo)
        if campo == "titulo":
            valor = limpar_texto(valor or "", 500) or None
        elif campo == "texto":
            valor = (valor or "").strip() or None
        elif campo == "hierarquia":
            if isinstance(valor, str):
                valor = [parte.strip() for parte in re.split(r"\s*(?:>|/|\|)\s*", valor) if parte.strip()]
            valor = [limpar_texto(p, 200) for p in (valor or [])] or None
        elif campo in ("edicao_extraordinaria",):
            valor = valor if isinstance(valor, bool) else None
        item[campo] = valor

    item["source_id"] = fonte.source_id
    item["nivel"] = getattr(fonte, "nivel", None)
    item["uf"] = getattr(fonte, "uf", None)
    item["municipio"] = getattr(fonte, "municipio", None)
    item["poder"] = getattr(fonte, "poder", None)
    item["jurisdicao"] = jurisdicao(fonte)
    item["modo_ingestao"] = bruto.get("modo_ingestao") or getattr(fonte, "modo_padrao", None)
    item["origem"] = bruto.get("origem") or getattr(fonte, "nome", None)
    item["coletado_em"] = coletado_em or bruto.get("coletado_em") or ts_iso()
    item["extras"] = dict(bruto.get("extras") or {})
    if not item.get("hash_conteudo"):
        item["hash_conteudo"] = hash_conteudo(item.get("titulo"), item.get("texto"))
    item["chave"] = chave_identidade(fonte.source_id, item)
    item["id"] = item["chave"]
    return item


def jurisdicao(fonte):
    """Rótulo de jurisdição da fonte (`federal`, `estadual:SP`, `municipal:SP:São Paulo`)."""
    nivel = (getattr(fonte, "nivel", None) or "nao_definido").lower()
    uf = getattr(fonte, "uf", None)
    municipio = getattr(fonte, "municipio", None)
    partes = [nivel]
    if uf:
        partes.append(uf)
    if municipio:
        partes.append(municipio)
    return ":".join(partes)


def item_valido(item):
    """Item só entra no pipeline com URL oficial e um rótulo mínimo verificável."""
    if not item.get("url_oficial"):
        return False
    return bool(item.get("titulo") or item.get("id_oficial"))


# ------------------------------------------------------------------- métricas
class MetricasIngestao:
    """Contadores da ingestão, medidos **independentemente da classificação**.

    É isto que o relatório precisa mostrar para separar "a fonte não respondeu"
    de "a fonte respondeu e nada era temático":

        itens_fonte          itens que a fonte entregou (antes de filtro algum)
        itens_normalizados   itens que passaram pela normalização
        itens_classificados  itens submetidos ao classificador temático
        itens_relevantes     itens classificados como relevantes ('forte')
        itens_descartados    itens sem sinal temático (não é erro de ingestão)
        itens_revisao        itens marcados para revisão ('revisar')
        duplicados           itens repetidos na mesma execução (dedup intra-run)
        falhas_parse         itens/páginas que o parser não conseguiu interpretar
    """

    CAMPOS = ("itens_fonte", "itens_normalizados", "itens_classificados", "itens_relevantes",
              "itens_descartados", "itens_revisao", "duplicados", "falhas_parse")

    def __init__(self, **valores):
        for campo in self.CAMPOS:
            setattr(self, campo, int(valores.get(campo) or 0))

    def somar(self, **valores):
        for campo, valor in valores.items():
            if campo in self.CAMPOS:
                setattr(self, campo, getattr(self, campo) + int(valor or 0))
        return self

    def para_dict(self):
        dados = {campo: getattr(self, campo) for campo in self.CAMPOS}
        dados["itens_invalidos"] = self.itens_fonte - self.itens_normalizados
        return dados

    def __repr__(self):  # pragma: no cover - representação de depuração
        return f"MetricasIngestao({self.para_dict()})"


# --------------------------------------------------------------- fonte/contexto
class ContextoDiario:
    """Contexto de execução de uma fonte de Diário Oficial.

    Reaproveita o cliente HTTP do projeto (timeout, retry, cache, telemetria e
    orçamento global) — nenhuma pilha de rede paralela.
    """

    def __init__(self, source_id, timeout_s=180, orcamento=None, dry_run=False,
                 logger=print, timeout_http=25, retries=3, dias=1, ua=None):
        self.source_id = source_id
        self.timeout_s = max(10, int(timeout_s))
        self.t0 = datetime.now(BRT)
        self.orcamento = orcamento
        self.dry_run = dry_run
        self.log = logger
        self.dias = max(1, int(dias))
        self.cliente = Cliente(timeout=timeout_http, retries=retries, orcamento=orcamento,
                               **({"ua": ua} if ua else {}), logger=logger)

    def expirado(self, folga=0.0):
        decorrido = (datetime.now(BRT) - self.t0).total_seconds()
        if decorrido >= (self.timeout_s - folga):
            return True
        if self.orcamento is not None:
            try:
                return self.orcamento.expirado()
            except Exception:  # noqa: BLE001 — orçamento só sinaliza
                return True
        return False

    def restante(self):
        return max(0.0, self.timeout_s - (datetime.now(BRT) - self.t0).total_seconds())

    def checar(self, folga=0.0):
        if self.expirado(folga):
            raise TimeoutError(f"tempo da fonte '{self.source_id}' esgotado "
                               f"({self.timeout_s}s)")


class ResultadoColeta:
    """Resultado bruto de uma fonte de Diário Oficial (ainda sem classificação).

    Campos de saúde/layout (FASE 12):
      · `layout_changed=True`  → a página respondeu 200, tinha conteúdo
        substancial e o parser deixou de reconhecer a estrutura que reconhece
        normalmente. Nunca é reportado como "nenhuma publicação nova".
      · `zero_publicacao_confirmado=True` → zero itens *com* estrutura
        reconhecida (ausência legítima, ex.: edição não publicada naquele dia).
      · `falhas_parse`         → itens/páginas que o parser não interpretou.
    """

    def __init__(self, source_id, nome):
        self.source_id = source_id
        self.nome = nome
        self.itens = []                    # itens brutos (não classificados)
        self.metricas = MetricasIngestao()
        self.tentativa_em = ts_iso()
        self.duracao = 0.0
        self.canais_ok = []
        self.canais_falhos = []
        self.canais_obrigatorios_falhos = []
        self.erros = []
        self.avisos = []
        self.endpoints = []
        self.layout_changed = None         # None = não aplicável a esta fonte
        self.layout_evidencia = None
        self.zero_publicacao_confirmado = False
        self.zero_evidencia = None
        self.paginacao_detectada = False
        self.truncado = False
        self.modo_ingestao = None          # 'xml' | 'integral' | 'integral+complementar' | 'fallback'
        self.fallback_usado = False
        self.verificacao_complementar = False
        self.cobertura_integral = None     # bool | None
        self.estrutura_fonte = None        # 'xml' | 'json' | 'html' | 'pdf' | 'api'
        self.arquivos_fonte = {}           # nome → conteúdo (bytes/str) para o raw storage
        self.edicoes = []                  # [{data, secao, itens, layout_ok, paginacao}]
        self.ultima_publicacao = None      # data da publicação mais recente detectada
        self.ultima_execucao_ok = None
        self.http = {}

    # ------------------------------------------------------------------ status
    @property
    def status(self):
        """ok · parcial · falha — com quebra de parser tratada como problema real."""
        if not self.canais_ok:
            return "falha"
        if self.layout_changed:
            return "parcial" if self.itens else "falha"
        if self.canais_obrigatorios_falhos or self.truncado:
            return "parcial"
        if self.erros:
            return "parcial"
        return "ok"

    @property
    def status_registry(self):
        """Status no vocabulário do registry de cobertura (FASE 4/11)."""
        if self.status == "falha":
            return "falha"
        if self.status == "parcial":
            return "parcial"
        if self.cobertura_integral is False:
            return "parcial"   # coletou por fallback: funciona, com cobertura reduzida
        return "funcionando"

    def erro_resumo(self):
        return "; ".join((self.erros or self.avisos)[:4]) or None

    def para_saude(self, novidades=0, itens_relevantes=0, itens_descartados=0,
                   itens_revisao=0):
        """Formato de saúde consumido por update_sources/painel (compatível com o
        `ResultadoFonte.como_dict()` já publicado — campos a mais, nenhum a menos)."""
        h = self.metricas.para_dict()
        return {
            "nome": self.nome,
            "status": self.status,
            "ultima_tentativa": self.tentativa_em,
            "ultima_execucao_ok": self.ultima_execucao_ok,
            "itens_consultados": h["itens_fonte"],
            "itens_relevantes": itens_relevantes or h["itens_relevantes"],
            "itens_descartados": itens_descartados or h["itens_descartados"],
            "itens_duplicados": h["duplicados"],
            "revisao_pendente": itens_revisao or h["itens_revisao"],
            "novidades": novidades,
            "erros": len(self.erros),
            "duracao_segundos": round(self.duracao, 1),
            "endpoints": self.endpoints,
            "canais_detalhe": self.edicoes,
            "canais_ok": self.canais_ok,
            "canais_falhos": self.canais_falhos,
            "canais_falhos_obrigatorios": self.canais_obrigatorios_falhos,
            "canais_opcionais_falhos": [c for c in self.canais_falhos
                                        if c not in self.canais_obrigatorios_falhos],
            "erro_detalhe": self.erro_resumo(),
            # --- campos novos da camada de Diários (ingestão x classificação) ---
            "diarios": {
                "modo_ingestao": self.modo_ingestao,
                "cobertura_integral": self.cobertura_integral,
                "fallback_usado": self.fallback_usado,
                "verificacao_complementar": self.verificacao_complementar,
                "estrutura_fonte": self.estrutura_fonte,
                "layout_changed": self.layout_changed,
                "layout_evidencia": self.layout_evidencia,
                "zero_publicacao_confirmado": self.zero_publicacao_confirmado,
                "paginacao_detectada": self.paginacao_detectada,
                "truncado": self.truncado,
                "ultima_publicacao": self.ultima_publicacao,
                "metricas_ingestao": h,
                "edicoes": self.edicoes,
                "avisos": self.avisos,
            },
        }


class FonteDiario:
    """Conector de um Diário Oficial (federal, estadual, municipal ou judiciário).

    Subclasses implementam `coletar(ctx, resultado)` e devolvem itens **brutos**
    (`resultado.itens`), sem qualquer filtro temático: a classificação é etapa
    posterior. Fonte que não responde levanta `FonteIndisponivel` ou registra o
    erro em `resultado.erros` — nunca devolve dado estimado.
    """

    source_id = "?"
    nome = "?"
    nivel = None
    uf = None
    municipio = None
    poder = None
    url = None
    tipo_acesso = "nao_definido"
    formato = "nao_definido"
    collector = None
    adaptador_familia = "nao_aplicavel"
    obrigatorio = True
    ativo = True
    modo_padrao = None
    # Estrutura mínima que a página/arquivo precisa conter para que "zero itens"
    # seja lido como ausência legítima de publicação, e não como layout quebrado.
    marcadores_estruturais = ()
    tamanho_minimo_para_layout = 4000

    def __init__(self, logger=print):
        self.log = logger

    # ------------------------------------------------------------------ coleta
    def coletar(self, ctx, resultado):  # pragma: no cover - contrato
        raise NotImplementedError(f"{type(self).__name__}.coletar() não implementado")

    # ------------------------------------------------------------------ helpers
    def registrar_arquivo_fonte(self, resultado, nome, conteudo):
        """Guarda o arquivo-fonte (para o raw storage) sem inflar o dataset público."""
        if nome and conteudo is not None:
            resultado.arquivos_fonte[nome] = conteudo

    def avaliar_layout(self, resultado, html_ou_texto, marcadores, itens, rotulo):
        """Detecta quebra de layout (FASE 12) sem confundir com "sem publicação".

        Regra: resposta substancial + ausência dos marcadores estruturais +
        nenhum item reconhecido = parser não reconheceu o layout. Nunca esconder.
        """
        marcadores = self.marcadores_estruturais if marcadores is None else marcadores
        tamanho = len(html_ou_texto or "")
        if itens:
            return False
        if tamanho < self.tamanho_minimo_para_layout:
            resultado.avisos.append(
                f"{rotulo}: resposta curta ({tamanho} bytes) sem itens — "
                f"não é tratada como layout quebrado, mas também não é confirmada")
            return None
        faltando = [m for m in (marcadores or []) if m and not re.search(m, html_ou_texto, re.I)]
        if marcadores and not faltando:
            resultado.zero_publicacao_confirmado = True
            resultado.zero_evidencia = (f"{rotulo}: estrutura oficial reconhecida "
                                        f"({tamanho} bytes) e zero itens na edição")
            return False
        resultado.layout_changed = True
        resultado.layout_evidencia = (
            f"{rotulo}: página respondeu com {tamanho} bytes, mas o parser não "
            f"reconheceu a estrutura esperada"
            + (f" (marcadores ausentes: {', '.join(faltando[:3])})" if faltando else ""))
        return True


# ------------------------------------------------------------- persistência local
def carregar_json(caminho, padrao=None):
    import json
    if not caminho or not os.path.exists(caminho):
        return padrao
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def salvar_json(caminho, obj):
    """Grava JSON com escrita atômica (nunca deixa arquivo pela metade)."""
    import json
    import tempfile
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=os.path.dirname(caminho), prefix=".tmp_", suffix=".json")
    os.close(fd)
    try:
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.chmod(temp, 0o644)   # o site publica estes arquivos (Vercel/docs)
        os.replace(temp, caminho)
    except Exception:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    return caminho


def dias_uteis_janela(dias=1, hoje=None):
    """Lista de datas (YYYY-MM-DD) a tentar, do mais recente para o mais antigo.

    Não presume calendário oficial: apenas reduz tentativas de fim de semana
    (edições ordinárias não são publicadas nesses dias), sempre com registro do
    que foi tentado. Se o dia seguinte não tiver edição, o resultado é
    explicitamente `zero_publicacao_confirmado`.
    """
    hoje = hoje or agora_brt().date()
    datas = []
    cursor = hoje
    limite = max(1, int(dias)) * 3 + 4  # margem para cobrir fins de semana
    while len(datas) < max(1, int(dias)) and limite > 0:
        datas.append(cursor.isoformat())
        cursor -= timedelta(days=1)
        limite -= 1
    return datas


def data_brt(valor):
    """DD-MM-AAAA (formato exigido pelas URLs oficiais do DOU)."""
    if isinstance(valor, str):
        return datetime.strptime(valor, "%Y-%m-%d").strftime("%d-%m-%Y")
    return valor.strftime("%d-%m-%Y")
