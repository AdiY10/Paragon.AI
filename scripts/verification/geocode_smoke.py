"""Exercise live Census retrieval, private evidence, cache, and explicit acceptance.

Uses the actual public Staples Plaza address in a temporary SQLite test database.
No configured production database, real account, or saved portfolio is modified.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    with tempfile.TemporaryDirectory(prefix='paragon-geocode-test-') as directory:
        root=Path(directory)
        (root/'geocode_test_settings.py').write_text(
            'from config.settings.test import *\nDATABASES='+repr({'default':{
                'ENGINE':'django.db.backends.sqlite3','NAME':str(root/'test.sqlite3')}})+'\n'
            +'SOURCE_ARTIFACT_ROOT='+repr(str(root/'private-artifacts'))+'\n')
        env=dict(os.environ,DJANGO_SETTINGS_MODULE='geocode_test_settings',
            PYTHONPATH=os.pathsep.join([str(ROOT/'backend'),directory]))
        code='''import django;django.setup()
import json
from django.core.management import call_command
from django.contrib.auth import get_user_model
from apps.locations.seeding import import_public_portfolio
from apps.locations.models import Location
from apps.locations.geocoding import request_lookup,accept_lookup
from apps.sources.models import SourceCheck
call_command('migrate',verbosity=0)
call_command('sync_sources',verbosity=0)
import_public_portfolio()
actor=get_user_model().objects.create_user(username='geocode-test-only',email='geocode-test@example.invalid')
item=Location.objects.get(seed_id='P03')
lookup=request_lookup(location_id=item.id,expected_version=item.version,actor=actor)
assert lookup.status=='matched' and len(lookup.candidates)==1
assert abs(lookup.candidates[0]['lat']-41.12661107292)<.00001
checks=SourceCheck.objects.count()
cached=request_lookup(location_id=item.id,expected_version=item.version,actor=actor)
assert cached.id==lookup.id and SourceCheck.objects.count()==checks
changed=accept_lookup(location_id=item.id,lookup_id=lookup.id,expected_version=item.version,candidate_index=0,actor=actor)
assert changed.current_revision.method=='census_interpolated' and not changed.current_revision.confirmed
assert changed.current_revision.context['geographies']['block_group']['geoid']=='091900435001'
assert changed.current_revision.context['geographies']['block']['geoid']=='090010435001001'
assert changed.revisions.count()==2 and not changed.confirmed
print(json.dumps({'status':'passed','property':'Real public Staples Plaza address','lookup':lookup.status,'revisions':changed.revisions.count(),'cache_reused':True,'source_checks':checks,'confirmed':changed.confirmed}))
'''
        subprocess.run([str(ROOT/'.venv/bin/python'),'-c',code],cwd=ROOT,env=env,check=True)


if __name__=='__main__':main()
