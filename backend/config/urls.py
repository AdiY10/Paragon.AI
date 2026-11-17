from django.urls import path, include
from . import views
from apps.accounts import views as accounts
from apps.sources.views import source_list

urlpatterns = [
    path('health/', views.health, name='health'),
    path('accounts/', include('allauth.urls')),
    path('api/admin/users/', accounts.users),
    path('api/admin/users/<uuid:member_id>/', accounts.member_detail),
    path('api/sources/', source_list),
    path('api/session/', views.session, name='session'),
    path('', views.application, name='application'),
]
