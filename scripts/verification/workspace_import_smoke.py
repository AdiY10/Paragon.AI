"""Verify a private workspace export in a disposable database; never print its data."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def verify(path):
    import django
    django.setup()
    from django.core.management import call_command
    from django.utils.dateparse import parse_datetime
    from apps.locations.models import Location,ImportedSiteAudit,WorkspaceImport
    from apps.locations.workspace_import import import_workspace
    from apps.locations.seeding import import_public_portfolio
    call_command('migrate',verbosity=0)
    raw=path.read_bytes();data=json.loads(raw)
    assert not import_workspace(raw).applied
    result=import_workspace(raw,apply=True)
    assert result.locations==Location.objects.count()==len(data['locations'])
    for source in data['locations']:
        item=Location.objects.get(source_context__migration__original_location_id=source['id'])
        for field in ('name','address','city','state','notes','status','asset_type','ring_preset','gla_sqft','confirmed','origin','seed_id'):
            assert getattr(item,field)==source[field],f'Imported field differs: {field}'
        pin=item.current_revision
        for field in ('number','lat','lon','method','matched_address','confirmed'):
            assert getattr(pin,field)==source['current_revision'][field],f'Imported pin differs: {field}'
        assert pin.created_at==parse_datetime(source['current_revision']['created_at'])
    assert ImportedSiteAudit.objects.count()==len(data.get('audits',[]))
    assert WorkspaceImport.objects.count()==1 and import_workspace(raw,apply=True).reused
    assert import_public_portfolio().created==0
    print(json.dumps({'verified':True,'locations':result.locations,'revisions':result.revisions,'audits':result.audits,'sha256':result.sha256}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export',type=Path)
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args();path=args.export.resolve()
    if args.child:return verify(path)
    with tempfile.TemporaryDirectory(prefix='paragon-migration-qa-') as directory:
        root=Path(directory)
        (root/'migration_test_settings.py').write_text('from config.settings.test import *\n'
            +'DATABASES='+repr({'default':{'ENGINE':'django.db.backends.sqlite3','NAME':str(root/'db.sqlite3')}})+'\n'
            +'SOURCE_ARTIFACT_ROOT='+repr(str(root/'private-evidence'))+'\n')
        env=dict(os.environ,DJANGO_SETTINGS_MODULE='migration_test_settings',PYTHONPATH=os.pathsep.join([str(ROOT/'backend'),directory]))
        subprocess.run([str(ROOT/'.venv/bin/python'),str(Path(__file__).resolve()),str(path),'--child'],cwd=ROOT,env=env,check=True)


if __name__=='__main__':main()
