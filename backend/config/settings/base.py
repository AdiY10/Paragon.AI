"""Shared configuration. Production validation lives in production.py."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
DEBUG = False
ALLOWED_HOSTS = [v.strip() for v in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if v.strip()]
INSTALLED_APPS = [
    'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
    'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'drf_spectacular', 'apps.accounts', 'apps.sources', 'apps.operations', 'apps.locations', 'apps.demographics', 'apps.area', 'django_q',
    'allauth', 'allauth.account', 'allauth.socialaccount',
    'allauth.socialaccount.providers.openid_connect',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.accounts.middleware.ActiveMembershipMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.auth.middleware.LoginRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'backend' / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'apps.accounts.context_processors.access_options',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = 'America/New_York'
LANGUAGE_CODE = 'en-us'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'var' / 'static'
STATICFILES_DIRS = [BASE_DIR / 'backend' / 'static'] if (BASE_DIR / 'backend' / 'static').exists() else []
FRONTEND_MANIFEST = BASE_DIR / 'backend' / 'static' / 'ui' / '.vite' / 'manifest.json'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'}}
WHITENOISE_INDEX_FILE = False
PASSWORD_ACCESS_ENABLED = os.environ.get('PASSWORD_ACCESS_ENABLED','false').lower()=='true'
LOGIN_URL = '/access/login/' if PASSWORD_ACCESS_ENABLED else '/accounts/login/'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':14}},
    {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
]
LOGIN_REDIRECT_URL = '/'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}
SPECTACULAR_SETTINGS = {'TITLE': 'Paragon Radar API', 'VERSION': '0.1.0', 'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAdminUser']}

AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend', 'allauth.account.auth_backends.AuthenticationBackend']
ACCOUNT_ADAPTER = 'apps.accounts.adapters.ClosedAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'apps.accounts.adapters.InviteOnlySocialAdapter'
SOCIALACCOUNT_ONLY = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = False
# The OIDC adapter requires the provider's verified email; local email flows are disabled.
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*']
ACCOUNT_LOGOUT_ON_GET = False
SOCIALACCOUNT_PROVIDERS = {}
if os.environ.get('OIDC_CLIENT_ID') and os.environ.get('OIDC_CLIENT_SECRET') and os.environ.get('OIDC_SERVER_URL'):
    SOCIALACCOUNT_PROVIDERS = {'openid_connect': {'APPS': [{
        'provider_id': 'paragon', 'name': 'Organization sign-in',
        'client_id': os.environ['OIDC_CLIENT_ID'], 'secret': os.environ['OIDC_CLIENT_SECRET'],
        'settings': {'server_url': os.environ['OIDC_SERVER_URL']},
    }]}}

if os.environ.get('GEOS_LIBRARY_PATH'):
    GEOS_LIBRARY_PATH = os.environ['GEOS_LIBRARY_PATH']
if os.environ.get('GDAL_LIBRARY_PATH'):
    GDAL_LIBRARY_PATH = os.environ['GDAL_LIBRARY_PATH']

Q_CLUSTER = {
    'name': 'paragon-maintenance', 'orm': 'default', 'workers': 1,
    'timeout': 1800, 'retry': 2100, 'max_attempts': 3,
    'queue_limit': 1, 'bulk': 1, 'poll': 1, 'save_limit': 250,
    'scheduler': False, 'catch_up': False,
    'ALT_CLUSTERS': {'paragon-foreground': {
        'workers': 2, 'timeout': 90, 'retry': 150, 'queue_limit': 2,
    }},
}

# Public raster endpoint; never place a private provider credential here.
MAP_TILE_URL = os.environ.get('MAP_TILE_URL', 'https://tile.openstreetmap.org/{z}/{x}/{y}.png')
# Raster provider policy requires a Referer; send only our origin cross-origin.
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Requires private durable storage for the full backend deployment.
SOURCE_ARTIFACT_ROOT = Path(os.environ.get('SOURCE_ARTIFACT_ROOT') or BASE_DIR / 'var' / 'artifacts')
