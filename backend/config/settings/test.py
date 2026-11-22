"""Isolated test settings; never selected by the production entrypoint."""
from .base import *  # noqa: F403
SECRET_KEY = 'test-only-key-with-no-production-access'
ALLOWED_HOSTS = ['testserver', 'localhost']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True

# Tests queue analyses explicitly; location changes do not start jobs on their own.
AUTO_ANALYZE = False
