"""Validate archived bootstrap extracts before registering their actual provenance."""
from datetime import datetime
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
import re
from .snapshots import publish_snapshot, ValidationReport

COLUMNS = {'id','name','basic_category','brand','operating_status','confidence','sources','lat','lon'}


def import_capture(manifest_path, store):
    manifest_path = Path(manifest_path)
    if not manifest_path.name.endswith('.manifest.json'):
        raise ValueError('Expected a capture manifest')
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest,dict):
        raise ValueError('Capture manifest must be an object')
    release = manifest.get('release','')
    seed_id = manifest.get('seed_id','')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}\.\d+',release) or not re.fullmatch(r'P\d{2}',seed_id):
        raise ValueError('Invalid capture release or seed identifier')
    if manifest.get('status') != 'complete' or set(manifest.get('schema',[])) != COLUMNS:
        raise ValueError('Capture is incomplete or has an unsupported schema')
    source = f's3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*'
    if manifest.get('source') != source:
        raise ValueError('Unexpected Overture capture source')
    coords = manifest.get('coordinates',{})
    for key,limit in [('lat',90),('lon',180)]:
        value = coords.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>limit:
            raise ValueError('Invalid capture pin coordinates')
    if manifest.get('radius_miles') != 3 or manifest.get('pin_status') != 'unconfirmed_seed_reference':
        raise ValueError('Unsupported capture radius or pin provenance')
    if not manifest.get('pin_provenance','').startswith('https://paragonct.com/properties/'):
        raise ValueError('Capture requires its original public pin provenance')
    payload_path = manifest_path.with_name(manifest_path.name.replace('.manifest.json','.json'))
    if payload_path.stat().st_size > 256*1024*1024:
        raise ValueError('Capture exceeds the supported archive size')
    payload = payload_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest.get('sha256'):
        raise ValueError('Archived capture checksum mismatch')
    records = json.loads(payload)
    if not isinstance(records,list) or type(manifest.get('record_count')) is not int or len(records) != manifest['record_count']:
        raise ValueError('Capture record count mismatch')
    ids=set()
    for record in records:
        if not isinstance(record,dict) or set(record) != COLUMNS or not isinstance(record['id'],str) or record['id'] in ids:
            raise ValueError('Capture contains malformed or duplicate place records')
        ids.add(record['id'])
        for key,limit in [('lat',90),('lon',180)]:
            value=record[key]
            if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>limit:
                raise ValueError('Place coordinates are invalid')
        lat1,lat2=math.radians(coords['lat']),math.radians(record['lat'])
        dlon=math.radians(record['lon']-coords['lon'])
        h=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        distance=3958.7613*2*math.asin(math.sqrt(min(1,max(0,h))))
        if distance>3.000001:
            raise ValueError('Place lies outside the capture radius')
        confidence=record['confidence']
        if confidence is not None and (type(confidence) not in (int,float) or not math.isfinite(confidence) or not 0<=confidence<=1):
            raise ValueError('Place confidence is invalid')
        if record['operating_status'] not in (None,'open','temporarily_closed','permanently_closed'):
            raise ValueError('Unsupported operating status')
        if record['sources'] is not None and not isinstance(record['sources'],list):
            raise ValueError('Place attribution must preserve source records')
    context={'coordinates':coords,'radius_miles':3,'pin_status':manifest['pin_status'],
        'pin_provenance':manifest['pin_provenance'],'attribution_url':'https://docs.overturemaps.org/attribution/'}
    pin_key=hashlib.sha256(json.dumps(coords,sort_keys=True).encode()).hexdigest()[:16]
    return publish_snapshot(source_id='SRC-13',scope=f'seed:{seed_id}:pin:{pin_key}',
        release=release,data_period=f'Overture {release}',source_url=source,
        adapter_version='bootstrap-import-v1',stream=BytesIO(payload),store=store,
        validation=ValidationReport(True,True,{'columns':sorted(COLUMNS)},len(records)),
        retrieved_at=datetime.fromisoformat(manifest['retrieved_at']),context=context)
