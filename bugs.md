# Production Bugs & Remediation Roadmap

This document serves as the master tracking plan for identifying, fixing, and verifying all production/deployment bugs and vulnerabilities across the frontend, backend, database, and cloud configurations.

---

## Progress Overview

| Phase | Description | Status | Completed |
|---|---|---|---|
| **Phase 1** | Configuration, Deployment Manifests & Infrastructure | ✅ Completed | 4 / 4 |
| **Phase 2** | Routing, API Prefixes & Reverse Proxy Alignment | ✅ Completed | 1 / 1 |
| **Phase 3** | Backend Authentication, Security & Webhook Hardening | ✅ Completed | 4 / 4 |
| **Phase 4** | Frontend Client Resilience & OAuth Integration | ✅ Completed | 2 / 2 |
| **Phase 5** | Verification Media Persistence & Storage Architecture | ✅ Completed | 1 / 1 |
| **Phase 6** | Deployment Staging, Release Commit & Remote Synchronization | 🔄 In Progress | 0 / 2 |

---

## Detailed Step-by-Step Fix Plan

### Phase 1: Configuration, Manifests & Infrastructure

---

#### Step 1: BUG-02 — Fix Environment Variable Names in `render.yaml`
- **Severity**: 🔴 Critical
- **Affected Files**:
  - [`render.yaml`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/render.yaml)
- **Problem**: 
  `render.yaml` specifies `JWT_SECRET` instead of `SECRET_KEY`, and `VITE_API_URL` instead of `VITE_API_BASE_URL`. This causes the backend to fall back to the hardcoded insecure default secret key in production, and causes the frontend to run in demo/offline mode.
- **Detailed Plan**:
  1. In `render.yaml` under `hacktober-backend`, rename envVar key `JWT_SECRET` to `SECRET_KEY`.
  2. Under `hacktober-frontend`, rename envVar key `VITE_API_URL` to `VITE_API_BASE_URL`.
  3. Ensure both keys match `backend/app/config.py` and `frontend/src/lib/api.js`.
- **Status**: [x] Completed (Render env vars renamed to SECRET_KEY and VITE_API_BASE_URL; declared GitHub secrets)

---

#### Step 2: BUG-09 — Remove Dead Celery Worker from `render.yaml`
- **Severity**: 🟡 Medium
- **Affected Files**:
  - [`render.yaml`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/render.yaml)
- **Problem**: 
  The v2 architecture migrated away from Celery to the database-backed `webhook_jobs` table. `render.yaml` still provisions a second `hacktober-celery` container that connects to Postgres via SQLAlchemy broker and polls continuously, consuming compute and database connections.
- **Detailed Plan**:
  1. Remove the `hacktober-celery` worker service block from `render.yaml`.
  2. Keep only `hacktober-backend` and `hacktober-frontend`.
- **Status**: [x] Completed (Removed hacktober-celery worker from render.yaml)

---

#### Step 3: BUG-11 — Execute Database Migrations on Railway Deploy
- **Severity**: 🟡 Medium
- **Affected Files**:
  - [`backend/Procfile`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/Procfile)
- **Problem**: 
  Railway executes the `Procfile` start command `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT` directly. On a fresh PostgreSQL database, tables and enum types will not exist, resulting in 500 errors on first access.
- **Detailed Plan**:
  1. Update `backend/Procfile` to run Alembic migrations prior to starting Uvicorn:
     ```procfile
     web: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
- **Status**: [x] Completed (Added alembic upgrade head to Procfile web command)

---

#### Step 4: BUG-12 — Resolve CORS Wildcard with Credentials Conflict
- **Severity**: 🟡 Medium
- **Affected Files**:
  - [`backend/app/main.py`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/app/main.py)
  - [`backend/app/config.py`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/app/config.py)
- **Problem**: 
  `ALLOWED_ORIGINS="*"` combined with `allow_credentials=True` in `CORSMiddleware` violates the W3C CORS specification and is rejected by modern browsers for authenticated requests from custom production domains.
- **Detailed Plan**:
  1. In `app/main.py`, ensure that if `ALLOWED_ORIGINS` contains `*`, `allow_credentials` is set to `False` or origins are dynamically reflected based on request headers/regex.
  2. Update `app/config.py` to default to the regex pattern for Vercel/localhost domains rather than `*` when credentials are used.
- **Status**: [x] Completed (Filtered wildcard from allowed_origins_list and expanded allow_origin_regex to safely match localhost, Vercel, and Render)

---

### Phase 2: Routing & Reverse Proxy Alignment

---

#### Step 5: BUG-01 — Align FastAPI Route Prefixes with `vercel.json` Rewrites
- **Severity**: 🔴 Critical
- **Affected Files**:
  - [`backend/app/main.py`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/app/main.py)
  - [`vercel.json`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/vercel.json)
- **Problem**: 
  `vercel.json` rewrites `/api/*` to the backend, but FastAPI routers in `main.py` are mounted directly at `/auth`, `/issues`, `/dashboard`, etc. Calling `/auth/login` gets routed to the frontend, and calling `/api/auth/login` returns a 404 from FastAPI.
- **Detailed Plan**:
  1. In `backend/app/main.py`, mount routers so they are accessible both at root (`/auth`, `/issues`, etc.) and under `/api` (`/api/auth`, `/api/issues`, etc.), or cleanly wrap them under an `/api` router while providing backwards-compatible mounts.
  2. Verify that `/health` works on both `/health` and `/api/health`.
  3. Ensure `frontend/src/lib/api.js` connects smoothly whether `VITE_API_BASE_URL` is set to `/api` or directly to an external backend URL.
- **Status**: [x] Completed (Dual-mounted all routers on root and /api in main.py; added docs and openapi.json rewrites to vercel.json)

---

### Phase 3: Backend Authentication, Security & Webhook Hardening

---

#### Step 6: BUG-04 — Prevent Passwordless Login on Accounts Lacking Password Hash
- **Severity**: 🟠 High
- **Affected Files**:
  - [`backend/app/services/auth_service.py`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/app/services/auth_service.py)
  - [`backend/seed.py`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/seed.py)
- **Problem**: 
  `authenticate_user()` only verifies the password `if user.password_hash:`. If a user hasn't set a password or was seeded without one, anyone knowing the student roll number can log in without entering a password.
- **Detailed Plan**:
  1. In `authenticate_user()`, if `not user.password_hash`, reject the login request with `401 Unauthorized` stating that password setup is required.
  2. In `seed.py`, assign hashed default passwords to student, maintainer, and admin accounts so seeded test accounts are secure and functional.
  3. Add regression tests in `tests/test_auth_module.py`.
- **Status**: [x] Completed (authenticate_user strictly requires password_hash in production; default passwords seeded for all roles)

---

#### Step 7: BUG-06 — Strictly Enforce Webhook Signatures in Production
- **Severity**: 🟠 High
- **Affected Files**:
  - [`backend/app/services/webhook_service.py`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/app/services/webhook_service.py)
- **Problem**: 
  If `GITHUB_WEBHOOK_SECRET` is empty in production, `verify_github_signature` logs a warning and returns `True`, allowing attackers to spoof pull request merges and fake contributions.
- **Detailed Plan**:
  1. Check `settings.ENV == "development" and settings.DEBUG` before allowing empty webhook secrets.
  2. In production (`ENV != "development"`), reject webhooks with `401 Unauthorized` if the secret is not configured or signature does not match.
  3. Verify with existing webhook tests.
- **Status**: [x] Completed (Enforced strict signature header validation and rejection when secret is unconfigured in production; safely preserved dev test secrets)

---

#### Step 8: BUG-05 — Secure Administrative Webhook Endpoints
- **Severity**: 🟠 High
- **Affected Files**:
  - [`backend/app/routers/webhooks.py`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/app/routers/webhooks.py)
- **Problem**: 
  `POST /webhooks/jobs/drain` and `GET /webhooks/jobs` are completely unauthenticated and public, allowing anyone on the internet to trigger batch execution or inspect internal payloads and error traces.
- **Detailed Plan**:
  1. Protect `GET /webhooks/jobs` with `require_roles(UserRole.ADMIN)`.
  2. Protect `POST /webhooks/jobs/drain` with either `require_roles(UserRole.ADMIN)` or a secure shared secret header (`X-Cron-Secret` / `X-Admin-Key`) for automated schedulers.
- **Status**: [x] Completed (Secured GET /webhooks/jobs with require_roles(UserRole.ADMIN) and POST /webhooks/jobs/drain with X-Cron-Key or Admin JWT authentication)

---

#### Step 9: BUG-10 — Add Idempotency to Webhook Processing (`X-GitHub-Delivery`)
- **Severity**: 🟡 Medium
- **Affected Files**:
  - [`backend/app/models/webhook_job.py`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/app/models/webhook_job.py)
  - [`backend/app/routers/webhooks.py`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/app/routers/webhooks.py)
  - [`backend/app/services/webhook_job_service.py`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/app/services/webhook_job_service.py)
- **Problem**: 
  GitHub webhooks frequently retry on network delay. Without tracking `X-GitHub-Delivery`, duplicate events are executed, leading to duplicate commits, notifications, and activity feed rows.
- **Detailed Plan**:
  1. Add an optional `delivery_id` column to `WebhookJob` with a unique index.
  2. Extract `X-GitHub-Delivery` in `github_webhook_receiver()`.
  3. If a job with the same `delivery_id` already exists, return `200 OK` ("duplicate delivery acknowledged") without re-processing.
- **Status**: [x] Completed (Added delivery_id column and migration; enforced delivery idempotency in webhook_job_service and webhooks router)

---

### Phase 4: Frontend Client Resilience & OAuth Integration

---

#### Step 10: BUG-07 — Protect Sessions from Cold-Start Network Timeouts
- **Severity**: 🟠 High
- **Affected Files**:
  - [`frontend/src/lib/auth.jsx`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/frontend/src/lib/auth.jsx)
- **Problem**: 
  During app mount, `api.me().catch(() => tokenStore.clear())` clears the saved JWT token on ANY error (e.g. backend sleeping, cold boot, 502/503 status, network hiccup).
- **Detailed Plan**:
  1. Update `AuthProvider` in `auth.jsx`: inspect the error object.
  2. Only call `tokenStore.clear()` when `err instanceof ApiError && err.status === 401`.
  3. For network timeouts and 5xx errors, preserve the stored token and show a retry state or keep trying.
- **Status**: [x] Completed (auth.jsx now only clears tokens on explicit 401 Unauthorized status, preserving tokens during server cold boots and transient errors)

---

#### Step 11: BUG-03 — Complete GitHub OAuth Callback Flow in Frontend
- **Severity**: 🔴 Critical
- **Affected Files**:
  - [`frontend/src/App.jsx`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/frontend/src/App.jsx)
  - [`frontend/src/pages/auth.jsx`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/frontend/src/pages/auth.jsx)
  - [`frontend/src/lib/api.js`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/frontend/src/lib/api.js)
- **Problem**: 
  Clicking "Link GitHub" redirects to `/#/auth/callback`, which is unhandled in `App.jsx` and hits `NotFound`. The frontend has no component or API call to exchange the OAuth code.
- **Detailed Plan**:
  1. In `frontend/src/lib/api.js`, add `githubCallback: (code) => request("/auth/github/callback", { method: "POST", body: { code } })`.
  2. In `frontend/src/pages/auth.jsx`, build a `GitHubOAuthCallback` component that extracts `code` from query params, calls `api.githubCallback()`, updates user profile, and navigates back to `/join` or `/dashboard`.
  3. In `frontend/src/App.jsx`, add `<Route path="/auth/callback" element={<GitHubOAuthCallback />} />`.
- **Status**: [x] Completed (Added githubCallback API call, implemented GitHubOAuthCallback component handling code exchange & error states, mounted /auth/callback route in App.jsx, and verified with production Vite build)

---

### Phase 5: Verification Media Persistence & Storage Architecture

---

#### Step 12: BUG-08 — Implement ID Card Image Upload Persistence
- **Severity**: 🟡 Medium
- **Affected Files**:
  - [`backend/app/services/auth_service.py`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/app/services/auth_service.py)
  - [`backend/app/services/storage_service.py`](file:///d:/Abu%20Horairah%20Ansari/HacktoberFest_Backend_v2/backend/app/services/) *(create)*
- **Problem**: 
  In `process_id_card_verification`, image bytes are validated and QR decoded, but the raw image is never saved to disk or Supabase Storage. The admin manual review queue cannot display the uploaded ID card image.
- **Detailed Plan**:
  1. Create a storage utility supporting Supabase Storage bucket upload with local filesystem fallback for development.
  2. Save `id_card_image_bytes` under `user.id_card_image_url` upon upload.
  3. Ensure administrative endpoints provide secure access to review images.
- **Status**: [x] Completed (Implemented storage_service with Supabase Storage and disk fallback; added authenticated GET /auth/id-card-image/{student_id} endpoint; added ID card photo preview modal in admin console; added regression test)

---

### Phase 6: Deployment Staging, Release Commit & Remote Synchronization

---

#### Step 13: Stage and Commit Remediation Changes
- **Severity**: ℹ️ Informational
- **Affected Files**: All remediated backend, frontend, configuration, and documentation files.
- **Problem**: 
  Uncommitted changes must be cleanly packaged into a structured git commit with atomic changelogs and verification traces.
- **Detailed Plan**:
  1. Stage all modified and untracked code and test files.
  2. Create a clean git commit summarizing the 12 production fixes.
- **Status**: [ ] Pending

---

#### Step 14: Synchronize with Remote Repositories
- **Severity**: ℹ️ Informational
- **Affected Files**: Git remotes (`origin`, `upstream`)
- **Problem**: 
  Production fixes must be pushed to upstream and origin repositories for automated CI/CD pipeline triggers (Vercel, Render, Railway).
- **Detailed Plan**:
  1. Push current `main` branch to `origin/main`.
  2. Push current `main` branch to `upstream/main` (`https://github.com/PSIT-GDGOC/HACKTOBER_Tracking_System`).
- **Status**: [ ] Pending

---

## Log of Completed Fixes

| Date | Issue ID | Summary of Changes Made | Verification Method |
|---|---|---|---|
| 2026-09-27 | **BUG-02** | Renamed `JWT_SECRET` -> `SECRET_KEY` and `VITE_API_URL` -> `VITE_API_BASE_URL` in `render.yaml`. Declared required GitHub secrets. | Config audit & schema alignment |
| 2026-09-27 | **BUG-09** | Removed unused `hacktober-celery` container from `render.yaml` to prevent dead DB polling. | Config audit |
| 2026-09-27 | **BUG-11** | Added `alembic upgrade head` before `uvicorn` in `backend/Procfile` for automatic schema migrations. | Procfile validation |
| 2026-09-27 | **BUG-12** | Filtered `*` from `allowed_origins_list` and broadened `allow_origin_regex` to safely allow credentials on localhost, Vercel, and Render. | Pytest auth & user test pass |
| 2026-09-27 | **BUG-01** | Implemented dual mounting for all routers on root and `/api` in `app/main.py`. Added `/api`, `/docs`, `/openapi.json` rewrites to `vercel.json`. | Direct test client verification on `/health` and `/api/health` + full pytest pass |
| 2026-09-27 | **BUG-04** | Hardened `authenticate_user()` to strictly require `password_hash` in production. Seeded default hashed passwords for all role accounts in `seed.py`. | Pytest auth suite pass |
| 2026-09-27 | **BUG-06** | Strictly enforced `X-Hub-Signature-256` HMAC-SHA256 signature verification in production and unconfigured environments. | Critical webhook security test suite pass |
| 2026-09-27 | **BUG-05** | Protected `GET /webhooks/jobs` with `require_roles(UserRole.ADMIN)` and secured `POST /webhooks/jobs/drain` with `X-Cron-Key` / Admin JWT. | Automated CI role tests & direct endpoint validation |
| 2026-09-27 | **BUG-10** | Added `delivery_id` column to `WebhookJob`, Alembic migration, and idempotency check in `webhook_job_service.py` to deduplicate retried webhook events. | Pytest webhook lifecycle & idempotency pass |
| 2026-09-27 | **BUG-07** | Updated `AuthProvider` in `frontend/src/lib/auth.jsx` to only clear stored JWT on explicit 401 Unauthorized status, preserving tokens during server cold boots. | Frontend build validation |
| 2026-09-27 | **BUG-03** | Implemented `api.githubCallback`, created neo-brutalist `GitHubOAuthCallback` page in `auth.jsx`, and mounted `/auth/callback` in `App.jsx`. | Vite production build passing |
| 2026-09-27 | **BUG-08** | Created `storage_service.py` with Supabase/disk storage, persisted raw uploaded ID card bytes in `process_id_card_verification`, created authenticated `GET /auth/id-card-image/{student_id}` admin endpoint, and enabled image inspection modal in `admin.jsx`. | Pytest regression suite pass (111/111) & Vite build pass |
