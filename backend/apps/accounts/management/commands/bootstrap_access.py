"""One-time host-secret bootstrap; never reset or reactivate an existing account."""
import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from apps.accounts.models import Membership
from apps.accounts.password_provisioning import configure_password

class Command(BaseCommand):
    help='Create the initial password administrator from host secrets; skip established accounts.'
    def handle(self,*args,**options):
        if not settings.PASSWORD_ACCESS_ENABLED:return
        email=os.environ.get('ACCESS_BOOTSTRAP_EMAIL','').strip().lower()
        password=os.environ.pop('ACCESS_BOOTSTRAP_PASSWORD','')
        if not email and not password:
            admins=Membership.objects.filter(active=True,role='admin',user__is_active=True).select_related('user')
            if any(member.user.has_usable_password() for member in admins):return
            raise CommandError('Configure both access bootstrap secrets or provision an active password administrator first.')
        if not email or not password:raise CommandError('Both access bootstrap secrets are required together.')
        member=Membership.objects.filter(email=email).select_related('user').first()
        if member:
            if not member.user_id or not member.user.has_usable_password():
                raise CommandError('Existing membership requires explicit set_access_password provisioning.')
            self.stdout.write('Existing access account retained; bootstrap never rotates or reactivates it.')
            return
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise CommandError('Existing identity requires explicit set_access_password provisioning.')
        try:configure_password(email=email,password=password,role='admin')
        except CommandError:raise CommandError('Access bootstrap rejected; use an approved email and a strong password of at least 14 characters.') from None
        self.stdout.write('Initial access account created from host secrets. Remove the bootstrap secrets after verification.')
