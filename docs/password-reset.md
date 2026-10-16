# Password reset delivery and throttling

`POST /auth/forgot-password` accepts `identifier` or `email` (email address or
roll number), and retains the `success`, `message`, and nullable `email` response
fields. For roll numbers, `email` is always null. For email input it echoes only
the normalized input. Existing and missing accounts receive the same message
and status for the same input type, including when email delivery fails.

Lookup, token generation and email delivery run in a FastAPI background task
after the response. Each task owns its database session. SMTP must return an
empty refusal map, or Resend must return a nonempty message ID, before new OTP
and reset-link credentials are committed. On failure, the transaction rolls
back, retaining previous credentials. Provider acceptance does not prove inbox
delivery: bounces and spam filtering must be investigated in provider dashboards.
Logs report acceptance/failure without OTPs, reset links, subjects or raw provider
exception messages. No configured provider is a failure, not simulated delivery.

Request reservations are persisted in `email_rate_limits`, shared across workers
and restarts. PostgreSQL row locks and SQLite write serialization prevent concurrent
requests from exceeding the limit. Keys are HMACs using `SECRET_KEY`; raw addresses,
roll numbers and client IPs are not stored in this table. Expired rows are removed
as requests arrive.

- Each normalized reset identifier: one request per 60 seconds, five per rolling hour.
- Each source IP: 20 reset requests per rolling hour, including rejected identifier retries.
- Each destination address: one delivery attempt per 60 seconds, five per rolling hour,
  shared by email/roll aliases. Verification uses a separate request budget, so its
  public HTTP 429 responses cannot expose account-dependent reset delivery activity.
- Failed sends and unknown identifiers consume reservations. Public request limits
  return HTTP 429 with `Retry-After`. Account-dependent delivery limits silently
  suppress sending to avoid revealing registered accounts.

## Deployment

Apply `python -m alembic upgrade head` from `backend` before starting the updated
app. Migration `0007_email_rate_limits` adds the shared limiter table. The existing
Render pre-deploy command and Procfile already run migrations. All workers must
use the same database and production `SECRET_KEY`.

With SQLAlchemy versions that default to psycopg v3, use a
`postgresql+psycopg2://...` database URL for Alembic to match the installed
`psycopg2-binary` dependency. The full PostgreSQL migration chain and this
migration's downgrade/reapply have been tested. A fresh SQLite migration chain
still fails at the pre-existing `0004` ALTER COLUMN operation; this new migration
is independently tested on SQLite.

Configure SMTP credentials or `RESEND_API_KEY` and an authorized sender. Confirm
`FRONTEND_URL` points to the deployed HashRouter frontend. Reset email links retain
the `/#/reset-password?token=...` format, and OTP reset requests keep their existing
payload. Use a controlled account to check actual delivery after deployment;
automated tests mock providers and send no real emails.

The IP limit uses `request.client.host`. Configure the server to trust forwarded
addresses only from the deployment proxy; the application does not parse arbitrary
`X-Forwarded-For` headers. Shared campus/NAT addresses share the 20/hour budget;
adjust that policy if production traffic requires it and retain edge abuse controls.

Background tasks are not a durable queue: process termination can lose a pending
send. A database commit failure after provider acceptance can also result in an
unusable new code. The user can retry after the cooldown; a transactional outbox
would be a separate reliability improvement. PostgreSQL is preferred in production;
SQLite holds a database write lock while the delivery transaction is pending.

## Regression checks

From `backend`, run:

```sh
python -m pytest tests/test_email_delivery.py tests/test_email_verification.py tests/test_auth_module.py tests/test_critical_openapi_and_frontend_contract.py
```

These cover SMTP/Resend failure and fallback, redacted logging, rollback, unknown
accounts, case normalization, aliases, wildcard inputs, concurrent reservations,
expiry, persisted limits, single-use links, OTP reset and frontend API contracts.
