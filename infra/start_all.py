"""Single-container process supervisor: web, job worker and scheduler together.

Render persistent disks attach to one service only, so the background worker and the
scheduler must run beside Gunicorn in the same container to reach the private
source-evidence disk. If any process exits, the others are stopped and the container
exits non-zero so the host restarts it. Opt in with RUN_BACKGROUND_WORKERS=true.
"""
import os
import signal
import subprocess
import sys
import time


def build_commands(env=None):
    """(argv, extra env) for each process: Gunicorn, plus both job clusters and the scheduler."""
    env = os.environ if env is None else env
    commands = [(['gunicorn', '--config', 'infra/gunicorn.conf.py', 'config.wsgi:application'], {})]
    if env.get('RUN_BACKGROUND_WORKERS', '').lower() == 'true':
        manage = [sys.executable, 'backend/manage.py']
        commands += [
            (manage + ['qcluster'], {}),  # paragon-maintenance: scheduled refreshes
            (manage + ['qcluster'], {'Q_CLUSTER_NAME': 'paragon-foreground'}),  # screens, computes, brief
            (manage + ['run_scheduler', '--interval', '30'], {}),
        ]
    return commands


def main():
    subprocess.run([sys.executable, 'backend/manage.py', 'prepare_release'], check=True)
    subprocess.run([sys.executable, 'backend/manage.py', 'sync_schedules', '--enable-available'], check=False)
    os.environ.pop('ACCESS_BOOTSTRAP_PASSWORD', None)
    processes = [subprocess.Popen(argv, env={**os.environ, **extra}) for argv, extra in build_commands()]

    def stop(*_):
        for p in processes:
            if p.poll() is None:
                p.terminate()
        deadline = time.time() + 20
        for p in processes:
            try:
                p.wait(max(0.1, deadline - time.time()))
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(1)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while True:
        for p in processes:
            if p.poll() is not None:
                print(f'process {p.args[0:3]} exited with {p.returncode}; stopping the container', flush=True)
                stop()
        time.sleep(2)


if __name__ == '__main__':
    main()
