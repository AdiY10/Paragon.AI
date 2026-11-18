"""Browser verification on an ephemeral test database, never production accounts.

Build frontend first. Set CHROMIUM_PATH for an existing Chromium, or install
Playwright's browser with `cd frontend && npx playwright install chromium`.
Optional UI_SCREENSHOT_DIR retains screenshots of the real public seed records.
"""
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def main():
    with tempfile.TemporaryDirectory(prefix='paragon-ui-test-') as directory:
        testdir = Path(directory)
        (testdir/'ui_test_settings.py').write_text(
            'from config.settings.test import *\n'
            'DATABASES=' + repr({"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(testdir/"test.sqlite3")}}) + '\n'
            'ALLOWED_HOSTS=["127.0.0.1", "localhost"]\n')
        env = dict(os.environ, DJANGO_SETTINGS_MODULE='ui_test_settings',
                   PYTHONPATH=os.pathsep.join([str(ROOT/'backend'), directory]))
        setup = '''import django; django.setup()
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import Client
from apps.accounts.models import Membership
from apps.locations.seeding import import_public_portfolio
call_command('migrate', verbosity=0)
call_command('sync_sources', verbosity=0)
import_public_portfolio()
user=get_user_model().objects.create_user(username='ui-test-only',email='ui-test@example.invalid')
Membership.objects.create(user=user,email=user.email,role='admin')
client=Client(); client.force_login(user)
print('UI_SESSION='+client.cookies['sessionid'].value)
'''
        result = subprocess.run([str(ROOT/'.venv/bin/python'), '-c', setup],
                                cwd=ROOT, env=env, capture_output=True, text=True, check=True)
        session = next(line.removeprefix('UI_SESSION=') for line in result.stdout.splitlines() if line.startswith('UI_SESSION='))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        with (testdir/'server.log').open('w+') as log:
            process = subprocess.Popen([str(ROOT/'.venv/bin/gunicorn'), '--bind',
                f'127.0.0.1:{port}', '--workers', '1', 'config.wsgi:application'],
                cwd=ROOT, env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('UI test server exited')
                    try:
                        urllib.request.urlopen(base+'/health/', timeout=1).close()
                        break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise TimeoutError('UI test server did not start')
                subprocess.run(['node', 'tests/browser-smoke.mjs'], cwd=ROOT/'frontend',
                    env=dict(env, UI_BASE_URL=base, UI_SESSION_KEY=session), check=True)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == '__main__':
    main()
