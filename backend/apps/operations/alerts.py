"""Operational alerts: shown in-app to administrators, emailed only when email is configured.

Keys and summaries never contain addresses or coordinates (candidate sites are confidential).
"""
from datetime import timedelta
import logging
from django.conf import settings
from django.db import transaction
from django.utils import timezone

log = logging.getLogger(__name__)
EMAIL_EVERY = timedelta(hours=24)


@transaction.atomic
def raise_alert(key, summary):
    from .models import AlertEvent
    now = timezone.now()
    alert, created = AlertEvent.objects.select_for_update().get_or_create(
        key=key[:200], defaults={'summary': summary[:300], 'first_at': now, 'last_at': now})
    if not created:
        if alert.resolved_at is not None:  # a new occurrence after resolution starts fresh
            alert.first_at, alert.count, alert.resolved_at, alert.notified_at = now, 0, None, None
        alert.count += 1
        alert.summary = summary[:300]
        alert.last_at = now
    log.warning('alert raised: %s (%s)', alert.key, alert.summary)
    if _email_configured() and (alert.notified_at is None or now - alert.notified_at >= EMAIL_EVERY):
        if _send_email(alert):
            alert.notified_at = now
    alert.save()
    return alert


def resolve_alert(key):
    from .models import AlertEvent
    updated = AlertEvent.objects.filter(key=key[:200], resolved_at__isnull=True).update(resolved_at=timezone.now())
    if updated:
        log.info('alert resolved: %s', key)


def open_alerts():
    from .models import AlertEvent
    return AlertEvent.objects.filter(resolved_at__isnull=True)


def _email_configured():
    return bool(getattr(settings, 'ALERT_EMAILS', None)) and bool(getattr(settings, 'EMAIL_HOST', '') or
        getattr(settings, 'EMAIL_BACKEND', '').endswith(('locmem.EmailBackend', 'console.EmailBackend')))


def _send_email(alert):
    from django.core.mail import send_mail
    try:
        send_mail(f'[Paragon Radar] {alert.summary}', f'{alert.summary}\n\nOccurrences: {alert.count}. '
            'See Admin in Paragon Radar for details.', None, list(settings.ALERT_EMAILS), fail_silently=False)
        return True
    except Exception:
        log.exception('alert email failed for %s', alert.key)
        return False
