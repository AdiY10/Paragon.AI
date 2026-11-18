# Invite-only authentication

The temporary OpenAI Site uses built-in ChatGPT sign-in and owner-private platform
access; it does not require these OIDC settings. See TEMPORARY_SITE.md. The following
configuration applies to the canonical Django application.

The application uses django-allauth's OpenID Connect authorization-code flow and
server sessions. There is no local password signup. A provider identity must supply
an explicitly verified email matching an active invitation. An email string alone
is insufficient. Multiple matching invitations are rejected as ambiguous.

Configure `OIDC_SERVER_URL`, `OIDC_CLIENT_ID`, and `OIDC_CLIENT_SECRET` through the
hosting secret store. Register this exact redirect path with the identity provider:
`https://<application-host>/accounts/oidc/paragon/login/callback/`.
Google's discovery base is `https://accounts.google.com`. For another organization
provider, verify its issuer and verified-email claims before deployment; do not
assume an unverified claim is safe or globally mark all provider emails verified.

Run `python backend/manage.py migrate` and then
`python backend/manage.py invite_admin <owner-email>` to create the initial admin
invitation. This creates no user/password and does not bypass OIDC. The owner signs
in through the registered provider. Admins then invite Members through
`POST /api/admin/users/`. The sign-in URL can be delivered through the team's
existing private channel; the invitation endpoint does not send email.

Membership is checked against the database on every authenticated request. Removal
invalidates access on the next request and clears that browser session. Role guards
are server-side. Reposting an invitation does not reactivate a removed member.
Admins can reassign roles with `PATCH /api/admin/users/<id>/`.
The last administrator who has signed in cannot be removed or demoted; a pending
admin invitation cannot substitute for them. Invitation, removal, role changes,
and initial-admin bootstrap create access audit records. POST/DELETE use Django/DRF CSRF protection.

Local tests verify adapter email checks, persistence, roles, revocation, and CSRF.
A live provider callback is still unverified until owner-provided OIDC credentials
and an HTTPS deployment are available. These local tests do not establish live
AC-01/AC-02 completion.
