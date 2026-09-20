#!/usr/bin/env python3
"""Restaura uma lacuna histórica comprovada na fonte primária do Senado.

A API do Senado pode ficar indisponível enquanto a ficha pública permanece
consultável. Este registro mínimo é uma curadoria documental datada, NÃO
uma alegação de ingestão de API em tempo real. O coletor continua tentando
atualizá-lo normalmente nas próximas execuções.
"""
import json
from pathlib import Path
from update_legislation import infer_categories
from scoring import compute_impact_score

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "legislation" / "propositions.json"
ID = "senado_pl_3592_2023"
FONTE = "https://www25.senado.leg.br/web/atividade/materias/-/materia/158816"


def main():
    dataset = json.loads(PATH.read_text(encoding="utf-8"))
    props = dataset["proposicoes"]
    if any(p.get("id") == ID for p in props):
        print("PL 3592/2023 já consta do dataset; preservado.")
        return 0

    ementa = ("Estabelece diretrizes para o uso de imagens e áudios de pessoas "
              "falecidas por meio de inteligência artificial (IA), com o "
              "intuito de preservar a dignidade, a privacidade e os direitos "
              "dos indivíduos mesmo após sua morte.")
    rec = {
        "id": ID,
        "tipo": "PL", "numero": 3592, "ano": 2023,
        "titulo": "Uso de imagens e áudios de pessoas falecidas por IA",
        "ementa": ementa,
        "casa_origem": "Senado Federal",
        "casa_atual": "Senado Federal (tramitação encerrada)",
        "url_oficial": FONTE,
        "autor": {"nome": "Rodrigo Cunha"},
        "data_apresentacao": "2023-07-19",
        "situacao": "Prejudicada e arquivada em 10/12/2024",
        "ultima_movimentacao": {
            "data": "2024-12-10",
            "descricao": "Prejudicada — ao arquivo.",
        },
        "resumo": ementa,
        "categorias": infer_categories(ementa),
        "documentos": [{"titulo": "Ficha oficial do Senado (histórico)",
                        "url": FONTE}],
        "timeline": [
            {"data": "2023-07-19", "evento": "Apresentação no Senado Federal.",
             "fonte": FONTE},
            {"data": "2024-12-10", "evento": "Declarada prejudicada; ao arquivo.",
             "fonte": FONTE},
        ],
        "origem": "curadoria_fonte_primaria",
        "fonte_descoberta": FONTE,
        "fonte_consultada_em": "2026-09-20",
        "revisao_pendente": True,
    }
    # Aplica a função já existente do produto, sem inventar nota editorial.
    rec["impacto"] = compute_impact_score(rec)
    props.append(rec)
    PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print("Restaurado PL 3592/2023 a partir de ficha histórica oficial.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
