"""Real password browser login on a disposable database, without identity bypass."""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]


def main():
    with tempfile.TemporaryDirectory(prefix='paragon-password-qa-') as directory:
        root=Path(directory)
        (root/'password_test_settings.py').write_text('from config.settings.test import *\n'
            +'DATABASES='+repr({'default':{'ENGINE':'django.db.backends.sqlite3','NAME':str(root/'db.sqlite3')}})+'\n'
            +'PASSWORD_ACCESS_ENABLED=True\nLOGIN_URL="/access/login/"\nALLOWED_HOSTS=["127.0.0.1"]\n')
        env=dict(os.environ,DJANGO_SETTINGS_MODULE='password_test_settings',
            PYTHONPATH=os.pathsep.join([str(ROOT/'backend'),directory]),PARAGON_QA_PASSWORD=secrets.token_urlsafe(32))
        code='''import django;django.setup()
import os
from unittest.mock import patch
from django.core.management import call_command
from io import StringIO
from apps.locations.seeding import import_public_portfolio
call_command('migrate',verbosity=0);call_command('sync_sources',verbosity=0);import_public_portfolio()
with patch('sys.stdin',StringIO(os.environ['PARAGON_QA_PASSWORD']+'\\n')):
 call_command('set_access_password','access-test@example.invalid',role='admin',password_stdin=True,stdout=StringIO())
'''
        subprocess.run([str(ROOT/'.venv/bin/python'),'-c',code],cwd=ROOT,env=env,check=True)
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        with (root/'server.log').open('w+') as log:
            process=subprocess.Popen([str(ROOT/'.venv/bin/gunicorn'),'--bind',f'127.0.0.1:{port}','--workers','1','config.wsgi:application'],cwd=ROOT,env=env,stdout=log,stderr=log)
            try:
                for _ in range(100):
                    if process.poll() is not None:raise RuntimeError('Password QA server exited')
                    try:urllib.request.urlopen(base+'/health/',timeout=1).close();break
                    except OSError:time.sleep(.1)
                else:raise TimeoutError('Password QA server did not start')
                subprocess.run(['node','scripts/verification/password_browser.mjs'],cwd=ROOT,env=dict(env,PARAGON_QA_BASE=base),check=True)
            finally:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


if __name__=='__main__':main()
