"""Validated, idempotent migration of a single Sites workspace into a clean backend."""
from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
import hashlib
import json
import math
import re
import uuid
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from apps.sources.catalog import sync_catalog
from apps.sources.storage import LocalArtifactStore
from apps.sources.snapshots import publish_snapshot,ValidationReport,public_source_url
from apps.sources.health import record_check,ERROR_CODES
from .census import parse_census,ENDPOINT,ADAPTER_VERSION
from .models import Location,LocationRevision,WorkspaceImport,ImportedSiteAudit

MAX_BYTES=50*1024*1024

@dataclass(frozen=True)
class ImportResult:
    sha256:str
    locations:int
    revisions:int
    audits:int
    applied:bool
    reused:bool=False


def require(value,message='Invalid workspace export'):
    if not value:raise ValueError(message)


def ident(value):
    try:return str(uuid.UUID(str(value)))
    except (ValueError,TypeError,AttributeError):raise ValueError('Invalid source identifier') from None


def stamp(value):
    try:result=parse_datetime(value) if isinstance(value,str) else None
    except ValueError:result=None
    require(result is not None and timezone.is_aware(result),'Source timestamps must include a timezone')
    require(result<=timezone.now()+timedelta(minutes=5),'Source timestamp is in the future')
    return result


def text(value,length,blank=False):
    require(isinstance(value,str) and len(value)<=length and (blank or value.strip()),'Invalid source text field')
    return value


def integer(value):
    require(type(value) is int and value>=1,'Invalid source version')
    return value


def boolean(value):
    require(type(value) is bool,'Invalid source confirmation')
    return value


def source_url(value):
    if not value:return ''
    require(isinstance(value,str) and len(value)<=2048 and value.startswith('https://'),'Invalid source URL')
    return public_source_url(value)


def _dict(value):
    require(isinstance(value,dict),'Expected source object')
    return value


def load_export(raw):
    require(isinstance(raw,bytes) and len(raw)<=MAX_BYTES,'Workspace export exceeds the migration limit')
    try:data=json.loads(raw,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite JSON value')))
    except (ValueError,UnicodeError):raise ValueError('Invalid workspace JSON') from None
    require(isinstance(data,dict),'Expected workspace object')
    require(type(data.get('schema_version')) is int and data['schema_version'] in (1,2,3),'Unsupported workspace export version')
    rows=data.get('locations');require(isinstance(rows,list) and 36<=len(rows)<=1000,'A complete workspace portfolio is required')
    require(all(isinstance(row,dict) for row in rows),'Invalid portfolio rows')
    require({row.get('seed_id') for row in rows if row.get('seed_id')}=={f'P{i:02}' for i in range(1,37)},'The public portfolio seed is incomplete')
    ids=[ident(row['id']) for row in rows];require(len(set(ids))==len(ids),'Duplicate source location identifiers')
    seeds=[row['seed_id'] for row in rows if row.get('seed_id')]
    require(len(seeds)==len(set(seeds)),'Duplicate source seed identifiers')
    for key in ('revisions','audits','geocode_lookups','source_checks'):
        require(isinstance(data.get(key,[]),list),'Invalid workspace history arrays')
        for row in data.get(key,[]):
            require(isinstance(row,dict),'Invalid source history row')
            require(row.get('location_id') in ids,'History lacks location relationships; use migration export version 3')
    return data


def revision_data(row):
    row=_dict(row);ident(row['id']);integer(row['number']);method=row['method']
    require(method in {v for v,_ in LocationRevision._meta.get_field('method').choices},'Unknown pin method')
    lat,lon=row['lat'],row['lon']
    require((lat is None and lon is None and method=='unplaced') or
        (method!='unplaced' and all(type(v) in (int,float) and math.isfinite(v) for v in (lat,lon)) and -90<=lat<=90 and -180<=lon<=180),'Invalid source coordinates')
    require(not boolean(row['confirmed']) or lat is not None,'Unplaced pins cannot be verified')
    return {'number':row['number'],'lat':lat,'lon':lon,'method':method,'matched_address':text(row.get('matched_address',''),500,True),
        'confirmed':row['confirmed'],'context':_dict(row.get('context',{})),'created_at':stamp(row['created_at'])}


@transaction.atomic
def import_workspace(raw,*,apply=False,store=None):
    data=load_export(raw);digest=hashlib.sha256(raw).hexdigest()
    receipt=WorkspaceImport.objects.filter(pk=digest).first()
    if receipt:return ImportResult(digest,receipt.locations,receipt.revisions,receipt.audits,apply,True)
    workspace=text(data.get('workspace_id','legacy-single-workspace'),160)
    project=text(data.get('source_project_id',''),160,True)
    planned={};source_by_id={ident(row['id']):row for row in data['locations']}
    for source_id,row in source_by_id.items():
        existing=Location.objects.select_for_update().filter(seed_id=row['seed_id']).first() if row.get('seed_id') else Location.objects.select_for_update().filter(pk=source_id).first()
        if existing:
            require(existing.origin=='public_seed' and existing.version==1 and existing.analysis_version==1 and not existing.confirmed and not existing.notes,'Destination has edits; use a clean migration target')
        target=existing or Location(id=source_id)
        for key,limit in [('name',200),('address',500),('city',120),('state',2),('notes',20000)]:setattr(target,key,text(row.get(key,''),limit,key in {'city','state','notes'}))
        require(not target.state or bool(re.fullmatch('[A-Z]{2}',target.state)),'Invalid state code')
        require(row['status'] in Location.Status.values and row['asset_type'] in Location.AssetType.values,'Invalid source location classification')
        require(row['ring_preset'] in ('1/3/5','3/5/10'),'Invalid ring preset')
        gla=row.get('gla_sqft');require(gla is None or (type(gla) is int and gla>0),'Invalid user-provided GLA')
        for key in ('status','asset_type','ring_preset'):setattr(target,key,row[key])
        target.gla_sqft=gla;target.seed_id=row.get('seed_id');target.origin=row['origin']
        require(target.origin in ('public_seed','user'),'Invalid source origin')
        require((target.origin=='public_seed')==bool(target.seed_id),'Source origin and seed identifier conflict')
        target.source_url=source_url(row.get('source_url',''));target.confirmed=boolean(row['confirmed'])
        target.confirmed_at=stamp(row['confirmed_at']) if target.confirmed else None;target.confirmed_by=None
        target.version=max(existing.version if existing else 0,integer(row['version']))+1
        target.analysis_version=integer(row['analysis_version'])
        target.source_context={**_dict(row.get('source_context',{})),'migration':{'workspace_id':workspace,'source_project_id':project,'export_sha256':digest,
            'original_location_id':source_id,'original_version':row['version'],'original_created_at':row['created_at'],'original_updated_at':row['updated_at']}}
        stamp(row['created_at']);stamp(row['updated_at']);target.full_clean()
        planned[source_id]=(target,row,existing is not None)
    revisions={}
    for row in data.get('revisions',[]):
        source_id=ident(row['id']);require(source_id not in revisions,'Duplicate source pin identifiers');revisions[source_id]=(row['location_id'],{key:value for key,value in row.items() if key!='location_id'})
    for source_id,(_,row,_) in planned.items():
        pin=row['current_revision'];key=ident(pin['id'])
        if key in revisions:require(revisions[key][0]==source_id and revisions[key][1]==pin,'Conflicting current pin history')
        revisions[key]=(source_id,pin)
    clean_revisions={key:(location_id,row,revision_data(row)) for key,(location_id,row) in revisions.items()}
    for location_id,(_,row,_) in planned.items():
        values=[entry[2]['number'] for entry in clean_revisions.values() if entry[0]==location_id]
        require(sorted(values)==list(range(1,row['current_revision']['number']+1)),'Pin revision history is incomplete')
    clean_audits=[]
    for event in data.get('audits',[]):
        ident(event['id']);created=stamp(event['created_at']);_dict(event['before']);_dict(event['after'])
        action=text(event['action'],32);actor=text(event.get('actor') or '',254,True)
        clean_audits.append((event,created,action,actor or None))
    require(len({event[0]['id'] for event in clean_audits})==len(clean_audits),'Duplicate source audit identifiers')
    captures=[]
    for lookup in data.get('geocode_lookups',[]):
        source=_dict(lookup['source']);body=text(lookup['raw_response'],1_048_576).encode();result=parse_census(body)
        require(hashlib.sha256(body).hexdigest()==source['sha256'],'Census source hash mismatch')
        require(list(result.candidates)==lookup['candidates'] and result.status==lookup['status'],'Census result conflicts with original response')
        captures.append((lookup,body,result,stamp(lookup['retrieved_at'])))
    for check in data.get('source_checks',[]):
        boolean(check['succeeded']);stamp(check['completed_at']);ident(check['id'])
    result=ImportResult(digest,len(planned),len(clean_revisions),len(clean_audits),apply)
    if not apply:return result
    store=store or LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT)
    # Persist the complete private source export before committing any data pointers.
    artifact=store.put(BytesIO(raw),max_bytes=MAX_BYTES)
    require(artifact.sha256==digest,'Migration artifact digest mismatch')
    sync_catalog();snapshot_map={}
    for lookup,body,parsed,retrieved in captures:
        target=planned[lookup['location_id']][0]
        snapshot,_=publish_snapshot(source_id='SRC-01',scope='geocode:'+str(target.id),
            release=parsed.benchmark['name']+'/'+parsed.vintage['name'],data_period='Current address ranges; geography vintages retained per layer',
            source_url=ENDPOINT,adapter_version=ADAPTER_VERSION,stream=BytesIO(body),store=store,
            validation=ValidationReport(True,True,{'format':'Census geographies JSON','adapter':ADAPTER_VERSION},len(parsed.candidates)),retrieved_at=retrieved,
            context={'migration_export_sha256':digest,'original_snapshot_id':lookup['source']['snapshot_id']})
        snapshot_map[lookup['source']['snapshot_id']]=snapshot
    receipt=WorkspaceImport.objects.create(sha256=digest,workspace_id=workspace,source_project_id=project,
        artifact_key=artifact.key,size_bytes=artifact.size_bytes,locations=result.locations,revisions=result.revisions,audits=result.audits)
    revision_map={}
    for source_id,(target,row,existing) in planned.items():
        old_pin=target.current_revision if existing else None
        target.save()
        entries=sorted([(key,entry) for key,entry in clean_revisions.items() if entry[0]==source_id],key=lambda pair:pair[1][2]['number'])
        for key,(_,original,values) in entries:
            context={**values['context'],'migration':{'original_revision_id':key,'original_actor_id':original.get('actor_id'),'export_sha256':digest}}
            if context.get('snapshot_id') in snapshot_map:context['snapshot_id']=str(snapshot_map[context['snapshot_id']].id)
            if context.get('lookup_id'):context['source_site_lookup_id']=context.pop('lookup_id')
            values={**values,'context':context}
            if old_pin and values['number']==1:
                require(all(getattr(old_pin,field)==values[field] for field in ('lat','lon','method','confirmed')),'Destination reference pin differs; use a clean target')
                pin=old_pin
            else:
                require(not LocationRevision.objects.filter(location=target,number=values['number']).exists(),'Destination pin history conflicts')
                pin=LocationRevision.objects.create(location=target,**values)
            revision_map[key]=pin.id
        target.current_revision_id=revision_map[ident(row['current_revision']['id'])];target.save()
    for event,created,action,actor in clean_audits:
        def mapped(values):return {key:str(revision_map[value]) if key=='revision' and isinstance(value,str) and value in revision_map else value for key,value in values.items()}
        ImportedSiteAudit.objects.create(receipt=receipt,original_id=event['id'],location=planned[event['location_id']][0],
            actor_email=actor,action=action,created_at=created,before=mapped(event['before']),after=mapped(event['after']))
    for check in data.get('source_checks',[]):
        error=check.get('error_code') or ''
        record_check(source_id='SRC-01',scope='geocode:'+str(planned[check['location_id']][0].id),run_key='sites-import:'+check['id'],
            succeeded=check['succeeded'],completed_at=stamp(check['completed_at']),error_code=error if error in ERROR_CODES else ('' if check['succeeded'] else 'SOURCE_ERROR'),
            snapshot=snapshot_map.get(check.get('snapshot_id')))
    return result
