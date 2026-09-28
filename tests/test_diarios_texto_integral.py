#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Texto integral do ato + quality gate na ingestão (FASES 1 e 10) — offline.

A listagem oficial da edição pode trazer (ou não) o conteúdo de cada ato. Quando
não traz, o coletor abre a **página oficial do ato** para capturar o texto, com
teto por edição; o que não for capturado é registrado como pendente e o item
segue publicado com `texto` ausente — nada é inferido a partir do título.

O quality gate (`evaluate_text_quality`) roda na normalização e o resultado fica
no item (`qualidade_texto`), com contadores por fonte no payload legado.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from diarios.base import ContextoDiario  # noqa: E402
from diarios.dou import (ColetorDouIntegral, extrair_texto_ato,  # noqa: E402
                         url_leitura_jornal)
from diarios.pipeline import PipelineDiarios  # noqa: E402
from diarios.registry import registry_padrao  # noqa: E402


# ------------------------------------------------------------------ HTTP falso
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


# ------------------------------------------------------------------- fixtures
def pagina_edicao(atos, secao="do1"):
    """Página oficial mínima com o JSON embutido da edição (mesmo formato real)."""
    itens = [{
        "title": ato["titulo"], "urlTitle": ato["slug"], "pubDate": "2026-09-25",
        "content": ato.get("content"), "artType": ato.get("artType", "Portaria"),
        "hierarchyStr": "Ministério da Gestão e da Inovação", "pubName": secao,
        "editionNumber": "182", "numberPage": "7", "classPK": ato["id"],
    } for ato in atos]
    payload = json.dumps({"jsonArray": itens, "itemsTotal": len(itens)}, ensure_ascii=False)
    return ("<!doctype html><html><body><div id=\"leitura\">"
            f"<script id=\"LeituraJornalPortlet_params\" type=\"application/json\">{payload}"
            "</script></div></body></html>")


PAGINA_ATO = ('<!doctype html><html><body><div class="materia"><h1>Portaria nº 10</h1>'
              '<div id="conteudo"><p>O MINISTRO DE ESTADO, no uso das atribuições, resolve:'
              '</p><p>Art. 1º Instituir o uso de inteligência artificial no órgão, com '
              'governança algorítmica e proteção de dados pessoais.</p><p>Art. 2º Esta '
              'portaria entra em vigor na data de sua publicação.</p></div></div>'
              '</body></html>')
PAGINA_ATO_VAZIA = "<!doctype html><html><body><div class=\"materia\"></div></body></html>"


def pagina_sem_texto(qtd=3):
    return pagina_edicao([
        {"titulo": f"PORTARIA Nº {i}", "slug": f"portaria-n-{i}-2026-7345001{i}",
         "id": f"7345001{i}", "content": None} for i in range(qtd)])


# --------------------------------------------------------------------- testes
class ExtrairTextoAtoTests(unittest.TestCase):
    def test_texto_do_bloco_de_conteudo(self):
        texto = extrair_texto_ato(PAGINA_ATO)
        self.assertIn("Art. 1º Instituir o uso de inteligência artificial", texto)
        self.assertIn("Art. 2º", texto)
        self.assertNotIn("<p>", texto)

    def test_sem_bloco_reconhecivel_devolve_none(self):
        self.assertIsNone(extrair_texto_ato(PAGINA_ATO_VAZIA))
        self.assertIsNone(extrair_texto_ato(""))
        self.assertIsNone(extrair_texto_ato("<html><body>   <br>  </body></html>"))

    def test_script_e_estilo_nunca_viram_texto(self):
        html = ('<html><body><div id="conteudo"><script>var x = "AI";</script>'
                '<style>.a{}</style><p>Texto oficial do ato.</p></div></body></html>')
        texto = extrair_texto_ato(html)
        self.assertIn("Texto oficial do ato.", texto)
        self.assertNotIn("var x", texto)
        self.assertNotIn(".a{}", texto)


class TextoIntegralDoAtoTests(unittest.TestCase):
    def test_listagem_sem_conteudo_busca_o_texto_na_pagina_do_ato(self):
        rotas = {
            "secao=do1": pagina_sem_texto(2),
            "secao=do2": pagina_edicao([]),
            "secao=do3": pagina_edicao([]),
            "/web/dou/-/portaria-n-0-2026-73450010": PAGINA_ATO,
            "/web/dou/-/portaria-n-1-2026-73450011": PAGINA_ATO,
        }
        resultado = ColetorDouIntegral(logger=lambda *_: None, secoes=("do1",),
                                       max_textos_por_edicao=5).coletar(
            contexto(rotas), _resultado())
        self.assertEqual(resultado.metricas.itens_fonte, 2)
        textos = [i.get("texto") for i in resultado.itens]
        self.assertTrue(all(t and "Art. 1º" in t for t in textos))
        self.assertTrue(all(i.get("texto_fonte") for i in resultado.itens))
        bloco = [e for e in resultado.edicoes if e.get("secao") == "texto integral"][0]
        self.assertEqual(bloco["itens"], 2)
        self.assertEqual(bloco["textos_pendentes"], 0)
        self.assertEqual(bloco["textos_buscados"], 2)

    def test_teto_por_edicao_e_respeitado_e_o_resto_e_registrado(self):
        rotas = {"secao=do1": pagina_sem_texto(3),
                 "/web/dou/-/portaria-n-0-2026-73450010": PAGINA_ATO}
        resultado = ColetorDouIntegral(logger=lambda *_: None, secoes=("do1",),
                                       max_textos_por_edicao=1).coletar(
            contexto(rotas), _resultado())
        self.assertEqual(sum(1 for i in resultado.itens if i.get("texto")), 1)
        bloco = [e for e in resultado.edicoes if e.get("secao") == "texto integral"][0]
        self.assertEqual(bloco["textos_buscados"], 1)
        self.assertEqual(bloco["textos_pendentes"], 2)
        self.assertTrue(any("seguem sem texto integral" in a for a in resultado.avisos))
        # A listagem foi lida por inteiro: a cobertura integral da edição não
        # depende do texto ter sido servido em cada ato.
        self.assertTrue(resultado.cobertura_integral)

    def test_pagina_sem_texto_nao_inventa_conteudo(self):
        rotas = {"secao=do1": pagina_sem_texto(1),
                 "/web/dou/-/portaria-n-0-2026-73450010": PAGINA_ATO_VAZIA}
        resultado = ColetorDouIntegral(logger=lambda *_: None, secoes=("do1",),
                                       max_textos_por_edicao=5).coletar(
            contexto(rotas), _resultado())
        item = resultado.itens[0]
        self.assertIsNone(item.get("texto"))
        self.assertIsNone(item.get("texto_fonte"))
        bloco = [e for e in resultado.edicoes if e.get("secao") == "texto integral"][0]
        self.assertEqual(bloco["textos_pendentes"], 1)

    def test_teto_zero_desliga_a_busca_de_texto(self):
        rotas = {"secao=do1": pagina_sem_texto(2)}
        coletor = ColetorDouIntegral(logger=lambda *_: None, secoes=("do1",),
                                     max_textos_por_edicao=0)
        resultado = coletor.coletar(contexto(rotas), _resultado())
        self.assertEqual(len(resultado.itens), 2)
        self.assertFalse([e for e in resultado.edicoes if e.get("secao") == "texto integral"])


class QualityGateNaIngestaoTests(unittest.TestCase):
    def _pipeline(self):
        coletores = {"dou": ColetorDouIntegral(logger=lambda *_: None, secoes=("do1",),
                                               max_textos_por_edicao=5)}
        return PipelineDiarios(registry_padrao(), coletores, raw_storage=None,
                               metadata_store=None, logger=lambda *_: None)

    def _ctx_factory(self, rotas):
        def fabrica(fonte, coletor):
            return contexto(rotas)
        return fabrica

    def test_item_recebe_qualidade_texto_e_contadores(self):
        rotas = {"secao=do1": pagina_edicao([
                    {"titulo": "PORTARIA Nº 10", "slug": "portaria-n-10-2026-73450010",
                     "id": "73450010", "content": None}])}
        rotas["/web/dou/-/portaria-n-10-2026-73450010"] = PAGINA_ATO
        pipeline = self._pipeline()
        relatorios = pipeline.executar(["dou"], timeout_s=30,
                                       ctx_factory=self._ctx_factory(rotas))
        relatorio = relatorios["dou"]
        item = relatorio.itens_normalizados[0]
        self.assertEqual(item["qualidade_texto"]["estado"], "good")
        self.assertEqual(relatorio.textos_ok, 1)
        self.assertEqual(relatorio.textos_degradados, 0)
        legado = relatorio.para_resultado_legado()
        self.assertEqual(legado["diarios"]["qualidade_texto"],
                         {"good": 1, "degraded": 0, "failed": 0})

    def test_ato_sem_texto_e_marcado_como_failed_e_nao_entra_como_bom(self):
        rotas = {"secao=do1": pagina_sem_texto(1),
                 "/web/dou/-/portaria-n-0-2026-73450010": PAGINA_ATO_VAZIA}
        pipeline = self._pipeline()
        relatorios = pipeline.executar(["dou"], timeout_s=30,
                                       ctx_factory=self._ctx_factory(rotas))
        relatorio = relatorios["dou"]
        self.assertEqual(relatorio.itens_normalizados[0]["qualidade_texto"]["estado"], "failed")
        self.assertEqual(relatorio.textos_falhos, 1)
        self.assertEqual(relatorio.textos_ok, 0)


def _resultado():
    from diarios.base import ResultadoColeta
    return ResultadoColeta("dou", "DOU")


if __name__ == "__main__":
    unittest.main()
