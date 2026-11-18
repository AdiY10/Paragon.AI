"""Load only local assets from the Vite production manifest."""
import json
from pathlib import PurePosixPath
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def asset_url(value):
    if not isinstance(value, str) or not value.startswith('assets/'):
        raise ImproperlyConfigured('Frontend manifest has an invalid asset path')
    path = PurePosixPath(value)
    if '..' in path.parts or '\\' in value or '?' in value or '#' in value:
        raise ImproperlyConfigured('Frontend manifest has an invalid asset path')
    if not all(c.isalnum() or c in '/._-' for c in value):
        raise ImproperlyConfigured('Frontend manifest has an invalid asset path')
    return settings.STATIC_URL + 'ui/' + value


def frontend_assets():
    try:
        manifest = json.loads(settings.FRONTEND_MANIFEST.read_text())
        entry = manifest['src/main.tsx']
        if not entry.get('isEntry'):
            raise ValueError('Missing frontend entry')
        return {'javascript': asset_url(entry['file']),
                'stylesheets': [asset_url(path) for path in entry.get('css', [])]}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ImproperlyConfigured('Frontend build unavailable; run npm ci and npm run build in frontend/') from exc
