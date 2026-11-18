"""Persist source-backed previews without holding database locks during HTTP I/O."""
from datetime import timedelta
import hashlib
import re
from io import BytesIO
import uuid
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from apps.sources.health import record_check
from apps.sources.models import SourceDefinition
from apps.sources.snapshots import publish_snapshot,ValidationReport
from apps.sources.storage import LocalArtifactStore,ArtifactIntegrityError
from .census import fetch_census,normalized_address,GeocoderError,ENDPOINT,ADAPTER_VERSION,MAX_BYTES
from .models import GeocodeLookup,Location
from .service import change_pin,LocationConflict,locked_location

CACHE_TTL=timedelta(days=30)


def lookup_address(location):
    address=location.address
    for extra in (location.city,location.state):
        if extra and not re.search(r'(?<!\w)'+re.escape(extra.casefold())+r'(?!\w)',address.casefold()):address+=', '+extra
    return normalized_address(address)


def address_hash(location):
    return hashlib.sha256(lookup_address(location).casefold().encode()).hexdigest()


def lookup_payload(lookup):
    return {'id':str(lookup.id),'location_id':str(lookup.location_id),
        'expected_version':lookup.requested_version,'status':lookup.status,'candidates':lookup.candidates,
        'benchmark':lookup.benchmark,'vintage':lookup.vintage,'expires_at':lookup.expires_at,
        'retrieved_at':lookup.snapshot.retrieved_at,'last_checked_at':lookup.checked_at,'source':{'id':'SRC-01','name':'U.S. Census Bureau',
        'url':lookup.snapshot.source_url,'snapshot_id':str(lookup.snapshot_id),'sha256':lookup.snapshot.sha256},
        'notice':'Census interpolates along the street. This is not building verification. Review the pin before accepting.'}


def request_lookup(*,location_id,expected_version,actor,fetcher=None,store=None):
    if actor is None:raise ValueError('A signed-in user is required')
    location=Location.objects.get(pk=location_id)
    if type(expected_version) is not int or location.version!=expected_version:
        raise LocationConflict('Location changed; reload before requesting a lookup')
    if not SourceDefinition.objects.filter(pk='SRC-01').exists():raise GeocoderError('NOT_CONFIGURED')
    address=lookup_address(location);digest=address_hash(location)
    cached=GeocodeLookup.objects.select_related('snapshot').filter(location=location,address_hash=digest,
        expires_at__gt=timezone.now()).order_by('-snapshot__retrieved_at','-created_at').first()
    if cached:
        snapshot=cached.snapshot;status=cached.status;candidates=cached.candidates
        benchmark=cached.benchmark;vintage=cached.vintage;expires_at=cached.expires_at;checked_at=cached.checked_at
    else:
        run_key='geocode:'+str(uuid.uuid4());scope='geocode:'+str(location.id)
        try:
            capture=(fetcher or fetch_census)(address)
        except GeocoderError as exc:
            record_check(source_id='SRC-01',scope=scope,run_key=run_key,succeeded=False,error_code=exc.code)
            raise
        result=capture.result
        try:
            snapshot,_=publish_snapshot(source_id='SRC-01',scope=scope,
                release=result.benchmark['name']+'/'+result.vintage['name'],
                data_period='Current address ranges; geography vintages retained per layer',
                source_url=ENDPOINT,adapter_version=ADAPTER_VERSION,stream=BytesIO(capture.raw),
                store=store or LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT),max_bytes=MAX_BYTES,
                validation=ValidationReport(passed=True,complete=True,schema={'format':'Census geographies JSON','adapter':ADAPTER_VERSION},record_count=len(result.candidates)),
                retrieved_at=capture.retrieved_at,context={'address_hash':digest,'benchmark':result.benchmark,'vintage':result.vintage,'scope':'Private location address lookup'})
        except (OSError,ArtifactIntegrityError):
            record_check(source_id='SRC-01',scope=scope,run_key=run_key,succeeded=False,error_code='STORAGE_ERROR')
            raise GeocoderError('STORAGE_ERROR') from None
        record_check(source_id='SRC-01',scope=scope,run_key=run_key,succeeded=True,
            completed_at=capture.retrieved_at,snapshot=snapshot)
        status=result.status;candidates=list(result.candidates);benchmark=result.benchmark;vintage=result.vintage
        expires_at=capture.retrieved_at+CACHE_TTL;checked_at=capture.retrieved_at
    # A response may be valid source evidence even if another editor changed the
    # record during the HTTP request. Preserve evidence, reject a stale preview.
    with transaction.atomic():
        current=locked_location(location_id,expected_version)
        if address_hash(current)!=digest:raise LocationConflict('Address changed; request a new lookup')
        lookup,_=GeocodeLookup.objects.get_or_create(location=current,requested_by=actor,
            requested_version=expected_version,snapshot=snapshot,checked_at=checked_at,
            defaults={'address_hash':digest,'status':status,'candidates':candidates,
                'benchmark':benchmark,'vintage':vintage,'expires_at':expires_at})
    return lookup


@transaction.atomic
def accept_lookup(*,location_id,lookup_id,expected_version,candidate_index,actor):
    if actor is None:raise ValueError('A signed-in user is required')
    lookup=GeocodeLookup.objects.select_related('snapshot').get(pk=lookup_id,location_id=location_id,requested_by=actor)
    if type(expected_version) is not int or expected_version!=lookup.requested_version:
        raise LocationConflict('Lookup version does not match the reviewed record')
    if lookup.expires_at<=timezone.now():raise LocationConflict('Lookup expired; request a new suggestion')
    if type(candidate_index) is not int or not 0<=candidate_index<len(lookup.candidates):
        raise ValueError('Select one of the recorded suggestions')
    location=Location.objects.select_for_update().get(pk=location_id)
    context=location.current_revision.context
    if location.version==expected_version+1 and context.get('lookup_id')==str(lookup.id) and context.get('candidate_index')==candidate_index:
        return location
    if location.version!=expected_version or address_hash(location)!=lookup.address_hash:
        raise LocationConflict('Location changed; request and review a new lookup')
    candidate=lookup.candidates[candidate_index]
    return change_pin(location_id=location_id,expected_version=expected_version,
        lat=candidate['lat'],lon=candidate['lon'],method='census_interpolated',confirmed=False,
        matched_address=candidate['matched_address'],actor=actor,
        context={'lookup_id':str(lookup.id),'candidate_index':candidate_index,'source_id':'SRC-01',
            'source_url':lookup.snapshot.source_url,'snapshot_id':str(lookup.snapshot_id),
            'response_sha256':lookup.snapshot.sha256,'retrieved_at':lookup.snapshot.retrieved_at.isoformat(),
            'last_checked_at':lookup.checked_at.isoformat(),'benchmark':lookup.benchmark,'vintage':lookup.vintage,'geographies':candidate['geographies'],
            'match_quality':'not_reported','coordinate_attribution':'U.S. Census Bureau · street-interpolated; not building-verified'})
