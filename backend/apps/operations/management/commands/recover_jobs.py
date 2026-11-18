import json
from django.core.management.base import BaseCommand
from apps.operations.recovery import recover_jobs

class Command(BaseCommand):
    help='Recover bounded lost-message/expired-lease jobs without duplicating active attempts.'
    def handle(self,*args,**options):
        self.stdout.write(json.dumps(recover_jobs()))
