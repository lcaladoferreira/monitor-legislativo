#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tetos de memória da ingestão integral (incidente 2026-09-28: OOM no runner).

A primeira execução do workflow de diagnóstico com a rota nova morreu com
**exit code 137** (OOM). Causas encontradas e cobertas aqui:

  1. o arquivo-fonte (página HTML inteira da edição) era guardado em memória e
     **nunca** liberado — nem gravado no raw storage, apesar do contrato;
  2. não havia teto de bytes para o texto integral capturado por edição;
  3. o fallback reabria o pipeline de diários dentro do subprocesso do coletor
     histórico, repetindo a ingestão inteira (tempo e memória dobrados).

Estes testes são offline e usam clientes HTTP simulados.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from diarios.base import (LIMITE_ARQUIVO_FONTE_BYTES, ContextoDiario,  # noqa: E402
                          ResultadoColeta)
from diarios.dou import ColetorDouIntegral  # noqa: E402
from diarios.pipeline import PipelineDiarios  # noqa: E402
from diarios.registry import registry_padrao  # noqa: E402
from storage.base import RawStorage  # noqa: E402


class RespostaFalsa:
    def __init__(self, url, status=200, texto="", erro=None):
        self.url, self.status, self.texto, self.erro = url, status, texto, erro
        self.content_type, self.url_final = "text/html", url

    @property
    def ok(self):
        return self.status is not None and 200 <= self.status < 300


class ClienteFalso:
    def __init__(self, rotas):
        self.rotas, self.pedidos = rotas, []

    def get(self, url, **kw):
        self.pedidos.append(url)
        for chave in sorted(self.rotas, key=len, reverse=True):
            valor = self.rotas[chave]
            if chave in url:
                return valor if isinstance(valor, RespostaFalsa) else RespostaFalsa(url, 200, valor)
        return RespostaFalsa(url, 404, "", erro="HTTP 404")

    def resumo_stats(self):
        return {"chamadas": len(self.pedidos), "falhas": 0, "cache": 0, "tempo_total": 0.0,
                "por_endpoint": {}}


def contexto(rotas, timeout_s=60):
    ctx = ContextoDiario("dou", timeout_s=timeout_s, dias=1, logger=lambda *_: None)
    ctx.cliente = ClienteFalso(rotas)
    return ctx


def pagina_edicao(atos, secao="do1"):
    import json
    itens = [{"title": a["titulo"], "urlTitle": a["slug"], "pubDate": "2026-09-25",
              "content": a.get("content"), "artType": "Portaria",
              "hierarchyStr": "Órgão", "pubName": secao, "editionNumber": "182",
              "numberPage": "7", "classPK": a["id"]} for a in atos]
    payload = json.dumps({"jsonArray": itens, "itemsTotal": len(itens)}, ensure_ascii=False)
    return ('<html><body><div id="leitura">'
            f'<script id="Leiruta" type="application/json">{payload}</script>'
            "</div></body></html>")


class RawStorageFalso(RawStorage):
    """Raw storage em memória: registra o que recebeu, inclusive os arquivos-fonte."""

    nome = "falso"

    def __init__(self):
        self.chamadas = []
        self.arquivos = {}

    def save(self, source_id, referencia, itens, meta=None, arquivos=None):
        self.chamadas.append({"source_id": source_id, "referencia": referencia,
                              "itens": len(itens or []), "meta": dict(meta or {})})
        self.itens = itens
        self.arquivos = dict(arquivos or {})
        return f"{source_id}/{referencia}"

    def exists(self, source_id, referencia):
        return False

    def get(self, source_id, referencia):
        return None

    def listar(self, source_id=None, desde=None):
        return []


class ArquivoFonteTests(unittest.TestCase):
    def test_pagina_grande_e_cortada_com_aviso(self):
        resultado = ResultadoColeta("dou", "DOU")
        coletor = ColetorDouIntegral(logger=lambda *_: None)
        grande = "x" * (LIMITE_ARQUIVO_FONTE_BYTES + 10)
        coletor.registrar_arquivo_fonte(resultado, "pagina.html", grande)
        self.assertEqual(len(resultado.arquivos_fonte["pagina.html"]),
                         LIMITE_ARQUIVO_FONTE_BYTES)
        self.assertTrue(any("guardado parcialmente" in a for a in resultado.avisos))

    def test_pagina_pequena_passa_intacta(self):
        resultado = ResultadoColeta("dou", "DOU")
        coletor = ColetorDouIntegral(logger=lambda *_: None)
        coletor.registrar_arquivo_fonte(resultado, "pagina.html", "<html>ok</html>")
        self.assertEqual(resultado.arquivos_fonte["pagina.html"], "<html>ok</html>")
        self.assertEqual(resultado.avisos, [])


class LiberacaoDeMemoriaTests(unittest.TestCase):
    def _pipeline(self, raw):
        coletores = {"dou": ColetorDouIntegral(logger=lambda *_: None, secoes=("do1",),
                                               max_textos_por_edicao=0)}
        return PipelineDiarios(registry_padrao(), coletores, raw_storage=raw,
                               metadata_store=None, logger=lambda *_: None)

    def test_arquivo_fonte_vai_para_o_raw_storage_e_e_liberado(self):
        rotas = {"secao=do1": pagina_edicao([
                    {"titulo": "PORTARIA Nº 1", "slug": "portaria-n-1-2026-73450010",
                     "id": "73450010", "content": "Resumo oficial do ato."}])}
        raw = RawStorageFalso()
        pipeline = self._pipeline(raw)
        relatorio = pipeline.executar(["dou"], timeout_s=30,
                                      ctx_factory=lambda fonte, coletor: contexto(rotas))["dou"]
        self.assertEqual(len(raw.chamadas), 1)
        self.assertTrue(any("leiturajornal" in nome for nome in raw.arquivos),
                        f"arquivos-fonte não chegaram ao storage: {list(raw.arquivos)}")
        # nada fica pendurado em memória depois da gravação
        self.assertEqual(relatorio.coleta.arquivos_fonte, {})

    def test_sem_storage_nada_fica_em_memoria(self):
        rotas = {"secao=do1": pagina_edicao([
                    {"titulo": "PORTARIA Nº 1", "slug": "portaria-n-1-2026-73450010",
                     "id": "73450010", "content": "Resumo oficial do ato."}])}
        pipeline = self._pipeline(None)
        relatorio = pipeline.executar(["dou"], timeout_s=30,
                                      ctx_factory=lambda fonte, coletor: contexto(rotas))["dou"]
        self.assertEqual(relatorio.coleta.arquivos_fonte, {})
        self.assertIsNone(relatorio.raw_referencia)


class TetoDeTextoPorEdicaoTests(unittest.TestCase):
    PAGINA_ATO = ('<html><body><div id="conteudo"><p>' + ("Art. 1º texto oficial. " * 40)
                  + "</p></div></body></html>")

    def test_teto_de_bytes_interrompe_a_captura_e_registra_o_motivo(self):
        rotas = {"secao=do1": pagina_edicao([
            {"titulo": f"PORTARIA Nº {i}", "slug": f"portaria-n-{i}-2026-7345001{i}",
             "id": f"7345001{i}", "content": None} for i in range(5)])}
        rotas.update({f"/web/dou/-/portaria-n-{i}-2026-7345001{i}": self.PAGINA_ATO
                      for i in range(5)})
        coletor = ColetorDouIntegral(logger=lambda *_: None, secoes=("do1",),
                                     max_textos_por_edicao=10,
                                     max_texto_bytes_por_edicao=600)
        resultado = coletor.coletar(contexto(rotas), ResultadoColeta("dou", "DOU"))
        bloco = [e for e in resultado.edicoes if e.get("secao") == "texto integral"][0]
        self.assertLess(bloco["itens"], 5, "o teto de bytes precisa interromper a captura")
        self.assertIn("teto de", bloco["motivo_parada"])
        self.assertGreater(bloco["textos_pendentes"], 0)
        self.assertTrue(any("seguem sem texto integral" in a for a in resultado.avisos))

    def test_teto_generoso_captura_todos_os_textos(self):
        rotas = {"secao=do1": pagina_edicao([
            {"titulo": f"PORTARIA Nº {i}", "slug": f"portaria-n-{i}-2026-7345001{i}",
             "id": f"7345001{i}", "content": None} for i in range(3)])}
        rotas.update({f"/web/dou/-/portaria-n-{i}-2026-7345001{i}": self.PAGINA_ATO
                      for i in range(3)})
        coletor = ColetorDouIntegral(logger=lambda *_: None, secoes=("do1",),
                                     max_textos_por_edicao=10,
                                     max_texto_bytes_por_edicao=10 * 1024 * 1024)
        resultado = coletor.coletar(contexto(rotas), ResultadoColeta("dou", "DOU"))
        bloco = [e for e in resultado.edicoes if e.get("secao") == "texto integral"][0]
        self.assertEqual(bloco["itens"], 3)
        self.assertEqual(bloco["textos_pendentes"], 0)
        self.assertIsNone(bloco["motivo_parada"])


if __name__ == "__main__":
    unittest.main()
