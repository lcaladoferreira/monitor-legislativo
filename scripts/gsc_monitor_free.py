#!/usr/bin/env python3
"""Relatório GSC gratuito, limitado exclusivamente ao Monitor LCF.

Requer uma conta de serviço Google autorizada como usuário restrito na
propriedade sc-domain:lcfconsulting.com.br, e credenciais apenas em segredo.
Não altera o site, não envia e-mails e não usa serviços pagos.
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

PROPERTY = "sc-domain:lcfconsulting.com.br"
PREFIX = "https://monitor.lcfconsulting.com.br/"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
END_LAG_DAYS = 3


def date_window(end, days):
    return ((end - dt.timedelta(days=days - 1)).isoformat(), end.isoformat())


def page_filter(operator="contains", expression=PREFIX):
    return {"dimensionFilterGroups": [{"filters": [
        {"dimension": "page", "operator": operator, "expression": expression}
    ]}]}


def fetch(session, start, end, dimensions=(), page=None, limit=25000):
    from urllib.parse import quote
    url = ("https://www.googleapis.com/webmasters/v3/sites/"
           + quote(PROPERTY, safe="") + "/searchAnalytics/query")
    body = {"startDate": start, "endDate": end, "type": "web",
            "dataState": "final", "dimensions": list(dimensions),
            "rowLimit": limit, "startRow": 0}
    if page is not None:
        body.update(page_filter("equals" if page != PREFIX else "contains", page))
    rows = []
    while True:
        response = session.post(url, json=body, timeout=40)
        response.raise_for_status()
        batch = response.json().get("rows", [])
        rows.extend(batch)
        if len(batch) < limit:
            break
        body["startRow"] += limit
        if body["startRow"] >= 50000:
            break
    return rows


def summarize(rows):
    clicks = sum(r.get("clicks", 0) for r in rows)
    impressions = sum(r.get("impressions", 0) for r in rows)
    weighted_position = sum(r.get("position", 0) * r.get("impressions", 0) for r in rows)
    return {"clicks": clicks, "impressions": impressions,
            "ctr": round(clicks / impressions, 5) if impressions else 0,
            "position": round(weighted_position / impressions, 2) if impressions else None}


def report(session, end):
    result = {"property": PROPERTY, "url_prefix": PREFIX, "search_type": "web",
              "data_state": "final", "end_date": end.isoformat(),
              "note": "Data final escolhida com margem de 3 dias; verificar maturidade no GSC."}
    for days in (7, 28):
        start, finish = date_window(end, days)
        previous_end = dt.date.fromisoformat(start) - dt.timedelta(days=1)
        pstart, pend = date_window(previous_end, days)
        current = fetch(session, start, finish, page=PREFIX)
        previous = fetch(session, pstart, pend, page=PREFIX)
        result[f"{days}d"] = {"start": start, "end": finish,
                               "current": summarize(current),
                               "previous": summarize(previous),
                               "previous_start": pstart, "previous_end": pend}
    start, finish = date_window(end, 28)
    pages = fetch(session, start, finish, dimensions=("page",), page=PREFIX)
    pages = [r for r in pages if r.get("keys", [""])[0].startswith(PREFIX)]
    pages.sort(key=lambda r: (-r.get("impressions", 0), r.get("keys", [""])[0]))
    queries = fetch(session, start, finish, dimensions=("query",), page=PREFIX)
    result["pages_28d"] = pages
    result["queries_28d"] = queries
    result["page_queries_28d"] = {}
    for r in pages[:10]:
        page = r["keys"][0]
        result["page_queries_28d"][page] = fetch(
            session, start, finish, dimensions=("query",), page=page, limit=1000)
    result["opportunities"] = [
        {"page": r["keys"][0], "clicks": r.get("clicks", 0),
         "impressions": r.get("impressions", 0),
         "ctr": r.get("ctr", 0), "position": r.get("position", 0)}
        for r in pages if 3 <= r.get("position", 0) <= 10
        and r.get("impressions", 0) >= 20
    ]
    result["opportunities"].sort(
        key=lambda r: (-r["impressions"] * (1 - r["ctr"]), r["page"]))
    return result


def main():
    secret = os.environ.get("GSC_SERVICE_ACCOUNT_JSON", "")
    if not secret:
        print("GSC_SERVICE_ACCOUNT_JSON ausente: conexão Google pendente.", file=sys.stderr)
        return 2
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    info = json.loads(secret)
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=[SCOPE])
    session = AuthorizedSession(credentials)
    end = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=END_LAG_DAYS)
    data = report(session, end)
    out = Path(os.environ.get("GSC_REPORT_PATH", "reports/gsc_monitor_latest.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Relatório GSC Monitor:", out, "28d:", data["28d"]["current"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
