import os
import subprocess
import sys
from pathlib import Path


def test_health_contains_no_business_data(client):
    response = client.get('/health/')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_anonymous_application_redirects_to_sign_in(client):
    response = client.get('/')
    assert response.status_code == 302
    assert response.url.startswith('/accounts/login/')


def test_anonymous_api_denies_access(client):
    response = client.get('/api/session/')
    assert response.status_code == 403
    assert 'email' not in response.json()


def test_production_refuses_missing_secret():
    env = {k: v for k, v in os.environ.items() if k not in {'DJANGO_SECRET_KEY', 'DJANGO_SETTINGS_MODULE'}}
    result = subprocess.run([sys.executable, 'backend/manage.py', 'check'],
        cwd=Path(__file__).resolve().parents[2], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'DJANGO_SECRET_KEY' in result.stderr
