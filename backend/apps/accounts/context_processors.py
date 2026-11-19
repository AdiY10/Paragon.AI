from django.conf import settings

def access_options(request):
    return {'password_access_enabled':settings.PASSWORD_ACCESS_ENABLED}
