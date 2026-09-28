#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integração `update_sources.py` ↔ pipeline de Diários (FASES 15–16).

Estes testes cobrem a costura que liga a ingestão integral do DOU ao fluxo
principal (o que grava `atos.json`/`updates.json`), **sem rede**: o subprocesso é
substituído por um duplo que escreve os mesmos arquivos que o CLI real escreve
(`--json` e `--json-legado`). O que se verifica aqui:

  · o payload legado volta com itens, saúde e telemetria (round-trip JSON);
  · falha do pipeline devolve `_resultado_falha` com motivo auditável — nunca
    sucesso silencioso;
  · quando a integral cai, a busca temática assume e **deixa rastro**
    (`caminho_ingestao`/`saude.diarios`), sem declarar cobertura integral;
  · `MONITOR_DOU_DIARIOS=0` restaura o caminho antigo (rollback seguro);
  · `executar_todas` não acrescenta fonte fictícia à saúde monitorada (o gate
    `check_collection.py` continua válido).
"""
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

BASE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE))

import update_sources as us  # noqa: E402


def _saude_ok(orgao="dou", itens=2):
    return {
        "nome": "DOU", "status": "ok", "ultima_tentativa": "2026-09-25T10:00:00-03:00",
        "ultima_execucao_ok": "2026-09-25T10:00:00-03:00", "itens_consultados": itens,
        "itens_relevantes": itens, "itens_descartados": 0, "itens_duplicados": 0,
        "revisao_pendente": 0, "novidades": itens, "erros": 0, "duracao_segundos": 12.0,
        "endpoints": ["https://www.in.gov.br/leiturajornal?data=25-09-2026&secao=do1"],
        "canais_ok": ["edição integral do1"], "canais_falhos": [],
        "canais_falhos_obrigatorios": [], "canais_opcionais_falhos": [],
        "erro_detalhe": None,
        "diarios": {
            "modo_ingestao": "integral", "cobertura_integral": True,
            "fallback_usado": False, "layout_changed": False,
            "metricas_ingestao": {"itens_fonte": 120, "itens_normalizados": 120,
                                  "itens_classificados": 120, "itens_relevantes": itens,
                                  "itens_descartados": 118, "itens_revisao": 0,
                                  "duplicados": 0, "falhas_parse": 0},
        },
    }


def _payload(orgao="dou", itens=2):
    return {
        orgao: {
            "orgao": orgao, "nome": "DOU", "obrigatoria": True,
            "itens": [{"id": f"dou:oficial:dou:734{n:06d}", "titulo": f"Ato {n}",
                       "data": "2026-09-25", "url_oficial":
                       f"https://www.in.gov.br/web/dou/-/ato-{n}",
                       "relevancia": "forte", "texto_hash": f"h{n}"} for n in range(itens)],
            "saude": _saude_ok(orgao, itens),
            "http": {"chamadas": 4, "falhas": 0, "cache": 0, "tempo_total": 3.2,
                     "por_endpoint": {}},
            "erro_fatal": None,
            "diarios": {"source_id": orgao, "nivel": "federal", "jurisdicao": "federal",
                        "modo_ingestao": "integral", "cobertura_integral": True,
                        "itens_publicaveis": itens},
        }
    }


class _SubprocessoFalso:
    """Duplo de `_executar_cmd` que escreve os arquivos pedidos pelo CLI."""

    def __init__(self, payload, relatorio=None, returncode=0):
        self.payload = payload
        self.relatorio = relatorio if relatorio is not None else {"cobertura": {"fontes_ok": 1}}
        self.returncode = returncode
        self.chamadas = []

    def __call__(self, cmd, timeout_s, env=None):
        self.chamadas.append(list(cmd))
        if self.payload is not None:
            destino = pathlib.Path(cmd[cmd.index("--json-legado") + 1])
            destino.write_text(json.dumps(self.payload, ensure_ascii=False), encoding="utf-8")
        if self.relatorio is not None:
            destino = pathlib.Path(cmd[cmd.index("--json") + 1])
            destino.write_text(json.dumps(self.relatorio, ensure_ascii=False), encoding="utf-8")
        return us._Processo(self.returncode, b"", b"")


class ExecutarDiariosFonteTests(unittest.TestCase):
    def test_payload_legado_volta_com_itens_e_saude(self):
        falso = _SubprocessoFalso(_payload())
        with mock.patch.object(us, "_executar_cmd", falso):
            dados = us.executar_diarios_fonte("dou", timeout_s=5, logger=lambda *_: None)
        self.assertEqual(dados["orgao"], "dou")
        self.assertEqual(len(dados["itens"]), 2)
        self.assertEqual(dados["saude"]["status"], "ok")
        self.assertEqual(dados["caminho_ingestao"], "diarios_integral")
        self.assertIn("relatorio_diarios", dados)
        self.assertTrue(dados["duracao_subprocesso"] >= 0)
        cmd = falso.chamadas[0]
        self.assertIn("--json-legado", cmd)
        self.assertIn(us.UPDATE_DIARIOS, cmd)

    def test_falha_do_pipeline_nunca_vira_sucesso(self):
        falso = _SubprocessoFalso(payload=None, relatorio=None, returncode=2)
        with mock.patch.object(us, "_executar_cmd", falso):
            dados = us.executar_diarios_fonte("dou", timeout_s=5, logger=lambda *_: None)
        self.assertEqual(dados["saude"]["status"], "falha")
        self.assertEqual(dados["itens"], [])
        self.assertIn("sem resultado para 'dou'", dados["saude"]["erro_detalhe"])

    def test_timeout_do_subprocesso_e_registrado(self):
        def estoura(cmd, timeout_s, env=None):
            raise us.subprocess.TimeoutExpired(cmd, timeout_s)

        antes = set(pathlib.Path(tempfile.gettempdir()).glob("diarios_dou_*.json"))
        with mock.patch.object(us, "_executar_cmd", estoura):
            dados = us.executar_diarios_fonte("dou", timeout_s=5, logger=lambda *_: None)
        self.assertEqual(dados["saude"]["status"], "falha")
        self.assertIn("não terminou", dados["saude"]["erro_detalhe"])
        # os temporários desta execução não ficam para trás
        depois = set(pathlib.Path(tempfile.gettempdir()).glob("diarios_dou_*.json"))
        self.assertEqual(depois - antes, set())

    def test_dry_run_e_repassado_ao_pipeline(self):
        falso = _SubprocessoFalso(_payload())
        with mock.patch.object(us, "_executar_cmd", falso):
            us.executar_diarios_fonte("dou", timeout_s=5, logger=lambda *_: None, dry_run=True)
        self.assertIn("--dry-run", falso.chamadas[0])

    def test_timeout_da_ingestao_integral_tem_piso_proprio(self):
        """A edição integral é mais cara que uma listagem: não herda timeout curto.

        Sem piso, um `MONITOR_FONTES_TIMEOUT_S` baixo estrangulava a ingestão
        integral e a fonte caía sempre no fallback (mesmo com a integral sadia).
        """
        falso = _SubprocessoFalso(_payload())
        with mock.patch.object(us, "_executar_cmd", falso):
            us.executar_diarios_fonte("dou", timeout_s=30, logger=lambda *_: None)
        cmd = falso.chamadas[0]
        self.assertEqual(int(cmd[cmd.index("--timeout") + 1]), us.DIARIOS_TIMEOUT_S)
        # um timeout maior pedido pelo chamador é respeitado
        with mock.patch.object(us, "_executar_cmd", falso):
            us.executar_diarios_fonte("dou", timeout_s=us.DIARIOS_TIMEOUT_S + 60,
                                      logger=lambda *_: None)
        cmd = falso.chamadas[1]
        self.assertEqual(int(cmd[cmd.index("--timeout") + 1]), us.DIARIOS_TIMEOUT_S + 60)

    def test_coletor_historico_roda_sem_reentrar_no_pipeline_de_diarios(self):
        """O subprocesso do fallback não pode reexecutar a ingestão integral.

        Sem `MONITOR_DOU_DIARIOS=0` no ambiente do filho, `--fonte dou` reabriria o
        pipeline de diários inteiro: trabalho dobrado (tempo e memória) e a mesma
        resposta que já falhou.
        """
        capturado = {}

        def falso(cmd, capture_output=True, timeout=None, env=None):
            capturado["cmd"] = list(cmd)
            capturado["env"] = env
            return mock.Mock(returncode=1, stderr=b"", stdout=b"")

        with mock.patch.object(us, "_executar_cmd", falso):
            us.executar_fonte_subprocesso("dou", timeout_s=5, logger=lambda *_: None)
        self.assertIsNotNone(capturado["env"])
        self.assertEqual(capturado["env"]["MONITOR_DOU_DIARIOS"], "0")
        # as demais fontes seguem sem forçar variável nenhuma
        with mock.patch.object(us, "_executar_cmd", falso):
            us.executar_fonte_subprocesso("anpd", timeout_s=5, logger=lambda *_: None)
        self.assertIsNone(capturado["env"])


class FallbackDaFonteTests(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        os.environ.pop("MONITOR_DOU_DIARIOS", None)
        os.environ.pop("MONITOR_DOU_FALLBACK", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_integral_com_sucesso_nao_aciona_o_coletor_antigo(self):
        with mock.patch.object(us, "executar_diarios_fonte", return_value={
                "orgao": "dou", "itens": [1], "saude": _saude_ok(),
                "http": {}, "caminho_ingestao": "diarios_integral"}) as integral, \
             mock.patch.object(us, "executar_fonte") as legado, \
             mock.patch.object(us, "executar_fonte_subprocesso") as legado_sub:
            dados = us.executar_fonte_com_fallback("dou", timeout_s=5, logger=lambda *_: None,
                                                   usar_subprocesso=False)
        self.assertEqual(dados["caminho_ingestao"], "diarios_integral")
        integral.assert_called_once()
        legado.assert_not_called()
        legado_sub.assert_not_called()

    def test_integral_falha_aciona_busca_tematica_e_deixa_rastro(self):
        falha = us._resultado_falha("dou", "TLS/SSL connection has been closed", 1.0)
        falha["saude"]["erro_detalhe"] = "TLS/SSL connection has been closed"
        sucesso = {"orgao": "dou", "nome": "DOU", "itens": [{"id": "x"}],
                   "saude": {"status": "ok", "itens_consultados": 1, "canais_ok": ["busca"],
                             "canais_falhos": [], "erros": 0}, "http": {},
                   "erro_fatal": None}
        with mock.patch.object(us, "executar_diarios_fonte", return_value=falha), \
             mock.patch.object(us, "executar_fonte", return_value=sucesso) as legado:
            dados = us.executar_fonte_com_fallback("dou", timeout_s=5, logger=lambda *_: None,
                                                   usar_subprocesso=False)
        legado.assert_called_once()
        self.assertEqual(dados["caminho_ingestao"], "busca_tematica_fallback")
        diarios = dados["saude"]["diarios"]
        self.assertEqual(diarios["modo_ingestao"], "fallback")
        self.assertFalse(diarios["cobertura_integral"])
        self.assertEqual(diarios["caminho_integral_estado"], "falha")
        self.assertIn("TLS/SSL", diarios["erro_integral"])
        self.assertIn("sem cobertura integral", diarios["observacao"])

    def test_fallback_desligado_por_env_preserva_a_falha(self):
        os.environ["MONITOR_DOU_FALLBACK"] = "0"
        falha = us._resultado_falha("dou", "sem resposta", 1.0)
        with mock.patch.object(us, "executar_diarios_fonte", return_value=falha), \
             mock.patch.object(us, "executar_fonte") as legado:
            dados = us.executar_fonte_com_fallback("dou", timeout_s=5, logger=lambda *_: None,
                                                   usar_subprocesso=False)
        legado.assert_not_called()
        self.assertEqual(dados["saude"]["status"], "falha")

    def test_rollback_por_env_usa_o_caminho_antigo(self):
        os.environ["MONITOR_DOU_DIARIOS"] = "0"
        antigo = {"orgao": "dou", "itens": [], "saude": {"status": "ok"},
                  "http": {}, "erro_fatal": None}
        with mock.patch.object(us, "executar_diarios_fonte") as integral, \
             mock.patch.object(us, "executar_fonte", return_value=antigo) as legado:
            dados = us.executar_fonte_com_fallback("dou", timeout_s=5, logger=lambda *_: None,
                                                   usar_subprocesso=False)
        integral.assert_not_called()
        legado.assert_called_once()
        self.assertNotIn("caminho_ingestao", dados)

    def test_fontes_sem_pipeline_de_diarios_seguem_no_caminho_antigo(self):
        antigo = {"orgao": "anpd", "itens": [], "saude": {"status": "ok"},
                  "http": {}, "erro_fatal": None}
        with mock.patch.object(us, "executar_diarios_fonte") as integral, \
             mock.patch.object(us, "executar_fonte", return_value=antigo) as legado:
            us.executar_fonte_com_fallback("anpd", timeout_s=5, logger=lambda *_: None,
                                           usar_subprocesso=False)
        integral.assert_not_called()
        legado.assert_called_once()


class ExecutarTodasTests(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        os.environ["MONITOR_DOU_XML"] = "0"          # não tenta caminho XML local
        os.environ["MONITOR_DOU_DIARIOS"] = "0"      # rota antiga: sem subprocesso real

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_saude_monitorada_nao_ganha_fonte_ficticia(self):
        fake = {"nome": "F", "status": "ok", "itens_consultados": 0, "canais_ok": [],
                "canais_falhos": [], "erros": 0}
        with mock.patch.object(us, "executar_fonte", return_value={
                "orgao": "dou", "nome": "DOU", "itens": [], "saude": dict(fake),
                "http": {}, "erro_fatal": None}), \
             mock.patch.object(us, "executar_fonte_com_fallback",
                               side_effect=lambda orgao, **kw: {
                                   "orgao": orgao, "nome": orgao.upper(), "itens": [],
                                   "saude": dict(fake), "http": {}, "erro_fatal": None}):
            resultados = us.executar_todas(orgaos=["dou"], timeout_s=1,
                                           usar_subprocesso=False, limite_total_s=60,
                                           logger=lambda *_: None)
        self.assertEqual(set(resultados), {"dou"})
        self.assertEqual(set(resultados["dou"]["saude"]),
                         set(fake))  # nenhum campo de cobertura fabricado

    def test_orcamento_esgotado_marca_falha_explicita(self):
        with mock.patch.object(us, "executar_fonte_com_fallback") as coleta:
            resultados = us.executar_todas(orgaos=["dou"], timeout_s=1, usar_subprocesso=False,
                                           limite_total_s=19, logger=lambda *_: None)
        coleta.assert_not_called()   # nada roda sem tempo: falha explícita, não silêncio
        self.assertEqual(resultados["dou"]["saude"]["status"], "falha")
        self.assertIn("teto de tempo", resultados["dou"]["saude"]["erro_detalhe"])


class EncerramentoDeOrfaosTests(unittest.TestCase):
    """Timeout mata o processo **e a árvore** — nada continua rodando no runner."""

    def test_timeout_derruba_netos_sem_deixar_orfao(self):
        import subprocess as sp
        import time as _time
        marcador = pathlib.Path(tempfile.mkdtemp(prefix="orfao_")) / "pid.txt"
        neto = ("import os, pathlib, time; "
                f"pathlib.Path(r'{marcador}').write_text(str(os.getpid())); "
                "time.sleep(120)")
        pai = ("import subprocess, sys, time; "
               f"subprocess.Popen([sys.executable, '-c', {neto!r}]); "
               "time.sleep(120)")
        with self.assertRaises(sp.TimeoutExpired):
            us._executar_cmd([sys.executable, "-c", pai], 1)
        _time.sleep(1.5)
        self.assertTrue(marcador.exists(), "o neto precisa ter iniciado")
        pid_neto = int(marcador.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid_neto, 0)   # o neto foi morto junto com o grupo

    def test_execucao_normal_devolve_returncode_e_saidas(self):
        proc = us._executar_cmd([sys.executable, "-c", "import sys; print('ok'); "
                                 "sys.stderr.write('aviso')"], 30)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.decode().strip(), "ok")
        self.assertEqual(proc.stderr.decode().strip(), "aviso")


if __name__ == "__main__":
    unittest.main()
