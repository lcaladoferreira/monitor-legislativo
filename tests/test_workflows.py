"""Guarda-costas dos workflows do GitHub Actions (só stdlib).

Incidente 2026-09-18: linhas de script coladas na coluna 0 dentro de um
bloco `run: |` de `.github/workflows/update-legislation.yml` quebraram o
parse do YAML. O GitHub parou de agendar o cron (6 janelas perdidas, ~37 h
sem coleta) e os pushes falhavam em 0s com "workflow file issue".

Estes testes impedem a regressão sem depender de PyYAML (indisponível no
job de validação do PR): qualquer linha futura na coluna 0 que não seja
chave de topo conhecida quebra o teste antes do merge.
"""
import pathlib
import re
import unittest

WORKFLOWS = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows"

# Chaves de primeiro nível usadas pelos workflows deste repositório.
TOP_LEVEL_KEYS = ("name", "on", "run-name", "permissions", "concurrency", "env", "jobs")


class WorkflowYamlTests(unittest.TestCase):
    def test_workflows_exist(self):
        files = sorted(WORKFLOWS.glob("*.yml"))
        self.assertIn("update-legislation.yml", [f.name for f in files])

    def test_no_tabs(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                self.assertNotIn("\t", line, f"{path.name}:{lineno} contém TAB (ilegal em YAML)")

    def test_no_stray_column_zero_lines(self):
        """Só chaves de topo podem começar na coluna 0.

        Linhas de script/heredoc dentro de `run: |` precisam estar indentadas:
        uma linha na coluna 0 encerra o bloco literal e invalida o arquivo.
        """
        allowed = re.compile(rf"^({'|'.join(TOP_LEVEL_KEYS)}):(\s|$)|^---|^#")
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                if line[0] not in (" ", "\t"):
                    self.assertRegex(
                        line, allowed,
                        f"{path.name}:{lineno} começa na coluna 0 e não é chave de topo: {line.strip()[:60]!r}. "
                        "Se for linha de script dentro de run: |, indente-a (incidente 2026-09-18).",
                    )

    def test_daily_cron_slots_present(self):
        """O cron diário (07:17 BRT + repetições) precisa continuar agendado."""
        text = (WORKFLOWS / "update-legislation.yml").read_text(encoding="utf-8")
        self.assertIn("17 10 * * *", text, "slot principal 07:17 BRT ausente do cron")
        self.assertIn("43 13,17,21 * * *", text, "slots de repetição ausentes do cron")
        self.assertIn("schedule:", text)

    def test_yaml_parses_when_pyyaml_available(self):
        try:
            import yaml  # type: ignore
        except ImportError:
            self.skipTest("PyYAML indisponível (job de PR usa só stdlib)")
        for path in sorted(WORKFLOWS.glob("*.yml")):
            with path.open(encoding="utf-8") as fh:
                yaml.safe_load(fh)


if __name__ == "__main__":
    unittest.main()
