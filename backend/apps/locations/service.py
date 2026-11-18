import math
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Location,LocationRevision,LocationAuditEvent

EDITABLE={'name','address','city','state','status','asset_type','ring_preset','gla_sqft','notes'}

class LocationConflict(ValueError):
    pass


def validate_pin(lat,lon,method):
    allowed={value for value,_ in LocationRevision._meta.get_field('method').choices}
    if method not in allowed:raise ValueError('Invalid pin method')
    if lat is None and lon is None and method=='unplaced':return
    if method=='unplaced' or type(lat) not in (int,float) or type(lon) not in (int,float) or not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90 or not -180<=lon<=180:
        raise ValueError('A finite, valid coordinate pair is required')


def audit(location,actor,action,before,after):
    LocationAuditEvent.objects.create(location=location,actor=actor,action=action,before=before,after=after)


@transaction.atomic
def create_location(*,name,address,actor=None,status='candidate',asset_type='other',lat=None,lon=None,
        pin_method='unplaced',pin_context=None,seed_id=None,source_url='',city='',state='',origin='user',source_context=None):
    validate_pin(lat,lon,pin_method)
    location=Location(name=name,address=address,created_by=actor,status=status,asset_type=asset_type,
        seed_id=seed_id,source_url=source_url,city=city,state=state,origin=origin,source_context=dict(source_context or {}))
    location.full_clean();location.save()
    revision=LocationRevision.objects.create(location=location,number=1,lat=lat,lon=lon,
        method=pin_method,actor=actor,context=dict(pin_context or {}))
    location.current_revision=revision;location.save(update_fields=['current_revision','updated_at'])
    audit(location,actor,'created',{}, {'origin':origin,'status':status,'revision':str(revision.pk)})
    return location


def locked_location(location_id,expected_version):
    location=Location.objects.select_for_update().get(pk=location_id)
    if type(expected_version) is not int or location.version!=expected_version:
        raise LocationConflict('Location changed; reload before saving')
    return location


@transaction.atomic
def update_location(*,location_id,expected_version,attributes,actor):
    if not attributes or set(attributes)-EDITABLE:raise ValueError('Invalid editable location attributes')
    location=locked_location(location_id,expected_version)
    before={key:getattr(location,key) for key in attributes}
    address_changed=any(key in attributes and attributes[key]!=getattr(location,key) for key in ('address','city','state'))
    previous_address=location.address
    previous_revision=location.current_revision
    previous_confirmed=location.confirmed
    for key,value in attributes.items():setattr(location,key,value)
    ring_changed='ring_preset' in attributes and attributes['ring_preset']!=before['ring_preset']
    if address_changed or ring_changed:location.analysis_version+=1
    after=dict(attributes)
    if address_changed:
        location.current_revision=LocationRevision.objects.create(location=location,
            number=previous_revision.number+1,lat=None,lon=None,method='unplaced',
            matched_address='',confirmed=False,actor=actor,
            context={'reason':'Address changed; pin placement requires review',
                'previous_revision_id':str(previous_revision.pk)})
        location.confirmed=False;location.confirmed_at=None;location.confirmed_by=None
        location.source_context={**location.source_context,'address_override':{
            'original_address':location.source_context.get('address_override',{}).get('original_address',previous_address),
            'changed_at':timezone.now().isoformat(),'nature':'User-edited address'}}
        before.update(revision=str(previous_revision.pk),confirmed=previous_confirmed)
        after.update(revision=str(location.current_revision.pk),confirmed=False,
            analysis_version=location.analysis_version,reason='Address changed; pin and ownership require review')
    location.version+=1
    location.full_clean();location.save()
    audit(location,actor,'address_changed' if address_changed else 'attributes_changed',before,after)
    return location


@transaction.atomic
def change_pin(*,location_id,expected_version,lat,lon,actor,method='manual',matched_address='',context=None,confirmed=False):
    validate_pin(lat,lon,method)
    location=locked_location(location_id,expected_version)
    old=location.current_revision
    revision=LocationRevision.objects.create(location=location,number=old.number+1,
        lat=lat,lon=lon,method=method,matched_address=matched_address,context=dict(context or {}),actor=actor,confirmed=confirmed)
    location.current_revision=revision;location.version+=1;location.analysis_version+=1
    location.save(update_fields=['current_revision','version','analysis_version','updated_at'])
    audit(location,actor,'pin_changed',{'revision':str(old.pk)},{'revision':str(revision.pk),'analysis_version':location.analysis_version})
    return location


@transaction.atomic
def confirm_location(*,location_id,expected_version,actor):
    if actor is None:raise ValueError('Ownership confirmation requires a user')
    location=locked_location(location_id,expected_version)
    if location.confirmed:return location
    location.confirmed=True;location.confirmed_at=timezone.now();location.confirmed_by=actor
    location.version+=1;location.save()
    audit(location,actor,'confirmed',{'confirmed':False},{'confirmed':True})
    return location
