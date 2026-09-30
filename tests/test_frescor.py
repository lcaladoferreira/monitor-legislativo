"""Contrato da atualização: cadência, frescor e o gate de publicação.

Incidente 2026-09-30: o site publicava "última verificação há 23 h" enquanto o
cron horário coletava e descartava tudo — `validate_site.py` reprovava por uma
menção ao domínio legado dentro do próprio README, e o erro bloqueia o commit.
Em paralelo, o selo/painel classificavam 23 h de silêncio como "Monitoramento em
dia" (limiares fixos de 30/54 h, pensados para 4 coletas/dia) e anunciavam um
"cron diário às 07:17 BRT" que não existe.

Estes testes travam a correção: cadência lida do workflow, limiares derivados
dela, números consistentes entre build e navegador, e documentação unable de
derrubar a publicação.
"""
import datetime as dt
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_site_core as bsc  # noqa: E402
import frescor  # noqa: E402
import validate_site as vs  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "update-legislation.yml"
BRT = dt.timezone(dt.timedelta(hours=-3))


class CadenciaTests(unittest.TestCase):
    def test_cron_lido_do_proprio_workflow(self):
        texto = WORKFLOW.read_text(encoding="utf-8")
        declarados = re.findall(r'-\s*cron:\s*"([^"]+)"', texto)
        self.assertTrue(declarados, "workflow sem schedule: cron:")
        self.assertEqual(frescor.crons(), declarados)
        self.assertEqual(frescor.AVISOS, [])

    def test_intervalo_compativel_com_sla_de_2h(self):
        self.assertLessEqual(frescor.intervalo_horas(), 2.0)

    def test_descricao_reflete_o_cron(self):
        minutos = frescor._minutos_do_dia(frescor.crons()[0])
        self.assertTrue(minutos)
        self.assertIn(f"minuto {minutos[0] % 60}", frescor.descricao())

    def test_limiares_derivados_do_intervalo(self):
        ok, warn = frescor.limiares()
        self.assertLess(ok, warn)
        self.assertGreaterEqual(ok, frescor.PISO_OK_H)
        self.assertGreaterEqual(warn, frescor.PISO_ATENCAO_H)

    def test_23_horas_de_silencio_e_critico(self):
        """A regressão exata: com cron horário, 23 h não é 'em dia'."""
        self.assertEqual(frescor.estado(23.0), "critico")
        self.assertEqual(frescor.estado(0.5), "ok")
        self.assertEqual(frescor.estado(frescor.limiares()[0]), "ok")
        self.assertEqual(frescor.estado(frescor.limiares()[1]), "atencao")
        self.assertEqual(frescor.estado(None), "atencao")   # sem timestamp: sem verde

    def test_estado_e_monotono(self):
        anterior = "ok"
        for h in [i / 2 for i in range(0, 400)]:
            atual = frescor.estado(h)
            ordem = {"ok": 0, "atencao": 1, "critico": 2}
            self.assertGreaterEqual(ordem[atual], ordem[anterior], f"regressão em {h} h")
            anterior = atual


class ExecucaoTests(unittest.TestCase):
    def test_ultima_execucao_vence_por_timestamp_nao_por_posicao(self):
        execs = [
            {"id": "antigo", "data_hora": "2026-09-01T10:00:00-03:00", "fim": "2026-09-01T10:10:00-03:00"},
            {"id": "novo", "data_hora": "2026-09-02T10:00:00-03:00", "fim": "2026-09-02T10:10:00-03:00"},
        ]
        self.assertEqual(bsc._ultima_execucao(execs)["id"], "novo")
        self.assertEqual(bsc._ultima_execucao(list(reversed(execs)))["id"], "novo")

    def test_execucao_sem_timestamp_nao_ganha_de_execucao_com_timestamp(self):
        execs = [
            {"id": "bootstrap", "data_hora": "2026-09-01"},
            {"id": "nova", "data_hora": "2026-09-02T10:00:00-03:00"},
        ]
        self.assertEqual(bsc._ultima_execucao(execs)["id"], "nova")

    def test_rotulo_relativo_usa_o_dia_real_nao_o_da_execucao(self):
        """Com o dataset parado, um item de hoje continua sendo 'hoje'."""
        hoje = dt.datetime.now(BRT).date()
        exec_antigo, ref_antigo = bsc.EXECUTION_DATE, bsc.REF_DATE
        try:
            bsc.REF_DATE = None
            bsc.EXECUTION_DATE = (hoje - dt.timedelta(days=3)).isoformat()  # parado há 3 dias
            self.assertEqual(bsc.rel_label(hoje.isoformat()), "Hoje")
            self.assertEqual(bsc.days_ago(hoje.isoformat()), 0)
            bsc.REF_DATE = hoje + dt.timedelta(days=2)   # relógio da fonte adiantado
            self.assertEqual(bsc.rel_label(bsc.REF_DATE.isoformat()), "Hoje")
        finally:
            bsc.EXECUTION_DATE, bsc.REF_DATE = exec_antigo, ref_antigo


class SiteGeradoTests(unittest.TestCase):
    def setUp(self):
        self.ok, self.warn = frescor.limiares()
        self.paginas = [ROOT / "docs" / "index.html", ROOT / "docs" / "monitoramento" / "index.html"]

    def test_selo_e_painel_usam_os_mesmos_limiares(self):
        for p in self.paginas:
            html = p.read_text(encoding="utf-8")
            self.assertIn(f'data-fresh-ok="{self.ok}"', html, str(p))
            self.assertIn(f'data-fresh-warn="{self.warn}"', html, str(p))
            self.assertIn('data-fresh-cron="' + frescor.descricao() + '"', html, str(p))

    def test_cartao_de_idade_e_recalculavel_no_navegador(self):
        """O cartão não pode ficar congelado com o valor do build."""
        for p in self.paginas:
            html = p.read_text(encoding="utf-8")
            self.assertIn("data-age-from=", html, str(p))
            self.assertIn("data-age-num>", html, str(p))
            self.assertIn(f'data-age-ok="{self.ok}"', html, str(p))
            self.assertIn(f'data-age-warn="{self.warn}"', html, str(p))

    def test_selo_e_cartao_apontam_para_o_mesmo_instante(self):
        html = (ROOT / "docs" / "monitoramento" / "index.html").read_text(encoding="utf-8")
        ts = set(re.findall(r'data-freshness="([^"]+)"', html)
                 + re.findall(r'data-freshness-panel="([^"]+)"', html)
                 + re.findall(r'data-age-from="([^"]+)"', html))
        ts.discard("")
        self.assertEqual(len(ts), 1, f"instantes divergentes no painel: {ts}")

    def test_sem_limiares_ou_agendamento_fixos_no_codigo_do_site(self):
        for nome in ["build_site_core.py", os.path.join("assets", "site.js")]:
            texto = (ROOT / "scripts" / nome).read_text(encoding="utf-8")
            for legado in ("<= 30)", "<= 54)", "07:17", "10:43", "14:43", "18:43",
                           "quatro agendamentos"):
                self.assertNotIn(legado, texto, f"{nome} ainda fixa {legado!r}")
            self.assertNotIn("cron diário às", texto, f"{nome} descreve um cron inexistente")


class PublicacaoTests(unittest.TestCase):
    def test_arvore_atual_passa_na_validacao(self):
        """O gate de publicação precisa estar verde — foi o que congelou o site."""
        rep = vs.Report()
        vs.check_data(rep)
        vs.check_docs(rep, vs.site_url())
        vs.check_artigos(rep, vs.site_url())
        self.assertEqual(rep.errors, [])

    def test_dominio_antigo_em_documentacao_e_aviso_nao_erro(self):
        """Menção em prosa não pode derrubar a publicação (incidente 2026-09-30)."""
        original = (ROOT / "README.md").read_text(encoding="utf-8")
        with open(ROOT / "README.md", "a", encoding="utf-8") as f:
            f.write(f"\n<!-- {vs.OLD_DOMAIN} -->\n")
        try:
            alvo = ROOT / "scripts" / "_tmp_legado_check.py"
            alvo.write_text(f'URL = "{vs.OLD_DOMAIN}"\n', encoding="utf-8")
            try:
                saida = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_site.py")],
                                       capture_output=True, text=True, cwd=ROOT)
                # aviso em .md, erro em .py
                self.assertIn("README.md", saida.stdout)
                self.assertIn("documentação", saida.stdout)
                self.assertIn("_tmp_legado_check.py", saida.stdout)
                self.assertNotIn("documentação: sem impacto no build\n  ERRO: README.md", saida.stdout)
            finally:
                alvo.unlink()
        finally:
            (ROOT / "README.md").write_text(original, encoding="utf-8")

    def test_workflow_falha_visivel_quando_publicacao_e_bloqueada(self):
        texto = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("PUBLICAÇÃO BLOQUEADA", texto)
        self.assertIn("steps.validate.outcome == 'failure'", texto)
        # A restauração histórica não pode abortar a coleta antes dela.
        bloco = texto.split("Recuperar lacuna histórica", 1)[1].split("Coletar dados oficiais", 1)[0]
        self.assertIn("continue-on-error: true", bloco)


if __name__ == "__main__":
    unittest.main()
