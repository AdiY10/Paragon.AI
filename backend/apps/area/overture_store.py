"""Compact Overture captures and the release-pair guard (R2 item 14)."""
import gzip
import io
import json
import logging
from django.db import transaction
from apps.demographics.rings import haversine_miles
from apps.sources.models import SourceSnapshot
from . import businesses as biz
from .models import OvertureCapture, OvertureReleasePair

log = logging.getLogger(__name__)
FIELDS = ('id', 'name', 'basic_category', 'brand', 'brand_wikidata', 'operating_status', 'confidence', 'lat', 'lon')
BRAND_DROP_MIN = 3       # distinct places of the brand before a drop counts
BRAND_DROP_SHARE = 0.5   # ...and must lose at least half of them in one release


def pin_key(lat, lon):
    return f'{lat:.6f},{lon:.6f}'


def compact(records):
    return [{k: r.get(k) for k in FIELDS} for r in records]


def _summary(records, lat, lon):
    one_mile, brands = 0, {}
    for r in records:
        if not biz.countable(r):
            continue
        d = haversine_miles(lat, lon, r['lat'], r['lon'])
        if d <= 1 and biz.CATEGORY_GROUP.get(r.get('basic_category')):
            one_mile += 1
        b = biz.normalize_brand(r.get('brand'))
        if b:
            brands.setdefault(b, []).append(r['id'])
    return {'one_mile_count': one_mile, 'brand_ids': brands}


def encode(records):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0) as gz:
        for r in records:
            gz.write(json.dumps(r, sort_keys=True, separators=(',', ':')).encode() + b'\n')
    return buf.getvalue()


def load(capture, store):
    with store.open_verified(capture.compact_key) as handle:
        with gzip.GzipFile(fileobj=handle) as gz:
            return [json.loads(line) for line in gz if line.strip()]


@transaction.atomic
def store_capture(lat, lon, release, records, store, *, raw_snapshot=None):
    records = compact(records)
    artifact = store.put(io.BytesIO(encode(records)))
    capture, _ = OvertureCapture.objects.get_or_create(release=release, pin_key=pin_key(lat, lon), defaults={
        'compact_key': artifact.key, 'record_count': len(records), 'summary': _summary(records, lat, lon),
        'raw_snapshot': raw_snapshot})
    return capture


def _raw_snapshot(lat, lon, release):
    for snap in SourceSnapshot.objects.filter(source_id='SRC-13', release=release).order_by('-retrieved_at'):
        if (snap.context or {}).get('format') == 'compact':
            continue  # already compact (gzipped JSON lines), not a raw capture
        c = (snap.context or {}).get('coordinates') or {}
        if round(c.get('lat', 999), 6) == round(lat, 6) and round(c.get('lon', 999), 6) == round(lon, 6) \
                and snap.context.get('radius_miles') == 3:
            return snap
    return None


def get_capture(lat, lon, release, store):
    """The compact capture, compacting an older raw snapshot on first use; None if neither exists."""
    capture = OvertureCapture.objects.filter(release=release, pin_key=pin_key(lat, lon)).first()
    if capture is not None:
        return capture
    snap = _raw_snapshot(lat, lon, release)
    if snap is None:
        return None
    with store.open_verified(snap.artifact_key) as handle:
        records = json.loads(handle.read())
    return store_capture(lat, lon, release, records, store, raw_snapshot=snap)


def compact_all(store):
    """Backfill: compact every raw SRC-13 snapshot that has no compact capture yet."""
    done = 0
    for snap in SourceSnapshot.objects.filter(source_id='SRC-13').order_by('release'):
        c = (snap.context or {}).get('coordinates') or {}
        if (snap.context or {}).get('format') == 'compact':
            continue
        if 'lat' not in c or OvertureCapture.objects.filter(release=snap.release,
                pin_key=pin_key(c['lat'], c['lon'])).exists():
            continue
        get_capture(c['lat'], c['lon'], snap.release, store)
        done += 1
    return done


def pair(prior, latest, *, recompute=False):
    """Release-pair guard from capture summaries of pins captured in both releases."""
    row = OvertureReleasePair.objects.filter(prior=prior, latest=latest).first()
    if row is not None and not recompute:
        return row
    before = {c.pin_key: c.summary for c in OvertureCapture.objects.filter(release=prior)}
    after = {c.pin_key: c.summary for c in OvertureCapture.objects.filter(release=latest)}
    pins = sorted(set(before) & set(after))
    counts = [(before[p].get('one_mile_count', 0), after[p].get('one_mile_count', 0)) for p in pins]
    broad = biz.broad_change(counts)
    # Brand-wide drops, by distinct place id across all captured pins (nearby captures overlap):
    # a brand that loses half its places at once (3+ places) is a data change, not closures.
    had, now = {}, {}
    for p in pins:
        for b, ids in (before[p].get('brand_ids') or {}).items():
            had.setdefault(b, set()).update(ids)
        for b, ids in (after[p].get('brand_ids') or {}).items():
            now.setdefault(b, set()).update(ids)
    drops = sorted(b for b, ids in had.items()
        if len(ids) >= BRAND_DROP_MIN and len(ids - now.get(b, set())) / len(ids) >= BRAND_DROP_SHARE)
    row, _ = OvertureReleasePair.objects.update_or_create(prior=prior, latest=latest, defaults={
        'broad_change': broad, 'cohort_size': len(pins), 'brand_drops': drops})
    return row


def prune_raw(store, keep_releases):
    """Delete raw capture files for releases older than ``keep_releases`` once a compact copy exists.

    The immutable snapshot rows remain as provenance; the off-box archive keeps the originals.
    """
    import os
    pruned = 0
    for capture in (OvertureCapture.objects.filter(raw_pruned=False, raw_snapshot__isnull=False)
            .exclude(release__in=keep_releases).select_related('raw_snapshot')):
        key = capture.raw_snapshot.artifact_key
        if key != capture.compact_key:
            try:
                os.unlink(store._path(key))
            except FileNotFoundError:
                pass
        OvertureCapture.objects.filter(pk=capture.pk).update(raw_pruned=True)
        pruned += 1
    return pruned


# ---- moving the captured history to another server (redesign B2) -----------------------
# Overture deletes releases after about two months, so captured history cannot be re-downloaded.

def export_history(locations, store, out):
    """Write a tar of the compact captures for these locations' current pins plus manifest.jsonl.

    Only release, pin coordinates key, counts, summaries, checksums and provenance: no names,
    addresses or screens.
    """
    import tarfile
    pins = {pin_key(l.current_revision.lat, l.current_revision.lon) for l in locations
        if l.current_revision_id and l.current_revision.lat is not None}
    manifest, written, files = [], 0, set()
    with tarfile.open(out, 'w') as tar:
        for capture in (OvertureCapture.objects.filter(pin_key__in=pins).select_related('raw_snapshot')
                .order_by('release', 'pin_key')):
            with store.open_verified(capture.compact_key) as handle:
                data = handle.read()
            compact_sha = capture.compact_key.rsplit('/', 1)[1]
            if compact_sha not in files:  # identical captures (content-addressed) are written once
                info = tarfile.TarInfo(f'captures/{compact_sha}.jsonl.gz')
                info.size, info.mtime = len(data), 0
                tar.addfile(info, io.BytesIO(data))
                files.add(compact_sha)
            raw = capture.raw_snapshot
            manifest.append({'release': capture.release, 'pin_key': capture.pin_key, 'record_count': capture.record_count,
                'summary': capture.summary, 'compact_sha256': compact_sha,
                'raw_sha256': raw.sha256 if raw else None,
                'retrieved_at': (raw.retrieved_at if raw else capture.created_at).isoformat(),
                'source_url': f's3://overturemaps-us-west-2/release/{capture.release}/theme=places/type=place/*'})
            written += 1
        body = ''.join(json.dumps(m, sort_keys=True) + '\n' for m in manifest).encode()
        info = tarfile.TarInfo('manifest.jsonl')
        info.size, info.mtime = len(body), 0
        tar.addfile(info, io.BytesIO(body))
    return written


class HistoryError(Exception):
    pass


def import_history(path, store):
    """Load an exported history: verify every checksum, store the compact files, create the
    captures (existing release/pin pairs are kept), then recompute the release-pair guards.
    Returns (created, skipped)."""
    import hashlib
    import re
    import tarfile
    created = skipped = 0
    with tarfile.open(path, 'r') as tar:
        member = tar.getmember('manifest.jsonl')
        manifest = [json.loads(line) for line in tar.extractfile(member).read().decode().splitlines() if line.strip()]
        for m in manifest:
            if not re.fullmatch(r'[0-9a-f]{64}', m.get('compact_sha256') or '') or \
                    not re.fullmatch(r'\d{4}-\d{2}-\d{2}\.\d+', m.get('release') or ''):
                raise HistoryError('invalid manifest entry')
            if OvertureCapture.objects.filter(release=m['release'], pin_key=m['pin_key']).exists():
                skipped += 1
                continue
            data = tar.extractfile(f'captures/{m["compact_sha256"]}.jsonl.gz').read()
            if hashlib.sha256(data).hexdigest() != m['compact_sha256']:
                raise HistoryError(f'checksum mismatch for {m["release"]} {m["pin_key"]}')
            artifact = store.put(io.BytesIO(data))
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
                count = sum(1 for line in gz if line.strip())
            if count != m['record_count']:
                raise HistoryError(f'record count mismatch for {m["release"]} {m["pin_key"]}')
            OvertureCapture.objects.create(release=m['release'], pin_key=m['pin_key'], compact_key=artifact.key,
                record_count=count, summary={**m['summary'], 'imported': True, 'retrieved_at': m['retrieved_at'],
                    'raw_sha256': m.get('raw_sha256')}, raw_pruned=True)
            created += 1
    releases = sorted(set(OvertureCapture.objects.values_list('release', flat=True)))
    for prior, latest in zip(releases, releases[1:]):
        pair(prior, latest, recompute=True)
    return created, skipped
