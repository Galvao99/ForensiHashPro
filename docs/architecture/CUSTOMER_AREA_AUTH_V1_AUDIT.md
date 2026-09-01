# Customer Area Auth V1 — Architectural Checkpoint

## 1. Current relevant architecture

The Web backend is FastAPI with synchronous SQLAlchemy 2 sessions, Alembic migrations and PostgreSQL in deployed environments (SQLite is used by isolated tests). Routes are grouped below `/api/v1`. The existing Web application already had Argon2 password hashing, signed browser cookies, double-submit CSRF, CORS configuration and an authentication React context. The frontend is React, TypeScript, React Router, Vite and Vitest.

The pre-patch `User` table also carried `name`, `role`, `analysis_profile`, `is_active` and a relationship to forensic-result retention preferences. Analysis routes use that legacy state for the old browser analysis product.

## 2. Existing reusable pieces

- SQLAlchemy `Base`, session dependency and the existing PostgreSQL database.
- Alembic migration chain.
- Argon2 (`argon2-cffi`) password hashing and password policy.
- Email normalization, cookie security and CORS configuration.
- FastAPI error envelope and dependency injection.
- React API client, `AuthProvider`, protected-route component, generic inputs/buttons and design tokens.

## 3. Pieces that must not be reused

`AnalysisJob`, `AnalysisSetRecord`, `StoredAnalysis`, retention preferences, analysis profiles, uploads, OCR, Facts, Findings, Evidence Graph and case correlation are not identity/customer-account concepts. They are not used by the new session or recovery implementation. Old analysis pages and routes remain present only to avoid a large deletion in this patch.

## 4. Files planned to modify

`.env.example`; `web/backend/app/{models.py,runtime_config.py,security.py}`; `web/backend/app/api/{auth.py,dependencies.py}`; `web/backend/app/schemas/auth.py`; `web/frontend/src/{App.tsx,types/api.ts,lib/api.ts,context/AuthContext.tsx,pages/AuthPages.tsx,styles/global.css}`.

## 5. Files planned to create

Auth application service, email-delivery boundary, Alembic migration, customer shell, backend/frontend Auth V1 tests, this checkpoint and the final architecture document.

## 6. Migration/database implications

The migration adds `status` and `email_verified` to the existing `users` identity record and creates `auth_sessions` and `password_reset_tokens`. It deliberately does not create profile, plan, subscription, entitlement, license, device, billing or support tables. Legacy columns remain until the old Web analysis system is decommissioned in a separate migration.

## 7. Risks

- Existing deployed users receive `ACTIVE` and unverified defaults; a later verification rollout needs an explicit policy.
- Legacy Web analysis still references customer identities through historical foreign keys. Removing those links is outside this patch.
- Process-local throttling is only a bounded development protection and is not horizontally consistent.
- A production email provider is not present, so production recovery delivery must remain disabled/unavailable until one is configured.

## 8. Selected authentication approach

Opaque, cryptographically random, server-managed sessions were selected. The browser receives an expiring HttpOnly cookie while only its SHA-256 digest is stored. This supports immediate revocation, real logout, expiry checks and global revocation after password reset without localStorage or long-lived JWTs. State-changing requests also require a session-bound CSRF token. Cookies are `Secure` in deployed environments and use configurable SameSite semantics.

## 9. Explicit boundary

Browser forensic analysis is outside Customer Area Authentication V1. This patch does not upload, move, interpret or modify forensic evidence or Desktop case data, and it does not remove the old Web analysis system.
