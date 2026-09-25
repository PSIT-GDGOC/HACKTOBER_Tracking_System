# Backend Tasks v2 — Abu (Ansari)
> GDGOC Hacktoberfest — Open Source Contribution Management Platform
> Last updated: September 2026 | Based on README v2

---

## Project Overview

A centralized platform for PSIT students to discover, claim, and track open-source contributions across GDGOC's two official Hacktoberfest repositories (Web App + Android App). GitHub is the source of truth for code — this platform is the event-management layer on top of it.

**Core lifecycle:** `Discover → Claim → Work → Submit → Review → Accept → Track`

**Team:**
| Person | Owns |
|---|---|
| Abu (you) | Entire backend logic |
| Rudransh | Entire frontend |
| Aditya | Auth, ID/QR verification, infra, deployment |

**Stack (your concern):**
- FastAPI (Python) + Pydantic
- SQLAlchemy + Alembic
- Supabase Postgres
- Supabase `pg_cron` (for webhook job retries — Aditya sets this up, you design the table)
- PyGithub / GitHub REST API + webhook signature verification
- No Celery, No Redis, No separate broker

---

## What Changed From v1 — Summary

| Area | v1 Plan | v2 Plan |
|---|---|---|
| Verification | Roll number + community code (env var) | ID card photo + QR decode + PSIT portal fetch (Aditya's module) |
| Async jobs | Celery + Postgres as broker | `webhook_jobs` table + pg_cron polling worker |
| `users` table | Had ERP/community-code fields | New verification fields; old fields removed |
| Total tables | 10 | 11 (new: `webhook_jobs`) |
| Your webhook engine | Dispatch to Celery | Insert into `webhook_jobs` table; build polling worker |

---

## Database Schema — Full Picture (11 Tables)

### Tables You Own Entirely

---

#### `users` ← MODIFIED FROM v1

**Fields added (new in v2):**
| Field | Type | Notes |
|---|---|---|
| `id_card_image_url` | String | Private Supabase Storage path — never a public URL |
| `qr_token` | String | Raw decoded QR payload from the ID card |
| `portal_snapshot_json` | JSON | What the PSIT portal returned; used for manual review fallback; purged post-event |
| `verification_method` | Enum | `qr_auto` or `manual` |
| `verified_at` | DateTime | Timestamp of verification completion |

**Fields removed (were in v1, gone in v2):**
| Field | Why Removed |
|---|---|
| `erp_verified` | ERP integration dropped entirely |
| `community_code_used` | Community code approach replaced by QR verification |   
| `year_mismatch_flag` | Not needed in new flow |
| `duplicate_roll_flag` | Handled differently now |

**Fields written by Aditya, defined by you in schema — coordinate on exact types:**
- `verified` (Boolean)
- `verified_at` (DateTime)
- `verification_method` (String/Enum)
- `qr_token` (String)
- `portal_snapshot_json` (JSON)
- `id_card_image_url` (String)

**Full `users` field list (v2):**
```
id, name, email, psit_roll_no, github_username, github_id, role,
id_card_image_url, qr_token, portal_snapshot_json,
verification_method, verified, verified_at
```

---

#### `webhook_jobs` ← ENTIRELY NEW IN v2

This table replaces Celery entirely. Every incoming GitHub webhook event is inserted as a row here. A polling worker drains pending rows and processes them.

**Fields:**
```
id, payload_json, status, attempts, next_attempt_at, created_at, updated_at
```

**Status values:** `pending` / `processing` / `done` / `failed`

**How it works:**
1. Webhook receiver endpoint gets a GitHub event → inserts a row with `status = pending`
2. Polling worker (or Supabase `pg_cron` — Aditya sets the schedule) picks up `pending` rows
3. Worker processes the event (dispatch to the right handler)
4. On success → `status = done`
5. On failure → bump `attempts`, push `next_attempt_at` out (backoff), `status = failed`
6. pg_cron retries failed rows when `next_attempt_at` is due

---

#### `repositories` — UNCHANGED
```
id, name, github_repo_url, platform (web/android)
```

---

#### `issues` — UNCHANGED
```
id, repo_id, github_issue_id, title, description,
difficulty, category, tech_tags, labels, status
```

---

#### `claims` — UNCHANGED
```
id, issue_id, user_id, claimed_at, status
```
- **Unique constraint on `issue_id` where `status = active`** — this is what prevents double-claiming
- Status values: `active`, `released`, `expired`, `completed`

---

#### `pull_requests` — UNCHANGED
```
id, repo_id, github_pr_id, issue_id, user_id,
title, status, reviewer_id, created_at, updated_at
```

---

#### `commits` — UNCHANGED
```
id, repo_id, github_commit_sha, user_id,
message, issue_id, pr_id, committed_at
```

---

#### `contributions` — UNCHANGED
```
id, user_id, issue_id, pr_id, status, timeline_json
```

---

#### `reviews` — UNCHANGED
```
id, pr_id, reviewer_id, status, comment, reviewed_at
```

---

#### `notifications` — UNCHANGED
```
id, user_id, type, payload, read, created_at
```

---

#### `activity_feed` — UNCHANGED
```
id, type, actor_id, target_type, target_id, created_at
```

---

### Indexes (unchanged from v1)
- `issues.status`
- `issues.repo_id`
- `pull_requests.status`
- `users.github_username`
- `users.psit_roll_no`

---

## Your Task List — v2

---

### Module 1 — Database Build-Out
> Start here. Everything depends on this.

**What changed from v1:** `users` table has new/removed fields; `webhook_jobs` is a new table to add.

- [x] Write SQLAlchemy model for `users` with v2 fields (add new, remove old)
- [x] Write SQLAlchemy model for `webhook_jobs` (new)
- [x] Write SQLAlchemy models for remaining 9 unchanged tables
- [x] Set up all foreign keys, relationships, and constraints
- [x] Add unique constraint on `claims(issue_id)` where `status = active`
- [x] Add all indexes listed above
- [x] Initialize Alembic
- [x] Write and apply first migration
- [x] Write seed data script for local dev
- [x] **Coordinate with Aditya** — align on exact field names/types for the 6 auth-related fields on `users` before writing models

---

### Module 2 — Issue Management
> No changes from v1.

- [x] Sync issues from GitHub via REST API (initial backfill)
- [x] `GET /issues` — list with filters (repo, difficulty, tech, category, status)
- [x] `GET /issues/{id}` — single issue
- [x] `POST /issues/{id}/claim` — **atomic DB operation, no race conditions**
- [x] `POST /issues/{id}/unclaim` — release endpoint
- [x] Claim-limit enforcement (max active claims per student)

---

### Module 3 — GitHub Webhook Sync Engine
> **Changed from v1** — no Celery; use `webhook_jobs` table instead.

- [x] `POST /webhooks/github` — receiver endpoint with GitHub signature verification
- [x] On valid webhook received → insert row into `webhook_jobs` with `status = pending`
- [x] Event dispatcher — reads from `webhook_jobs` and routes by event type:
  - [x] `issues` events
  - [x] `pull_request` events
  - [x] `push` events
  - [x] `pull_request_review` events
- [x] Auto-link PRs to claimed issues via GitHub username match
- [x] Lightweight polling worker to drain `pending` / due-for-retry rows from `webhook_jobs` (`POST /webhooks/jobs/drain`)
- [x] Retry logic — on failure: bump `attempts`, calculate and set `next_attempt_at` (exponential backoff), set `status = failed`

---

### Module 4 — PR & Commit Tracking
> No changes from v1.

- [x] `GET /pull-requests` — list, filterable by repo / contributor / status
- [x] `GET /pull-requests/{id}` — single PR
- [x] `GET /commits` — list per repo and per contributor

---

### Module 5 — Contribution State Machine
> No changes from v1.

States: `claimed → in_progress → pr_submitted → under_review → changes_requested → accepted → merged`

- [x] Implement state machine logic
- [x] `GET /contributions/{user_id}` — full contribution timeline
- [x] Validation status handling: `valid / pending / rejected / duplicate / invalid`

---

### Module 6 — Dashboard Aggregation Endpoints
> **v2 update:** `erp_verified` replaced with `verified` + `pending_manual_review_students` in Admin Dashboard.

- [x] `GET /dashboard/student` — summary for logged-in student
- [x] `GET /dashboard/maintainer` — review queue
- [x] `GET /dashboard/repository/{id}` — repo-level stats
- [x] `GET /dashboard/admin` — event-wide overview

---

### Module 7 — Contributor Profiles
> **v2 update:** `erp_verified` replaced with `verified`, `verified_at`, `verification_method` in public and private profile responses.

- [x] `GET /users/{id}` — public profile
- [x] `PATCH /users/me` — update own profile

---

### Module 8 — Engagement Layer
> **v2 verified:** All engagement hooks are integrated with the webhook job engine and claim service. No Celery.

- [x] `GET /leaderboard` — plain Postgres aggregation query (no Redis, no external store); weighted difficulty points
- [x] Notification creation hooked into all key events:
  - `claim_created` / `claim_released` — from `issue_service.py`
  - `pr_opened` / `pr_merged` / `pr_review` — from `webhook_service.py`
- [x] `GET /notifications` — paginated, unread-first ordering, `unread_only` filter
- [x] `PATCH /notifications/{id}/read` — mark single read (user-ownership enforced)
- [x] `POST /notifications/read-all` — single-query batch mark-all-read
- [x] `GET /activity` — global activity feed with enriched actor/target, batch N+1-safe lookups, type/actor/target filters

---

### Module 9 — Search
> **v2 update:** Contributors now searchable by `psit_roll_no` (institutional ID) in addition to name and GitHub username.

- [x] `GET /search?q=` — unified search across issues, PRs, contributors (name/github/roll no.), repos, commits
  - [x] Full-text `ILIKE` matching on all entity fields
  - [x] Numeric query auto-matches `github_issue_id` / `github_pr_id`
  - [x] Scopeable by `category` param: `all`, `issues`, `pull_requests`, `contributors`, `repositories`, `commits`
  - [x] v2: `psit_roll_no` added as searchable contributor field

---

## Build Order (your lane only)

| Step | Task | Depends On |
|---|---|---|
| 1 | DB schema + migrations (all 11 tables) | Nothing — start immediately |
| 2 | Issue CRUD + claim system | Schema done, Aditya's auth live |
| 3 | Webhook sync engine + `webhook_jobs` worker | Schema done |
| 4 | PR/commit tracking | Webhook engine done |
| 5 | Contribution state machine | PR tracking done |
| 6 | Dashboard aggregation endpoints | All above done |
| 7 | Contributor profiles | Schema done |
| 8 | Engagement layer | Dashboard done |
| 9 | Search | All modules done |

---

## Coordination Points With Aditya
> **Aligned & Implemented:**
> - Auth fields defined in `User` model (`app/models/user.py`).
> - Verification writes separated (Aditya's service writes `verified`, `verified_at`, `verification_method`, `id_card_image_url`, `qr_token`, `portal_snapshot_json`).
> - `pg_cron` calls `POST /webhooks/jobs/drain` worker logic.
> - JWT role middleware: RBAC dependencies (`require_roles`, `require_verified_student`) implemented in `app/dependencies.py`.

- [x] Exact field names and types for the 6 auth fields on `users` (`verified`, `verified_at`, `verification_method`, `qr_token`, `portal_snapshot_json`, `id_card_image_url`)
- [x] Who writes to which fields — his verification service writes `verified`, `verified_at`, `verification_method`; you define the column in the model
- [x] `pg_cron` retry schedule for `webhook_jobs` — he sets it up, you define the worker logic it calls
- [x] JWT role middleware — he builds it, you consume it to protect your endpoints

---

## Critical Rules (do not skip)
> **Verified & Tested:**
> - Claim locking concurrency stress tests pass (atomic DB row locking + partial unique index `uq_active_claim_per_issue`).
> - Webhook signature verification verified (rejects invalid HMAC-SHA256 signatures with 401 before queueing).
> - `id_card_image_url`, `qr_token`, and `portal_snapshot_json` are strictly omitted from all public/client response schemas and OpenAPI specs.
> - Global `SensitiveDataFilter` in `app/logging_config.py` automatically scrubs verification PII and storage paths from all logging handlers.

- [x] Claim locking must use an atomic DB operation — application-level check is not enough
- [x] Webhook receiver must verify GitHub signature before inserting into `webhook_jobs`
- [x] `id_card_image_url` must never be a public URL — always a signed URL (Aditya handles storage, you just store the path)
- [x] `portal_snapshot_json` and ID image paths are excluded from logs

---

### Module 10 — Auth & Student Verification Module (ID Card + QR Engine)
> **Built & Fully Operational:** Server-side ID card photo processing, QR cross-check with PSIT portal snapshot, fallback review queue, JWT token authentication, and GitHub account linking.

- [x] `POST /auth/signup` — Student registration with official PSIT roll number and name
- [x] `POST /auth/login` — JWT token issuance with role claims (`student` / `maintainer` / `admin`)
- [x] `GET /auth/me` — Authenticated user session endpoint
- [x] `POST /auth/verify-id` — Server-side ID card photo & QR decode cross-check
  - [x] Roll number exact match
  - [x] Student name fuzzy match threshold
  - [x] Auto-verify on match (`qr_auto`); route to admin review on mismatch/unreadable
- [x] `GET /auth/pending-verifications` — Admin review queue for unverified students
- [x] `POST /auth/verify-manual/{student_id}` — Admin approve/reject verification decision
- [x] `GET /auth/github/login` — GitHub OAuth authorization flow initiator
- [x] `POST /auth/github/link` — Connect verified student to their GitHub identity


