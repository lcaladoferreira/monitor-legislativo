#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes do pipeline de Diários (FASE 2, 7, 8 e 14) — offline.

Cobrem normalização, deduplicação com histórico, alteração de conteúdo,
storage abstrato (raw + metadados) e a separação entre ingestão e classificação:
um item sem nenhum termo temático não é erro de ingestão, é item descartado.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from diarios.base import (FonteDiario, MetricasIngestao, ResultadoColeta,  # noqa: E402
                          chave_identidade, normalizar_item)
from diarios.classificacao import aplicar_classificacao, classificar_item  # noqa: E402
from diarios.dedup import Deduplicador, carregar_estado  # noqa: E402
from diarios.pipeline import PipelineDiarios  # noqa: E402
from diarios.registry import FonteCadastrada, RegistryFontes  # noqa: E402
from storage import LocalMetadataStore, LocalRawStorage  # noqa: E402


class FonteFalsa(FonteDiario):
    """Fonte offline que devolve exatamente os itens brutos declarados."""

    source_id = "falsa_federal"
    nome = "Diário Oficial de teste (fonte falsa)"
    nivel = "federal"
    poder = "todos"
    url = "https://exemplo.gov.br/diario"
    tipo_acesso = "json"
    formato = "json"
    collector = "tests.test_diarios_pipeline::FonteFalsa"
    modo_padrao = "integral"
    marcadores_estruturais = (r"diario",)

    def __init__(self, itens=None, erro=None, logger=print):
        super().__init__(logger=logger)
        self._itens = itens if itens is not None else []
        self._erro = erro

    def coletar(self, ctx, resultado):
        if self._erro:
            raise self._erro
        resultado.itens.extend(self._itens)
        resultado.metricas.itens_fonte = len(self._itens)
        resultado.canais_ok.append("canal de teste")
        resultado.modo_ingestao = "integral"
        resultado.cobertura_integral = True
        resultado.ultima_publicacao = "2026-09-25"
        return resultado


def item_bruto(titulo, url, texto=None, **extra):
    dados = {"titulo": titulo, "url_oficial": url, "data": "2026-09-25",
             "texto": texto, "coletado_em": "2026-09-26T09:00:00-03:00"}
    dados.update(extra)
    return dados


def montar_pipeline(itens, tmp, erro=None, fonte_id="falsa_federal"):
    registry = RegistryFontes()
    registro = FonteCadastrada(
        source_id=fonte_id, nome="Diário Oficial de teste", nivel="federal",
        url="https://exemplo.gov.br/diario", tipo_acesso="json", formato="json",
        collector="tests.test_diarios_pipeline::FonteFalsa", implementado=True,
        obrigatorio=True)
    registry.registrar(registro)
    coletor = FonteFalsa(itens=itens, erro=erro)
    coletor.source_id = fonte_id
    raw = LocalRawStorage(raiz=str(Path(tmp) / "raw"))
    metadata = LocalMetadataStore(caminho=str(Path(tmp) / "indice.json"))
    pipeline = PipelineDiarios(registry, {fonte_id: coletor}, raw_storage=raw,
                               metadata_store=metadata,
                               logger=lambda *_: None)
    return pipeline, registry, raw, metadata, registro


class NormalizacaoTests(unittest.TestCase):
    def test_campos_ausentes_ficam_ausentes(self):
        fonte = FonteFalsa()
        item = normalizar_item(item_bruto("Ato sem campos", "https://exemplo.gov.br/a/1"), fonte)
        self.assertIsNone(item["secao"])
        self.assertIsNone(item["edicao"])
        self.assertIsNone(item["tipo_ato"])
        self.assertIsNone(item["orgao"])
        self.assertIsNone(item["id_oficial"])
        self.assertIsNone(item["edicao_extraordinaria"])
        self.assertEqual(item["nivel"], "federal")
        self.assertEqual(item["jurisdicao"], "federal")
        self.assertTrue(item["hash_conteudo"].startswith("sha1:"))
        self.assertTrue(item["chave"])

    def test_hierarquia_em_texto_vira_lista(self):
        fonte = FonteFalsa()
        item = normalizar_item(item_bruto("Ato", "https://exemplo.gov.br/a/2",
                                          hierarquia="Ministério X > Secretaria Y"), fonte)
        self.assertEqual(item["hierarquia"], ["Ministério X", "Secretaria Y"])

    def test_identidade_prefere_identificador_oficial(self):
        fonte = FonteFalsa()
        a = normalizar_item(item_bruto("Ato", "https://exemplo.gov.br/a/3",
                                       id_oficial="dou:123"), fonte)
        b = normalizar_item(item_bruto("Ato renomeado", "https://exemplo.gov.br/a/3",
                                       id_oficial="dou:123"), fonte)
        self.assertEqual(a["chave"], b["chave"])
        self.assertEqual(a["chave"], "falsa_federal:oficial:dou:123")

    def test_identidade_estavel_quando_so_o_texto_muda(self):
        """A identidade não pode depender do hash: senão a alteração some do histórico."""
        base = {"url_oficial": "https://exemplo.gov.br/a/4", "titulo": "Resolução 1",
                "data": "2026-09-25", "texto": "texto original"}
        alterado = dict(base, texto="texto corrigido")
        self.assertEqual(chave_identidade("fonte", base), chave_identidade("fonte", alterado))

    def test_sem_url_nao_entra(self):
        fonte = FonteFalsa()
        item = normalizar_item({"titulo": "Sem URL"}, fonte)
        self.assertIsNone(item["url_oficial"])


class DeduplicacaoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.estado = None

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _itens(self):
        return [
            item_bruto("Resolução sobre inteligência artificial",
                       "https://exemplo.gov.br/a/10", "Texto sobre IA e proteção de dados."),
            item_bruto("Portaria de rotina administrativa",
                       "https://exemplo.gov.br/a/11", "Designação de servidor."),
        ]

    def test_fluxo_novo_inalterado_alterado_com_historico(self):
        store = LocalMetadataStore(caminho=str(Path(self.tmp) / "indice.json"))
        fonte = FonteFalsa()
        item = normalizar_item(item_bruto("Resolução sobre IA",
                                          "https://exemplo.gov.br/a/10",
                                          "texto original"), fonte)
        dedup = Deduplicador(metadata_store=store)
        primeiro = dedup.processar(item, registrar_relevante=False)
        self.assertEqual(primeiro.estado, "novo")
        self.assertTrue(primeiro.primeira_deteccao)

        # Repetir o mesmo item na MESMA execução é duplicata (dedup intra-run).
        segundo = dedup.processar(dict(item), registrar_relevante=False)
        self.assertEqual(segundo.estado, "duplicado")

        # Execução seguinte (mesmo índice, hash igual) → inalterado.
        item2 = normalizar_item(item_bruto("Resolução sobre IA",
                                           "https://exemplo.gov.br/a/10",
                                           "texto original"), fonte)
        dedup2 = Deduplicador(metadata_store=store)
        estado = dedup2.processar(item2, registrar_relevante=False)
        self.assertEqual(estado.estado, "inalterado")
        self.assertEqual(estado.hash_anterior, estado.hash_atual)

        # Conteúdo mudou → alterado, com hash anterior e novo preservados.
        item3 = normalizar_item(item_bruto("Resolução sobre IA",
                                           "https://exemplo.gov.br/a/10",
                                           "texto corrigido pelo órgão"), fonte)
        dedup3 = Deduplicador(metadata_store=store)
        alterado = dedup3.processar(item3, registrar_relevante=False)
        self.assertEqual(alterado.estado, "alterado")
        self.assertNotEqual(alterado.hash_anterior, alterado.hash_atual)
        self.assertTrue(alterado.ultima_alteracao)
        self.assertEqual(alterado.primeira_deteccao, estado.primeira_deteccao)
        self.assertEqual(dedup3.estado["itens_relevantes"], {})  # nada relevante ainda

    def test_sem_indice_local_so_relevante_sobrevive_entre_execucoes(self):
        """Limitação documentada: sem índice local, o estado versionado guarda só os
        itens relevantes/de revisão (o corpus integral não vai para o Git)."""
        fonte = FonteFalsa()
        item = normalizar_item(item_bruto("Portaria de rotina",
                                          "https://exemplo.gov.br/a/11", "Designação."), fonte)
        dedup = Deduplicador()
        self.assertEqual(dedup.processar(item, registrar_relevante=False).estado, "novo")
        seguinte = Deduplicador(estado=dedup.estado)
        self.assertEqual(seguinte.processar(dict(item), registrar_relevante=False).estado,
                         "novo")
        self.assertEqual(dedup.estado["itens_relevantes"], {})

    def test_relevante_registrado_com_historico_versionado(self):
        fonte = FonteFalsa()
        dedup = Deduplicador(estado={"itens_relevantes": {}, "edicoes": {}})
        item = normalizar_item(item_bruto("Resolução sobre IA",
                                          "https://exemplo.gov.br/a/12", "IA"), fonte)
        aplicar_classificacao(item, classificar_item(item))
        resultado = dedup.processar(item, registrar_relevante=False)
        dedup.registrar_relevante(item, resultado)
        registro = dedup.estado["itens_relevantes"][item["chave"]]
        self.assertEqual(registro["relevancia"], "forte")
        self.assertIn("primeira_deteccao", registro)
        self.assertEqual(registro["hash_atual"], item["hash_conteudo"])
        primeiro_hash = registro["hash_atual"]

        item2 = normalizar_item(item_bruto("Resolução sobre IA",
                                           "https://exemplo.gov.br/a/12", "IA e biometria"), fonte)
        aplicar_classificacao(item2, classificar_item(item2))
        dedup2 = Deduplicador(estado=dedup.estado)
        resultado2 = dedup2.processar(item2, registrar_relevante=False)
        dedup2.registrar_relevante(item2, resultado2)
        registro2 = dedup2.estado["itens_relevantes"][item2["chave"]]
        self.assertEqual(registro2["hash_anterior"], primeiro_hash)
        self.assertEqual(registro2["hash_atual"], item2["hash_conteudo"])
        self.assertTrue(registro2["historico"])
        self.assertEqual(registro2["historico"][-1]["campo"], "texto")

    def test_duplicado_na_mesma_execucao_conta_uma_vez(self):
        fonte = FonteFalsa()
        a = normalizar_item(item_bruto("Ato X", "https://exemplo.gov.br/a/13"), fonte)
        b = normalizar_item(item_bruto("Ato X", "https://exemplo.gov.br/a/13"), fonte)
        dedup = Deduplicador()
        self.assertEqual(dedup.processar(a).estado, "novo")
        self.assertEqual(dedup.processar(b).estado, "duplicado")

    def test_digest_da_edicao_registra_reingestao(self):
        fonte = FonteFalsa()
        dedup = Deduplicador()
        itens = [normalizar_item(item_bruto("Ato 1", "https://exemplo.gov.br/a/14"), fonte)]
        primeira = dedup.registrar_edicao("falsa_federal", "2026-09-25", itens)
        self.assertEqual(primeira["itens"], 1)
        itens2 = itens + [normalizar_item(item_bruto("Ato 2", "https://exemplo.gov.br/a/15"), fonte)]
        segunda = dedup.registrar_edicao("falsa_federal", "2026-09-25", itens2)
        self.assertIn("reingestao", segunda)
        self.assertTrue(dedup.edicao_registrada("falsa_federal", "2026-09-25"))

    def test_estado_ilegivel_nao_quebra(self):
        caminho = Path(self.tmp) / "estado.json"
        caminho.write_text("{isso não é json", encoding="utf-8")
        self.assertIsNone(carregar_estado(str(caminho)))


class StoragesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_raw_storage_local_grava_e_le(self):
        raw = LocalRawStorage(raiz=str(Path(self.tmp) / "raw"))
        self.assertFalse(raw.exists("dou", "2026-09-25"))
        referencia = raw.save("dou", "2026-09-25", [{"titulo": "Ato"}],
                              {"modo_ingestao": "integral"},
                              arquivos={"pagina.html": "<html>ok</html>"})
        self.assertTrue(referencia)
        self.assertTrue(raw.exists("dou", "2026-09-25"))
        lido = raw.get("dou", "2026-09-25")
        self.assertEqual(lido["itens"][0]["titulo"], "Ato")
        self.assertEqual(lido["modo_ingestao"], "integral")
        self.assertEqual(len(lido["arquivos_fonte"]), 1)
        self.assertEqual(len(raw.listar("dou")), 1)
        self.assertFalse(raw.descricao()["versionado_no_git"])

    def test_metadata_store_upsert_com_historico(self):
        store = LocalMetadataStore(caminho=str(Path(self.tmp) / "indice.json"))
        self.assertFalse(store.exists("k1"))
        r1 = store.upsert({"chave": "k1", "hash_conteudo": "sha1:a",
                           "ultima_verificacao": "2026-09-25T10:00:00-03:00"})
        self.assertTrue(r1["novo"])
        r2 = store.upsert({"chave": "k1", "hash_conteudo": "sha1:b",
                           "ultima_verificacao": "2026-09-26T10:00:00-03:00"})
        self.assertTrue(r2["alterado"])
        self.assertEqual(r2["registro"]["hash_anterior"], "sha1:a")
        self.assertEqual(r2["registro"]["hash_atual"], "sha1:b")
        self.assertTrue(store.exists("k1"))
        self.assertEqual(store.find("k1")["hash_conteudo"], "sha1:b")
        self.assertEqual(len(store.todos()), 1)
        self.assertEqual(store.salvar(), 1)
        recarregado = LocalMetadataStore(caminho=str(Path(self.tmp) / "indice.json"))
        self.assertEqual(recarregado.find("k1")["hash_anterior"], "sha1:a")

    def test_backend_desconhecido_falha_explicitamente(self):
        from storage import obter_raw_storage
        from storage.base import StorageError
        with self.assertRaises(StorageError):
            obter_raw_storage("inexistente")

    def test_object_storage_nao_disponivel_nao_grava(self):
        from storage import ObjectStorageRaw
        from storage.base import BackendIndisponivel
        with self.assertRaises(BackendIndisponivel):
            ObjectStorageRaw().save("dou", "2026-09-25", [])


class ClassificacaoSeparadaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_metricas_independentes_da_classificacao(self):
        itens = [
            item_bruto("RESOLUÇÃO sobre inteligência artificial e biometria",
                       "https://exemplo.gov.br/a/20", "Governança de IA e LGPD."),
            item_bruto("PORTARIA de designação de servidor",
                       "https://exemplo.gov.br/a/21", "Designa servidor para função."),
            item_bruto("EDITAL de licitação de material de escritório",
                       "https://exemplo.gov.br/a/22", "Compra de papel."),
            item_bruto("Extrato de contrato de tecnologia",
                       "https://exemplo.gov.br/a/23", "Contratação de software."),
        ]
        pipeline, registry, raw, metadata, registro = montar_pipeline(itens, self.tmp)
        relatorios = pipeline.executar([registro.source_id], dias=1,
                                       ctx_factory=lambda f, c: _ctx_falso())
        relatorio = relatorios[registro.source_id]
        metricas = relatorio.metricas
        self.assertEqual(metricas.itens_fonte, 4)
        self.assertEqual(metricas.itens_normalizados, 4)
        self.assertEqual(metricas.itens_classificados, 4)
        self.assertEqual(metricas.itens_relevantes, 1)
        self.assertEqual(metricas.itens_revisao, 1)      # "software/tecnologia" → revisar
        self.assertEqual(metricas.itens_descartados, 2)
        self.assertEqual(metricas.duplicados, 0)
        self.assertEqual(metricas.falhas_parse, 0)
        # Descarte temático NÃO é falha de ingestão.
        self.assertEqual(relatorio.status, "ok")
        self.assertFalse(relatorio.coleta.erros)

    def test_item_sem_url_conta_como_falha_de_parse(self):
        itens = [item_bruto("Ato sem URL", None), item_bruto("Ato bom", "https://exemplo.gov.br/a/30")]
        pipeline, registry, raw, metadata, registro = montar_pipeline(itens, self.tmp)
        relatorio = pipeline.executar([registro.source_id],
                                      ctx_factory=lambda f, c: _ctx_falso())[registro.source_id]
        self.assertEqual(relatorio.metricas.itens_fonte, 2)
        self.assertEqual(relatorio.metricas.itens_normalizados, 1)
        self.assertEqual(relatorio.metricas.falhas_parse, 1)
        self.assertEqual(relatorio.metricas.itens_classificados, 1)

    def test_publicaveis_no_formato_do_dataset_e_raw_gravado(self):
        itens = [item_bruto("RESOLUÇÃO sobre reconhecimento facial",
                            "https://exemplo.gov.br/a/31", "Uso de reconhecimento facial.")]
        pipeline, registry, raw, metadata, registro = montar_pipeline(itens, self.tmp)
        relatorio = pipeline.executar([registro.source_id],
                                      ctx_factory=lambda f, c: _ctx_falso())[registro.source_id]
        legado = relatorio.para_resultado_legado()
        self.assertEqual(legado["orgao"], registro.source_id)
        self.assertTrue(legado["obrigatoria"])
        self.assertEqual(len(legado["itens"]), 1)
        item = legado["itens"][0]
        for campo in ("id", "titulo", "descricao", "data", "url_oficial", "fonte",
                      "relevancia", "grupos_tematicos", "hash_conteudo"):
            self.assertIn(campo, item)
        self.assertIn("reconhecimento facial", item["grupos_tematicos"])
        self.assertEqual(item["dedup_estado"], "novo")
        saude = legado["saude"]
        self.assertEqual(saude["itens_consultados"], 1)
        self.assertEqual(saude["itens_relevantes"], 1)
        self.assertEqual(saude["diarios"]["modo_ingestao"], "integral")
        # raw storage guardado e índice de metadados populado
        self.assertTrue(raw.exists(registro.source_id, "2026-09-25"))
        self.assertTrue(metadata.salvar() >= 1)

    def test_fonte_indisponivel_marca_falha_e_nao_inventa(self):
        pipeline, registry, raw, metadata, registro = montar_pipeline(
            [], self.tmp, erro=RuntimeError("fonte fora do ar"))
        relatorio = pipeline.executar([registro.source_id],
                                      ctx_factory=lambda f, c: _ctx_falso())[registro.source_id]
        self.assertEqual(relatorio.status, "falha")
        self.assertEqual(relatorio.status_registry, "falha")
        self.assertTrue(relatorio.erro_fatal)
        self.assertEqual(relatorio.metricas.itens_fonte, 0)
        self.assertEqual(relatorio.itens_publicaveis, [])

    def test_cobertura_reflete_estado_das_fontes(self):
        itens = [item_bruto("RESOLUÇÃO sobre IA", "https://exemplo.gov.br/a/40", "IA")]
        pipeline, registry, raw, metadata, registro = montar_pipeline(itens, self.tmp)
        pipeline.executar([registro.source_id], ctx_factory=lambda f, c: _ctx_falso())
        cobertura = pipeline.cobertura()
        self.assertEqual(cobertura["metricas"]["fontes_totais"], 1)
        self.assertEqual(cobertura["metricas"]["fontes_implementadas"], 1)
        self.assertEqual(cobertura["metricas"]["fontes_ok"], 1)
        fonte = cobertura["fontes"][registro.source_id]
        for campo in ("source_id", "jurisdicao", "nivel", "ultima_tentativa",
                      "ultima_coleta_ok", "ultima_publicacao_detectada",
                      "itens_coletados", "erro", "status", "duracao", "layout_changed"):
            self.assertIn(campo, fonte)
        self.assertEqual(fonte["itens_coletados"], 1)
        self.assertEqual(fonte["ultima_publicacao_detectada"], "2026-09-25")

    def test_metricas_ingestao_do_contrato(self):
        metricas = MetricasIngestao(itens_fonte=10, itens_normalizados=9,
                                    itens_descartados=7)
        dados = metricas.para_dict()
        for campo in ("itens_fonte", "itens_normalizados", "itens_classificados",
                      "itens_relevantes", "itens_descartados", "itens_revisao",
                      "duplicados", "falhas_parse"):
            self.assertIn(campo, dados)
        self.assertEqual(dados["itens_invalidos"], 1)


def _ctx_falso():
    from diarios.base import ContextoDiario
    return ContextoDiario("teste", timeout_s=30, logger=lambda *_: None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
