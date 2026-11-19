# Temporary password access for the regular host

Adi's priority in AGENT_HANDOFF §0 authorizes named password accounts until OIDC is
configured. Set PASSWORD_ACCESS_ENABLED=true in the host secret/environment store.
The root redirects to /access/login/; every business page/API still requires an
active membership. OIDC remains configured separately and is not removed. Health
returns only the original minimal status; static bundles contain no business data.

Provision or rotate a named account from a trusted host shell:

```
python backend/manage.py set_access_password <approved-email> --role admin
```

The command prompts without echoing the password. For automation, use --password-stdin
and pipe from the host's secret mechanism; never put a password in command arguments,
source, PR text, or logs. Existing roles are not changed by this command. Revoked
memberships require explicit --reactivate, and disabled Django users remain disabled.
An unchanged password is retained without revoking sessions; a new password uses
Django's configured hash and invalidates old sessions on their next request.

Passwords require at least 14 characters and Django common/numeric/similarity
validation. Production uses Django's normal strong password hashers, secure HttpOnly
session/CSRF cookies, HTTPS redirect, and HSTS. Passwords are never returned by APIs.
Login is CSRF-protected and never cached; errors do not distinguish unknown, wrong,
or unavailable accounts. Database-backed account/IP buckets permit eight account
attempts or thirty remote-IP attempts per fifteen minutes across workers. Only HMAC
keys and counters are stored. Client forwarding headers cannot spoof these keys.
A shared ingress IP may share the IP budget; revisit trusted ingress configuration
before scaling. Do not simply trust arbitrary X-Forwarded-For.

Logout requires CSRF-protected POST to /access/logout/. Membership removal revokes
access on the next request. Provisioning, rotation, and successful password sign-in
create audit records without the password/hash. Password mode is opt-in; when disabled,
its login route is unavailable and the existing invite-only OIDC flow remains.

Verification: the automated suite covers brute-force races, wrong/revoked users,
CSRF, unsafe redirects, logout, hash rotation/session invalidation, and no secret echo.
Run scripts/verification/password_smoke.py with Node/Chromium available for a real
password-browser flow against an isolated copy of the public portfolio. It uses no
ChatGPT identity or forced session. Local test HTTP is disposable; deployment still
requires real HTTPS and a successful external-browser acceptance check.

The regular-host entrypoint can create the first named administrator using
`ACCESS_BOOTSTRAP_EMAIL` and `ACCESS_BOOTSTRAP_PASSWORD` from the host secret store.
Remove both after login verification. Bootstrap never resets an existing password,
changes a role, or reactivates a revoked account. See [DEPLOYMENT.md](DEPLOYMENT.md).
