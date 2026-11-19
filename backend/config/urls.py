from django.urls import path, include
from . import views
from apps.accounts import views as accounts
from apps.accounts import password_access
from apps.sources.views import source_list
from apps.operations import views as operations
from apps.locations import views as locations
from apps.demographics import views as demographics
from apps.area import views as area
from apps.insights import views as insights
from apps.insights import tenant_views as tenants

urlpatterns = [
    path('health/', views.health, name='health'),
    path('access/login/', password_access.sign_in, name='password_login'),
    path('access/logout/', password_access.sign_out, name='password_logout'),
    path('accounts/', include('allauth.urls')),
    path('api/admin/users/', accounts.users),
    path('api/admin/users/<uuid:member_id>/', accounts.member_detail),
    path('api/admin/schedules/', operations.schedules),
    path('api/admin/jobs/', operations.jobs),
    path('api/admin/jobs/<uuid:job_id>/rerun/', operations.rerun),
    path('api/locations/', locations.locations),
    path('api/locations/search/', locations.search),
    path('api/locations/<uuid:location_id>/', locations.location_detail),
    path('api/locations/<uuid:location_id>/geocode/', locations.geocode),
    path('api/locations/<uuid:location_id>/geocode/<uuid:lookup_id>/accept/', locations.geocode_accept),
    path('api/locations/<uuid:location_id>/pin/', locations.pin),
    path('api/locations/<uuid:location_id>/confirm/', locations.confirm),
    path('api/locations/<uuid:location_id>/history/', locations.history),
    path('api/locations/<uuid:location_id>/demographics/', demographics.demographics),
    path('api/locations/<uuid:location_id>/area/', area.area),
    path('api/locations/<uuid:location_id>/summary/', insights.location_summary),
    path('api/signals/', insights.signal_list),
    path('api/screens/', insights.screens),
    path('api/screens/<uuid:location_id>/save/', insights.screen_save),
    path('api/locations/<uuid:location_id>/compute/', insights.location_compute),
    path('api/compare/', insights.compare_view),
    path('api/locations/<uuid:location_id>/tenants/', tenants.tenant_list),
    path('api/locations/<uuid:location_id>/tenants/<uuid:tenant_id>/', tenants.tenant_detail),
    path('api/locations/<uuid:location_id>/tenants/<uuid:tenant_id>/confirm/', tenants.tenant_confirm),
    path('api/locations/<uuid:location_id>/tenants/<uuid:tenant_id>/sec/', tenants.tenant_filer),
    path('api/sec/search/', tenants.sec_search),
    path('api/briefs/latest/', insights.brief_latest),
    path('api/briefs/generate/', insights.brief_generate),
    path('api/briefs/<uuid:brief_id>/', insights.brief_detail),
    path('api/signals/<uuid:signal_id>/review/', insights.signal_review),
    path('api/sources/', source_list),
    path('api/session/', views.session, name='session'),
    path('', views.application, name='application'),
]
