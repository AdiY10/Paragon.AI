"""Production refuses to boot without explicitly configured secrets and database."""
import os
from urllib.parse import unquote, urlsplit, parse_qsl
from django.core.exceptions import ImproperlyConfigured
from .base import *  # noqa: F403

if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must contain at least 50 characters')
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must list explicit hostnames')
if LOCAL_PREVIEW or LOCAL_SHARED_PASSWORD or os.environ.get('LOCAL_SHARED_PASSWORD'):
    raise ImproperlyConfigured('LOCAL_PREVIEW and LOCAL_SHARED_PASSWORD are for local previews only')
url = urlsplit(os.environ.get('DATABASE_URL', ''))
if url.scheme not in ('postgres', 'postgresql') or not url.hostname or not url.path.strip('/'):
    raise ImproperlyConfigured('DATABASE_URL must identify a PostgreSQL database')
DATABASES = {'default': {
    'ENGINE': 'django.contrib.gis.db.backends.postgis',
    'NAME': unquote(url.path.lstrip('/')), 'USER': unquote(url.username or ''),
    'PASSWORD': unquote(url.password or ''), 'HOST': unquote(url.hostname),
    'PORT': url.port or 5432, 'CONN_MAX_AGE': 60,
    'OPTIONS': dict(parse_qsl(url.query)),
}}
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# Enable only when the trusted hosting ingress strips client-supplied proxy headers.
if os.environ.get('TRUST_PROXY_SSL_HEADER') == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = [v.strip() for v in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if v.strip()]
