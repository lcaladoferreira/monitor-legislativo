"""Regressões: a coleta só é saudável se os órgãos reguladores também estiverem."""
import unittest
from datetime import datetime, timedelta, timezone

from scripts.check_collection import problems

BRT = timezone(timedelta(hours=-3))


class CollectionHealthMultisourceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 20, 14, 0, tzinfo=BRT)
        self.record = {
            "fim": self.now.isoformat(),
            "status": "concluida",
            "cobertura_pct": 100,
            "erros": [],
            "proposicoes_pendentes": 0,
            "status_global": "ok",
            "fontes_falha": [],
            "fontes_parciais": [],
            "fontes_monitoradas": {"cnj": {"status": "ok"}, "dou": {"status": "ok"}},
        }

    def test_coleta_integral(self):
        self.assertEqual(problems(self.record, now=self.now), [])

    def test_cnj_indisponivel_nao_passa_com_100_por_cento(self):
        self.record["fontes_monitoradas"]["cnj"]["status"] = "falha"
        self.assertTrue(any("cnj" in e for e in problems(self.record, now=self.now)))

    def test_fonte_parcial_reprova(self):
        self.record["fontes_parciais"] = ["dou"]
        self.assertTrue(any("dou" in e for e in problems(self.record, now=self.now)))

    def test_status_global_incompleto_reprova(self):
        self.record["status_global"] = "parcial"
        self.assertTrue(any("status_global" in e for e in problems(self.record, now=self.now)))


if __name__ == "__main__":
    unittest.main()
