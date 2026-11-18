from django.urls import path, include
from . import views
from apps.accounts import views as accounts
from apps.sources.views import source_list
from apps.operations import views as operations
from apps.locations import views as locations

urlpatterns = [
    path('health/', views.health, name='health'),
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
    path('api/sources/', source_list),
    path('api/session/', views.session, name='session'),
    path('', views.application, name='application'),
]
