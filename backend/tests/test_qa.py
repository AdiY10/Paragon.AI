"""Redesign B6a: data-quality gate."""
from datetime import timedelta
import pytest
from django.core.management import call_command
from django.utils import timezone
from apps.insights import qa
from backend.tests.test_signals import placed, section

pytestmark = pytest.mark.django_db


def ring(miles, pop, hh, med, mean, rel='high'):
    m = lambda v, r=rel: {'value': v, 'reliability': r}  # noqa: E731
    return {'radius_miles': miles, 'metrics': {'population': m(pop), 'households': m(hh),
        'median_household_income': m(med), 'mean_household_income': m(mean, 'high')}}


class Demo:
    acs_year = 2024

    def __init__(self, rings):
        self.rings = rings


GOOD = [ring(1, 10_000, 4_000, 80_000, 100_000), ring(3, 80_000, 32_000, 85_000, 110_000),
    ring(5, 150_000, 60_000, 90_000, 115_000)]


@pytest.fixture
def clean(monkeypatch):
    """A property whose stored analysis passes every check."""
    loc = placed('Clean Center')
    state = {'demo': Demo(GOOD)}
    monkeypatch.setattr('apps.demographics.service.current_result', lambda l: state['demo'])
    monkeypatch.setattr('apps.demographics.vintage.current_acs_year', lambda *a: 2024)
    monkeypatch.setattr('apps.area.analysis.missing_sections', lambda l: [])
    section(loc, 'economy', {'county': {'fips': '09190', 'name': 'Western CT'}})
    section(loc, 'traffic', {'roads': [{'label': 'Route 1', 'aadt': 14_400, 'road_class': 'Principal arterial', 'distance_m': 8}]})
    section(loc, 'hazards', {'flood_at_pin': {'zone': 'AE', 'sfha': True, 'in_sfha': True}, 'flood_nearby': {'zone': 'AE', 'inside': True},
        'nri': {'tract': '09190043500'}})
    section(loc, 'jobs', {'rings': [{'radius_miles': 1, 'total': 5000}, {'radius_miles': 3, 'total': 44_000}]})
    section(loc, 'businesses', {'release': '2026-11-18.0', 'retail_and_services_total': {'3mi': 1861}})
    return loc, state


def checks(loc):
    return {(f['check'], f['level']) for f in qa.check_location(loc)}


def test_a_plausible_analysis_passes(clean):
    loc, _ = clean
    assert qa.check_location(loc) == []


@pytest.mark.parametrize('rings,check', [
    ([ring(1, 10_000, 4_000, 80_000, 100_000), ring(3, 9_000, 3_600, 80_000, 100_000)], 'rings_increase'),
    ([ring(1, 10_000, 9_000, 80_000, 100_000)], 'households_per_person'),
    ([ring(1, 10_000, 4_000, 300_000, 400_000)], 'median_income_range'),
    ([ring(1, 10_000, 4_000, 90_000, 60_000)], 'median_vs_mean_income'),
    ([ring(3, 80_000, 32_000, 85_000, 110_000, rel='very_low')], 'headline_reliability'),
])
def test_implausible_demographics_fail(clean, rings, check):
    loc, state = clean
    state['demo'] = Demo(rings)
    assert (check, 'fail') in checks(loc)


@pytest.mark.parametrize('section_name,data,check', [
    ('traffic', {'roads': [{'label': 'K120 Birch St', 'aadt': 9_000, 'road_class': 'Minor arterial', 'distance_m': 20}]}, 'road_label'),
    ('traffic', {'roads': [{'label': 'Elm St', 'aadt': 90_000, 'road_class': 'Local', 'distance_m': 20}]}, 'aadt_plausible'),
    ('traffic', {'roads': [{'label': 'Elm St', 'aadt': 900, 'road_class': 'Local', 'distance_m': 400}]}, 'road_distance'),
    ('hazards', {'flood_at_pin': {'zone': 'X', 'in_sfha': True}, 'flood_nearby': {}, 'nri': {'tract': '09190043500'}}, 'flood_zone_consistent'),
    ('hazards', {'flood_at_pin': {'zone': 'X'}, 'flood_nearby': {}, 'nri': {'tract': '36111951400'}}, 'county_matches_tract'),
    ('jobs', {'rings': [{'radius_miles': 1, 'total': 5000}, {'radius_miles': 3, 'total': 4000}]}, 'rings_increase'),
])
def test_inconsistent_sections_fail(clean, section_name, data, check):
    loc, _ = clean
    section(loc, section_name, data)  # newer row wins
    assert (check, 'fail') in checks(loc)


def test_ordinal_streets_are_not_inventory_codes():
    for label in ('16th St SW', '2nd Ave', '101st St', 'US 9W', 'NC-87', 'Ulster Ave US 9W'):
        assert not qa.INVENTORY_CODE.match(label), label


def test_business_count_swing_between_releases(clean):
    loc, _ = clean
    section(loc, 'businesses', {'release': '2026-12-16.0', 'retail_and_services_total': {'3mi': 2400}})
    assert ('business_count_swing', 'fail') in checks(loc)


def test_stale_and_missing_sections(clean, monkeypatch):
    loc, _ = clean
    from apps.area.models import AreaSection
    row = AreaSection.objects.get(location=loc, section='economy')
    # Results are immutable through `objects`; age this one through the base manager.
    AreaSection._base_manager.filter(pk=row.pk).update(computed_at=timezone.now() - timedelta(days=30))
    assert ('fresh', 'fail') in checks(loc)
    monkeypatch.setattr('apps.area.analysis.missing_sections', lambda l: ['traffic'])
    assert ('complete', 'fail') in checks(loc)


def test_golden_values(clean, tmp_path, settings):
    loc, _ = clean
    golden = tmp_path / 'config'
    golden.mkdir()
    (golden / 'qa_golden.yaml').write_text("""schema_version: 1
golden:
  - {location: clean center, check: population, ring_miles: 3, value: 84000, tolerance: 0.10}
  - {location: clean center, check: population, ring_miles: 1, value: 20000, tolerance: 0.10}
  - {location: clean center, check: road_aadt, road: route 1, year: 2025, value: 14400, tolerance: 0}
  - {location: clean center, check: flood_zone, value: AE}
  - {location: nowhere, check: flood_zone, value: AE}
""")
    entries = qa.load_golden(golden / 'qa_golden.yaml')
    section(loc, 'traffic', {'roads': [{'label': 'Route 1', 'aadt': 14_400, 'year': 2025, 'road_class': 'Principal arterial', 'distance_m': 8}]})
    from apps.locations.models import Location
    Location.objects.filter(pk=loc.pk).update(status='owned')
    results = [qa.check_golden(e) for e in entries]
    assert results[0] == [] and results[2] == [] and results[3] == []
    assert 'expected 20000 ±10%, got 10000' in results[1][0]['detail']
    assert results[4][0]['detail'] == 'property not found'


def test_strict_command_exits_non_zero_on_failure(clean, monkeypatch, capsys):
    loc, state = clean
    monkeypatch.setattr(qa, 'load_golden', lambda path=None: [])
    call_command('qa_report', '--strict')
    assert '0 failures' in capsys.readouterr().out
    state['demo'] = Demo([ring(1, 10_000, 9_000, 80_000, 100_000)])
    with pytest.raises(SystemExit) as exit_:
        call_command('qa_report', '--strict')
    assert exit_.value.code == 1
