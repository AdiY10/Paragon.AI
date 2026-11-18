import json
import re
import pytest
from django.test import Client
from config.frontend import frontend_assets
from django.core.exceptions import ImproperlyConfigured
from .test_accounts import member


@pytest.fixture
def frontend_manifest(settings, tmp_path):
    settings.FRONTEND_MANIFEST = tmp_path / 'manifest.json'
    settings.FRONTEND_MANIFEST.write_text(json.dumps({'src/main.tsx': {
        'isEntry': True, 'file': 'assets/main-test.js', 'css': ['assets/main-test.css']}}))
    return settings.FRONTEND_MANIFEST


@pytest.mark.django_db
def test_workspace_uses_local_assets_no_private_data_and_no_cache(frontend_manifest):
    user, _ = member()
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    response = client.get('/')
    assert response.status_code == 200
    html = response.content.decode()
    assert '/static/ui/assets/main-test.js' in html
    assert '/static/ui/assets/main-test.css' in html
    assert 'no-store' in response['Cache-Control']
    assert user.email not in html
    assert client.cookies['csrftoken']['httponly']
    token = re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)
    assert len(token) == 64
    path = '/api/locations/'
    data = {'name': 'Test-only record', 'address': 'Test-only address'}
    assert client.post(path, data, content_type='application/json').status_code == 403
    assert client.post(path, data, content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code == 201


@pytest.mark.parametrize('path', ['https://evil.test/code.js', '../private.json',
    'assets/../../private.json', 'assets/code.js?inject', 'assets/evil\\code.js'])
def test_manifest_rejects_nonlocal_assets(frontend_manifest, path):
    frontend_manifest.write_text(json.dumps({'src/main.tsx': {'isEntry': True, 'file': path}}))
    with pytest.raises(ImproperlyConfigured):
        frontend_assets()


@pytest.mark.django_db
def test_missing_build_is_explicit_and_private(settings, tmp_path, client):
    settings.FRONTEND_MANIFEST = tmp_path / 'missing.json'
    assert client.get('/').status_code == 302
    user, _ = member()
    client.force_login(user)
    response = client.get('/')
    assert response.status_code == 503
    assert 'no-store' in response['Cache-Control']
    assert str(tmp_path).encode() not in response.content
