"""Generate private HTML + text for printing and e-mail; never writes into docs/data."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from commercial.intelligence import briefing,CONFIG
import build_site as core
from commercial_pages import briefing_body
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--since');p.add_argument('--as-of');p.add_argument('--sector',choices=list(CONFIG['sectors']));p.add_argument('--output',default='.private/briefing.html');a=p.parse_args()
    output=Path(a.output).resolve()
    if (Path(core.OUT).resolve() in output.parents):raise SystemExit('Private reports must not be written under docs/.')
    core.build_slugs(core.load('propositions.json')['proposicoes'])
    model=briefing(a.as_of,a.since,a.sector)
    body=briefing_body(model,core)
    html='<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Executive Regulatory Brief</title><body style="font-family:Arial,sans-serif;max-width:900px;margin:2em auto"><h1>Executive Regulatory Brief</h1>'+body+'</body></html>'
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(html)
    text=['Executive Regulatory Brief',model['since']+' a '+model['as_of']]
    for prop in model['top']:text += [prop['titulo'],prop['url_oficial']]
    text += ['Análise preliminar; não constitui aconselhamento jurídico.']
    output.with_suffix('.txt').write_text('\n'.join(text));print(output)
