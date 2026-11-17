"""Short HTTP work only; ingestion runs in separate worker processes."""
import os

bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:' + os.environ.get('PORT', '8000'))
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
worker_class = 'gthread'
threads = 2
timeout = 30
graceful_timeout = 30
keepalive = 5
# Avoid logging candidate addresses or confidential query strings by default.
accesslog = None
errorlog = '-'
capture_output = True
# Django trusts proxy HTTPS headers only through an explicit deployment switch.
forwarded_allow_ips = ''
