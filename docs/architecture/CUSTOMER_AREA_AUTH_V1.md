# Customer Area Authentication V1

## Purpose

Authentication V1 establishes identity and secure browser access for the ForensiHash / ARQEN Customer Area. It is independent of local forensic evidence and does not implement commercial/customer domains beyond identity.

## Authentication flow

Registration normalizes the email, validates and Argon2-hashes the password, creates the user, rotates to a new opaque session and sets session/CSRF cookies. Login uses a generic credentials failure, rejects disabled users, updates `last_login_at` and creates a fresh session. Startup calls `/api/v1/auth/me`; protected routes render only after that check. Logout revokes the database session before deleting cookies.

## User model

The public identity fields are `id`, normalized `email`, `password_hash` (never serialized), `status`, `email_verified`, `created_at`, `updated_at` and `last_login_at`. Status values are `ACTIVE`, `DISABLED` and `PENDING_VERIFICATION`. Historical analysis-related columns remain temporarily in the physical table for compatibility but are excluded from the Customer Area DTO.

## Session architecture

Session tokens contain 256 bits of randomness. Only SHA-256 digests are persisted in `auth_sessions`; raw tokens exist only in an HttpOnly cookie. Each record has explicit creation, expiry and revocation timestamps. CSRF is double-submit and bound by digest to the active server session. Password reset revokes every active session for that user.

## Password storage

Passwords use the existing `argon2-cffi` Argon2id implementation. The minimum policy is 12 characters with letters and numbers. Plaintext passwords and hashes are never returned or logged.

## Password reset

Forgot-password always returns the same public message. For a valid active identity it invalidates prior unused reset records, creates a random one-time token and stores only its digest with a configurable lifetime. Successful reset marks it used, changes the Argon2 hash and revokes sessions. A delivery protocol isolates email infrastructure; the development sink never logs the URL/token. No production delivery is claimed.

## Email verification state

The `email_verified` field and `PENDING_VERIFICATION` status prepare the domain, but token issuance and delivery are intentionally deferred. V1 registrations remain `ACTIVE` and unverified until a product verification policy is selected.

## Security considerations

- HttpOnly, expiring session cookie; `Secure` is mandatory in staging/production.
- Configurable `SameSite`; `none` requires Secure.
- Session-bound CSRF on logout and legacy mutations.
- CORS allowlist with credentials; HTTPS-only origins in deployed environments.
- Generic login and recovery responses limit enumeration.
- ORM parameter binding avoids string-built SQL.
- Email is rendered as React text, not injected HTML.
- Tokens/passwords are excluded from operational logs.
- Login/recovery throttling is bounded but process-local; production needs a shared gateway/store limit.
- Deployed startup validates HTTPS, database, cookie and secret configuration.

## Database tables

- `users`: identity and authentication status (plus explicitly transitional legacy columns).
- `auth_sessions`: digested opaque sessions, CSRF digest, expiry and revocation.
- `password_reset_tokens`: digested one-time recovery tokens, expiry and use timestamp.

No customer profile, commercial or forensic table was added.

## Frontend route protection

Public routes are `/login`, `/register`, `/forgot-password` and `/reset-password`. `/customer` is protected by the canonical `AuthProvider`, which exposes loading, authenticated/unauthenticated state and user. Authenticated users visiting login/register are redirected to `/customer`; guests are redirected to login without an authenticated-content flash.

## Configuration

- `FORENSIHASH_SESSION_LIFETIME_SECONDS` (default 28800)
- `FORENSIHASH_RESET_TOKEN_LIFETIME_SECONDS` (default 1800)
- `FORENSIHASH_APPLICATION_BASE_URL`
- `FORENSIHASH_COOKIE_SECURE`, `FORENSIHASH_COOKIE_SAMESITE`
- `FORENSIHASH_ALLOWED_ORIGINS`, `FORENSIHASH_DATABASE_URL`

Opaque sessions need no signing secret: token entropy comes from the operating system and only digests are stored.

## Known limitations

There is no email verification flow or production email provider. Rate limiting is process-local and documented as non-production. Session cleanup is evaluated on access; a scheduled purge is not included. Legacy Web analysis routes/tables remain and require a separate decommissioning patch.

## Future integration points

Profile, Subscription, Entitlement, License, Device, Billing and Support must be separate domains referencing `users.id`. None is implemented in V1.
