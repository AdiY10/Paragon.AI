"""R2 item 2: admin permission, throttles, input validation, redirects, readiness."""
from unittest.mock import MagicMock
import pytest
from backend.tests.test_accounts import member

pytestmark = pytest.mark.django_db


def test_signal_list_rejects_bad_location_param(client):
    user, _ = member()
    client.force_login(user)
    assert client.get('/api/signals/?location=not-a-uuid').status_code == 400
    assert client.get('/api/signals/?location=00000000-0000-0000-0000-000000000000').json() == {'groups': [], 'results': []}


def test_admin_only_endpoints_use_shared_permission(client):
    user, _ = member('m@example.org', 'member')
    client.force_login(user)
    assert client.post('/api/briefs/generate/').status_code == 403


def test_expensive_endpoints_are_throttled_per_user(client, settings):
    from django.core.cache import cache
    cache.clear()
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {'expensive': '2/hour'}}
    from rest_framework.throttling import SimpleRateThrottle
    SimpleRateThrottle.THROTTLE_RATES = {'expensive': '2/hour'}
    try:
        user, _ = member()
        client.force_login(user)
        codes = [client.post('/api/screens/', {'address': ''}, content_type='application/json').status_code
            for _ in range(3)]
        assert codes[-1] == 429 and 429 not in codes[:2]
        assert client.get('/api/screens/').status_code == 200  # reads are not throttled
    finally:
        from rest_framework.settings import api_settings
        SimpleRateThrottle.THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES
        cache.clear()


def test_geoids_are_validated_before_the_arcgis_query(monkeypatch):
    from apps.demographics import geography
    wheres = []

    def fake_paged(url, params, opener, timeout):
        if 'where' in params:
            wheres.append(params['where'])
            return []
        return [{'GEOID': "090010101001000"}, {'GEOID': "0') OR 1=1 --xxxxx"}]
    monkeypatch.setattr(geography, '_paged', fake_paged)
    geography.fetch_geography(41.1, -73.4, 1, acs_year=2024)
    assert wheres == ["GEOID IN ('090010101001')"]


def test_redirects_only_within_the_same_site():
    from urllib.error import HTTPError
    from urllib.request import Request
    from apps.area.http import _SameSiteRedirects
    h = _SameSiteRedirects()
    req = Request('https://www.census.gov/a')
    assert h.redirect_request(req, MagicMock(), 302, 'Found', {}, 'https://www2.census.gov/b').full_url.endswith('/b')
    for bad in ('https://evil.example/b', 'http://www2.census.gov/b', 'file:///etc/passwd'):
        with pytest.raises(HTTPError):
            h.redirect_request(req, MagicMock(), 302, 'Found', {}, bad)


def test_health_ready_checks_database(client):
    assert client.get('/health/ready/').json() == {'status': 'ok'}
