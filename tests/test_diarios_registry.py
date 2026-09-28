#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes do Source Registry e do Coverage Monitor (FASE 4–6, 11, 14).

O que estes testes protegem:

  · os 27 entes estaduais estão cadastrados (mesmo sem coletor);
  · fonte sem coletor aparece como `nao_implementado` — nunca como cobertura;
  · a cobertura técnica mede apenas fontes cadastradas × implementadas e não é
    apresentada como "100% de cobertura";
  · a arquitetura municipal existe (famílias de adapter) sem inventar cidade.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from diarios.coverage import (DEFINICAO_COBERTURA, monitor,  # noqa: E402
                              registro_fonte)
from diarios.municipal import (FAMILIAS_ADAPTER, adapters_disponiveis,  # noqa: E402
                               fontes_municipais_do_config, uf_do_codigo_ibge)
from diarios.registry import FonteCadastrada, RegistryFontes, registry_padrao  # noqa: E402
from diarios.states import estaduais_implementados, estaduais_pendentes  # noqa: E402
from diarios.base import UFS  # noqa: E402

UFS_ESPERADAS = ("AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT",
                 "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO",
                 "RR", "SC", "SP", "SE", "TO")


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = registry_padrao()

    def test_vinte_e_sete_entes_estaduais_cadastrados(self):
        self.assertEqual(len(UFS), 27)
        self.assertEqual(UFS_ESPERADAS, UFS)
        estaduais = self.registry.por_nivel("estadual")
        self.assertEqual(len(estaduais), 27)
        self.assertEqual({f.uf for f in estaduais}, set(UFS))
        for fonte in estaduais:
            self.assertEqual(fonte.status, "nao_implementado")
            self.assertFalse(fonte.implementado)
            self.assertIsNone(fonte.collector)

    def test_dou_e_fontes_federais_registradas(self):
        dou = self.registry.obter("dou")
        self.assertTrue(dou.implementado)
        self.assertEqual(dou.nivel, "federal")
        self.assertEqual(dou.tipo_acesso, "html")
        self.assertTrue(dou.obrigatorio)
        self.assertIn("in.gov.br", dou.url)
        self.assertTrue(self.registry.obter("dou_inlabs_xml").implementado)
        self.assertEqual(self.registry.obter("dou_inlabs_xml").tipo_acesso, "xml")
        self.assertTrue(self.registry.obter("dou_busca_tematica").implementado)

    def test_nivel_judiciario_existe_e_nao_finge_cobertura(self):
        djen = self.registry.obter("djen")
        self.assertEqual(djen.nivel, "judiciario")
        self.assertFalse(djen.implementado)
        self.assertEqual(djen.status, "nao_implementado")

    def test_fonte_nao_implementada_nao_recebe_status_operacional(self):
        fonte = self.registry.obter("estadual_sp")
        with self.assertRaises(ValueError):
            fonte.atualizar_saude(status="funcionando")
        self.assertEqual(fonte.status, "nao_implementado")

    def test_fonte_implementada_sem_execucao_fica_implementado(self):
        fonte = FonteCadastrada(source_id="x", nome="X", nivel="federal",
                                collector="modulo::Classe", implementado=True)
        self.assertEqual(fonte.status, "implementado")
        fonte.atualizar_saude(status="funcionando", ultima_tentativa="2026-09-26T09:00:00-03:00")
        self.assertEqual(fonte.status, "funcionando")

    def test_vocabularios_fechados(self):
        with self.assertRaises(ValueError):
            FonteCadastrada(source_id="x", nome="X", nivel="planetario")
        with self.assertRaises(ValueError):
            FonteCadastrada(source_id="x", nome="X", nivel="federal", tipo_acesso="telepatia")
        with self.assertRaises(ValueError):
            FonteCadastrada(source_id="x", nome="X", nivel="municipal",
                            adapter_family="scraper_unico_por_cidade")
        with self.assertRaises(ValueError):
            FonteCadastrada(source_id="x", nome="X", nivel="municipal",
                            poder="partido")

    def test_snapshot_com_campos_do_contrato(self):
        snapshot = self.registry.snapshot()
        self.assertIn("dou", snapshot["fontes"])
        fonte = snapshot["fontes"]["dou"]
        for campo in ("source_id", "nome", "nivel", "uf", "municipio", "poder", "url",
                      "tipo_acesso", "formato", "collector", "ativo", "obrigatorio",
                      "status", "ultima_tentativa", "ultima_execucao_ok",
                      "ultima_publicacao", "itens_coletados", "duracao",
                      "layout_changed", "erro", "adapter_family", "jurisdicao"):
            self.assertIn(campo, fonte)

    def test_snapshot_persistido_reidrata_saude(self):
        """A saúde operacional sobrevive entre execuções via snapshot versionado."""
        dou = self.registry.obter("dou")
        dou.atualizar_saude(status="parcial", ultima_tentativa="2026-09-26T09:00:00-03:00",
                            ultima_execucao_ok="2026-09-26T09:00:00-03:00",
                            ultima_publicacao="2026-09-25", itens_coletados=42,
                            duracao=12.5, layout_changed=False,
                            erro="layout não reconhecido em do3",
                            extra={"modo_ingestao": "integral+complementar"})
        with tempfile.TemporaryDirectory() as tmp:
            caminho = str(Path(tmp) / "snapshot.json")
            self.registry.salvar_snapshot(caminho)
            conteudo = json.loads(Path(caminho).read_text(encoding="utf-8"))
            novo = RegistryFontes.de_snapshot(caminho)
        # `de_snapshot` não traz definições de fonte: snapshot só aplica saúde a um
        # registry existente (nunca inventa fonte).
        self.assertEqual(novo.todas(), [])
        outro = registry_padrao().aplicar_saude(conteudo)
        reidratada = outro.obter("dou")
        self.assertEqual(reidratada.status, "parcial")
        self.assertEqual(reidratada.erro, "layout não reconhecido em do3")
        self.assertEqual(reidratada.itens_coletados, 42)
        self.assertEqual(reidratada.ultima_publicacao, "2026-09-25")
        self.assertEqual(reidratada.extra["modo_ingestao"], "integral+complementar")
        # fonte não implementada no snapshot continua sem status operacional
        self.assertEqual(outro.obter("estadual_sp").status, "nao_implementado")
        self.assertEqual(conteudo["fontes"]["estadual_sp"]["erro"], None)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.registry = registry_padrao()

    def test_cobertura_tecnica_conta_apenas_implementadas(self):
        metricas = monitor(self.registry)["metricas"]
        self.assertEqual(metricas["fontes_totais"], len(self.registry.todas()))
        self.assertEqual(metricas["fontes_implementadas"], 3)
        self.assertEqual(metricas["fontes_nao_implementadas"],
                         metricas["fontes_totais"] - 3)
        self.assertAlmostEqual(metricas["cobertura_tecnica_pct"],
                               round(100 * 3 / metricas["fontes_totais"], 2))
        definicao = metricas["definicao_cobertura"]
        self.assertIn("fontes cadastradas", definicao)
        self.assertIn("publicações cobertas", definicao)
        self.assertIn("pendência explícita", definicao)
        self.assertEqual(metricas["definicao_cobertura"], DEFINICAO_COBERTURA)
        self.assertNotEqual(metricas["cobertura_tecnica_pct"], 100)

    def test_nenhuma_fonte_nao_implementada_aparece_como_ok(self):
        snapshot = monitor(self.registry)
        for fonte in snapshot["fontes"].values():
            if not fonte["implementado"]:
                self.assertEqual(fonte["status"], "nao_implementado")
                self.assertIsNone(fonte["ultima_coleta_ok"])
                self.assertIsNone(fonte["itens_coletados"])

    def test_status_operacionais_aparecem_quando_existem(self):
        from diarios.base import ResultadoColeta
        from diarios.coverage import aplicar_resultado
        resultado = ResultadoColeta("dou", "DOU")
        resultado.canais_ok.append("do1 2026-09-25")
        resultado.modo_ingestao = "integral"
        resultado.cobertura_integral = True
        resultado.ultima_publicacao = "2026-09-25"
        resultado.itens = [{"chave": "k"}]
        aplicar_resultado(self.registry, "dou", resultado)
        dou = self.registry.obter("dou")
        self.assertEqual(dou.status, "funcionando")
        self.assertEqual(dou.itens_coletados, 1)
        self.assertEqual(dou.ultima_publicacao, "2026-09-25")
        metricas = monitor(self.registry)["metricas"]
        self.assertEqual(metricas["fontes_ok"], 1)
        # 1 de 3 implementadas leu a edição integral: parcial, não 100%.
        self.assertEqual(metricas["cobertura_integral_pct"], 33.33)
        self.assertEqual(metricas["fontes_implementadas_sem_execucao"], 2)

    def test_registro_por_fonte_tem_os_campos_do_monitor(self):
        registro = registro_fonte(self.registry.obter("dou"))
        for campo in ("source_id", "jurisdicao", "nivel", "ultima_tentativa",
                      "ultima_coleta_ok", "ultima_publicacao_detectada",
                      "itens_coletados", "erro", "status", "duracao", "layout_changed"):
            self.assertIn(campo, registro)
        self.assertEqual(registro["jurisdicao"], "federal")

    def test_pendentes_nomeadas_por_jurisdicao(self):
        pendentes = monitor(self.registry)["pendentes"]
        self.assertEqual(pendentes["total"], 28)   # 27 estaduais + DJEN
        self.assertIn("estadual_sp", pendentes["amostra"])
        por_nivel = monitor(self.registry)["por_nivel"]
        self.assertEqual(por_nivel["estadual"]["nao_implementadas"], 27)
        self.assertEqual(por_nivel["federal"]["implementadas"], 3)


class MunicipalTests(unittest.TestCase):
    def test_familias_de_adapter_documentadas(self):
        for familia in ("querido_diario", "diario_individual", "plataforma_compartilhada",
                        "api_municipal", "pdf_listing"):
            self.assertIn(familia, FAMILIAS_ADAPTER)
            self.assertTrue(FAMILIAS_ADAPTER[familia]["descricao"])
        disponiveis = adapters_disponiveis()
        self.assertTrue(disponiveis["querido_diario"]["implementado"])
        self.assertFalse(disponiveis["api_municipal"]["implementado"])

    def test_configuracao_vazia_nao_cria_cobertura(self):
        self.assertEqual(fontes_municipais_do_config(), [])

    def test_municipio_configurado_sem_url_fica_pendente(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "municipios.json"
            caminho.write_text(json.dumps({"municipios": [
                {"municipio": "São Paulo", "uf": "SP", "codigo_ibge": "3550308",
                 "adapter_family": "querido_diario", "habilitado": True}
            ]}), encoding="utf-8")
            fontes = fontes_municipais_do_config(str(caminho))
        self.assertEqual(len(fontes), 1)
        fonte = fontes[0]
        self.assertFalse(fonte.implementado)        # sem endpoint confirmado
        self.assertEqual(fonte.status, "nao_implementado")
        self.assertEqual(fonte.adapter_family, "querido_diario")
        self.assertEqual(fonte.uf, "SP")

    def test_municipio_habilitado_com_endpoint_vira_implementado(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "municipios.json"
            caminho.write_text(json.dumps({"municipios": [
                {"source_id": "municipal_sp_saopaulo", "municipio": "São Paulo", "uf": "SP",
                 "codigo_ibge": "3550308", "adapter_family": "querido_diario",
                 "url": "https://exemplo.org/api/gazettes", "habilitado": True}
            ]}), encoding="utf-8")
            fontes = fontes_municipais_do_config(str(caminho))
        fonte = fontes[0]
        self.assertTrue(fonte.implementado)
        self.assertEqual(fonte.status, "implementado")
        self.assertIn("AdapterQueridoDiario", fonte.collector)
        self.assertEqual(fonte.tipo_acesso, "agregador")

    def test_municipio_sem_familia_implementada_nao_e_habilitado(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "municipios.json"
            caminho.write_text(json.dumps({"municipios": [
                {"municipio": "Cidade Exemplo", "uf": "MG", "adapter_family": "pdf_listing",
                 "url": "https://exemplo.mg.gov.br/diario", "habilitado": True}
            ]}), encoding="utf-8")
            fontes = fontes_municipais_do_config(str(caminho))
        self.assertFalse(fontes[0].implementado)

    def test_codigo_ibge_deriva_uf_oficial(self):
        self.assertEqual(uf_do_codigo_ibge("3550308"), "SP")
        self.assertEqual(uf_do_codigo_ibge("5300108"), "DF")
        self.assertIsNone(uf_do_codigo_ibge(""))

    def test_uniao_registry_ve_municipio_do_config(self):
        """Registry com configuração municipal: a cidade aparece cadastrada."""
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "municipios.json"
            caminho.write_text(json.dumps({"municipios": [
                {"municipio": "São Paulo", "uf": "SP", "codigo_ibge": "3550308",
                 "adapter_family": "querido_diario"}
            ]}), encoding="utf-8")
            registro = registry_padrao()
            for fonte in fontes_municipais_do_config(str(caminho)):
                registro.registrar(fonte)
        municipais = registro.por_nivel("municipal")
        self.assertEqual(len(municipais), 1)
        self.assertEqual(municipais[0].municipio, "São Paulo")
        self.assertFalse(municipais[0].implementado)
        metricas = monitor(registro)["metricas"]
        self.assertEqual(metricas["fontes_nao_implementadas"],
                         metricas["fontes_totais"] - 3)


class EstadosHelpersTests(unittest.TestCase):
    def test_pendentes_e_implementados(self):
        registro = registry_padrao()
        self.assertEqual(len(estaduais_pendentes(registro)), 27)
        self.assertEqual(estaduais_implementados(registro), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
