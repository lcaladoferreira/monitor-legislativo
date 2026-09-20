"""A cobertura da auditoria deve ser verificada no dataset, não no código."""
import unittest
from scripts.check_collection import AUDIT_WATCHLIST, audit_coverage


class CoverageAuditTests(unittest.TestCase):
    def test_ficha_ausente_e_detectada(self):
        errors = audit_coverage([])
        self.assertEqual(len(errors), len(AUDIT_WATCHLIST))
        self.assertTrue(any("camara_pl_2688_2025" in e for e in errors))

    def test_fonte_nao_primaria_e_detectada(self):
        records = [{"id": identifier, "url_oficial": url}
                   for identifier, url in AUDIT_WATCHLIST.items()]
        records[0]["url_oficial"] = "https://www.camara.leg.br/noticias/exemplo"
        self.assertEqual(len(audit_coverage(records)), 1)

    def test_todos_presentes_e_com_fonte_correta(self):
        records = [{"id": identifier, "url_oficial": url}
                   for identifier, url in AUDIT_WATCHLIST.items()]
        self.assertEqual(audit_coverage(records), [])


if __name__ == "__main__":
    unittest.main()
