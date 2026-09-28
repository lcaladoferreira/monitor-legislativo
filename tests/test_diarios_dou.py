#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes do DOU integral (FASE 1, 12 e 14) — offline, com fixtures mínimas.

Cobrem: parser do XML estruturado do INLABS, parser do JSON embutido da edição,
parser HTML de fallback, edições extra declaradas pela própria página, quebra de
layout, zero publicação legítimo, fonte indisponível, pacote XML local e o
acionamento da busca temática como fallback/verificação complementar.

Nenhum teste depende de rede: as respostas HTTP são simuladas com as fixtures
`tests/fixtures/diarios/` (amostras mínimas e representativas do formato oficial).
"""
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from diarios.base import ContextoDiario  # noqa: E402
from diarios.dou import (  # noqa: E402
    ColetorDiarioDou, ColetorDouBuscaTematica, ColetorDouIntegral, ColetorDouXMLINLABS,
    extrair_edicoes_extras, normalizar_secao, parse_dou_html_edicao,
    parse_dou_json_embutido, parse_dou_xml, url_leitura_jornal,
)

FIXTURES = ROOT / "tests" / "fixtures" / "diarios"
HTML_JSON = (FIXTURES / "leiturajornal_do1_json_embutido.html").read_text(encoding="utf-8")
HTML_LISTA = (FIXTURES / "leiturajornal_do3_html_sem_json.html").read_text(encoding="utf-8")
HTML_ZERO = (FIXTURES / "leiturajornal_zero_publicacao.html").read_text(encoding="utf-8")
HTML_LAYOUT = (FIXTURES / "leiturajornal_layout_alterado.html").read_text(encoding="utf-8")
XML_AMOSTRA = (FIXTURES / "dou_inlabs_amostra.xml").read_text(encoding="utf-8")


# ------------------------------------------------------------- HTTP simulado
class RespostaFalsa:
    def __init__(self, url, status=200, texto="", erro=None):
        self.url = url
        self.status = status
        self.texto = texto
        self.erro = erro
        self.content_type = "text/html"
        self.url_final = url

    @property
    def ok(self):
        return self.status is not None and 200 <= self.status < 300

    def json(self):
        import json
        try:
            return json.loads(self.texto)
        except ValueError:
            return None


class ClienteFalso:
    """Cliente HTTP determinístico por rota (substring → conteúdo)."""

    def __init__(self, rotas):
        self.rotas = rotas
        self.pedidos = []

    def get(self, url, accept=None, timeout=None, cache=True, headers=None, retry_403=False):
        self.pedidos.append(url)
        # Rota mais específica primeiro (evita "secao=do1" capturar "secao=do1&edicao=extra").
        for chave in sorted(self.rotas, key=len, reverse=True):
            valor = self.rotas[chave]
            if chave in url:
                if isinstance(valor, RespostaFalsa):
                    return valor
                return RespostaFalsa(url, 200, valor)
        return RespostaFalsa(url, 503, "", erro="HTTP 503")

    def resumo_stats(self):
        return {"chamadas": len(self.pedidos), "falhas": 0, "cache": 0, "tempo_total": 0.0,
                "por_endpoint": {}}


def contexto(rotas, dias=1, timeout_s=60):
    ctx = ContextoDiario("dou", timeout_s=timeout_s, dias=dias, logger=lambda *_: None)
    ctx.cliente = ClienteFalso(rotas)
    return ctx


# ------------------------------------------------------------------- parsers
class ParserDouTests(unittest.TestCase):
    def test_json_embutido_da_edicao(self):
        itens, total = parse_dou_json_embutido(HTML_JSON)
        self.assertEqual(total, 3)
        self.assertEqual(len(itens), 3)
        lei = itens[0]
        self.assertEqual(lei["titulo"], "LEI Nº 15.520, DE 24 DE SETEMBRO DE 2026")
        self.assertEqual(lei["data"], "2026-09-25")
        self.assertEqual(lei["secao"], "Seção 1")
        self.assertEqual(lei["tipo_ato"], "Lei")
        self.assertEqual(lei["edicao"], "182")
        self.assertEqual(lei["pagina"], "1")
        self.assertEqual(lei["id_oficial"], "dou:734421039")
        self.assertEqual(lei["url_oficial"],
                         "https://www.in.gov.br/web/dou/-/"
                         "lei-n-15.520-de-24-de-setembro-de-2026-734421039")
        self.assertIn("Universidade Federal da Fronteira Norte", lei["texto"])
        self.assertEqual(lei["modo_ingestao"], "integral")

    def test_json_embutido_nao_encontra_ato_sem_url_oficial(self):
        html = ('<script type="application/json">'
                '{"jsonArray":[{"title":"ATO SEM URL","pubDate":"2026-09-25"}]}</script>')
        itens, _total = parse_dou_json_embutido(html)
        self.assertEqual(itens, [])

    def test_html_de_fallback_com_breadcrumb(self):
        itens = parse_dou_html_edicao(HTML_LISTA, "do3")
        self.assertEqual(len(itens), 2)
        edital = itens[0]
        self.assertEqual(edital["secao"], "Seção 3")
        self.assertEqual(edital["edicao"], "182")
        self.assertEqual(edital["pagina"], "41")
        self.assertEqual(edital["data"], "2026-09-25")
        self.assertEqual(edital["hierarquia"], ["Seção 3", "Ministério da Fazenda",
                                                "Secretaria Especial da Receita Federal do Brasil"])
        self.assertTrue(edital["url_oficial"].startswith("https://www.in.gov.br/web/dou/-/"))
        # O tipo do ato não é afirmado quando o HTML não o traz com segurança.
        self.assertIsNone(edital["tipo_ato"])

    def test_edicoes_extras_so_quando_a_pagina_declara(self):
        extras = extrair_edicoes_extras(HTML_JSON)
        self.assertEqual(len(extras), 1)
        self.assertEqual(extras[0][0], "EDIÇÃO EXTRA")
        self.assertIn("edicao=extra", extras[0][1])
        self.assertNotIn("&amp;", extras[0][1])
        self.assertEqual(extrair_edicoes_extras("<html>sem link</html>"), [])

    def test_parser_do_xml_estruturado(self):
        itens, erro = parse_dou_xml(XML_AMOSTRA, "2026-09-25-DO1.zip")
        self.assertIsNone(erro)
        self.assertEqual(len(itens), 3)
        lei = itens[0]
        self.assertEqual(lei["titulo"], "LEI Nº 15.520, DE 24 DE SETEMBRO DE 2026")
        self.assertEqual(lei["id_oficial"], "dou:734421039")
        self.assertEqual(lei["secao"], "Seção 1")
        self.assertEqual(lei["data"], "2026-09-25")
        self.assertEqual(lei["tipo_ato"], "Lei")
        self.assertEqual(lei["orgao"], "Atos do Poder Legislativo")
        self.assertEqual(lei["hierarquia"], ["Atos do Poder Legislativo", "Lei Ordinária"])
        self.assertEqual(lei["pagina"], "1")
        self.assertEqual(lei["edicao"], "182")
        self.assertEqual(lei["arquivo_fonte"], "2026-09-25-DO1.zip")
        self.assertIn("Universidade Federal da Fronteira Norte", lei["texto"])
        self.assertEqual(lei["modo_ingestao"], "xml")

    def test_parser_xml_invalido_nao_inventa_item(self):
        itens, erro = parse_dou_xml("<xml><article", "pacote.xml")
        self.assertEqual(itens, [])
        self.assertEqual(erro, "XML inválido")

    def test_normalizacao_de_secao_e_url(self):
        self.assertEqual(normalizar_secao("DO1"), "Seção 1")
        self.assertEqual(normalizar_secao("do3"), "Seção 3")
        self.assertEqual(normalizar_secao(None), None)
        self.assertEqual(normalizar_secao("Edição Especial"), "Edição Especial")
        self.assertEqual(url_leitura_jornal("2026-09-25", "do1"),
                         "https://www.in.gov.br/leiturajornal?data=25-09-2026&secao=do1")


class BuscaFalsa(ColetorDouBuscaTematica):
    """Busca temática simulada (evita rede): devolve um item oficial verificado."""

    def __init__(self, itens=None, falhar=False):
        super().__init__(logger=lambda *_: None)
        self._itens = itens if itens is not None else [{
            "titulo": "RESOLUÇÃO Nº 27 sobre inteligência artificial",
            "url_oficial": "https://www.in.gov.br/web/dou/-/resolucao-n-27-734499001",
            "data": "2026-09-25", "secao": "Seção 1", "modo_ingestao": "fallback",
            "origem": "busca",
        }]
        self._falhar = falhar

    def coletar(self, ctx, resultado):
        if self._falhar:
            from sources.base import FonteIndisponivel
            raise FonteIndisponivel("busca simulada indisponível")
        resultado.itens.extend(self._itens)
        resultado.metricas.itens_fonte += len(self._itens)
        resultado.canais_ok.append("busca por tema (7 dias)")
        return resultado


# ------------------------------------------------------------ coletor integral
class ColetorIntegralTests(unittest.TestCase):
    def test_coleta_integral_das_tres_secoes_sem_filtro_tematico(self):
        rotas = {"secao=do1": HTML_JSON, "secao=do2": HTML_ZERO, "secao=do3": HTML_LISTA,
                 "edicao=extra": HTML_ZERO}
        ctx = contexto(rotas)
        resultado = ColetorDouIntegral(logger=lambda *_: None).coletar(
            ctx, __import__("diarios.base", fromlist=["ResultadoColeta"])
            .ResultadoColeta("dou", "DOU"))
        # 3 (JSON da Seção 1) + 2 (HTML da Seção 3) — inclusive atos sem nenhum
        # termo temático; a edição extra desta fixture não publica atos.
        self.assertEqual(len(resultado.itens), 5)
        self.assertEqual(resultado.modo_ingestao, "integral")
        self.assertTrue(resultado.cobertura_integral)
        self.assertIsNone(resultado.layout_changed)
        self.assertEqual(resultado.status, "ok")
        secoes = {i["secao"] for i in resultado.itens}
        self.assertEqual(secoes, {"Seção 1", "Seção 3"})
        self.assertTrue(any("Seção 2" == e["secao"] and e["itens"] == 0
                            for e in resultado.edicoes))
        # Nenhum filtro temático na ingestão: o ato administrativo sem tema entra.
        self.assertTrue(any("Joaíma" in (i.get("texto") or "") for i in resultado.itens))

    def test_quebra_de_layout_nao_vira_ausencia_de_publicacao(self):
        rotas = {"secao=do1": HTML_LAYOUT, "secao=do2": HTML_LAYOUT, "secao=do3": HTML_LAYOUT}
        ctx = contexto(rotas)
        from diarios.base import ResultadoColeta
        resultado = ColetorDouIntegral(logger=lambda *_: None).coletar(
            ctx, ResultadoColeta("dou", "DOU"))
        self.assertTrue(resultado.layout_changed)
        self.assertIn("não reconheceu a estrutura", resultado.layout_evidencia)
        self.assertFalse(resultado.zero_publicacao_confirmado)
        self.assertEqual(resultado.status, "falha")   # 200 com conteúdo e nenhum item

    def test_zero_publicacao_confirmado(self):
        rotas = {secao: HTML_ZERO for secao in ("secao=do1", "secao=do2", "secao=do3")}
        from diarios.base import ResultadoColeta
        resultado = ColetorDouIntegral(logger=lambda *_: None).coletar(
            contexto(rotas), ResultadoColeta("dou", "DOU"))
        self.assertEqual(resultado.itens, [])
        self.assertFalse(resultado.layout_changed)
        self.assertTrue(resultado.zero_publicacao_confirmado)
        self.assertEqual(resultado.status, "ok")
        self.assertTrue(resultado.zero_evidencia)

    def test_fonte_indisponivel(self):
        from diarios.base import ResultadoColeta, dias_uteis_janela
        from sources.base import FonteIndisponivel
        resultado = ResultadoColeta("dou", "DOU")
        rotas = {secao: RespostaFalsa("x", 500, "", erro="HTTP 500")
                 for secao in ("secao=do1", "secao=do2", "secao=do3")}
        # Janela explícita: o teste não pode depender do dia em que roda.
        coletor = ColetorDouIntegral(logger=lambda *_: None, datas=["2026-09-25"])
        with self.assertRaises(FonteIndisponivel):
            coletor.coletar(contexto(rotas), resultado)
        self.assertTrue(resultado.erros)
        self.assertEqual(resultado.canais_falhos, ["do1 2026-09-25", "do2 2026-09-25",
                                                   "do3 2026-09-25"])
        self.assertEqual(coletor.janela(None), ["2026-09-25"])
        self.assertTrue(dias_uteis_janela(1))   # a janela padrão continua existindo

    def test_edicao_extra_declarada_pela_pagina_e_coletada(self):
        rotas = {"secao=do1": HTML_JSON, "secao=do2": HTML_ZERO, "secao=do3": HTML_ZERO,
                 "edicao=extra": HTML_LISTA}
        from diarios.base import ResultadoColeta
        resultado = ColetorDouIntegral(logger=lambda *_: None).coletar(
            contexto(rotas), ResultadoColeta("dou", "DOU"))
        extras = [i for i in resultado.itens if i.get("edicao_extraordinaria") is True]
        self.assertEqual(len(extras), 2)
        self.assertTrue(any("extra" in canal for canal in resultado.canais_ok))


# --------------------------------------------------------- coletor composto
class ColetorCompostoTestes(unittest.TestCase):
    def _resultado(self):
        from diarios.base import ResultadoColeta
        return ResultadoColeta("dou", "DOU")

    def test_integral_ok_sem_acionar_fallback(self):
        rotas = {"secao=do1": HTML_JSON, "secao=do2": HTML_JSON, "secao=do3": HTML_JSON}
        coletor = ColetorDiarioDou(logger=lambda *_: None, usar_xml=False)
        resultado = coletor.coletar(contexto(rotas), self._resultado())
        self.assertEqual(resultado.modo_ingestao, "integral")
        self.assertFalse(resultado.fallback_usado)
        self.assertTrue(resultado.cobertura_integral)
        self.assertEqual(resultado.status, "ok")
        self.assertEqual(resultado.status_registry, "funcionando")

    def test_integral_indisponivel_usa_busca_tematica_e_deixa_rastro(self):
        # Nenhuma seção responde; a busca temática (coletor legado) devolve 1 item.
        coletor = ColetorDiarioDou(logger=lambda *_: None, usar_xml=False, busca=BuscaFalsa())
        resultado = coletor.coletar(contexto({"in.gov.br": RespostaFalsa("x", 403, "", erro="HTTP 403")}),
                                    self._resultado())
        self.assertEqual(resultado.modo_ingestao, "fallback")
        self.assertTrue(resultado.fallback_usado)
        self.assertFalse(resultado.cobertura_integral)
        self.assertEqual(len(resultado.itens), 1)
        self.assertEqual(resultado.status, "ok")
        # Cobertura reduzida é visível no registry (parcial), não escondida.
        self.assertEqual(resultado.status_registry, "parcial")
        self.assertTrue(any("integral" in a for a in resultado.avisos))

    def test_layout_quebrado_reprova_mesmo_com_fallback(self):
        rotas = {"secao=do1": HTML_LAYOUT, "secao=do2": HTML_LAYOUT, "secao=do3": HTML_LAYOUT}
        coletor = ColetorDiarioDou(logger=lambda *_: None, usar_xml=False, busca=BuscaFalsa())
        resultado = coletor.coletar(contexto(rotas), self._resultado())
        self.assertTrue(resultado.layout_changed)
        self.assertEqual(resultado.status, "parcial")
        self.assertTrue(any("layout" in c for c in resultado.canais_falhos))
        self.assertIn("não reconheceu a estrutura", resultado.erros[0])
        # A quebra de layout é reportada mesmo com o fallback cobrindo o dia.
        self.assertEqual(resultado.metricas.duplicados, 0)
        self.assertTrue(resultado.fallback_usado)

    def test_sem_xml_configurado_informa_e_nao_declara_cobertura(self):
        coletor = ColetorDouXMLINLABS(logger=lambda *_: None)
        coletor.dir_local = None
        coletor.usuario = coletor.senha = None
        from diarios.base import ResultadoColeta
        from sources.base import FonteIndisponivel
        resultado = ResultadoColeta("dou_inlabs_xml", "XML")
        with self.assertRaises(FonteIndisponivel):
            coletor.coletar(contexto({}), resultado)
        self.assertIn("não configurado", resultado.erros[0])

    def test_pacote_xml_local_e_ingerido(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "2026-09-25-DO1.zip")
            with zipfile.ZipFile(zip_path, "w") as z:
                z.writestr("2026-09-25-DO1.xml", XML_AMOSTRA)
            os.environ["MONITOR_DOU_XML_DIR"] = tmp
            try:
                # Janela explícita: o pacote é de 25/09/2026 (importação dirigida).
                coletor = ColetorDouXMLINLABS(logger=lambda *_: None, datas=["2026-09-25"])
                from diarios.base import ResultadoColeta
                resultado = ResultadoColeta("dou_inlabs_xml", "XML")
                coletor.coletar(contexto({}, dias=1), resultado)
                self.assertEqual(len(resultado.itens), 3)
                self.assertEqual(resultado.modo_ingestao, "xml")
                self.assertTrue(resultado.canais_ok)
                self.assertTrue(resultado.arquivos_fonte)
            finally:
                os.environ.pop("MONITOR_DOU_XML_DIR", None)

    def test_ausencia_de_tema_nao_e_erro_de_ingestao(self):
        """Edição cheia de atos administrativos: status ok e zero relevantes (depois)."""
        rotas = {"secao=do1": HTML_LISTA, "secao=do2": HTML_LISTA, "secao=do3": HTML_LISTA}
        coletor = ColetorDiarioDou(logger=lambda *_: None, usar_xml=False,
                                   busca=BuscaFalsa(falhar=True))
        resultado = coletor.coletar(contexto(rotas), self._resultado())
        self.assertEqual(resultado.status, "ok")
        self.assertGreater(len(resultado.itens), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
