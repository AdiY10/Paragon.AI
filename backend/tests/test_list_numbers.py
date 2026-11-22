"""Redesign B9: the properties list carries flood, nearest supermarket and active alerts in one query budget."""
import pytest
from apps.insights.signals import safe_evaluate
from backend.tests.test_signals import placed, section, economy
from backend.tests.test_screen_compare import member

pytestmark = pytest.mark.django_db


def test_list_key_numbers_include_flood_supermarket_and_alerts(client):
    member(client)
    a, b, c = placed('A'), placed('B'), placed('C')
    section(a, 'hazards', {'flood_at_pin': {'zone': 'AE', 'sfha': True, 'in_sfha': True}, 'flood_nearby': {}, 'nri': {}})
    section(a, 'businesses', {'release': '2026-11-18.0', 'nearest_supermarket': {'name': 'Publix Super Market',
        'brand': 'Publix', 'distance_mi': 0.48}, 'changes': {}})
    section(a, 'economy', economy(priv=0.0, retail=0.0, permits=0.0, units=0))  # one county alert (SIG-05)
    section(b, 'hazards', {'flood_at_pin': {'zone': 'X', 'sfha': False}, 'flood_nearby': {'zone': 'AE', 'sfha': True,
        'inside': False, 'distance_m': 60}, 'nri': {}})
    for loc in (a, b, c):
        safe_evaluate(loc.pk)
    rows = {r['name']: r['key_numbers'] for r in client.get('/api/locations/?page_size=50').json()['results']}
    assert rows['A']['flood'] == 'inside' and rows['A']['nearest_supermarket'] == {'name': 'Publix', 'distance_mi': 0.48}
    assert rows['A']['active_alerts'] == 1
    assert rows['B']['flood'] == 'near' and rows['B']['nearest_supermarket'] is None and rows['B']['active_alerts'] == 0
    assert rows['C']['flood'] is None  # hazards not computed: unknown, not "none"
