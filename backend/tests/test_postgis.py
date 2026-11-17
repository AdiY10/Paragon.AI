import pytest
from django.db import connection, transaction, IntegrityError
from apps.accounts.models import Membership

pytestmark = pytest.mark.django_db


def test_membership_email_uniqueness_is_case_insensitive_in_database():
    Membership.objects.create(email='admin@example.org')
    with pytest.raises(IntegrityError), transaction.atomic():
        # bulk_create bypasses model normalization and exercises the SQL constraint.
        Membership.objects.bulk_create([Membership(email='Admin@Example.org')])


@pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires real PostGIS; SQLite cannot verify spatial behavior')
def test_postgis_spherical_distance_and_extension():
    with connection.cursor() as cursor:
        cursor.execute('SELECT postgis_version()')
        assert cursor.fetchone()[0]
        cursor.execute('''SELECT ST_DWithin(
            ST_SetSRID(ST_Point(-73,41),4326)::geography,
            ST_SetSRID(ST_Point(-73,42),4326)::geography, 112000, false),
            ST_DWithin(ST_SetSRID(ST_Point(-73,41),4326)::geography,
            ST_SetSRID(ST_Point(-73,42),4326)::geography, 110000, false)''')
        assert cursor.fetchone() == (True, False)
