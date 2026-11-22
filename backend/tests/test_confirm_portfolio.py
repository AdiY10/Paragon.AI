"""Redesign B1: owned properties are always confirmed."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from apps.locations.models import Location, LocationAuditEvent
from apps.locations.seeding import import_public_portfolio
from apps.locations.service import create_location, update_location
from backend.tests.test_accounts import member

pytestmark = pytest.mark.django_db


def test_confirm_portfolio_confirms_seeded_owned_properties_once():
    from apps.sources.catalog import sync_catalog
    sync_catalog()
    import_public_portfolio()
    with pytest.raises(CommandError):
        call_command('confirm_portfolio')  # no administrator yet
    member('admin@example.org', 'admin')
    call_command('confirm_portfolio', '--dry-run')
    assert not Location.objects.filter(confirmed=True).exists()
    call_command('confirm_portfolio')
    owned = Location.objects.filter(status='owned')
    assert owned.count() == 36 and not owned.filter(confirmed=False).exists()
    events = LocationAuditEvent.objects.filter(action='confirmed').count()
    call_command('confirm_portfolio')  # idempotent
    assert LocationAuditEvent.objects.filter(action='confirmed').count() == events == 36


def test_owned_properties_are_confirmed_when_created_or_promoted():
    user, _ = member()
    owned = create_location(name='New center', address='1 Main St', status='owned', actor=user)
    assert owned.confirmed and owned.confirmed_by == user
    candidate = create_location(name='Maybe', address='2 Main St', status='candidate', actor=user)
    assert not candidate.confirmed
    promoted = update_location(location_id=candidate.pk, expected_version=candidate.version,
        attributes={'status': 'owned'}, actor=user)
    assert promoted.confirmed


def test_address_change_keeps_owned_property_confirmed():
    user, _ = member()
    owned = create_location(name='Center', address='1 Main St', status='owned', actor=user)
    owned.refresh_from_db()
    changed = update_location(location_id=owned.pk, expected_version=owned.version,
        attributes={'address': '3 Elm St'}, actor=user)
    assert changed.confirmed and changed.current_revision.lat is None and not changed.current_revision.confirmed
