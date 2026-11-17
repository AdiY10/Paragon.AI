"""Exercise a real catalog-sync job through the configured durable worker.

Run only against an explicitly configured disposable deployment/database.
No provider checks or synthetic business facts are created by this command.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.production')
    sys.path.insert(0,str(ROOT/'backend'))
    import django
    django.setup()
    from apps.operations.service import enqueue_job
    from django_q.models import Task,OrmQ
    job,_=enqueue_job(kind='sync_source_catalog',scope='global',dedup_key='worker-smoke-'+uuid.uuid4().hex)
    with tempfile.TemporaryDirectory(prefix='paragon-worker-') as directory:
        with (Path(directory)/'worker.log').open('w') as log:
            process=subprocess.Popen([str(ROOT/'.venv/bin/python'),'backend/manage.py','qcluster'],
                cwd=ROOT,env=dict(os.environ),stdout=log,stderr=log,start_new_session=True)
            try:
                for _ in range(80):
                    job.refresh_from_db()
                    if job.status=='failed':
                        raise RuntimeError('Worker job failed: '+job.error_code)
                    if job.status=='succeeded' and Task.objects.filter(pk=job.transport_task_id,success=True).exists():
                        break
                    if process.poll() is not None:
                        raise RuntimeError('Worker exited before completing the job')
                    time.sleep(.5)
                else:
                    raise TimeoutError('Worker did not finish within 40 seconds')
            finally:
                if process.poll() is None:
                    # Signal the parent only; Q2 coordinates draining its children.
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL)
                        process.wait(timeout=5)
                        raise RuntimeError('Worker required forced termination; graceful shutdown unverified')
            if process.returncode!=0:
                raise RuntimeError('Worker did not shut down successfully')
    job.refresh_from_db()
    assert job.status=='succeeded' and job.records==16 and job.attempts==1
    assert not OrmQ.objects.filter(key='paragon-maintenance').exists()
    print(json.dumps({'status':'passed','records':job.records,'attempts':job.attempts,
        'transport_acknowledged':True,'graceful_shutdown':True}))

if __name__=='__main__':
    main()
