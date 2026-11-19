"""Prepare the mounted single-host deployment, then replace PID 1 with Gunicorn."""
import os
import subprocess
import sys

subprocess.run([sys.executable,'backend/manage.py','prepare_release'],check=True)
# Do not retain a bootstrap password in the long-lived HTTP worker environment.
os.environ.pop('ACCESS_BOOTSTRAP_PASSWORD',None)
os.execvp('gunicorn',['gunicorn','--config','infra/gunicorn.conf.py','config.wsgi:application'])
