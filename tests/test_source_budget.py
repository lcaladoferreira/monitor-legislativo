"""Regressões de resiliência: uma API indisponível não pode consumir o orçamento de todas."""
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import update_legislation as m


class SourceBudgetTests(unittest.TestCase):
    def setUp(self):
        with m._HTTP_LOCK:
            m._HTTP_HOST_FAILURES.clear()
            m._HTTP_CACHE.clear()

    def tearDown(self):
        with m._HTTP_LOCK:
            m._HTTP_HOST_FAILURES.clear()
            m._HTTP_CACHE.clear()

    def test_circuit_breaker_reduz_chamadas_repetidas(self):
        url = "https://dadosabertos.camara.leg.br/api/v2/proposicoes/123"
        with patch.object(m, "_CURL_BIN", "/usr/bin/curl"), \
             patch.object(m, "_http_curl", side_effect=TimeoutError("API indisponível")) as req, \
             patch.object(m, "HTTP_FAILURE_LIMIT", 2), \
             patch.object(m, "HTTP_RETRIES", 1):
            self.assertIsNone(m.http_get_json(url, timeout=1, cache=False))
            self.assertIsNone(m.http_get_json(url, timeout=1, cache=False))
            self.assertIsNone(m.http_get_json(url, timeout=1, cache=False))
            self.assertEqual(req.call_count, 2)

    def test_circuito_isolado_por_host(self):
        a = "https://dadosabertos.camara.leg.br/api/v2/proposicoes/123"
        b = "https://legis.senado.leg.br/dadosabertos/materia/123.json"
        with patch.object(m, "_CURL_BIN", "/usr/bin/curl"), \
             patch.object(m, "_http_curl", side_effect=TimeoutError("falha")) as req, \
             patch.object(m, "HTTP_FAILURE_LIMIT", 2), \
             patch.object(m, "HTTP_RETRIES", 1):
            m.http_get_json(a, timeout=1, cache=False)
            m.http_get_json(a, timeout=1, cache=False)
            m.http_get_json(b, timeout=1, cache=False)
            self.assertEqual(req.call_count, 3)

    def test_orgaos_sao_consultados_antes_das_fichas_legislativas(self):
        source = (Path(__file__).resolve().parents[1] /
                  "scripts" / "update_legislation.py").read_text(encoding="utf-8")
        self.assertLess(source.index("# 3.5) Fontes multiórgão"),
                        source.index("# 1) Atualizar proposições monitoradas"))


if __name__ == "__main__":
    unittest.main()
