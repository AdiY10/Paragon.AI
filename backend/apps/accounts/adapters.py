from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.core.exceptions import PermissionDenied
from django.db import transaction
from .models import Membership


def invited_membership(sociallogin):
    emails = {address.email.strip().lower() for address in sociallogin.email_addresses if address.verified}
    matches = list(Membership.objects.filter(email__in=emails, active=True))
    if len(matches) != 1:
        raise PermissionDenied('Sign-in requires a verified, invited email address.')
    return matches[0]


class ClosedAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False


class InviteOnlySocialAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        member = invited_membership(sociallogin)
        if sociallogin.is_existing:
            if member.user_id != sociallogin.user.pk:
                raise PermissionDenied('This identity is not linked to the invited membership.')
        elif member.user_id:
            # Link only after the provider proved ownership of the invited email.
            sociallogin.connect(request, member.user)
        sociallogin.user.email = member.email

    def is_open_for_signup(self, request, sociallogin):
        invited_membership(sociallogin)
        return True

    @transaction.atomic
    def save_user(self, request, sociallogin, form=None):
        member = Membership.objects.select_for_update().get(pk=invited_membership(sociallogin).pk)
        if not member.active or member.user_id:
            raise PermissionDenied('Invitation is no longer available.')
        sociallogin.user.email = member.email
        user = super().save_user(request, sociallogin, form)
        member.user = user
        member.save(update_fields=['user', 'updated_at'])
        return user
