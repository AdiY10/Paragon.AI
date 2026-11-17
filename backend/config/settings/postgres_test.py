"""Explicit integration-test settings, selected only by the test operator."""
import os
from .test import *  # noqa: F403

DATABASES = {'default': {
    'ENGINE': 'django.contrib.gis.db.backends.postgis',
    'NAME': os.environ['PARAGON_TEST_DB_NAME'],
    'USER': os.environ['PARAGON_TEST_DB_USER'],
    'PASSWORD': os.environ.get('PARAGON_TEST_DB_PASSWORD', ''),
    'HOST': os.environ.get('PARAGON_TEST_DB_HOST', 'localhost'),
    'PORT': os.environ.get('PARAGON_TEST_DB_PORT', '5432'),
}}
# Optional explicit paths support relocatable local GEOS/GDAL installations.
if os.environ.get('GEOS_LIBRARY_PATH'):
    GEOS_LIBRARY_PATH = os.environ['GEOS_LIBRARY_PATH']
if os.environ.get('GDAL_LIBRARY_PATH'):
    GDAL_LIBRARY_PATH = os.environ['GDAL_LIBRARY_PATH']
