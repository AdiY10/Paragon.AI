from django.core.management.base import BaseCommand
from apps.operations.scheduler import sync_schedules

class Command(BaseCommand):
    help='Load schedule definitions; nonexistent handlers remain disabled.'
    def add_arguments(self,parser):
        parser.add_argument('--enable-available',action='store_true')
    def handle(self,*args,**options):
        count=sync_schedules(enable_available=options['enable_available'])
        self.stdout.write(f'Synchronized {count} schedule definitions; no missing handler was enabled.')
