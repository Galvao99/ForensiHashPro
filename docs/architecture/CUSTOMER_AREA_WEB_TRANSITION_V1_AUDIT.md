# Customer Area Web Transition V1 — Impact Audit

## Scope and decision

The browser application is the ForensiHash / ARQEN Customer Area. Forensic analysis belongs to ForensiHash Desktop. This transition removes the active browser workflow before any destructive database cleanup. It does not implement Profile, Plan, License, Device, Billing, Support or Admin.

## Frontend inventory

| Artifact | Classification | Reason |
|---|---|---|
| `App.tsx` `/app/*` workspace and `/admin/users` routes | REMOVE | Active legacy browser-analysis/admin surface. `/customer` becomes canonical. |
| `AppShell.tsx` | REMOVE | Navigation, privacy onboarding and identity are coupled to uploads, history, DDNA and analysis profiles. |
| `AnalysisPage.tsx`, `DashboardPage.tsx`, `HistoryPage.tsx`, `ResultPage.tsx` | REMOVE | Upload, queue, history, forensic result and DDNA export UX. |
| `AccountPage.tsx` | REMOVE | This page only manages forensic retention/external-analysis preferences; it is not Customer Profile V1. |
| `AdminUsersPage.tsx` | REMOVE | Existing admin edits legacy analysis roles/profiles and is outside this patch. |
| `AnalysisSessionContext.tsx` | REMOVE | Browser evidence queue, file/folder state, jobs, Analysis Sets and results. |
| Forensic result components (`DocumentMetadata`, `EntityPresentation`, `EvidenceTimeline`, `ForensicSummary`, `JsonView`, `ResultPresentation`, `StatusBadge`, `TechnicalTree`, `WorkspaceArtifact`) | REMOVE when no public-page consumer remains | Dedicated to browser forensic result rendering. |
| `EvidenceExplorer`, `ArtifactGraph` | REUSE | Institutional/public explanatory presentation only; no upload or analysis execution. |
| `DdnaPage`, `DdnaDiagram`, DDNA reference content | DEFER | Public institutional content, not an authenticated analysis workflow. It remains outside Customer navigation. |
| `HomePage`, `ProductPage`, `ReferencesPage`, public layout/brand/legal pages | KEEP | Institutional site. Product calls-to-action must target `/customer`, never `/app/analysis`. |
| `CustomerAreaPage.tsx` | REUSE/UPDATE | Canonical authenticated shell; expand honest grouped placeholders without fake data. |
| `AuthContext`, `ProtectedRoute`, Auth pages, generic API client request function | KEEP/UPDATE | Authentication V1 and generic infrastructure; remove privacy/analysis/admin client methods and legacy user fields. |
| Forensic analysis frontend tests | REMOVE — OBSOLETE PRODUCT BEHAVIOR | They assert the intentionally removed browser product. Auth, public institutional, generic component and transition-boundary tests remain. |

## Backend inventory

| Artifact | Classification | Reason |
|---|---|---|
| `api/routes.py` router (`/capabilities`, `/analyses`, `/analysis-jobs`, `/analysis-sets`, history, results, DDNA snapshot) | REMOVE NOW FROM REGISTRATION | Exclusively exposes browser forensic analysis. Implementation remains temporarily for historical tests/reference and safe staged cleanup. |
| `api/admin.py` | REMOVE NOW FROM REGISTRATION | Existing operations manage legacy role/analysis profile; not the future ARQEN Admin domain. |
| analysis schemas and `services/analysis_*`, `ddna_snapshot`, `capabilities_service` | KEEP TEMPORARILY | Web-only and now unreachable, but physical deletion is deferred so transition risk and database history can be handled separately. |
| `AnalysisJobExecutor` lifecycle startup | REMOVE NOW | No registered endpoint may enqueue browser evidence; worker must not start in the Customer Area process. |
| `api/auth.py`, auth dependencies/schemas/service, email delivery | SHARED — MUST PRESERVE | Authentication V1. |
| FastAPI bootstrap, health, CORS, errors, SQLAlchemy, Alembic, logging/config | SHARED — MUST PRESERVE | Generic Customer Area infrastructure. |
| Desktop `app/`, Rust Core, parsers, engines, OCR and correlation | SHARED — MUST PRESERVE | Canonical forensic product; no modification authorized. |

Unregistering a router means the endpoints are absent from OpenAPI/runtime routing. It does not mean the implementation is safe to delete; physical backend cleanup is deferred.

## Database classification

| Object | Classification |
|---|---|
| `users` identity columns (`id`, `email`, `password_hash`, `status`, `email_verified`, timestamps) | ACTIVE CUSTOMER AREA |
| `auth_sessions`, `password_reset_tokens` | ACTIVE CUSTOMER AREA |
| `users.name`, `role`, `analysis_profile`, `is_active`, `session_version` | LEGACY/TRANSITIONAL; status compatibility still requires investigation before cleanup |
| `privacy_preferences`, `consents` | LEGACY UNUSED by Auth V1; SAFE TO DROP LATER only after data-retention review |
| `analyses`, `analysis_jobs`, `analysis_sets` | LEGACY UNUSED after endpoint decommission; SAFE TO DROP LATER after observation/export policy |
| Foreign keys from legacy analysis tables to `users` | LEGACY; REQUIRES coordinated future migration |

No database object is dropped and no Alembic history is rewritten in this patch.

## Authentication coupling

The public Auth V1 DTO and session/recovery flows do not depend on AnalysisJob, AnalysisSet, StoredAnalysis, retention, OCR, evidence or findings. Two transitional couplings remain in storage code: registration creates a default `UserPrivacyPreferences` row for old routes, and `User` retains legacy role/profile/activity columns. Because the forensic router is being unregistered, the default privacy-row creation is accidental coupling and may be removed without changing Auth. Account enablement continues to use both `status` and legacy `is_active`; consolidating that column requires a later data migration and is deferred.

## Test classification

- KEEP: Auth V1, runtime configuration, database configuration, health, container, public institutional/branding/accessibility tests and complete Desktop/Core suite.
- UPDATE: navigation, product CTA, theme/protected-route and new transition boundary tests.
- REMOVE — OBSOLETE PRODUCT BEHAVIOR: browser upload/job lifecycle, analysis workspace, analysis profiles, forensic overview/history/result/DDNA export endpoint and Web queue/capacity tests. Their service implementation is preserved temporarily, but the product endpoints they assert are intentionally gone.

## Risks and controls

- Historical tables remain: mitigated by zero destructive migration and explicit later cleanup.
- Dead backend implementation remains: mitigated by router non-registration tests and a dedicated later removal patch.
- Public institutional DDNA content may be mistaken for an analysis feature: it remains public marketing/reference content and is not present in Customer navigation.
- Authentication regression: covered by focused and broad tests; no Auth architecture change is planned.
