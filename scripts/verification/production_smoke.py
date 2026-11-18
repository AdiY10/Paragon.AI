"""Run production Gunicorn on a private socket and check anonymous routes.

Requires explicit production settings/secrets and a migrated disposable database.
Does not create any member, synthetic data, or authentication bypass.
"""
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


class SocketHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__('localhost', timeout=5)
        self.path = path
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect(self.path)


def main():
    with tempfile.TemporaryDirectory(prefix='paragon-wsgi-') as directory:
        path = str(Path(directory)/'http.sock')
        env = dict(os.environ, DJANGO_SETTINGS_MODULE='config.settings.production',
            PYTHONPATH=str(ROOT/'backend'), GUNICORN_BIND='unix:'+path, WEB_CONCURRENCY='1')
        with (Path(directory)/'gunicorn.log').open('w+') as log:
            process = subprocess.Popen([str(ROOT/'.venv/bin/gunicorn'), '--config',
                'infra/gunicorn.conf.py', 'config.wsgi:application'], cwd=ROOT, env=env,
                stdout=log, stderr=log)
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('Production WSGI process exited before becoming ready')
                    if Path(path).exists():
                        break
                    time.sleep(.1)
                else:
                    raise TimeoutError('Production WSGI socket did not appear')
                results = {}
                manifest = json.loads((ROOT/'backend/static/ui/.vite/manifest.json').read_text())['src/main.tsx']
                static_routes = [('/static/ui/assets/'+asset.name, 200)
                    for asset in sorted((ROOT/'backend/static/ui/assets').iterdir())
                    if asset.suffix in {'.js', '.css'}]
                for route, expected in [('/health/',200),('/',302),('/api/session/',403),('/api/locations/',403),('/api/sources/',403),('/api/admin/jobs/',403),('/api/admin/schedules/',403),('/accounts/login/',200), *static_routes]:
                    connection = SocketHTTPConnection(path)
                    connection.request('GET', route, headers={'Host':'localhost','X-Forwarded-Proto':'https'})
                    response = connection.getresponse()
                    payload = response.read()
                    assert response.status == expected, (route, response.status)
                    assert response.getheader('Strict-Transport-Security')
                    if route == '/health/':
                        assert json.loads(payload) == {'status':'ok'}
                    results[route] = response.status
                    connection.close()
                print(json.dumps({'status':'passed','routes':results,'settings':'production'}))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

if __name__ == '__main__':
    main()
