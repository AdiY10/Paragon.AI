"""Versioned tenant maintenance; brands are never silently mapped to legal filers."""
import hashlib
import json
import unicodedata
import uuid
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Location,Tenant,TenantAudit
from .service import LocationConflict,audit


def normalized_name(name):
    if not isinstance(name,str) or not name.strip() or len(name)>200 or any(ord(c)<32 for c in name):
        raise ValueError('A tenant name of at most 200 characters is required')
    return ' '.join(unicodedata.normalize('NFKC',name).replace('’',"'").split()).casefold()


def name_key(name):return hashlib.sha256(normalized_name(name).encode()).hexdigest()


def _location(location_id,*,require_owned=True):
    location=Location.objects.select_for_update().get(pk=location_id)
    if require_owned and location.status!='owned':raise ValueError('Tenant management requires an owned property')
    return location


def _state(tenant):
    return {key:getattr(tenant,key) for key in ('name','is_anchor','confirmed','archived','notes','version')}


def _audit(tenant,actor,action,before):
    after=_state(tenant)
    TenantAudit.objects.create(tenant=tenant,actor=actor,action=action,before=before,after=after)
    audit(tenant.location,actor,'tenant_'+action,{'tenant_id':str(tenant.id),**before},{'tenant_id':str(tenant.id),**after})


def _touch(location):
    # Tenants do not change the trade area: bump the record version (optimistic locking) only.
    # analysis_version is for the pin and ring preset; bumping it here forced every section to recompute.
    location.version+=1
    location.save(update_fields=['version','updated_at'])


def _unique(location,key,exclude=None):
    rows=Tenant.objects.filter(location=location,normalized_key=key,archived=False)
    if exclude:rows=rows.exclude(pk=exclude)
    if rows.exists():raise LocationConflict('An active tenant with this name already exists')


@transaction.atomic
def create_tenant(*,location_id,name,request_key,actor,is_anchor=None,notes=''):
    if actor is None:raise ValueError('A signed-in user is required')
    location=_location(location_id);key=name_key(name)
    if is_anchor is not None and type(is_anchor) is not bool:raise ValueError('Anchor must be true, false, or unknown')
    if not isinstance(notes,str) or len(notes)>5000:raise ValueError('Tenant notes are limited to 5000 characters')
    request_key=uuid.UUID(str(request_key))
    creation_hash=hashlib.sha256(json.dumps({'name':name.strip(),'is_anchor':is_anchor,'notes':notes},sort_keys=True).encode()).hexdigest()
    existing=Tenant.objects.filter(location=location,request_key=request_key).first()
    if existing:
        if existing.creation_hash!=creation_hash:raise LocationConflict('Submission key already used for different tenant data')
        return existing,False
    _unique(location,key)
    tenant=Tenant(location=location,name=name.strip(),normalized_key=key,is_anchor=is_anchor,notes=notes,
        origin='user',source_context={'nature':'User-provided'},created_by=actor,request_key=request_key,creation_hash=creation_hash)
    tenant.full_clean();tenant.save();_audit(tenant,actor,'created',{});_touch(location)
    return tenant,True


@transaction.atomic
def edit_tenant(*,location_id,tenant_id,expected_version,attributes,actor):
    if actor is None:raise ValueError('A signed-in user is required')
    if not attributes or set(attributes)-{'name','is_anchor','notes','archived'}:raise ValueError('Unsupported tenant attributes')
    location=_location(location_id)
    tenant=Tenant.objects.get(pk=tenant_id,location=location)
    if type(expected_version) is not int or expected_version!=tenant.version:raise LocationConflict('Tenant changed; reload before saving')
    before=_state(tenant);was_archived=tenant.archived
    if 'name' in attributes:
        name=attributes['name'];key=name_key(name)
        if name.strip()!=tenant.name:
            tenant.confirmed=False;tenant.confirmed_at=None;tenant.confirmed_by=None
            tenant.source_context={**tenant.source_context,'name_override':{'original_name':tenant.source_context.get('name_override',{}).get('original_name',tenant.name),'changed_at':timezone.now().isoformat()}}
        tenant.name=name.strip();tenant.normalized_key=key
    if 'is_anchor' in attributes:
        value=attributes['is_anchor']
        if value is not None and type(value) is not bool:raise ValueError('Anchor must be true, false, or unknown')
        tenant.is_anchor=value
    if 'notes' in attributes:
        if not isinstance(attributes['notes'],str) or len(attributes['notes'])>5000:raise ValueError('Tenant notes are limited to 5000 characters')
        tenant.notes=attributes['notes']
    if 'archived' in attributes:
        if type(attributes['archived']) is not bool:raise ValueError('Archived must be true or false')
        tenant.archived=attributes['archived']
    if tenant.archived or was_archived:
        tenant.confirmed=False;tenant.confirmed_at=None;tenant.confirmed_by=None
    if not tenant.archived:_unique(location,tenant.normalized_key,exclude=tenant.id)
    tenant.version+=1;tenant.full_clean();tenant.save();_audit(tenant,actor,'archived' if tenant.archived else 'edited',before);_touch(location)
    return tenant


@transaction.atomic
def confirm_tenant(*,location_id,tenant_id,expected_version,actor):
    if actor is None:raise ValueError('A signed-in user is required')
    location=_location(location_id);tenant=Tenant.objects.get(pk=tenant_id,location=location)
    if type(expected_version) is not int or tenant.version!=expected_version:raise LocationConflict('Tenant changed; reload before confirming')
    if tenant.archived:raise ValueError('An archived tenant cannot be confirmed')
    if tenant.confirmed:return tenant
    before=_state(tenant);tenant.confirmed=True;tenant.confirmed_at=timezone.now();tenant.confirmed_by=actor;tenant.version+=1
    tenant.full_clean();tenant.save();_audit(tenant,actor,'confirmed',before);_touch(location)
    return tenant


def archive_for_address_change(location,actor):
    # Caller holds the parent location lock and owns its version/analysis update.
    for tenant in Tenant.objects.filter(location=location,archived=False):
        before=_state(tenant);tenant.archived=True;tenant.confirmed=False;tenant.confirmed_at=None;tenant.confirmed_by=None;tenant.version+=1
        tenant.save();_audit(tenant,actor,'address_archived',before)
