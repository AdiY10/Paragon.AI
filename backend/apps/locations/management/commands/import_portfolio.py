from django.core.management.base import BaseCommand,CommandError
from apps.locations.seeding import import_public_portfolio
from apps.sources.models import SourceDefinition

class Command(BaseCommand):
    help='Import the 36 unconfirmed public properties without listing metrics or overwriting edits.'
    def handle(self,*args,**options):
        try:result=import_public_portfolio()
        except SourceDefinition.DoesNotExist as exc:
            raise CommandError('Run sync_sources before importing the portfolio.') from exc
        self.stdout.write(f'Created {result.created}; retained {result.existing} existing locations. Ownership remains user-confirmed only.')
