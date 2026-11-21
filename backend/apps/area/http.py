"""Bounded HTTP helper shared by area-data adapters. Never logs URLs with pins."""
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
import ssl
import certifi

USER_AGENT = 'ParagonRadar/0.1 (+https://github.com/AdiY10/Paragon.AI)'
# Use Mozilla's CA bundle: geo.dot.gov chains to a root missing from some system stores.
_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class _SameSiteRedirects(HTTPRedirectHandler):
    """Follow redirects only to https URLs on the same registrable domain (census.gov -> www2.census.gov)."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        site = lambda host: '.'.join((host or '').lower().split('.')[-2:])
        if new.scheme != 'https' or not new.hostname or site(new.hostname) != site(old.hostname):
            raise HTTPError(newurl, code, 'Redirect blocked', headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def default_opener():
    return build_opener(HTTPSHandler(context=_CONTEXT), _SameSiteRedirects())


class SourceError(Exception):
    """Carries a sanitized reason code (docs/04 §7)."""
    def __init__(self, code='SOURCE_ERROR', detail=''):
        self.code, self.detail = code, detail
        super().__init__(f'{code}: {detail}' if detail else code)


def fetch(url, *, params=None, body=None, opener=None, timeout=30, max_bytes=16 * 1024 * 1024,
        retries=2, headers=None):
    full = url + ('?' + urlencode(params) if params else '')
    data = None if body is None else json.dumps(body).encode()
    hdrs = {'User-Agent': USER_AGENT, **({'Content-Type': 'application/json'} if body is not None else {}),
        **(headers or {})}
    last = None
    for attempt in range(retries + 1):
        try:
            with (opener or default_opener()).open(Request(full, data=data, headers=hdrs), timeout=timeout) as r:
                raw = r.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise SourceError('SCHEMA_ERROR', 'response too large')
            return raw
        except HTTPError as exc:
            if exc.code == 404:
                raise SourceError('NOT_COVERED', 'not published') from None
            last = SourceError('HTTP_ERROR', str(exc.code))
        except (URLError, OSError) as exc:
            last = SourceError('TIMEOUT' if 'timed out' in str(exc) else 'SOURCE_ERROR', type(exc).__name__)
        if attempt < retries:
            time.sleep(min(4, 0.5 * 2 ** attempt))
    raise last


def arcgis_json(raw):
    try:
        data = json.loads(raw)
    except ValueError:
        raise SourceError('SCHEMA_ERROR', 'not JSON') from None
    if 'error' in data or not isinstance(data.get('features'), list):
        raise SourceError('SOURCE_ERROR', 'ArcGIS query failed')
    return [f.get('attributes', {}) for f in data['features']]
