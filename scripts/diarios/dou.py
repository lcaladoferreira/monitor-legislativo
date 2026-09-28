#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarios/dou.py — ingestão integral do Diário Oficial da União (FASE 1).

Ordem de prioridade dos caminhos oficiais:

  1. **XML estruturado do INLABS** (Imprensa Nacional) — caminho mais rico:
     título, texto integral, tipo de ato, órgão, hierarquia, edição, página,
     identificador oficial e arquivo-fonte. O portal exige credencial própria
     para download automatizado; quando ela não está configurada, o coletor lê
     pacotes locais (`MONITOR_DOU_XML_DIR`) e, sem isso, registra
     `nao_configurado` — nunca declara cobertura que não teve.
  2. **Edição integral pela página oficial de leitura do jornal**
     (`https://www.in.gov.br/leiturajornal`), que expõe a edição inteira em JSON
     embutido na própria página (e, na falta dele, em HTML estruturado). Aqui
     não há busca temática: são coletados **todos** os atos da edição, seção por
     seção, e a classificação acontece depois.
  3. **Busca temática no in.gov.br** (`scripts/sources/dou.py`) — o coletor
     histórico continua existindo como redundância e verificação complementar,
     acionado quando a ingestão integral está indisponível ou truncada.

Nada é inventado: campo que a fonte oficial não fornece fica `None`; página que
responde 200 com conteúdo substancial e sem a estrutura reconhecida é marcada
como `layout_changed` (nunca como "não houve publicação").
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

from .base import (FonteDiario, ResultadoColeta, data_brt, dias_uteis_janela,
                   limpar_texto, ts_iso)

try:  # normalizador oficial de datas (usado pelo projeto inteiro)
    from sources.base import data_iso
except ImportError:
    from scripts.sources.base import data_iso

try:  # coletor histórico (fallback) — mesma base HTTP/orçamento do projeto
    from sources.base import ContextoFonte, FonteIndisponivel, ResultadoFonte
except ImportError:
    from scripts.sources.base import ContextoFonte, FonteIndisponivel, ResultadoFonte

# --------------------------------------------------------------------- URLs oficiais
LEITURA_JORNAL = "https://www.in.gov.br/leiturajornal"
BASE_DOU = "https://www.in.gov.br"
INLABS = "https://inlabs.in.gov.br"
SECOES = ("do1", "do2", "do3")
SECOES_NOMES = {"do1": "Seção 1", "do2": "Seção 2", "do3": "Seção 3",
                "doe": "Edição Extra", "do1e": "Seção 1 — Edição Extra",
                "do2e": "Seção 2 — Edição Extra", "do3e": "Seção 3 — Edição Extra"}
PUBNAME_PARA_SECAO = {"do1": "Seção 1", "do2": "Seção 2", "do3": "Seção 3",
                      "do1e": "Seção 1", "do2e": "Seção 2", "do3e": "Seção 3"}

# Texto integral preservado; o limite é apenas de segurança (uma publicação do DOU
# não chega a esse tamanho e, se chegar, o item continua íntegro no raw storage).
LIMITE_TEXTO_INTEGRAL = 2_000_000

# Estrutura que a página de leitura do jornal sempre apresenta (independe de haver
# ato na edição). É o que permite distinguir "edição sem publicações" de "layout
# mudou e o parser deixou de reconhecer a página".
MARCADORES_LEITURA = (
    r"Selecionar\s+Organiza[çc][ãa]o\s+Principal",
    r"Selecionar\s+Tipo\s+do\s+Ato",
    r"leiturajornal|Leitura\s+Jornal|VISUALIZAR\s+EM\s+LISTA|VISUALIZAR\s+EM\s+SUM[ÁA]RIO",
)
RE_SCRIPT_JSON = re.compile(
    r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', re.I | re.S)
RE_EDICAO_PAGINA = re.compile(
    r"Edi[çc][ãa]o\s+N[ºo°]?\s*([\d.]+)\s*de\s*(\d{2}/\d{2}/\d{4})\s*-\s*P[áa]g\.?\s*([\d\-\s]+)",
    re.I)
RE_EDICAO_EXTRA_LINK = re.compile(
    r'<a[^>]+href="([^"]*leiturajornal[^"]*)"[^>]*>\s*(EDI[ÇC][ÃA]O\s+EXTRA|EDI[ÇC][ÃA]O\s+ESPECIAL|SUPLEMENTO)',
    re.I | re.S)
RE_PAGINACAO = re.compile(r"b_start:int|Carregar\s+mais|pagination|currentPage\s*[:=]\s*2", re.I)


def normalizar_secao(pub_name):
    """'DO1'/'do1' → 'Seção 1'; valores desconhecidos voltam como vieram (sem invenção)."""
    if not pub_name:
        return None
    bruto = str(pub_name).strip()
    chave = unicodedata.normalize("NFKD", bruto).encode("ascii", "ignore").decode().lower()
    chave = chave.replace(" ", "")
    return PUBNAME_PARA_SECAO.get(chave, bruto)


def url_leitura_jornal(data_publicacao, secao):
    """URL oficial da edição integral de uma seção em uma data (formato DD-MM-AAAA)."""
    return f"{LEITURA_JORNAL}?data={data_brt(data_publicacao)}&secao={secao}"


def url_publicacao(url_title):
    """URL oficial do ato a partir do slug oficial (`urlTitle`)."""
    if not url_title:
        return None
    if str(url_title).startswith("http"):
        return str(url_title).split("#")[0]
    return f"{BASE_DOU}/web/dou/-/{str(url_title).lstrip('/')}"


# =========================================================== parsers (estruturado)
def _listar_itens_json(dados, profundidade=0):
    """Encontra, em qualquer nível do JSON embutido, a lista de atos da edição.

    O portal não garante o nome do envelope (`jsonArray`, `items`, `results`…) e
    a página de leitura usa um portlet próprio. Em vez de fixar um nome (e quebrar
    na próxima mudança de layout), procuramos listas cujos elementos têm a cara de
    um ato do DOU: `urlTitle`/`title` + algum campo oficial de data/órgão.
    """
    if profundidade > 6:
        return []
    if isinstance(dados, list):
        if dados and all(isinstance(i, dict) for i in dados):
            chaves = set().union(*[set(i) for i in dados[:5]])
            if {"urlTitle"} & chaves or {"title"} & chaves and (
                    {"pubDate", "pubName", "hierarchyStr", "artType"} & chaves):
                return dados
        for item in dados:
            achado = _listar_itens_json(item, profundidade + 1)
            if achado:
                return achado
        return []
    if isinstance(dados, dict):
        for chave in ("jsonArray", "items", "itens", "results", "resultado", "content",
                      "data", "dados"):
            if chave in dados:
                achado = _listar_itens_json(dados[chave], profundidade + 1)
                if achado:
                    return achado
        for valor in dados.values():
            achado = _listar_itens_json(valor, profundidade + 1)
            if achado:
                return achado
    return []


def _total_declarado(dados):
    """Total de resultados que o próprio portal declara (`itemsTotal`/`total`)."""
    if not isinstance(dados, dict):
        return None
    for chave in ("itemsTotal", "total", "totalItens", "count", "totalCount"):
        valor = dados.get(chave)
        if isinstance(valor, (int, float)):
            return int(valor)
    return None


def parse_dou_json_embutido(html):
    """Extrai os atos da edição do JSON embutido na página oficial.

    Devolve (itens, total_declarado). Campos ausentes ficam ausentes — nada é
    deduzido do layout.
    """
    if not html:
        return [], None
    itens, total = [], None
    for bloco in RE_SCRIPT_JSON.findall(html):
        bruto = limpar_entidades(bruto_script(bloco))
        if not bruto:
            continue
        try:
            dados = json.loads(bruto)
        except ValueError:
            continue
        lista = _listar_itens_json(dados)
        if not lista:
            continue
        total = total or _total_declarado(dados)
        for ato in lista:
            if not isinstance(ato, dict):
                continue
            item = item_de_ato_json(ato)
            if item:
                itens.append(item)
        if itens:
            break
    return itens, total


def bruto_script(bloco):
    return bloco.strip()


def limpar_entidades(texto):
    """Achata entidades HTML eventualmente usadas no JSON embutido."""
    if not texto:
        return ""
    return (texto.replace("&quot;", '"').replace("&#39;", "'").replace("&amp;", "&")
                 .replace("&lt;", "<").replace("&gt;", ">"))


def item_de_ato_json(ato):
    """Um ato do JSON oficial → item bruto (só campos presentes no payload)."""
    titulo = limpar_texto(ato.get("title") or ato.get("titulo") or ato.get("name") or "", 500)
    url_title = (ato.get("urlTitle") or ato.get("url") or "").strip()
    url = url_publicacao(url_title)
    if not titulo and not url:
        return None
    if not url:
        return None  # sem URL oficial o item não entra: nada é inventado
    hierarquia = limpar_texto(ato.get("hierarchyStr") or ato.get("hierarchyList")
                              or ato.get("hierarchy") or "", 400)
    conteudo = limpar_texto(ato.get("content") or ato.get("abstract") or
                            ato.get("resumo") or "", LIMITE_TEXTO_INTEGRAL) or None
    paginas = ato.get("numberPage") or ato.get("numberPageEnd") or None
    edicao = ato.get("editionNumber") or ato.get("edition") or None
    niveis = ([limpar_texto(p, 200) for p in re.split(r"\s*(?:>|/)\s*", hierarquia) if p.strip()]
              if hierarquia else [])
    return {
        "id_publicacao": str(ato.get("classPK") or ato.get("id") or "") or None,
        "id_oficial": (f"dou:{ato.get('classPK')}" if ato.get("classPK") else None),
        "titulo": titulo or None,
        "texto": conteudo,
        "data": data_iso(ato.get("pubDate") or ato.get("date")
                         or ato.get("dataPublicacao")),
        "secao": normalizar_secao(ato.get("pubName") or ato.get("section")),
        "edicao": str(edicao) if edicao else None,
        "edicao_extraordinaria": (bool(ato.get("extraEdition"))
                                  if isinstance(ato.get("extraEdition"), bool) else None),
        "tipo_ato": limpar_texto(ato.get("artType") or ato.get("type") or "", 120) or None,
        # `orgao` é o órgão emissor: campo próprio quando existe; senão, o
        # primeiro nível da hierarquia oficial — o mesmo dado, sem estimativa.
        "orgao": (limpar_texto(ato.get("artCategory") or ato.get("orgao") or "", 200)
                  or (niveis[0] if niveis else None)),
        "hierarquia": niveis or None,
        "pagina": str(paginas) if paginas else None,
        "url_oficial": url,
        "arquivo_fonte": "in.gov.br/leiturajornal (JSON embutido)",
        "coletado_em": ts_iso(),
        "modo_ingestao": "integral",
        "origem": "DOU — leitura do jornal (edição integral)",
    }


# --------------------------------------------------------------- parser HTML
def parse_dou_html_edicao(html, secao=None):
    """Fallback estruturado: lê a edição integral direto do HTML da listagem.

    Cada ato tem âncora `/web/dou/-/<slug>`; a hierarquia (Seção → órgão →
    unidade → edição/página) aparece no bloco anterior. Onde o HTML não informa,
    o campo fica `None` — o parser não completa por conta própria.
    """
    if not html:
        return []
    itens, vistos = [], set()
    for m in re.finditer(r'<a\s[^>]*href="(/web/dou/-/[^"#?]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
        href, interno = m.group(1), m.group(2)
        titulo = limpar_texto(interno, 500)
        if not titulo or href in vistos:
            continue
        vistos.add(href)
        contexto = html[max(0, m.start() - 3000):m.start()]
        # O breadcrumb do ato começa depois do ato anterior: cortar no último link
        # evita herdar a hierarquia do item de cima.
        corte = contexto.rfind("/web/dou/-/")
        if corte > 0:
            contexto = contexto[corte:]
        edicao, pagina, data = None, None, None
        achado = None
        for achado in RE_EDICAO_PAGINA.finditer(contexto):
            pass  # o último (mais próximo do ato) é o do ato
        if achado:
            edicao = achado.group(1).replace(".", "")
            data = _data_de_br(achado.group(2))
            pagina = achado.group(3).strip()
        hierarquia = _hierarquia_do_bloco(contexto)
        if secao:
            nome_secao = normalizar_secao(secao)
        else:
            nome_secao = hierarquia[0] if hierarquia and hierarquia[0].lower().startswith("seç") else None
        itens.append({
            "id_publicacao": None,
            "id_oficial": None,
            "titulo": titulo,
            "texto": None,
            "data": data,
            "secao": nome_secao,
            "edicao": edicao,
            "edicao_extraordinaria": None,
            "tipo_ato": None,   # o HTML de listagem não traz o tipo do ato com segurança
            "orgao": (hierarquia[1] if len(hierarquia) > 1 else None),
            "hierarquia": hierarquia or None,
            "pagina": pagina,
            "arquivo_fonte": "in.gov.br/leiturajornal (HTML)",
            "url_oficial": urllib.parse.urljoin(BASE_DOU, href.split("?")[0]),
            "coletado_em": ts_iso(),
            "modo_ingestao": "integral",
            "origem": "DOU — leitura do jornal (HTML)",
        })
    return itens


def _hierarquia_do_bloco(bloco):
    """Níveis institucionais declarados no bloco de breadcrumb (só o que está lá)."""
    niveis = []
    for m in re.finditer(r"<li[^>]*>(.*?)</li>", bloco or "", re.I | re.S):
        texto = limpar_texto(m.group(1), 200)
        texto = re.sub(r"^\s*\d+\.\s*", "", texto).strip()
        if not texto or len(texto) >= 120:
            continue
        if RE_EDICAO_PAGINA.search(texto):
            continue  # "Edição Nº … Pág. …" é a referência da edição, não hierarquia
        if texto not in niveis:
            niveis.append(texto)
    return niveis[-5:]


def _data_de_br(texto):
    """DD/MM/AAAA → YYYY-MM-DD (None se não for data válida)."""
    try:
        dia, mes, ano = texto.split("/")
        return f"{int(ano):04d}-{int(mes):02d}-{int(dia):02d}"
    except (ValueError, AttributeError):
        return None


def html_unescape(valor):
    """Desescapa entidades HTML de URLs coletadas em atributos href."""
    import html as _html
    return _html.unescape(valor or "")


RE_TEXTO_ATO = (
    # conteúdo principal da página oficial do ato (variações conhecidas do portal)
    re.compile(r'<div[^>]+(?:id="conteudo"|class="[^"]*(?:texto-dou|materia|conteudo)[^"]*")'
               r'[^>]*>(.*?)</div>\s*(?:</div>|<footer|<section)', re.S | re.I),
    re.compile(r"<article[^>]*>(.*?)</article>", re.S | re.I),
)
RE_SCRIPT_ESTILO = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
RE_TAG = re.compile(r"<[^>]+>")
RE_ESPACOS = re.compile(r"[ \t\u00a0]+")
RE_LINHAS_VAZIAS = re.compile(r"\n{3,}")


def extrair_texto_ato(html):
    """Texto integral da página oficial de um ato (None quando não há texto).

    Nunca inventa: se a página não trouxer bloco de conteúdo reconhecível, a
    função devolve `None` e o item segue com `texto` ausente (o quality gate
    marca como `degraded`/`failed`, e o painel mostra o texto pendente).
    """
    if not html:
        return None
    trecho = None
    for padrao in RE_TEXTO_ATO:
        m = padrao.search(html)
        if m and m.group(1):
            trecho = m.group(1)
            break
    if trecho is None:
        m = re.search(r"<body[^>]*>(.*?)</body>", html, re.S | re.I)
        trecho = m.group(1) if m else html
    trecho = RE_SCRIPT_ESTILO.sub(" ", trecho)
    trecho = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", trecho, flags=re.I)
    texto = html_unescape(RE_TAG.sub(" ", trecho))
    texto = texto.replace("\r", "\n")
    texto = RE_ESPACOS.sub(" ", texto)
    linhas = [linha.strip() for linha in texto.split("\n")]
    texto = "\n".join(linha for linha in linhas if linha)
    texto = RE_LINHAS_VAZIAS.sub("\n\n", texto).strip()
    if not texto:
        return None
    return texto[:LIMITE_TEXTO_INTEGRAL]


def extrair_edicoes_extras(html):
    """Links de Edição Extra/Especial/Suplemento **presentes na própria página**.

    Nada é montado por suposição: se a página não oferece o link, a edição extra
    não é consultada (e isso não é reportado como cobertura).
    """
    extras = []
    for m in re.finditer(r'<a[^>]+href="([^"]*leiturajornal[^"]*)"[^>]*>(.*?)</a>',
                         html or "", re.I | re.S):
        href, rotulo = m.group(1), limpar_texto(m.group(2), 60)
        alvo = unicodedata.normalize("NFKD", rotulo or "").encode("ascii", "ignore").decode().lower()
        if not any(chave in alvo for chave in ("edicao extra", "edicao especial", "suplemento")):
            continue
        url = urllib.parse.urljoin(BASE_DOU, html_unescape(href.strip()))
        if url not in [e[1] for e in extras]:
            extras.append((rotulo or "edição extra", url))
    return extras


def parse_dou_xml(texto_xml, arquivo_fonte=None):
    """Parser do XML estruturado do DOU (pacote do INLABS / dados abertos).

    O pacote traz um arquivo XML por seção com elementos `<article>` cujos
    atributos oficiais descrevem a publicação. O parser aceita os nomes
    documentados e variações conhecidas; **atributo ausente vira `None`**.
    """
    if not texto_xml:
        return [], None
    try:
        raiz = ET.fromstring(texto_xml.encode("utf-8", "replace")
                             if isinstance(texto_xml, str) else texto_xml)
    except ET.ParseError:
        return [], "XML inválido"
    artigos = [no for no in raiz.iter() if no.tag.split("}")[-1].lower() == "article"]
    if not artigos:
        # Alguns pacotes usam <xml><materia>…</materia></xml>
        artigos = [no for no in raiz.iter() if no.tag.split("}")[-1].lower() in ("materia", "materias")]
    itens = []
    for artigo in artigos:
        attrs = {k: (v if isinstance(v, str) else None) for k, v in artigo.attrib.items()}
        corpo = None
        for filho in list(artigo):
            if filho.tag.split("}")[-1].lower() in ("body", "texto", "conteudo"):
                corpo = "".join(filho.itertext())
                break
        url_title = attrs.get("urlTitle") or attrs.get("url_title")
        id_oficial = attrs.get("id") or attrs.get("idMateria") or attrs.get("idmateria")
        if not url_title and not attrs.get("name"):
            continue
        item = {
            "id_publicacao": attrs.get("id") or None,
            "id_oficial": f"dou:{id_oficial}" if id_oficial else None,
            "titulo": limpar_texto(attrs.get("name") or attrs.get("title") or "", 500) or None,
            "texto": (corpo or "").strip() or None,
            "data": attrs.get("pubDate") or attrs.get("pubdate") or None,
            "secao": normalizar_secao(attrs.get("pubName") or attrs.get("section")),
            "edicao": attrs.get("editionNumber") or attrs.get("edicaonumber"),
            "edicao_extraordinaria": (_bool_do_xml(attrs.get("edicaoExtra")
                                                   or attrs.get("extraEdition"))),
            "tipo_ato": limpar_texto(attrs.get("artType") or attrs.get("tipo") or "", 120) or None,
            "orgao": limpar_texto(attrs.get("artCategory") or attrs.get("orgao") or "", 200) or None,
            "hierarquia": _hierarquia_xml(attrs),
            "pagina": attrs.get("numberPage") or attrs.get("numberpage"),
            "url_oficial": url_publicacao(url_title) if url_title else None,
            "arquivo_fonte": arquivo_fonte,
            "coletado_em": ts_iso(),
            "modo_ingestao": "xml",
            "origem": "DOU — pacote XML oficial (INLABS)",
            "extras": {"artClass": attrs.get("artClass"), "sead": attrs.get("sead"),
                       "idMateria": attrs.get("idMateria") or attrs.get("idmateria")},
        }
        if item["url_oficial"]:
            itens.append(item)
    return itens, None


def _bool_do_xml(valor):
    if valor is None:
        return None
    return str(valor).strip().lower() in ("1", "true", "sim", "yes")


def _hierarquia_xml(attrs):
    niveis = [attrs.get(chave) for chave in ("artCategory", "artClass", "artSubCategory")
              if attrs.get(chave)]
    return [limpar_texto(n, 200) for n in niveis] or None


# ==================================================================== coletores
class ColetorDouXMLINLABS(FonteDiario):
    """Caminho estruturado prioritário: pacotes XML oficiais do DOU.

    Duas origens possíveis, ambas sem invenção de dado:

      · `MONITOR_DOU_XML_DIR` — diretório com pacotes já obtidos da fonte oficial
        (download manual no INLABS/dados abertos ou cópia de arquivo do órgão);
      · `MONITOR_INLABS_USUARIO` + `MONITOR_INLABS_SENHA` — download autenticado
        no portal INLABS (credenciais são segredo de ambiente, nunca do repositório).
        Sem credencial, o caminho HTTP responde `nao_configurado`.

    O status nunca é "funcionando" sem arquivo lido e item extraído.
    """

    source_id = "dou_inlabs_xml"
    nome = "DOU — pacote XML do INLABS"
    nivel = "federal"
    poder = "todos"
    url = INLABS
    tipo_acesso = "xml"
    formato = "xml"
    collector = "scripts/diarios/dou.py::ColetorDouXMLINLABS"
    modo_padrao = "xml"

    def __init__(self, logger=print, datas=None):
        super().__init__(logger=logger)
        self.dir_local = os.environ.get("MONITOR_DOU_XML_DIR") or None
        self.usuario = os.environ.get("MONITOR_INLABS_USUARIO") or None
        self.senha = os.environ.get("MONITOR_INLABS_SENHA") or None
        # Janela explícita: permite importar um pacote oficial de data específica
        # (backfill) sem confundir a data do arquivo com a data de hoje.
        self.datas = list(datas) if datas else None

    def janela(self, ctx):
        if self.datas:
            return list(self.datas)
        env = os.environ.get("MONITOR_DIARIOS_DATAS")
        if env:
            return [d.strip() for d in env.split(",") if d.strip()]
        return dias_uteis_janela(ctx.dias)

    # ------------------------------------------------------------------ origem
    def configurado(self):
        return bool(self.dir_local or (self.usuario and self.senha))

    def pacotes_locais(self, datas):
        """Pacotes XML locais que cobrem as datas pedidas (nome do arquivo é a pista)."""
        if not self.dir_local or not os.path.isdir(self.dir_local):
            return []
        arquivos = []
        for nome in sorted(os.listdir(self.dir_local)):
            if not nome.lower().endswith((".zip", ".xml")):
                continue
            if datas and not any(d.replace("-", "") in nome or d in nome for d in datas):
                continue
            arquivos.append(os.path.join(self.dir_local, nome))
        return arquivos

    # ------------------------------------------------------------------ coleta
    def coletar(self, ctx, resultado):
        datas = self.janela(ctx)
        resultado.estrutura_fonte = "xml"
        if not self.configurado():
            resultado.erros.append(
                "INLABS XML não configurado: defina MONITOR_DOU_XML_DIR (pacotes "
                "oficiais locais) ou MONITOR_INLABS_USUARIO/MONITOR_INLABS_SENHA "
                "(download autenticado). Nada é declarado como coberto por este caminho.")
            raise FonteIndisponivel("caminho XML do DOU não configurado")

        pacotes = self.pacotes_locais(datas)
        if not pacotes:
            resultado.erros.append(
                f"nenhum pacote XML em {self.dir_local} para as datas tentadas "
                f"({', '.join(datas[:3])})" if self.dir_local else
                "download autenticado do INLABS ainda não implementado neste ambiente")
            raise FonteIndisponivel("sem pacote XML disponível")

        for caminho in pacotes:
            ctx.checar(5)
            nome = os.path.basename(caminho)
            try:
                arquivos = self._ler_pacote(caminho)
            except (OSError, zipfile.BadZipFile) as e:
                resultado.metricas.falhas_parse += 1
                resultado.erros.append(f"{nome}: pacote ilegível ({e})")
                resultado.canais_falhos.append(nome)
                continue
            itens_pacote = 0
            for nome_interno, conteudo in arquivos.items():
                if not nome_interno.lower().endswith(".xml"):
                    continue
                itens, erro = parse_dou_xml(conteudo, nome)
                if erro:
                    resultado.metricas.falhas_parse += 1
                    resultado.erros.append(f"{nome}:{nome_interno}: {erro}")
                    continue
                if not itens:
                    resultado.metricas.falhas_parse += 1
                    resultado.avisos.append(f"{nome}:{nome_interno}: XML sem <article> reconhecível")
                    continue
                itens_pacote += len(itens)
                resultado.itens.extend(itens)
                self.registrar_arquivo_fonte(resultado, f"{nome}::{nome_interno}", conteudo)
            if itens_pacote:
                resultado.canais_ok.append(f"INLABS XML {nome}")
                resultado.metricas.itens_fonte += itens_pacote
                resultado.edicoes.append({"arquivo": nome, "itens": itens_pacote,
                                          "layout_ok": True})
            else:
                resultado.canais_falhos.append(f"INLABS XML {nome}")
        if not resultado.canais_ok:
            raise FonteIndisponivel("nenhum pacote XML pôde ser interpretado")
        resultado.modo_ingestao = "xml"
        resultado.cobertura_integral = True
        resultado.metricas.itens_fonte = len(resultado.itens)
        return resultado

    @staticmethod
    def _ler_pacote(caminho):
        arquivos = {}
        if caminho.lower().endswith(".zip"):
            with zipfile.ZipFile(caminho) as z:
                for info in z.infolist():
                    if info.is_dir():
                        continue
                    with z.open(info) as f:
                        arquivos[info.filename] = f.read().decode("utf-8", "replace")
        else:
            with open(caminho, encoding="utf-8", errors="replace") as f:
                arquivos[os.path.basename(caminho)] = f.read()
        return arquivos


class ColetorDouIntegral(FonteDiario):
    """Ingestão integral da edição do DOU pela página oficial de leitura do jornal.

    Coleta **todos** os atos das Seções 1, 2 e 3 (e das edições extra cujos links
    a própria página oferece) em uma janela de datas. Nenhum termo de busca é
    aplicado aqui: a classificação temática vem depois, em `diarios/pipeline.py`.
    """

    source_id = "dou"
    nome = "DOU — Diário Oficial da União (edição integral)"
    nivel = "federal"
    poder = "todos"
    url = LEITURA_JORNAL
    tipo_acesso = "html"
    formato = "misto"
    collector = "scripts/diarios/dou.py::ColetorDouIntegral"
    obrigatorio = True
    modo_padrao = "integral"
    marcadores_estruturais = MARCADORES_LEITURA

    def __init__(self, logger=print, secoes=SECOES, max_itens_por_edicao=None, datas=None,
                 max_textos_por_edicao=None, max_texto_bytes_por_edicao=None):
        super().__init__(logger=logger)
        self.secoes = tuple(secoes or SECOES)
        self.datas = list(datas) if datas else None
        self.max_itens_por_edicao = int(
            max_itens_por_edicao or os.environ.get("MONITOR_DOU_MAX_ITENS_EDICAO") or 2000)
        # Teto de páginas de ato abertas por edição só para capturar o texto que a
        # listagem não trouxe (0 desliga). O teto existe para não transformar a
        # ingestão integral em milhares de requisições; o que não for capturado é
        # registrado como pendente — nunca silenciado.
        self.max_textos_por_edicao = int(
            max_textos_por_edicao if max_textos_por_edicao is not None
            else (os.environ.get("MONITOR_DOU_TEXTOS_POR_EDICAO") or 25))
        # Teto de bytes de texto por data/edição: o texto integral é o que mais
        # pesa na memória do processo e no payload. Ao estourar, a captura para e
        # o que faltou entra em `textos_pendentes` (documentado, nunca inferido).
        mp = (max_texto_bytes_por_edicao if max_texto_bytes_por_edicao is not None
              else int(os.environ.get("MONITOR_DOU_TEXTO_MB_POR_EDICAO") or 12) * 1024 * 1024)
        self.max_texto_bytes_por_edicao = int(mp)

    def janela(self, ctx):
        """Datas a consultar: janela explícita (backfill) ou derivada da janela de dias."""
        return list(self.datas) if self.datas else dias_uteis_janela(ctx.dias)

    def coletar(self, ctx, resultado):
        resultado.estrutura_fonte = "html"
        resultado.modo_ingestao = "integral"
        resultado.cobertura_integral = True     # ajustado ao final conforme o que foi lido
        datas = self.janela(ctx)
        dados_consultados = 0
        for data in datas:
            if ctx.expirado(10):
                resultado.truncado = True
                resultado.avisos.append(f"orçamento da fonte esgotado antes de {data}")
                break
            itens_data = 0
            marcador_itens = len(resultado.itens)   # itens desta data (para o texto)
            for secao in self.secoes:
                ctx.checar(5)
                url = url_leitura_jornal(data, secao)
                resultado.endpoints.append(url)
                resp = ctx.cliente.get(url)
                if not resp.ok:
                    resultado.canais_falhos.append(f"{secao} {data}")
                    resultado.erros.append(f"{secao} {data}: HTTP {resp.status or resp.erro}")
                    continue
                # Respondeu 200: o canal respondeu. Zero itens não é falha de canal —
                # é edição vazia (estrutura reconhecida) ou layout quebrado, e os dois
                # casos são registrados separadamente logo abaixo.
                resultado.canais_ok.append(f"{secao} {data}")
                itens, total = parse_dou_json_embutido(resp.texto)
                estrutura = "json" if itens else "html"
                if not itens:
                    itens = parse_dou_html_edicao(resp.texto, secao)
                    estrutura = "html"
                if len(itens) > self.max_itens_por_edicao:
                    itens = itens[:self.max_itens_por_edicao]
                    resultado.truncado = True
                paginacao = bool(RE_PAGINACAO.search(resp.texto))
                if total and total > len(itens):
                    paginacao = True
                if not itens:
                    self.avaliar_layout(resultado, resp.texto, MARCADORES_LEITURA, itens,
                                        f"{secao} {data}")
                for item in itens:
                    item.setdefault("data", data)
                    item["secao"] = item.get("secao") or SECOES_NOMES.get(secao)
                    item["arquivo_fonte"] = f"{data}/{secao} ({estrutura})"
                resultado.itens.extend(itens)
                itens_data += len(itens)
                resultado.edicoes.append({
                    "data": data, "secao": SECOES_NOMES.get(secao, secao),
                    "itens": len(itens), "estrutura": estrutura,
                    "layout_ok": None if itens else (not bool(resultado.layout_changed)),
                    "paginacao_detectada": paginacao,
                    "total_declarado": total,
                })
                if paginacao:
                    resultado.paginacao_detectada = True
                resultado.metricas.itens_fonte += len(itens)
                self.registrar_arquivo_fonte(resultado, f"leiturajornal_{data}_{secao}.html",
                                             resp.texto)
            if itens_data:
                dados_consultados += 1
                if not resultado.ultima_publicacao or data > resultado.ultima_publicacao:
                    resultado.ultima_publicacao = data
            # Texto integral: a listagem nem sempre traz o conteúdo do ato. Quando
            # não traz, a página oficial do ato é aberta (com teto por edição).
            self._capturar_textos(ctx, resultado, data,
                                  itens=resultado.itens[marcador_itens:])
            # Edições extra: só as que a própria página oferece (o link é a evidência).
            self._coletar_extras(ctx, resultado, data)
        if not resultado.canais_ok and not resultado.itens:
            raise FonteIndisponivel(
                "nenhuma seção da edição respondeu: " + (resultado.erro_resumo() or "sem detalhe"))
        if resultado.paginacao_detectada:
            resultado.avisos.append(
                "a listagem da edição aparenta ser paginada: a ingestão pode ser parcial "
                "e a verificação complementar por busca temática é recomendada")
        # Integralidade só é afirmada com edição inteira lida, sem truncamento, sem
        # paginação suspeita e sem seção que não respondeu.
        resultado.cobertura_integral = bool(
            resultado.itens and not resultado.truncado
            and not resultado.paginacao_detectada and not resultado.canais_falhos)
        resultado.metricas.itens_fonte = len(resultado.itens)
        return resultado

    def _capturar_textos(self, ctx, resultado, data, itens=None):
        """Captura o texto integral dos atos da data cuja listagem não trouxe conteúdo.

        Só a página **oficial** do ato é usada; o que não puder ser lido permanece
        ausente e é contado em `textos_pendentes` (transparência sobre a cobertura
        do texto, que é o insumo do quality gate e, no futuro, do fallback visual).
        """
        if self.max_textos_por_edicao <= 0:
            return
        # `itens` são os itens lidos nesta data: a listagem oficial pode declarar
        # data de publicação diferente da data consultada, então a seleção é pela
        # origem no lote — nunca por comparação de strings de data.
        pendentes = [i for i in (itens if itens is not None else resultado.itens)
                     if not (i.get("texto") or "").strip() and i.get("url_oficial")]
        if not pendentes:
            return
        buscados = obtidos = 0
        bytes_texto = 0
        motivo_parada = None
        for item in pendentes:
            if buscados >= self.max_textos_por_edicao:
                motivo_parada = (f"teto de {self.max_textos_por_edicao} página(s) por "
                                 f"edição (MONITOR_DOU_TEXTOS_POR_EDICAO)")
                break
            if bytes_texto >= self.max_texto_bytes_por_edicao:
                motivo_parada = (f"teto de {self.max_texto_bytes_por_edicao // (1024 * 1024)}MB "
                                 f"de texto por edição (MONITOR_DOU_TEXTO_MB_POR_EDICAO)")
                break
            if ctx.expirado(3):
                motivo_parada = "orçamento da fonte esgotado durante a captura de texto"
                break
            ctx.checar(2)
            resp = ctx.cliente.get(item["url_oficial"])
            buscados += 1
            if not resp.ok:
                resultado.avisos.append(f"ato sem texto legível ({item['url_oficial']}): "
                                        f"HTTP {resp.status or resp.erro}")
                continue
            texto = extrair_texto_ato(resp.texto)
            if not texto:
                continue
            item["texto"] = texto
            item["texto_fonte"] = item["url_oficial"]
            bytes_texto += len(texto.encode("utf-8", "ignore"))
            obtidos += 1
        pendentes_restantes = len(pendentes) - obtidos
        resultado.edicoes.append({
            "data": data, "secao": "texto integral", "itens": obtidos,
            "textos_buscados": buscados, "textos_pendentes": pendentes_restantes,
            "teto_por_edicao": self.max_textos_por_edicao,
            "bytes_texto": bytes_texto,
            "teto_bytes": self.max_texto_bytes_por_edicao,
            "motivo_parada": motivo_parada,
        })
        if pendentes_restantes:
            resultado.avisos.append(
                f"{pendentes_restantes} ato(s) de {data} seguem sem texto integral na "
                f"listagem ({motivo_parada or 'conteúdo não servido pela fonte oficial'}): "
                f"o item permanece publicado com `texto` ausente — nada é inferido a "
                f"partir do título")

    def _coletar_extras(self, ctx, resultado, data):
        """Consulta as edições extra que a página da Seção 1 declarar (se declarar)."""
        url_base = url_leitura_jornal(data, "do1")
        resp = ctx.cliente.get(url_base)
        if not resp.ok:
            return
        for rotulo, url in extrair_edicoes_extras(resp.texto):
            if ctx.expirado(5):
                return
            resultado.endpoints.append(url)
            sub = ctx.cliente.get(url)
            if not sub.ok:
                resultado.avisos.append(f"edição extra '{rotulo}' ({url}) indisponível: "
                                        f"HTTP {sub.status or sub.erro}")
                continue
            itens, _total = parse_dou_json_embutido(sub.texto)
            if not itens:
                itens = parse_dou_html_edicao(sub.texto, secao=None)
            for item in itens:
                item.setdefault("data", data)
                item["edicao_extraordinaria"] = True
                item["arquivo_fonte"] = f"{data}/edição extra ({rotulo})"
            if itens:
                resultado.itens.extend(itens)
                resultado.canais_ok.append(f"edição extra {rotulo} {data}")
                resultado.edicoes.append({"data": data, "secao": rotulo, "itens": len(itens),
                                          "estrutura": "json" if itens else "html",
                                          "layout_ok": True, "edicao_extraordinaria": True,
                                          "url": url})
            else:
                self.avaliar_layout(resultado, sub.texto, MARCADORES_LEITURA, itens,
                                    f"edição extra {rotulo} {data}")


class ColetorDouBuscaTematica(FonteDiario):
    """Fallback: busca temática no in.gov.br (coletor histórico, preservado).

    Reaproveita `sources/dou.py` — os mesmos canais, termos (`DISCOVERY_TERMS`) e
    parser já publicados — e converte o resultado para o contrato de itens brutos
    da camada de Diários. Não altera nada no coletor original.
    """

    source_id = "dou_busca_tematica"
    nome = "DOU — busca temática (fallback)"
    nivel = "federal"
    poder = "todos"
    url = "https://www.in.gov.br/consulta/-/buscar/dou"
    tipo_acesso = "scraper"
    formato = "json"
    collector = "scripts/sources/dou.py::DOU"
    obrigatorio = False
    modo_padrao = "fallback"

    def __init__(self, logger=print, dias=None):
        super().__init__(logger=logger)
        self.dias = dias

    def coletar(self, ctx, resultado):
        resultado.estrutura_fonte = "json"
        resultado.modo_ingestao = "fallback"
        resultado.cobertura_integral = False
        try:
            from sources.dou import DOU
        except ImportError:
            from scripts.sources.dou import DOU
        fonte = DOU(logger=self.log)
        if self.dias:
            for canal in fonte.canais:
                canal.dias = self.dias
        ctx_legado = ContextoFonte(fonte.orgao, timeout_s=int(ctx.restante()), logger=self.log)
        ctx_legado.cliente = ctx.cliente  # reaproveita cliente/telemetria/orçamento
        res = ResultadoFonte(fonte.orgao, fonte.nome)
        fonte.coletar(ctx_legado, res)
        resultado.canais_ok.extend(res.canais_ok)
        resultado.canais_falhos.extend(res.canais_falhos)
        resultado.erros.extend(res.erros)
        resultado.endpoints.extend(res.endpoints)
        resultado.metricas.itens_fonte = res.itens_consultados
        for item in res.itens:
            resultado.itens.append({
                "id_publicacao": item.get("id_dou"),
                "id_oficial": (f"dou:{item['id_dou']}" if item.get("id_dou") else None),
                "titulo": item.get("titulo"),
                "texto": item.get("descricao"),
                "data": item.get("data"),
                "secao": item.get("secao") or None,
                "edicao": item.get("edicao"),
                "edicao_extraordinaria": None,
                "tipo_ato": item.get("tipo_ato"),
                "orgao": item.get("hierarquia") or None,
                "hierarquia": ([item["hierarquia"]] if item.get("hierarquia") else None),
                "url_oficial": item.get("url_oficial"),
                "arquivo_fonte": "in.gov.br/consulta (busca temática)",
                "coletado_em": ts_iso(),
                "modo_ingestao": "fallback",
                "origem": "DOU — busca temática (fallback)",
                "extras": {"canais": item.get("canais") or [],
                           "relevancia_origem": item.get("relevancia")},
            })
        if resultado.itens and not resultado.ultima_publicacao:
            resultado.ultima_publicacao = max((i.get("data") or "" for i in resultado.itens),
                                              default=None) or None
        if not res.itens and not resultado.canais_ok:
            raise FonteIndisponivel(
                "busca temática sem resposta: " + (res.erro_resumo() or "sem detalhe"))
        return resultado


class ColetorDiarioDou(ColetorDouIntegral):
    """Fonte `dou` do registry: integral primeiro, fallback temático depois.

    Estratégia (FASE 1 e 3):

      1. tenta o pacote XML oficial (INLABS) quando configurado;
      2. tenta a edição integral (`leiturajornal`) — caminho padrão;
      3. se a integral estiver indisponível, truncada, paginada ou com layout
         quebrado, roda a busca temática como **verificação complementar**;
      4. registra sempre em que modo coletou (`modo_ingestao`) e se a cobertura
         integral foi obtida (`cobertura_integral`) — nada é escondido.

    Leitura de saúde (documentada em docs/architecture-diarios.md):

      · `funcionando` no registry só com a edição integral lida;
      · falha de endpoint da integral com busca temática verificada → o painel de
        cobertura mostra `parcial` + `cobertura_integral=false` (degradação
        visível), sem transformar indisponibilidade de endpoint em erro de parser;
      · **quebra de layout** (`layout_changed`) rebaixa o status para `parcial`,
        aparece em `canais_falhos` e reprova o gate de saúde da coleta — quebra de
        parser nunca é mascarada como "não houve publicação";
      · nenhum caminho respondeu → `FonteIndisponivel` (status falha).
    """

    def __init__(self, logger=print, secoes=SECOES, xml=None, busca=None,
                 usar_xml=True, max_itens_por_edicao=None):
        super().__init__(logger=logger, secoes=secoes, max_itens_por_edicao=max_itens_por_edicao)
        self.xml = xml if xml is not None else ColetorDouXMLINLABS(logger=logger)
        self.busca = busca if busca is not None else ColetorDouBuscaTematica(logger=logger)
        self.usar_xml = usar_xml and os.environ.get("MONITOR_DOU_XML", "1") != "0"
        self.usar_fallback = os.environ.get("MONITOR_DOU_FALLBACK", "1") != "0"

    # ------------------------------------------------------------------ coleta
    def coletar(self, ctx, resultado):
        caminhos_usados = []

        # 1) XML estruturado oficial (prioritário quando configurado).
        if self.usar_xml and getattr(self.xml, "configurado", lambda: False)():
            sub = ResultadoColeta(self.xml.source_id, self.xml.nome)
            try:
                self.xml.coletar(ctx, sub)
                _absorver_resultado(resultado, sub)
                if sub.itens:
                    caminhos_usados.append("xml")
                    resultado.estrutura_fonte = "xml"
                    resultado.cobertura_integral = True
            except FonteIndisponivel as e:
                resultado.avisos.append(f"caminho XML oficial indisponível ({e}); "
                                        f"seguindo para a edição integral")
            except Exception as e:  # noqa: BLE001 — um caminho não derruba a fonte
                resultado.avisos.append(f"caminho XML falhou ({type(e).__name__}: {e})")

        # 2) Edição integral (padrão).
        integral = ResultadoColeta(self.source_id, self.nome)
        try:
            super().coletar(ctx, integral)
            _absorver_resultado(resultado, integral)
            if integral.itens:
                caminhos_usados.append("integral")
            if integral.cobertura_integral:
                resultado.cobertura_integral = True
            elif resultado.cobertura_integral is None:
                resultado.cobertura_integral = False
        except FonteIndisponivel as e:
            resultado.cobertura_integral = False
            resultado.avisos.append(f"edição integral indisponível ({e})")
        except Exception as e:  # noqa: BLE001
            resultado.cobertura_integral = False
            resultado.avisos.append(f"edição integral falhou ({type(e).__name__}: {e})")

        # A integral só é considerada completa sem paginação/truncamento/zero duvidoso.
        integral_completa = bool(
            resultado.cobertura_integral and not resultado.paginacao_detectada
            and not resultado.truncado and not resultado.layout_changed)

        # 3) Busca temática: complemento quando a integral não veio completa.
        precisa_complemento = (
            not integral_completa
            or not resultado.itens
            or bool(resultado.layout_changed)
            or resultado.paginacao_detectada
            or resultado.truncado
        )
        if precisa_complemento and self.usar_fallback:
            motivo = ("verificação complementar da edição integral"
                      if resultado.itens else "ingestão integral indisponível")
            self.log(f"    · busca temática acionada ({motivo})")
            complemento = ResultadoColeta(self.busca.source_id, self.busca.nome)
            try:
                self.busca.coletar(ctx, complemento)
                _absorver_resultado(resultado, complemento)
                if complemento.itens:
                    caminhos_usados.append("busca_tematica")
                    resultado.fallback_usado = True
                    resultado.verificacao_complementar = bool(resultado.itens)
            except FonteIndisponivel as e:
                if not resultado.itens:
                    resultado.canais_falhos.append("busca temática (fallback)")
                    resultado.erros.append(f"busca temática indisponível: {e}")
                else:
                    resultado.avisos.append(f"busca complementar indisponível ({e})")
            except Exception as e:  # noqa: BLE001
                if not resultado.itens:
                    resultado.canais_falhos.append("busca temática (fallback)")
                    resultado.erros.append(f"busca temática falhou: {type(e).__name__}: {e}")
                else:
                    resultado.avisos.append(f"busca complementar falhou ({type(e).__name__}: {e})")

        # Modo de ingestão (auditoria do caminho realmente usado).
        if "xml" in caminhos_usados:
            resultado.modo_ingestao = "xml"
        elif "integral" in caminhos_usados and resultado.fallback_usado:
            resultado.modo_ingestao = "integral+complementar"
        elif "integral" in caminhos_usados:
            resultado.modo_ingestao = "integral"
        elif "busca_tematica" in caminhos_usados:
            resultado.modo_ingestao = "fallback"
        else:
            resultado.modo_ingestao = None
        if not resultado.canais_ok:
            raise FonteIndisponivel(
                "nem a ingestão integral nem a busca temática responderam: "
                + (resultado.erro_resumo() or "sem detalhe"))

        # Quebra de parser é problema real: fica visível no canal e no gate de saúde.
        if resultado.layout_changed:
            resultado.canais_falhos.append("edição integral: layout não reconhecido")
            if resultado.layout_evidencia:
                resultado.erros.append(resultado.layout_evidencia)
        elif not resultado.itens and resultado.zero_publicacao_confirmado:
            resultado.avisos.append(resultado.zero_evidencia or
                                    "edição sem publicações reconhecidas (estrutura OK)")
        return resultado


def _absorver_resultado(destino, origem):
    """Soma itens e telemetria de um sub-resultado ao resultado principal.

    Deduplica na hora (mesma chave/URL não entra duas vezes), preserva a decisão
    de layout/zero-publicação e **não** copia falhas: quem decide o que é falha
    obrigatória é o coletor composto, que conhece a hierarquia dos caminhos.
    """
    chaves = {str(i.get("chave") or i.get("id") or i.get("url_oficial") or "")
              for i in destino.itens}
    for item in origem.itens:
        chave = str(item.get("chave") or item.get("id") or item.get("url_oficial") or "")
        if chave and chave in chaves:
            destino.metricas.duplicados += 1
            continue
        chaves.add(chave)
        destino.itens.append(item)
    destino.metricas.itens_fonte += origem.metricas.itens_fonte
    destino.canais_ok.extend(origem.canais_ok)
    destino.endpoints.extend(origem.endpoints)
    destino.edicoes.extend(origem.edicoes)
    destino.avisos.extend(origem.avisos)
    destino.paginacao_detectada = destino.paginacao_detectada or origem.paginacao_detectada
    destino.truncado = destino.truncado or origem.truncado
    if origem.layout_changed:
        destino.layout_changed = True
        destino.layout_evidencia = origem.layout_evidencia or destino.layout_evidencia
    if origem.zero_publicacao_confirmado:
        destino.zero_publicacao_confirmado = True
        destino.zero_evidencia = origem.zero_evidencia or destino.zero_evidencia
    if origem.ultima_publicacao and (not destino.ultima_publicacao
                                     or origem.ultima_publicacao > destino.ultima_publicacao):
        destino.ultima_publicacao = origem.ultima_publicacao
    destino.arquivos_fonte.update(origem.arquivos_fonte)
    destino.metricas.falhas_parse += origem.metricas.falhas_parse
    return len(origem.itens)


def fontes_dou(logger=print):
    """Fontes do DOU como objetos (para o pipeline/registry)."""
    return {
        "dou": ColetorDiarioDou(logger=logger),
        "dou_inlabs_xml": ColetorDouXMLINLABS(logger=logger),
        "dou_busca_tematica": ColetorDouBuscaTematica(logger=logger),
    }


__all__ = ["ColetorDouIntegral", "ColetorDouXMLINLABS", "ColetorDouBuscaTematica",
           "ColetorDiarioDou", "fontes_dou", "parse_dou_json_embutido",
           "parse_dou_html_edicao", "parse_dou_xml", "extrair_edicoes_extras",
           "url_leitura_jornal", "url_publicacao", "normalizar_secao", "SECOES",
           "MARCADORES_LEITURA", "LEITURA_JORNAL", "INLABS", "ResultadoColeta"]
