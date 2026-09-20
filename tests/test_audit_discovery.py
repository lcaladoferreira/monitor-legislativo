"""Coletor da auditoria: não inventar situação do Senado quando APIs falham."""
import unittest
from unittest.mock import patch

from scripts import update_legislation as monitor


class AuditDiscoveryTests(unittest.TestCase):
    def test_senado_detalhe_indisponivel_nao_gera_situacao_ativa(self):
        m = {"Codigo": "158816", "Sigla": "PL", "Numero": "3592",
             "Ano": "2023", "Ementa": "Uso de inteligência artificial"}
        with patch.object(monitor, "senado_detail", return_value=None), \
             patch.object(monitor, "senado_movimentacoes", return_value=None):
            rec = monitor.Collector().build_new_senado_record(m)
        self.assertIn("não confirmada", rec["situacao"])
        self.assertEqual(rec["numero"], 3592)

    def test_senado_tramitacao_encerrada_nao_aparece_ativa(self):
        m = {"Codigo": "158816", "Sigla": "PL", "Numero": "3592",
             "Ano": "2023", "Ementa": "Uso de inteligência artificial"}
        detalhe = {
            "IdentificacaoMateria": {"IndicadorTramitando": "Não"},
            "DadosBasicosMateria": {"EmentaMateria": m["Ementa"],
                                   "DataApresentacao": "2023-07-19"},
        }
        with patch.object(monitor, "senado_detail", return_value=detalhe), \
             patch.object(monitor, "senado_movimentacoes", return_value=None):
            rec = monitor.Collector().build_new_senado_record(m)
        self.assertIn("encerrada", rec["situacao"])
        self.assertNotIn("Em tramitação", rec["situacao"])


if __name__ == "__main__":
    unittest.main()
