"""Seed a non-production test pilot into the local SQLite store.

Run only for local testing:
    MONITOR_DEV=1 python3 scripts/seed_test_account.py
Never seed this account into a production database.
"""
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts'))
from commercial.store import connect,migrate
from commercial_admin import provision

ACCOUNT_ID='acct_testpiloto'
ACCOUNT_NAME='Piloto Teste'
EMAIL='teste@piloto.local'
PASSWORD='PilotoTeste123!'
ENDS_ON='2026-12-31'
THEMES=[1,3,20]


def main():
    if os.environ.get('MONITOR_DEV')!='1' or os.environ.get('VERCEL') or os.environ.get('DATABASE_URL'):
        raise SystemExit('Refusing to seed: set MONITOR_DEV=1 and use local SQLite only (no Vercel or DATABASE_URL).')
    migrate()
    with connect() as store:
        provision(store,ACCOUNT_ID,ACCOUNT_NAME,'pilot',ENDS_ON,5,THEMES,EMAIL,PASSWORD)
    print('Local test pilot ready.')
    print(f'Account: {ACCOUNT_ID} (pilot through {ENDS_ON})')
    print(f'Login: {EMAIL}')
    print(f'Password: {PASSWORD}')
    print('Open /login/ in the local development site.')


if __name__=='__main__':
    main()
