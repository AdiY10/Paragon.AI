from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health, name='health'),
    path('accounts/login/', views.sign_in, name='login'),
    path('api/session/', views.session, name='session'),
    path('', views.application, name='application'),
]
