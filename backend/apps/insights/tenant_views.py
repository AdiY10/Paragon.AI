"""Tenant roster API (thin layer over apps.locations.tenants) and SEC filer mapping (FR-07, FR-22)."""
import uuid
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from apps.accounts.permissions import IsAdministrator, ExpensiveThrottle
from rest_framework.response import Response
from apps.locations.models import Location, Tenant
from apps.locations.service import LocationConflict
from apps.locations import tenants as svc


def _payload(t):
    from .sec import tenant_events
    filer = getattr(t, 'sec_filer', None)
    return {'id': str(t.id), 'name': t.name, 'is_anchor': t.is_anchor, 'confirmed': t.confirmed, 'archived': t.archived,
        'origin': t.origin, 'presence': t.presence, 'notes': t.notes, 'version': t.version,
        'source_url': t.source_url, 'source_context': t.source_context,
        'sec': tenant_events(t) if filer else None}


def _after_change(location_id, user):
    # Tenant edits advance the location's analysis version (apps.locations.tenants._touch); recompute from cache.
    from .screens import start_computations
    loc = Location.objects.select_related('current_revision').get(pk=location_id)
    if loc.current_revision and loc.current_revision.lat is not None:
        start_computations(loc, user)


def _call(fn, location_id, user):
    try:
        result = fn()
    except (Tenant.DoesNotExist, Location.DoesNotExist):
        return Response({'detail': 'Not found'}, status=404)
    except LocationConflict as exc:
        return Response({'detail': str(exc)}, status=409)
    except (ValueError, ValidationError) as exc:
        return Response({'detail': str(exc)}, status=400)
    _after_change(location_id, user)
    tenant = result[0] if isinstance(result, tuple) else result
    return Response(_payload(Tenant.objects.select_related('sec_filer').get(pk=tenant.pk)))


@api_view(['GET', 'POST'])
def tenant_list(request, location_id):
    location = get_object_or_404(Location, pk=location_id)
    if request.method == 'POST':
        d = request.data
        return _call(lambda: svc.create_tenant(location_id=location.pk, name=str(d.get('name', '')),
            request_key=d.get('request_key') or uuid.uuid4(), actor=request.user, is_anchor=d.get('is_anchor'),
            notes=str(d.get('notes', ''))), location.pk, request.user)
    rows = location.tenants.select_related('sec_filer').order_by('archived', '-is_anchor', 'name')
    return Response({'results': [_payload(t) for t in rows], 'owned': location.status == 'owned'})


@api_view(['PATCH'])
def tenant_detail(request, location_id, tenant_id):
    d = dict(request.data)
    version = d.pop('expected_version', None)
    return _call(lambda: svc.edit_tenant(location_id=location_id, tenant_id=tenant_id, expected_version=version,
        attributes=d, actor=request.user), location_id, request.user)


@api_view(['POST'])
def tenant_confirm(request, location_id, tenant_id):
    return _call(lambda: svc.confirm_tenant(location_id=location_id, tenant_id=tenant_id,
        expected_version=request.data.get('expected_version'), actor=request.user), location_id, request.user)


@api_view(['GET'])
@throttle_classes([ExpensiveThrottle])
def sec_search(request):
    from apps.area.http import SourceError
    from .sec import search_companies
    try:
        return Response({'results': search_companies(str(request.query_params.get('q', ''))[:100])})
    except SourceError as exc:
        return Response({'results': [], 'error': exc.code,
            'detail': 'SEC search needs SEC_USER_AGENT with a contact email.' if exc.code == 'NOT_CONFIGURED' else 'SEC search unavailable.'},
            status=200)


@api_view(['POST', 'DELETE'])
@permission_classes([IsAdministrator])
def tenant_filer(request, location_id, tenant_id):
    """Admins map a tenant to an SEC filer after reviewing suggestions; mappings are never automatic."""
    from .models import TenantFiler
    from .signals import safe_evaluate
    tenant = get_object_or_404(Tenant, pk=tenant_id, location_id=location_id)
    if request.method == 'DELETE':
        TenantFiler.objects.filter(tenant=tenant).delete()
        safe_evaluate(location_id)
        return Response(status=204)
    cik = str(request.data.get('cik', '')).strip()
    name = str(request.data.get('company_name', '')).strip()[:200]
    if not cik.isdigit() or len(cik) > 10 or not name:
        return Response({'detail': 'A numeric CIK and the company name are required'}, status=400)
    TenantFiler.objects.update_or_create(tenant=tenant, defaults={'cik': str(int(cik)), 'company_name': name,
        'mapped_by': request.user})
    safe_evaluate(location_id)
    return Response(_payload(Tenant.objects.select_related('sec_filer').get(pk=tenant.pk)), status=201)
