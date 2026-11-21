"""Rekey signals to stable subjects (R2 item 5) and collapse the per-period duplicates.

Old subjects embedded the data period (``qcew:2025-Q2``), so every month raised a "new"
alert and lost dismissals. For each (location, rule, new subject) one row is kept: a
dismissed row if any (so the dismissal survives), else the most recently seen; it keeps
the earliest detection time.
"""
from django.db import migrations

RING = {'SIG-01': 'ring3:population', 'SIG-02': 'ring3:real_income', 'SIG-06': 'ring3:jobs',
    'SIG-08': 'road:primary', 'SIG-11': 'flood:sfha'}
COUNTY = {'SIG-03': 'private_jobs', 'SIG-04': 'retail_jobs', 'SIG-05': 'unemployment', 'SIG-07': 'permits'}


def new_subject(signal, fips):
    if signal.rule_id in RING:
        return RING[signal.rule_id]
    if signal.rule_id in COUNTY:
        return f'county:{fips}:{COUNTY[signal.rule_id]}' if fips else None
    if signal.rule_id in ('SIG-09', 'SIG-10') and signal.subject.startswith('overture:'):
        return 'place:' + signal.subject.split(':', 1)[1]
    return signal.subject


def forwards(apps, schema_editor):
    Signal = apps.get_model('insights', 'Signal')
    AreaSection = apps.get_model('area', 'AreaSection')
    fips_cache = {}

    def fips_for(location_id):
        if location_id not in fips_cache:
            row = (AreaSection.objects.filter(location_id=location_id, section='economy', status='available')
                .order_by('-computed_at').first())
            fips_cache[location_id] = ((row.data or {}).get('county') or {}).get('fips') if row else None
        return fips_cache[location_id]

    groups = {}
    for s in Signal.objects.all().order_by('first_detected_at'):
        subject = new_subject(s, fips_for(s.location_id) if s.rule_id in COUNTY else None)
        if subject is None:
            subject = s.subject
        groups.setdefault((s.location_id, s.rule_id, subject[:200]), []).append(s)
    for (location_id, rule_id, subject), rows in groups.items():
        keep = next((r for r in rows if r.status == 'dismissed'), None) or max(rows, key=lambda r: r.last_seen_at)
        earliest = min(r.first_detected_at for r in rows)
        for r in rows:
            if r.pk != keep.pk:
                r.delete()
        Signal.objects.filter(pk=keep.pk).update(subject=subject, first_detected_at=earliest,
            first_evidence=keep.evidence, episode_started_at=earliest)


class Migration(migrations.Migration):
    dependencies = [('insights', '0004_signal_episodes'), ('area', '0001_initial')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
