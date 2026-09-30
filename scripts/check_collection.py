"""Fail the scheduled run when the latest collection is stale or incomplete.

A regra de defasagem é derivada do agendamento real (scripts/frescor.py), não de
um "precisa ser de hoje" fixo: com o cron horário, uma coleta das 23:17 de
ontem está Perfectamente em dia às 00:30 de hoje, e era reprovada. O que reprova
é passar do limite de atenção da cadência — que é a mesma régua que o selo de
frescor do site usa, para que painel e gate nunca discordem.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frescor import descricao as _cron_descricao, estado as _estado_frescor, limiares as _limiares

BRT = timezone(timedelta(hours=-3))

# Fichas documentadas pela auditoria: exigimos presença real no dataset,
# e não apenas a existência de código que tentará descobri-las futuramente.
AUDIT_WATCHLIST = {
    "camara_pl_2688_2025": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2520003",
    "camara_pl_1884_2025": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2500594",
    "camara_pl_370_2024": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2418364",
    "senado_pl_3592_2023": "https://www25.senado.leg.br/web/atividade/materias/-/materia/158816",
}


def audit_coverage(props):
    by_id = {p.get("id"): p for p in props}
    errors = []
    for identifier, url in AUDIT_WATCHLIST.items():
        prop = by_id.get(identifier)
        if not prop:
            errors.append(f"Auditoria: proposição ausente do dataset: {identifier}")
        elif prop.get("url_oficial") != url:
            errors.append(f"Auditoria: fonte primária divergente: {identifier}")
    return errors

def problems(record, now=None):
    now = now or datetime.now(BRT)
    ok_h, warn_h = _limiares()
    errors = []
    try:
        finished = datetime.fromisoformat(record.get("fim") or record["data_hora"])
        if finished.tzinfo is None:
            raise ValueError("timestamp without timezone")
        if finished > now:
            errors.append("A coleta possui data futura.")
        else:
            idade_h = (now - finished).total_seconds() / 3600
            if _estado_frescor(idade_h, (ok_h, warn_h)) == "critico":
                errors.append(
                    f"A última coleta publicada tem {idade_h:.1f} h; o limite para o "
                    f"agendamento atual ({_cron_descricao()}) é {warn_h:g} h. "
                    "O selo de frescor do site também entra em crítico neste estado."
                )
    except (KeyError, TypeError, ValueError):
        errors.append("Data da coleta ausente ou inválida.")
    if record.get("status") != "concluida":
        errors.append("Coleta não concluída.")
    try:
        if float(record.get("cobertura_pct", 0)) < 100:
            errors.append("Cobertura inferior a 100%.")
    except (TypeError, ValueError):
        errors.append("Cobertura inválida.")
    if record.get("erros") or record.get("proposicoes_pendentes"):
        errors.append("Há erros ou proposições pendentes.")
    # A cobertura legislativa não substitui a saúde dos órgãos reguladores.
    # Um CNJ/DOU/TSE indisponível não pode produzir um falso "100% íntegro".
    if "status_global" in record and str(record["status_global"] or "").lower() not in ("ok", "concluida"):
        errors.append("Coleta multiórgão incompleta: status_global="
                      + str(record["status_global"]))
    if record.get("fontes_falha"):
        errors.append("Fontes com falha: " + ", ".join(map(str, record["fontes_falha"])))
    if record.get("fontes_parciais"):
        errors.append("Fontes parciais: " + ", ".join(map(str, record["fontes_parciais"])))
    for orgao, fonte in (record.get("fontes_monitoradas") or {}).items():
        if fonte.get("status") not in ("ok",):
            errors.append(f"Fonte {orgao} não íntegra: {fonte.get('status', 'sem status')}")
        if fonte.get("erros", 0):
            errors.append(f"Fonte {orgao} com {fonte['erros']} erro(s) de coleta.")
        if fonte.get("canais_falhos"):
            errors.append(f"Fonte {orgao}: canais com falha: " + ", ".join(fonte["canais_falhos"]))
    return errors

def main():
    try:
        data = json.loads(Path("data/legislation/updates.json").read_text())
        found = problems((data.get("execucoes") or [{}])[0])
        props = json.loads(Path("data/legislation/propositions.json").read_text())
        found.extend(audit_coverage(props.get("proposicoes") or []))
    except (OSError, ValueError, TypeError, AttributeError):
        found = ["Não foi possível verificar o registro da coleta."]
    for message in found:
        print("::error::" + message)
    if not found:
        print("Coleta do dia concluída, cobertura integral e sem erros.")
    return int(bool(found))

if __name__ == "__main__":
    sys.exit(main())
