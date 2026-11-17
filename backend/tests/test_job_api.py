import uuid
import pytest
from django_q.models import OrmQ
from apps.operations.models import JobRun
from apps.operations.runner import execute_job
from backend.tests.test_accounts import member

pytestmark=pytest.mark.django_db


def admin_client(client):
    user,_=member('admin@example.org','admin')
    client.force_login(user)
    return user


def submit(client,key=None):
    return client.post('/api/admin/jobs/',{'kind':'sync_source_catalog'},content_type='application/json',
        HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))


def test_admin_submission_is_idempotent_and_attributed(client):
    user=admin_client(client);key=uuid.uuid4()
    first=submit(client,key);second=submit(client,key)
    assert first.status_code==202 and second.status_code==200
    assert first.json()['id']==second.json()['id']
    assert JobRun.objects.get().requested_by==user
    assert OrmQ.objects.count()==1


def test_member_and_anonymous_users_cannot_access_job_controls(client):
    assert client.get('/api/admin/jobs/').status_code==403
    user,_=member();client.force_login(user)
    assert client.get('/api/admin/jobs/').status_code==403
    assert submit(client).status_code==403
    assert JobRun.objects.count()==0


def test_run_log_is_paginated_and_omits_transport_and_parameters(client):
    admin_client(client);submit(client)
    response=client.get('/api/admin/jobs/')
    data=response.json()
    assert response.status_code==200 and data['count']==1
    assert data['results'][0]['status']=='queued'
    assert 'parameters' not in data['results'][0] and 'transport_task_id' not in data['results'][0]


def test_rerun_preserves_original_run_and_links_new_attempt(client):
    user=admin_client(client)
    original=JobRun.objects.get(pk=submit(client).json()['id'])
    execute_job(original.pk)
    key=uuid.uuid4()
    response=client.post(f'/api/admin/jobs/{original.id}/rerun/',HTTP_IDEMPOTENCY_KEY=str(key))
    assert response.status_code==202
    new=JobRun.objects.get(pk=response.json()['id'])
    assert new.id!=original.id and new.rerun_of==original and new.requested_by==user
    original.refresh_from_db();assert original.status=='succeeded' and original.attempts==1
    again=client.post(f'/api/admin/jobs/{original.id}/rerun/',HTTP_IDEMPOTENCY_KEY=str(key))
    assert again.status_code==200 and again.json()['id']==str(new.id)


def test_active_run_cannot_be_rerun(client):
    admin_client(client);original=submit(client).json()['id']
    response=client.post(f'/api/admin/jobs/{original}/rerun/',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert response.status_code==409 and JobRun.objects.count()==1


def test_manual_submission_requires_valid_idempotency_key(client):
    admin_client(client)
    response=client.post('/api/admin/jobs/',{'kind':'sync_source_catalog'},content_type='application/json')
    assert response.status_code==400 and JobRun.objects.count()==0


def test_unknown_handler_cannot_be_invoked_through_api(client):
    admin_client(client)
    response=client.post('/api/admin/jobs/',{'kind':'os.system'},content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert response.status_code==400 and JobRun.objects.count()==0
