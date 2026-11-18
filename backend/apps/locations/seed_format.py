"""Strict validation of the public portfolio seed before any external lookup."""
import csv
from io import StringIO
import math
import re
from pathlib import Path

FIELDS = ['seed_id', 'name', 'street_address_as_listed', 'city', 'state',
    'inferred_asset_type', 'public_facts_as_listed', 'publicly_listed_tenants_or_occupants',
    'source_url', 'census_geocoder_result_2026_11_17', 'reference_lon', 'reference_lat', 'notes']


def read_seed(path: Path) -> list[dict[str, str]]:
    return read_seed_bytes(path.read_bytes())


def read_seed_bytes(payload: bytes) -> list[dict[str, str]]:
    with StringIO(payload.decode('utf-8'),newline='') as handle:
        reader = csv.reader(handle, strict=True)
        if next(reader, None) != FIELDS:
            raise ValueError('Portfolio seed header does not match the expected schema')
        result, seen = [], set()
        for line_number, row in enumerate(reader, 2):
            if len(row) != len(FIELDS):
                raise ValueError(f'Seed line {line_number}: expected {len(FIELDS)} columns, got {len(row)}')
            site = dict(zip(FIELDS, row))
            if not re.fullmatch(r'P\d{2}', site['seed_id']) or site['seed_id'] in seen:
                raise ValueError(f'Seed line {line_number}: invalid or duplicate seed ID')
            seen.add(site['seed_id'])
            if not site['name'] or not site['source_url'].startswith('https://paragonct.com/properties/'):
                raise ValueError(f'Seed line {line_number}: missing name or public provenance')
            if bool(site['reference_lat']) != bool(site['reference_lon']):
                raise ValueError(f'Seed line {line_number}: incomplete coordinate pair')
            if site['reference_lat']:
                lat, lon = float(site['reference_lat']), float(site['reference_lon'])
                if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError(f'Seed line {line_number}: invalid coordinates')
            result.append(site)
        return result
