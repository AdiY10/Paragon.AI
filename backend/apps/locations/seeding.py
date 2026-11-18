"""One-time public portfolio seed; never overwrite confirmation or user edits."""
from dataclasses import dataclass
from datetime import date
import hashlib
from pathlib import Path
from django.conf import settings
from django.db import transaction
from apps.sources.models import SourceDefinition
from .models import Location,SeedImportBatch
from .seed_format import read_seed_bytes
from .service import create_location

SOURCE_AS_OF=date(2026,11,17)

@dataclass(frozen=True)
class ImportResult:
    batch: SeedImportBatch
    created: int
    existing: int


def asset_type(text):
    normalized=text.casefold()
    if 'mixed-use' in normalized:return 'mixed_use'
    if normalized.startswith('office'):return 'office'
    if normalized.startswith('single-tenant'):return 'single_tenant_retail'
    if 'retail center' in normalized or 'retail strip' in normalized:return 'retail_center'
    return 'other'


@transaction.atomic
def import_public_portfolio(path=None):
    path=Path(path or settings.BASE_DIR/'data/seed/paragon_public_properties.csv')
    payload=path.read_bytes()
    rows=read_seed_bytes(payload)
    if {row['seed_id'] for row in rows}!={f'P{i:02}' for i in range(1,37)}:
        raise ValueError('This one-time portfolio seed must contain exactly P01 through P36')
    digest=hashlib.sha256(payload).hexdigest()
    # Serialize seed importers on the persistent source row, not a process-local lock.
    SourceDefinition.objects.select_for_update().get(pk='SRC-16')
    existing=set(Location.objects.exclude(seed_id=None).values_list('seed_id',flat=True))
    created=[]
    for row in rows:
        if row['seed_id'] in existing:continue
        has_pin=bool(row['reference_lat'])
        context={'source_as_of':SOURCE_AS_OF.isoformat(),'source_sha256':digest,
            'source_url':row['source_url'],'geocoder_result_as_listed':row['census_geocoder_result_2026_11_17']}
        if has_pin:
            osm='Nominatim' in row['notes']
            context['coordinate_source']='OpenStreetMap Nominatim (seed reference)' if osm else 'US Census Geocoder (seed reference)'
            context['coordinate_attribution']='© OpenStreetMap contributors' if osm else 'U.S. Census Bureau'
        location=create_location(name=row['name'],
            address=f"{row['street_address_as_listed']}, {row['city']}, {row['state']}",
            city=row['city'],state=row['state'],status='owned',origin='public_seed',
            seed_id=row['seed_id'],source_url=row['source_url'],
            asset_type=asset_type(row['inferred_asset_type']),
            lat=float(row['reference_lat']) if has_pin else None,
            lon=float(row['reference_lon']) if has_pin else None,
            pin_method='seed_reference' if has_pin else 'unplaced',pin_context=context,
            source_context={'source_as_of':SOURCE_AS_OF.isoformat(),'asset_type_as_listed':row['inferred_asset_type']})
        created.append(location.pk)
    batch,_=SeedImportBatch.objects.get_or_create(sha256=digest,
        defaults={'source_as_of':SOURCE_AS_OF,'rows':len(rows),'created_locations':len(created)})
    if created:Location.objects.filter(pk__in=created).update(seed_batch=batch)
    SourceDefinition.objects.filter(pk='SRC-16').update(adapter_version='public-seed-v1')
    return ImportResult(batch,len(created),len(rows)-len(created))
