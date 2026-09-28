#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_diarios.py — sonda dos Diários Oficiais (diagnóstico, não é coleta).

Serve para **confirmar antes de habilitar**: qual é o endereço oficial, o que ele
devolve, se o parser reconhece a estrutura e onde ela quebra. Nada é gravado no
dataset nem no registry — a sonda só relata.

Três usos:

    # 1. Conferir os caminhos integrais do DOU (federal) numa data
    python3 scripts/probe_diarios.py --federal --data 2026-09-25

    # 2. Conferir uma fonte já cadastrada no registry
    python3 scripts/probe_diarios.py --fonte dou

    # 3. Confirmar um candidato antes de cadastrar (ex.: Diário de um estado)
    python3 scripts/probe_diarios.py --url https://www.exemplo.gov.br/diario \
        --rotulo estadual_sp

A resposta é sempre explícita: `estrutura_detectada` só recebe um valor quando o
parser realmente achou itens; página que responde 200 sem estrutura reconhecida
aparece como `layout_nao_reconhecido` — nunca como "sem publicações".
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
sys.path.insert(0, BASE_DIR)

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36 monitor-legislativo-ia/1.0")
CABECALHOS = {"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
              "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                         "application/json;q=0.9,*/*;q=0.8")}

ESTRUTURAS = ("json_embutido", "json_oficial", "xml_oficial", "html_listagem",
              "feed_rss", "pdf", "layout_nao_reconhecido", "bloqueado", "erro")


def baixar(url, timeout=45):
    """GET simples e honesto: devolve status, content-type, bytes e erro (se houver)."""
    req = urllib.request.Request(url, headers=CABECALHOS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            corpo = resp.read()
            return {"status": getattr(resp, "status", None) or resp.getcode(),
                    "content_type": (resp.headers.get("Content-Type") or "").lower(),
                    "bytes": corpo, "erro": None}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "content_type": (e.headers.get("Content-Type") or "").lower(),
                "bytes": b"", "erro": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001 — sonda não pode morrer por rede
        return {"status": None, "content_type": "", "bytes": b"",
                "erro": f"{type(e).__name__}: {e}"}


def _texto(resposta):
    return (resposta.get("bytes") or b"").decode("utf-8", "replace")


def analisar(resposta, url="", rotulo=""):
    """Classifica a resposta com os mesmos parsers do pipeline de Diários."""
    corpo = _texto(resposta)
    status = resposta.get("status")
    ct = resposta.get("content_type") or ""
    info = {
        "rotulo": rotulo or url,
        "url": url,
        "status": status,
        "content_type": ct,
        "bytes": len(resposta.get("bytes") or b""),
        "erro": resposta.get("erro"),
        "estrutura_detectada": None,
        "itens_reconhecidos": 0,
        "layout_ok": None,
        "bloqueio": None,
        "amostra_titulos": [],
        "recomendacao_registry": {},
        "observacao": None,
    }
    if info["erro"] or not corpo:
        info["estrutura_detectada"] = "erro"
        return info
    if re.search(r"TSPD|APM_DO_NOT_TOUCH|Access Denied|403 Forbidden", corpo[:4000]):
        info["bloqueio"] = "desafio anti-bot / acesso negado"
        info["estrutura_detectada"] = "bloqueado"
        return info

    from diarios.dou import (parse_dou_html_edicao, parse_dou_json_embutido,  # noqa: PLC0415
                             parse_dou_xml)

    itens, total = parse_dou_json_embutido(corpo)
    if itens:
        info["estrutura_detectada"] = "json_embutido"
        info["itens_reconhecidos"] = len(itens)
        info["total_declarado"] = total
        info["layout_ok"] = True
        info["amostra_titulos"] = [(i.get("titulo") or "")[:80] for i in itens[:3]]
        info["recomendacao_registry"] = {"tipo_acesso": "html", "formato": "html",
                                         "observacao": ("listagem oficial com JSON embutido; "
                                                        "ingerir a edição inteira")}
        return info

    if corpo.lstrip()[:1] == "<":
        itens_xml, erro_xml = parse_dou_xml(corpo)
        if itens_xml:
            info["estrutura_detectada"] = "xml_oficial"
            info["itens_reconhecidos"] = len(itens_xml)
            info["layout_ok"] = True
            info["amostra_titulos"] = [(i.get("titulo") or "")[:80] for i in itens_xml[:3]]
            info["recomendacao_registry"] = {"tipo_acesso": "xml", "formato": "xml"}
            return info
        if erro_xml:
            info["observacao"] = erro_xml

    if corpo.lstrip()[:1] in "[{":
        try:
            dados = json.loads(corpo)
        except ValueError:
            dados = None
        if dados is not None:
            info["estrutura_detectada"] = "json_oficial"
            info["layout_ok"] = True
            info["recomendacao_registry"] = {"tipo_acesso": "api", "formato": "json",
                                             "observacao": "confirmar campos do contrato"}
            return info

    if re.search(r"<rss|<feed", corpo[:3000], re.I):
        from sources.base import parse_rss  # noqa: PLC0415
        itens_feed = parse_rss(corpo) or []
        info["estrutura_detectada"] = "feed_rss"
        info["itens_reconhecidos"] = len(itens_feed)
        info["layout_ok"] = bool(itens_feed)
        info["amostra_titulos"] = [(i.get("titulo") or "")[:80] for i in itens_feed[:3]]
        info["recomendacao_registry"] = {"tipo_acesso": "rss", "formato": "html"}
        return info

    if "pdf" in ct or corpo[:4] == "%PDF":
        info["estrutura_detectada"] = "pdf"
        info["layout_ok"] = None
        info["observacao"] = ("PDF exige quality gate de extração textual "
                              "(`diarios.quality`); sem camada textual não se inventa texto")
        info["recomendacao_registry"] = {"tipo_acesso": "pdf", "formato": "pdf"}
        return info

    itens_html = parse_dou_html_edicao(corpo, None)
    if itens_html:
        info["estrutura_detectada"] = "html_listagem"
        info["itens_reconhecidos"] = len(itens_html)
        info["layout_ok"] = True
        info["amostra_titulos"] = [(i.get("titulo") or "")[:80] for i in itens_html[:3]]
        info["recomendacao_registry"] = {"tipo_acesso": "html", "formato": "html"}
        return info

    if len(corpo) > 4000:
        info["estrutura_detectada"] = "layout_nao_reconhecido"
        info["layout_ok"] = False
        info["observacao"] = ("a página respondeu com conteúdo, mas o parser não "
                              "reconheceu a estrutura — cadastrar só com layout "
                              "confirmado; NÃO tratar como 'sem publicações'")
    else:
        info["estrutura_detectada"] = "erro"
        info["observacao"] = "resposta curta/sem conteúdo útil"
    return info


def alvos_do_registry(fontes):
    sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
    from diarios import registry_com_saude  # noqa: PLC0415
    registry = registry_com_saude(logger=lambda *_: None)
    alvos = []
    for fonte in registry.todas():
        if fontes and fonte.source_id not in fontes:
            continue
        if not fonte.url:
            continue
        alvos.append((fonte.source_id, fonte.url, f"registry[{fonte.nivel}]"))
    return alvos


def alvos_federais(data):
    from diarios.dou import url_leitura_jornal  # noqa: PLC0415
    alvos = [(f"dou_{secao}", url_leitura_jornal(data, secao), "DOU — leitura do jornal")
             for secao in ("do1", "do2", "do3")]
    alvos.append(("dou_inlabs", "https://inlabs.in.gov.br/", "INLABS (pacotes XML/PDF)"))
    return alvos, data


def resumir(relatorio, logger=print):
    logger("")
    logger(f"{'rótulo':28} {'status':>7} {'estrutura':24} {'itens':>6}  bytes")
    for info in relatorio:
        logger(f"{(info['rotulo'] or '')[:28]:28} {str(info['status']):>7} "
               f"{str(info['estrutura_detectada'])[:24]:24} "
               f"{info['itens_reconhecidos']:>6}  {info['bytes']}")
        if info.get("observacao"):
            logger(f"    · {info['observacao'][:160]}")
        for titulo in info.get("amostra_titulos") or []:
            logger(f"      - {titulo}")
    reconhecidas = [i for i in relatorio if i["estrutura_detectada"] in
                    ("json_embutido", "json_oficial", "xml_oficial", "html_listagem",
                     "feed_rss")]
    logger("")
    logger(f"{len(reconhecidas)}/{len(relatorio)} alvos com estrutura reconhecida · "
           f"{len([i for i in relatorio if i['estrutura_detectada'] == 'layout_nao_reconhecido'])} "
           f"com layout não reconhecido · "
           f"{len([i for i in relatorio if i['estrutura_detectada'] in ('erro', 'bloqueado')])} "
           f"indisponíveis")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sonda os Diários Oficiais (diagnóstico).")
    ap.add_argument("--fonte", action="append", help="source_id do registry (pode repetir)")
    ap.add_argument("--url", action="append", help="URL candidata (pode repetir)")
    ap.add_argument("--rotulo", default=None, help="rótulo da URL candidata")
    ap.add_argument("--federal", action="store_true",
                    help="sonda os caminhos integrais do DOU (leitura do jornal + INLABS)")
    ap.add_argument("--data", default=None, help="data AAAA-MM-DD para --federal")
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--json", dest="json_saida", help="grava o relatório da sonda")
    ap.add_argument("--salvar-dir", default=None,
                    help="guarda o payload baixado (para fixtures/inspeção)")
    args = ap.parse_args(argv)

    alvos = []
    if args.federal:
        from diarios.base import agora_brt  # noqa: PLC0415
        data = args.data or agora_brt().date().isoformat()
        federais, _ = alvos_federais(data)
        alvos.extend(federais)
    if args.fonte:
        alvos.extend(alvos_do_registry(args.fonte))
    for url in args.url or []:
        alvos.append((args.rotulo or url, url, "candidato"))
    if not alvos:
        ap.print_help()
        return 2

    relatorio = []
    for rotulo, url, origem in alvos:
        resposta = baixar(url, timeout=args.timeout)
        info = analisar(resposta, url=url, rotulo=rotulo)
        info["origem"] = origem
        relatorio.append(info)
        if args.salvar_dir and resposta.get("bytes"):
            os.makedirs(args.salvar_dir, exist_ok=True)
            nome = re.sub(r"[^a-zA-Z0-9_.-]", "_", rotulo)[:70]
            with open(os.path.join(args.salvar_dir, nome + ".payload"), "wb") as f:
                f.write(resposta["bytes"])
    resumir(relatorio)
    if args.json_saida:
        from diarios.base import salvar_json  # noqa: PLC0415
        salvar_json(args.json_saida, {"alvos": relatorio})
        print(f"\nrelatório da sonda: {args.json_saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
