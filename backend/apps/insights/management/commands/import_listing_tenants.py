"""Import tenants named on the public paragonct.com listings as unconfirmed references (A-06).

They are dated listing claims, not facts: presence is "listed_unverified" (or
neighbor/co-tenant, planned, name-only where the listing says so), anchors are
marked only where the listing says "anchor", and nothing is confirmed. Re-running
is idempotent (seed_key per location and name).
"""
import csv
import re
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.locations.models import Location, Tenant
from apps.locations.tenants import name_key


def parse_listing(text):
    text = text or ''
    row_presence = 'neighbor_or_cotenant' if 'co-tenants or neighbors' in text else None
    out = []
    for part in [p.strip() for p in text.split(';') if p.strip()]:
        qualifiers = re.findall(r'\(([^)]*)\)', part)
        name = re.sub(r'\s*\([^)]*\)', '', part).strip()
        if not name:
            continue
        q = ' '.join(qualifiers).lower()
        presence = row_presence or ('planned_unverified' if 'soon to open' in q else
            'name_only' if 'from the property name' in q else 'listed_unverified')
        for each in [n.strip() for n in re.split(r'\s+and\s+(?=[A-Z])', name)] if 'soon to open' in q else [name]:
            out.append({'name': each, 'is_anchor': True if 'anchor' in q else None, 'presence': presence,
                'qualifier': ' '.join(qualifiers)})
    return out


class Command(BaseCommand):
    help = 'Import publicly listed tenants for seeded owned properties as unconfirmed listing references.'

    def add_arguments(self, parser):
        parser.add_argument('--seed', type=Path, default=Path(settings.BASE_DIR) / 'data/seed/paragon_public_properties.csv')

    @transaction.atomic
    def handle(self, *args, **options):
        created = skipped = 0
        with open(options['seed'], newline='', encoding='utf-8') as handle:
            for row in csv.DictReader(handle):
                location = Location.objects.filter(seed_id=row['seed_id']).first()
                if location is None or location.status != 'owned':
                    continue
                for item in parse_listing(row['publicly_listed_tenants_or_occupants']):
                    key = name_key(item['name'])
                    if Tenant.objects.filter(location=location, seed_key=key).exists() or \
                            Tenant.objects.filter(location=location, normalized_key=key, archived=False).exists():
                        skipped += 1
                        continue
                    Tenant.objects.create(location=location, name=item['name'], normalized_key=key,
                        is_anchor=item['is_anchor'], origin='public_seed', source_url=row['source_url'],
                        presence=item['presence'], seed_key=key,
                        source_context={'nature': 'Public listing claim (unverified)', 'source_as_of': '2026-11-17',
                            'listing_text': row['publicly_listed_tenants_or_occupants'], 'qualifier': item['qualifier']})
                    created += 1
        self.stdout.write(f'Listing tenants created {created}; already present {skipped}.')
