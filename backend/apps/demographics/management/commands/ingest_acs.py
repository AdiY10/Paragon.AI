from django.core.management.base import BaseCommand, CommandError
from apps.locations.models import Location
from apps.sources.models import SourceDefinition
from apps.demographics.service import ingest_acs, ingest_acs_all, DEFAULT_ACS_YEAR
from apps.demographics.acs import AcsError

# State postal code -> FIPS, for the states a location can be in.
FIPS = {'AL':'01','AK':'02','AZ':'04','AR':'05','CA':'06','CO':'08','CT':'09','DE':'10','DC':'11','FL':'12',
    'GA':'13','HI':'15','ID':'16','IL':'17','IN':'18','IA':'19','KS':'20','KY':'21','LA':'22','ME':'23',
    'MD':'24','MA':'25','MI':'26','MN':'27','MS':'28','MO':'29','MT':'30','NE':'31','NV':'32','NH':'33',
    'NJ':'34','NM':'35','NY':'36','NC':'37','ND':'38','OH':'39','OK':'40','OR':'41','PA':'42','RI':'44',
    'SC':'45','SD':'46','TN':'47','TX':'48','UT':'49','VT':'50','VA':'51','WA':'53','WV':'54','WI':'55','WY':'56'}

# Rings can cross state lines, so neighbours of portfolio states are included.
NEIGHBOURS = {'CT':['NY','MA','RI'],'NY':['CT','NJ','PA','MA','VT'],'NJ':['NY','PA','DE'],'PA':['NY','NJ','DE','MD','OH','WV'],
    'MA':['CT','NY','RI','NH','VT'],'VT':['NY','MA','NH'],'MD':['PA','DE','VA','WV','DC'],'OH':['PA','WV','KY','IN','MI'],
    'NC':['VA','TN','SC','GA'],'FL':['GA','AL'],'NV':['CA','OR','ID','UT','AZ'],'ND':['MN','SD','MT']}


class Command(BaseCommand):
    help = ('Ingest ACS 5-year block-group tables (keyless bulk files) for the given or portfolio states. '
            'Use --year 2024 for current values and --year 2019 for the trend baseline.')

    def add_arguments(self, parser):
        parser.add_argument('--states', help='Comma-separated postal codes; default: states of non-archived locations plus neighbours')
        parser.add_argument('--year', type=int, default=DEFAULT_ACS_YEAR)
        parser.add_argument('--all-states', action='store_true',
            help='All 50 states and DC: national files downloaded once, parsed in memory-bounded batches; '
                 'states already ingested are skipped')

    def handle(self, *args, **options):
        if not SourceDefinition.objects.filter(pk='SRC-03').exists():
            raise CommandError('Run sync_sources first.')
        if options['all_states']:
            try:
                results = ingest_acs_all(options['year'], heartbeat=lambda: self.stdout.write('.', ending=''))
            except (AcsError, OSError) as exc:
                raise CommandError(f'ACS ingestion failed: {exc}') from exc
            self.stdout.write(f'\nACS {options["year"]}: {len(results)} state snapshots ingested (all states).')
            return
        if options['states']:
            codes = {c.strip().upper() for c in options['states'].split(',') if c.strip()}
        else:
            base = set(Location.objects.exclude(status='archived').exclude(state='').values_list('state', flat=True))
            codes = base | {n for s in base for n in NEIGHBOURS.get(s, [])}
        unknown = codes - set(FIPS)
        if unknown or not codes:
            raise CommandError(f'Unknown or missing states: {sorted(unknown) or "none"}')
        try:
            results = ingest_acs([FIPS[c] for c in sorted(codes)], year=options['year'])
        except AcsError as exc:
            raise CommandError(f'ACS ingestion failed: {exc}') from exc
        created = sum(1 for _, c in results if c)
        self.stdout.write(f'ACS {options["year"]}: {len(results)} state snapshots ({created} new) for {", ".join(sorted(codes))}.')
