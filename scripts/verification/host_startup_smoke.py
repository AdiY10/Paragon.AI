"""Exercise real host startup, passwords, migration, and restart on disposable PostGIS.

Requires the local verification PostGIS server. Private exports stay outside Git.
Uses a private UNIX socket as a trusted HTTPS ingress; real external TLS remains a
separate deployment acceptance check.
"""
import argparse
from http.cookies import SimpleCookie
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time
from urllib.parse import urlencode,quote
import uuid
import psycopg
from psycopg import sql
from production_smoke import SocketHTTPConnection

ROOT=Path(__file__).resolve().parents[2]

class Browser:
    def __init__(self,path):self.path=str(path);self.cookies={};self.csrf=''
    def request(self,method,path,body=None,form=False,expected=200):
        headers={'Host':'localhost','X-Forwarded-Proto':'https','Origin':'https://localhost','Referer':'https://localhost/'}
        if self.cookies:headers['Cookie']='; '.join(f'{key}={value}' for key,value in self.cookies.items())
        if self.csrf:headers['X-CSRFToken']=self.csrf
        if body is not None:
            headers['Content-Type']='application/x-www-form-urlencoded' if form else 'application/json'
            body=urlencode(body) if form else json.dumps(body)
        connection=SocketHTTPConnection(self.path);connection.request(method,path,body=body,headers=headers)
        response=connection.getresponse();payload=response.read()
        assert response.status==expected,(method,path,response.status)
        assert response.getheader('Strict-Transport-Security')
        for key,value in response.getheaders():
            if key.lower()=='set-cookie':
                cookie=SimpleCookie();cookie.load(value)
                for name,item in cookie.items():
                    if item.value:
                        assert item['secure'] and item['httponly']
                        self.cookies[name]=item.value
                    else:self.cookies.pop(name,None)
        connection.close();return payload
    def login(self,password):
        page=self.request('GET','/access/login/').decode()
        self.csrf=re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"',page)[1]
        self.request('POST','/access/login/',{'email':'host-qa@example.invalid','password':'incorrect-password','csrfmiddlewaretoken':self.csrf},form=True,expected=401)
        self.request('POST','/access/login/',{'email':'host-qa@example.invalid','password':password,'csrfmiddlewaretoken':self.csrf},form=True,expected=302)
        session=json.loads(self.request('GET','/api/session/'));self.csrf=session['csrfToken']


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('export',type=Path);args=parser.parse_args()
    export=args.export.resolve();digest=hashlib.sha256(export.read_bytes()).hexdigest()
    db='host_qa_'+uuid.uuid4().hex[:12]
    params={'dbname':os.environ.get('PARAGON_TEST_DB_NAME','paragon'),'user':os.environ.get('PARAGON_TEST_DB_USER','paragon'),
        'host':os.environ.get('PARAGON_TEST_DB_HOST','/tmp/paragon-pg-socket'),'port':os.environ.get('PARAGON_TEST_DB_PORT','55432')}
    with psycopg.connect(**params,autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(db)))
        try:
            with tempfile.TemporaryDirectory(prefix='paragon-host-qa-') as directory:
                root=Path(directory);socket_path=root/'http.sock';password=secrets.token_urlsafe(32)
                url=f"postgresql://{quote(params['user'],safe='')}@{quote(params['host'],safe='')}:{params['port']}/{db}"
                env=dict(os.environ,PATH=str(ROOT/'.venv/bin')+os.pathsep+os.environ['PATH'],PYTHONPATH=str(ROOT/'backend'),
                    DJANGO_SETTINGS_MODULE='config.settings.production',DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
                    DJANGO_ALLOWED_HOSTS='localhost',CSRF_TRUSTED_ORIGINS='https://localhost',DATABASE_URL=url,
                    PASSWORD_ACCESS_ENABLED='true',TRUST_PROXY_SSL_HEADER='true',ACCESS_BOOTSTRAP_EMAIL='host-qa@example.invalid',
                    ACCESS_BOOTSTRAP_PASSWORD=password,SOURCE_ARTIFACT_ROOT=str(root/'private-evidence'),
                    WORKSPACE_IMPORT_PATH=str(export),WORKSPACE_IMPORT_SHA256=digest,GUNICORN_BIND='unix:'+str(socket_path),WEB_CONCURRENCY='1')
                record_path=None;first_session=None
                for restart in (False,True):
                    if restart:
                        env.pop('ACCESS_BOOTSTRAP_EMAIL');env.pop('ACCESS_BOOTSTRAP_PASSWORD')
                    with (root/'server.log').open('w+') as log:
                        process=subprocess.Popen([str(ROOT/'.venv/bin/python'),'infra/start_web.py'],cwd=ROOT,env=env,stdout=log,stderr=log)
                        try:
                            for _ in range(300):
                                if process.poll() is not None:raise RuntimeError('Host startup exited; private logs retained only during this smoke run')
                                if socket_path.exists():
                                    try:Browser(socket_path).request('GET','/health/');break
                                    except OSError:pass
                                time.sleep(.1)
                            else:raise TimeoutError('Host startup timeout')
                            browser=Browser(socket_path)
                            browser.request('GET','/',expected=302);browser.request('GET','/api/locations/',expected=403)
                            browser.login(password)
                            browser.request('GET','/')
                            records=json.loads(browser.request('GET','/api/locations/'))
                            assert records['count']==36
                            if not restart:
                                record=records['results'][0];record_path=f"/api/locations/{record['id']}/"
                                browser.request('PATCH',record_path,{'expected_version':record['version'],'notes':'Disposable restart persistence check'})
                                first_session=browser
                            else:
                                record=json.loads(browser.request('GET',record_path));assert record['notes']=='Disposable restart persistence check'
                                first_session.request('GET','/api/session/')
                                browser.request('POST','/access/logout/',{},expected=302)
                                browser.request('GET','/api/locations/',expected=403)
                            archived=root/'private-evidence'/'sha256'/digest[:2]/digest
                            assert hashlib.sha256(archived.read_bytes()).hexdigest()==digest
                        finally:
                            process.terminate()
                            try:process.wait(timeout=10)
                            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                    socket_path.unlink(missing_ok=True)
                print(json.dumps({'verified':True,'database':'PostgreSQL/PostGIS disposable','locations':36,'password_login':True,'restart_persistence':True,'private_artifact_sha256':digest}))
        finally:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(db)))

if __name__=='__main__':main()
