"""Regressões documentadas pela auditoria QA de setembro de 2026.

Checa existência e rastreabilidade no dataset real, sem copiar estados
legislativos históricos da planilha nem fingir que links provam SLA.
"""
import json
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1] / "data" / "legislation"


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class AuditWatchlistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.props = read("propositions.json")["proposicoes"]
        cls.laws = read("laws.json")["normas"]

    def test_pl_5691_preservado_com_fonte_primaria(self):
        items = [p for p in self.props if p.get("numero") == 5691 and p.get("ano") == 2019]
        self.assertEqual(len(items), 1)
        self.assertEqual(urlparse(items[0]["url_oficial"]).hostname, "www25.senado.leg.br")

    def test_pl_5691_ligado_ao_marco_como_historico(self):
        p = next(p for p in self.props if p.get("numero") == 5691 and p.get("ano") == 2019)
        self.assertIn("camara_pl_2338_2023", p.get("relacionamentos", []))

    def test_cnj_615_preservada_e_documentada(self):
        x = [n for n in self.laws if n.get("id") == "resolucao_cnj_615_2025"]
        self.assertEqual(len(x), 1)
        self.assertEqual(urlparse(x[0]["url"]).hostname, "atos.cnj.jus.br")

    def test_lei_15123_fonte_primaria(self):
        x = [n for n in self.laws if n.get("id") == "lei_15123_2025"]
        self.assertEqual(len(x), 1)
        self.assertEqual(urlparse(x[0]["url"]).hostname, "www.planalto.gov.br")

    def test_tse_23755_sem_confundir_com_23748(self):
        x = [n for n in self.laws if n.get("id") == "resolucao_tse_23755_2026"]
        self.assertEqual(len(x), 1)
        self.assertEqual(urlparse(x[0]["url"]).hostname, "www.tse.jus.br")
        self.assertFalse(any(n.get("id") == "resolucao_tse_23748_2026" for n in self.laws))


if __name__ == "__main__":
    unittest.main()
