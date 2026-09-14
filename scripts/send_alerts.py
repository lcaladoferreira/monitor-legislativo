"""Generate queues by default; send only when explicitly enabled with --send."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from commercial.store import connect
from commercial.alerts import capture,prepare,deliver
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--send',action='store_true');p.add_argument('--capture',action='store_true');args=p.parse_args()
    with connect() as s:
        if args.capture:capture(s)
        prepare(s)
    if args.send:print('E-mails accepted by SMTP:',deliver(connect))
    else:print('Queues prepared. No e-mail sent; use --send when configured.')
