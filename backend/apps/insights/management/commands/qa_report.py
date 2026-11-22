"""Data-quality report (redesign B6a): `qa_report [--strict] [--json]`. --strict exits 1 on any failure."""
import json
import sys
from django.core.management.base import BaseCommand
from apps.insights.qa import report


class Command(BaseCommand):
    help = 'Check stored analyses for plausibility, consistency, freshness and golden values.'

    def add_arguments(self, parser):
        parser.add_argument('--strict', action='store_true', help='Exit with status 1 when any check fails.')
        parser.add_argument('--json', action='store_true', help='Print the findings as JSON.')

    def handle(self, *args, strict=False, json=False, **options):
        out = report()
        if json:
            self.stdout.write(__import__('json').dumps(out, indent=2, default=str))
        else:
            for f in out['findings']:
                self.stdout.write(f"{f['level'].upper():5} {f['check']:<24} {f['location']}: {f['detail']}")
            self.stdout.write(f"{out['checked']} properties checked: {out['failures']} failures, {out['warnings']} warnings.")
        if strict and out['failures']:
            sys.exit(1)
