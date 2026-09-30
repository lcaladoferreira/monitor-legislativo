"""Local full-stack preview: MONITOR_DEV=1 python3 scripts/serve_commercial.py."""
import os
import sys
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from api.index import handler as API
from commercial.store import migrate

class Local(API,SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'docs'),**kwargs)
    def do_GET(self):
        if self.path.startswith('/api/'):return API.do_GET(self)
        return SimpleHTTPRequestHandler.do_GET(self)

if __name__=='__main__':
    if os.environ.get('MONITOR_DEV')!='1' or os.environ.get('VERCEL') or os.environ.get('DATABASE_URL'):
        raise SystemExit('Use MONITOR_DEV=1 with local SQLite only; Vercel and DATABASE_URL are refused.')
    migrate()
    print('Local development server listening on 0.0.0.0:8765',flush=True)
    ThreadingHTTPServer(('0.0.0.0',8765),Local).serve_forever()
