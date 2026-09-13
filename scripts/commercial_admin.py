"""Operator CLI. No admin endpoint or secrets embedded in public pages."""
import argparse
import getpass
import json
import sys
import time
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from commercial.store import connect,migrate
from commercial import service as svc


def provision(s,account_id,name,status,ends_on,limit,themes,address,password):
    if status not in {'trial','pilot','active','inactive'}:raise ValueError('Invalid status')
    if not 1<=limit<=100:raise ValueError('User limit must be 1–100')
    if ends_on:date.fromisoformat(ends_on)
    if status in {'trial','pilot'} and not ends_on:raise ValueError('Trial/pilot requires an end date')
    if any(t not in {x['id'] for x in svc.load('categories')['categorias']} for t in themes):raise ValueError('Invalid theme')
    s.lock('account:'+account_id)
    existing=s.list('user',account_id)
    address=svc.email(address);uid=svc.digest(address)
    old=s.get('user',uid)
    if old and old['account_id']!=account_id:raise ValueError('User already belongs to another account')
    if len(existing)+(0 if old else 1)>limit:raise ValueError('User limit exceeded')
    s.put('account',account_id,{'name':name,'status':status,'ends_on':ends_on,'user_limit':limit,'themes':themes},account_id)
    s.put('user',uid,{'id':uid,'email':address,'account_id':account_id,'password_hash':svc.password_hash(password)},account_id)
    # Provision/reset revokes all existing sessions for this user.
    for key,session in s.list('session',account_id):
        if session['user_id']==uid:s.delete('session',key)
    s.insert('usage',svc.secrets.token_hex(16),{'event':'user_provisioned','user_id':uid,'timestamp':int(time.time())},account_id)


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('migrate')
    a=sub.add_parser('provision');a.add_argument('--account',required=True);a.add_argument('--name',required=True);a.add_argument('--email',required=True);a.add_argument('--status',choices=['trial','pilot','active','inactive'],default='pilot');a.add_argument('--ends-on');a.add_argument('--users',type=int,default=5);a.add_argument('--themes',type=int,nargs='*',default=[])
    sub.add_parser('leads')
    a=sub.add_parser('lead-stage');a.add_argument('id');a.add_argument('stage',choices=['lead','diagnostic','demo','pilot','contract','lost'])
    a=sub.add_parser('account-status');a.add_argument('id');a.add_argument('status',choices=['trial','pilot','active','inactive'])
    sub.add_parser('purge')
    args=p.parse_args()
    if args.command=='migrate':migrate();print('Private schema ready.');return
    with connect() as s:
        if args.command=='provision':provision(s,args.account,args.name,args.status,args.ends_on,args.users,args.themes,args.email,getpass.getpass('Password (12+ characters): '));print('Account/user provisioned. No e-mail sent.')
        elif args.command=='leads':
            for key,v in s.list('lead'):print(json.dumps({'id':key,**v},ensure_ascii=False))
        elif args.command=='lead-stage':
            lead=s.get('lead',args.id)
            if not lead:raise SystemExit('Lead not found')
            lead['stage']=args.stage;lead['stage_updated_at']=int(time.time());s.put('lead',args.id,lead)
        elif args.command=='account-status':
            account=s.get('account',args.id)
            if not account:raise SystemExit('Account not found')
            if args.status in {'trial','pilot'} and not account.get('ends_on'):raise SystemExit('Trial/pilot needs an end date; use provision.')
            account['status']=args.status;s.put('account',args.id,account,args.id)
        elif args.command=='purge':
            now=time.time()
            for kind in ('rate','session','confirm','unsubscribe'):
                for key,v in s.list(kind,limit=100000):
                    if v.get('expires',now+1)<now:s.delete(kind,key)
            for kind,age in [('event',90),('usage',90),('lead',180),('outbox',30),('alert_change',90),('alert_delivery',90),('subscription',7)]:
                for key,v in s.list(kind,limit=100000):
                    if kind=='lead' and v.get('stage') in {'pilot','contract'}:continue
                    if kind=='outbox' and v.get('status') not in {'sent','cancelled'}:continue
                    if kind=='subscription' and v.get('active'):continue
                    stamp=v.get('created_at') or v.get('timestamp') or v.get('detected_at') or v.get('sent_at') or v.get('queued_at')
                    if stamp and stamp<now-age*86400:s.delete(kind,key)
            print('Retention cleanup complete.')

if __name__=='__main__':main()
