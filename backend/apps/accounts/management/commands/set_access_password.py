import getpass
import sys
from django.core.management.base import BaseCommand
from apps.accounts.password_provisioning import configure_password

class Command(BaseCommand):
    help='Provision or rotate a named member password without exposing secrets in command arguments.'
    def add_arguments(self,parser):
        parser.add_argument('email')
        parser.add_argument('--role',choices=['admin','member'],default=None)
        parser.add_argument('--password-stdin',action='store_true')
        parser.add_argument('--reactivate',action='store_true')
    def handle(self,*args,**options):
        password=sys.stdin.readline().rstrip('\r\n') if options['password_stdin'] else getpass.getpass('New access password: ')
        configure_password(email=options['email'],password=password,role=options['role'],reactivate=options['reactivate'])
        self.stdout.write('Access account configured. Password is not displayed; changed passwords revoke prior sessions.')
