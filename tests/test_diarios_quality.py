#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes de descoberta × classificação, qualidade de texto e fallback visual
(FASE 3, 9, 10 e 14) — nenhum deles acessa a rede.

Protegem três decisões do projeto:

  · a busca por assunto (DISCOVERY_TERMS) continua funcionando como antes, mas a
    classificação (CLASSIFICATION_PATTERNS) é aplicada **depois** da coleta e
    cobre todos os grupos temáticos exigidos, com a mesma semântica de
    relevância (forte/revisar/nada) já publicada;
  · `evaluate_text_quality()` decide se um texto está bom, degradado ou perdido;
  · o fallback visual existe apenas como interface documentada, sem PyTorch,
    sem Qwen, sem FAISS e sem dependência pesada.
"""
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from diarios.classificacao import (classificar_item, grupos_disponiveis,  # noqa: E402
                                  padroes_do_grupo, resumo_regras, termos_descoberta)
from diarios.quality import (MIN_CARACTERES, QualidadeTexto,  # noqa: E402
                             evaluate_text_quality, precisa_fallback_visual)
from sources import base as base  # noqa: E402
from visual_fallback import (PixelRAGFallback, VisualFallbackNaoImplementado,  # noqa: E402
                             decidir_pipeline, status_visual_fallback)

# grupo obrigatório (nome usado no código) → texto de exemplo que deve disparar
GRUPOS_OBRIGATORIOS = {
    "inteligência artificial": "dispõe sobre inteligência artificial",
    "IA generativa": "regulamenta a inteligência artificial generativa",
    "machine learning": "uso de machine learning no setor público",
    "deep learning": "modelos de deep learning",
    "modelo de linguagem": "modelo de linguagem de grande porte",
    "LLM": "treinamento de LLM no serviço público",
    "redes neurais": "treinamento de redes neurais",
    "decisão automatizada": "decisão automatizada sobre benefícios",
    "decisão algorítmica": "revisão de decisões algorítmicas",
    "governança de IA": "marco de governança de IA",
    "governança algorítmica": "governança algorítmica de sistemas",
    "proteção de dados": "proteção de dados pessoais",
    "LGPD": "aplicação da LGPD",
    "ANPD": "resolução da ANPD",
    "biometria": "coleta de dados biométricos",
    "reconhecimento facial": "uso de reconhecimento facial",
    "deepfake": "combate a deepfakes",
    "conteúdo sintético": "identificação de conteúdo sintético",
    "plataformas digitais": "regulação de plataformas digitais",
    "big tech": "responsabilidades das big techs",
    "moderação algorítmica": "moderação algorítmica de conteúdo",
    "sandbox regulatório": "criação de sandbox regulatório",
    "soberania digital": "soberania digital nacional",
    "data center": "instalação de data center",
    "computação em nuvem": "computação em nuvem",
    "semicondutores": "cadeia de semicondutores",
    "infraestrutura digital": "infraestrutura digital crítica",
    "cibersegurança": "segurança cibernética",
    "IoT": "dispositivos de internet das coisas",
    "automação": "automação de processos administrativos",
}


TEXTO_BOM = ("Art. 1º Fica instituído o programa de governança de inteligência "
             "artificial no âmbito da administração pública federal, com objetivos "
             "de transparência, prestação de contas e avaliação de riscos. ") * 3


def classificar(texto):
    return classificar_item({"titulo": texto, "texto": texto})


class DescobrimentoEClassificacaoTests(unittest.TestCase):
    def test_termos_de_descobrimento_preservados(self):
        """A lista usada nas consultas por assunto continua a mesma das fontes."""
        self.assertTrue(base.DISCOVERY_TERMS)
        self.assertIs(base.TOPICOS_BUSCA, base.DISCOVERY_TERMS)
        self.assertEqual(termos_descoberta(), list(base.DISCOVERY_TERMS))
        for termo in base.DISCOVERY_TERMS:
            self.assertEqual(termo, termo.strip())
        # O DOU integral não usa busca temática na origem: a lista é do fallback.
        self.assertIn("inteligência artificial", base.DISCOVERY_TERMS)

    def test_todos_os_grupos_obrigatorios_existem_e_detectam(self):
        disponiveis = set(grupos_disponiveis())
        for grupo, exemplo in GRUPOS_OBRIGATORIOS.items():
            self.assertIn(grupo, disponiveis, grupo)
            self.assertTrue(padroes_do_grupo(grupo), grupo)
            self.assertIn(grupo, classificar(exemplo).grupos_tematicos,
                          f"{grupo}: {exemplo!r}")

    def test_semantica_de_relevancia_intacta(self):
        """A separação descobrimento/classificação não muda a decisão já publicada."""
        forte = base.classificar_relevancia(
            "Dispõe sobre inteligência artificial e proteção de dados pessoais.")
        self.assertEqual(forte, "forte")
        self.assertEqual(base.classificar_relevancia("Sistema de governança e automação"),
                         "forte")
        self.assertEqual(base.classificar_relevancia("Investimento em tecnologia"),
                         "revisar")
        self.assertEqual(base.classificar_relevancia("Aviso de manutenção do sistema"), None)
        self.assertIsNone(base.classificar_relevancia(None))
        self.assertIsNone(base.classificar_relevancia(""))

    def test_classificacao_com_trilha_de_auditoria(self):
        resultado = classificar("Resolução sobre reconhecimento facial e LGPD")
        self.assertEqual(resultado.relevancia, "forte")
        self.assertIn("reconhecimento facial", resultado.grupos_tematicos)
        self.assertIn("LGPD", resultado.grupos_tematicos)
        self.assertTrue(resultado.padroes_detectados)
        self.assertTrue(resultado.relevante)
        self.assertFalse(resultado.descartado)

    def test_item_fora_do_tema_e_descartado_sem_erro(self):
        resultado = classificar("Nomeia servidora para cargo em comissão.")
        self.assertIsNone(resultado.relevancia)
        self.assertEqual(resultado.grupos_tematicos, [])
        self.assertTrue(resultado.descartado)
        self.assertFalse(resultado.revisao)

    def test_resumo_de_regras_auditavel(self):
        resumo = resumo_regras()
        self.assertEqual(resumo["termos_descoberta"], list(base.DISCOVERY_TERMS))
        self.assertEqual(resumo["total_grupos"], len(base.CLASSIFICATION_GROUPS))
        self.assertEqual(resumo["total_padroes"], len(base.CLASSIFICATION_PATTERNS))
        self.assertGreaterEqual(resumo["total_grupos"], len(GRUPOS_OBRIGATORIOS))

    def test_classificacao_usa_metadados_do_item(self):
        item = {"titulo": "Portaria nº 1", "orgao": "Autoridade Nacional de Proteção de Dados",
                "texto": "Dispõe sobre procedimentos internos."}
        self.assertEqual(classificar_item(item).relevancia, "forte")


class QualidadeDeTextoTests(unittest.TestCase):
    TEXTO_BOM = TEXTO_BOM

    def test_texto_bom(self):
        qualidade = evaluate_text_quality(self.TEXTO_BOM)
        self.assertEqual(qualidade.estado, "good")
        self.assertEqual(qualidade.motivos, [])
        self.assertTrue(qualidade.utilizavel)
        self.assertFalse(qualidade.aciona_visual)
        self.assertGreater(qualidade.metricas["caracteres"], MIN_CARACTERES)

    def test_texto_vazio_ou_curto_demais(self):
        vazio = evaluate_text_quality("")
        self.assertEqual(vazio.estado, "failed")
        self.assertIn("texto_vazio", vazio.motivos)
        self.assertTrue(vazio.aciona_visual)
        self.assertIsInstance(evaluate_text_quality(None), QualidadeTexto)
        curto = evaluate_text_quality("Ver PDF.")
        self.assertEqual(curto.estado, "failed")
        self.assertIn("texto_curto", curto.motivos)

    def test_encoding_corrompido_e_caracteres_invalidos(self):
        ruim = "Ã© Ã§ Ã£ " * 60
        qualidade = evaluate_text_quality(ruim)
        self.assertEqual(qualidade.estado, "failed")
        self.assertTrue(any("alfabetica" in m or "encoding" in m or "invalid" in m
                            for m in qualidade.motivos))

        invalido = ("Art. 1º " * 40) + "\ufffd" * 60
        qualidade2 = evaluate_text_quality(invalido)
        self.assertEqual(qualidade2.estado, "failed")
        self.assertIn("caracteres_invalidos", qualidade2.motivos)
        self.assertGreater(qualidade2.metricas["razao_invalidos"], 0.02)

    def test_fragmentacao_e_repeticao_anormal(self):
        fragmentado = "\n".join(["a", "b", "c", "d"] * 40)
        qualidade = evaluate_text_quality(fragmentado)
        self.assertIn(qualidade.estado, ("degraded", "failed"))
        self.assertTrue(any("fragmentacao" in m for m in qualidade.motivos))

        repetido = "PORTARIA " * 200
        qualidade2 = evaluate_text_quality(repetido)
        self.assertIn(qualidade2.estado, ("degraded", "failed"))
        self.assertTrue(any("repeticao" in m or "vocabulario" in m
                            for m in qualidade2.motivos))

    def test_pagina_sem_texto(self):
        qualidade = evaluate_text_quality("[Página sem texto]")
        self.assertEqual(qualidade.estado, "failed")
        self.assertTrue(qualidade.aciona_visual)

    def test_regra_de_acionamento_visual(self):
        bom = evaluate_text_quality(self.TEXTO_BOM)
        self.assertFalse(precisa_fallback_visual(bom)["acionar"])
        ruim = evaluate_text_quality("Art. 1º " + "abc " * 5)
        self.assertTrue(precisa_fallback_visual(ruim)["acionar"])
        escaneado = precisa_fallback_visual(None, pdf_escaneado=True)
        self.assertTrue(escaneado["acionar"])
        self.assertIn("sem_quality_gate", escaneado["motivos"])
        tabela = precisa_fallback_visual(bom, tabela_complexa=True)
        self.assertTrue(tabela["acionar"])


class VisualFallbackTests(unittest.TestCase):
    def test_pixelrag_e_apenas_stub_desligado(self):
        stub = PixelRAGFallback()
        self.assertFalse(stub.disponivel())
        self.assertFalse(stub.descricao()["ativa_no_pipeline"])
        with self.assertRaises(VisualFallbackNaoImplementado):
            stub.extrair(io.BytesIO(b"%PDF-1.4"), paginas=[1])
        info = status_visual_fallback()
        self.assertFalse(info["implementado"])
        self.assertFalse(info["ativa_no_pipeline"])
        self.assertIn("PyTorch", info["observacao"])

    def test_nenhuma_dependencia_pesada(self):
        import visual_fallback.pixelrag as pixelrag
        fonte = Path(pixelrag.__file__).read_text(encoding="utf-8")
        for proibido in ("import torch", "import faiss", "import transformers",
                         "from qwen", "import numpy"):
            self.assertNotIn(proibido, fonte)
        self.assertIsNone(sys.modules.get("torch"))
        self.assertIsNone(sys.modules.get("faiss"))
        self.assertIsNone(sys.modules.get("transformers"))

    def test_regra_estruturado_texto_visual(self):
        self.assertEqual(decidir_pipeline(estruturado_disponivel=True)["etapa"],
                         "estruturado")
        self.assertEqual(decidir_pipeline(texto=TEXTO_BOM)["etapa"], "texto")
        decisao = decidir_pipeline(pdf=True, texto="")
        self.assertEqual(decisao["etapa"], "visual")
        self.assertIn("pdf_sem_camada_textual", decisao["motivos"])
        self.assertFalse(decisao["visual_disponivel"])   # stub: nada é executado
        # Sem fonte estruturada, sem texto e sem sinal explícito: nada a extrair.
        from diarios.quality import QualidadeTexto
        indisponivel = decidir_pipeline(texto="", qualidade=QualidadeTexto("good", [], {}))
        self.assertEqual(indisponivel["etapa"], "indisponivel")
        self.assertEqual(indisponivel["motivos"], ["sem_texto_e_sem_fonte_estruturada"])
        # Texto vazio sem quality gate explícito: a extração falhou → visual (futuro).
        self.assertEqual(decidir_pipeline(texto="")["etapa"], "visual")

    def test_texto_bom_nunca_aciona_visual(self):
        decisao = decidir_pipeline(texto=TEXTO_BOM)
        self.assertEqual(decisao["etapa"], "texto")
        self.assertEqual(decisao["motivos"], ["extracao_textual_ok"])


class SemDependenciaDeRedeTests(unittest.TestCase):
    def test_modulos_de_diarios_nao_fazem_io_no_import(self):
        for relativo in ("diarios/dou.py", "diarios/pipeline.py", "diarios/registry.py",
                         "diarios/coverage.py", "diarios/quality.py",
                         "visual_fallback/__init__.py", "storage/__init__.py"):
            fonte = (ROOT / "scripts" / relativo).read_text(encoding="utf-8")
            self.assertNotIn("urlopen(", fonte, relativo)
            self.assertNotIn("requests.", fonte, relativo)


if __name__ == "__main__":
    unittest.main(verbosity=2)
