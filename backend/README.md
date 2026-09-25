# GDGOC Hacktoberfest — Open Source Contribution Management Platform

[![Backend CI](https://github.com/AbuAnsari-06/GDGOC-Hacktoberfest-Open-Source-Contribution-Management-Platform/actions/workflows/ci.yml/badge.svg?branch=v2)](https://github.com/AbuAnsari-06/GDGOC-Hacktoberfest-Open-Source-Contribution-Management-Platform/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.137.1-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg?logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-4169E1.svg?logo=postgresql&logoColor=white)](https://supabase.com)
[![Tests](https://img.shields.io/badge/Tests-61%20Passed%20(100%25)-success.svg)](./tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

A centralized platform for PSIT students to discover, claim, track, and manage open-source contributions across GDGOC's two official Hacktoberfest repositories (**Web App** + **Android App**).

GitHub remains the source of truth for code — this platform is the event-management layer that sits on top of it: verifying students server-side via ID card and QR code analysis, preventing duplicate work through atomic row locks, orchestrating asynchronous webhook event ingestion with native DB queues, and tracking the complete contribution lifecycle in real time.

---

## 📌 Table of Contents

- [Overview & Core Lifecycle](#-overview--core-lifecycle)
- [Tech Stack](#-tech-stack)
- [Team & Ownership](#-team--ownership)
- [Auth & Verification Flow (ID + QR)](#-auth--verification-flow-id--qr)
- [Frontend Pages (Consolidated IA)](#-frontend-pages-consolidated-ia)
- [Database Schema (11 Tables)](#-database-schema-11-tables)
- [System Modules & API Endpoints](#-system-modules--api-endpoints)
- [Security & Critical Guarantees](#-security--critical-guarantees)
- [Member Task Breakdown](#-member-task-breakdown)
  - [Frontend Tasks — Rudransh](#frontend-tasks--rudransh)
  - [Backend Tasks — Abu](#backend-tasks--abu)
  - [Auth, Verification & Infra Tasks — Aditya](#auth-verification--infra-tasks--aditya)
- [Build Order & Collaboration](#-build-order--collaboration)
- [Directory Structure](#-directory-structure)
- [Getting Started & Local Setup](#-getting-started--local-setup)
- [Running Automated Tests](#-running-automated-tests)
- [Deployment & CI/CD](#-deployment--cicd)
- [License](#-license)

---

## 🔄 Overview & Core Lifecycle

```
Discover Issue ➔ Claim (Atomic Lock) ➔ Work on GitHub ➔ PR Submitted ➔ Review Queue ➔ Accepted / Merged ➔ Leaderboard Points
```

- **Student Verification**: Only verified PSIT students can register and participate.
- **Issue Claiming**: Students claim GitHub issues via the platform — claiming locks the issue atomically so no two students work on the same task.
- **Coding on GitHub**: Actual coding happens on GitHub (fork ➔ branch ➔ PR) as normal.
- **Webhook Sync Engine**: GitHub webhooks push real-time updates back into the platform, auto-linking PRs and commits to the correct claimed issue and updating dashboards, review queues, and the leaderboard automatically.
- **Three Core Experiences**: Student, Maintainer, and Admin/Organizer.

---

## 🛠️ Tech Stack

| Layer | Choice |
|---|---|
| **Frontend** | Next.js (React + **plain JavaScript**, no TypeScript), TailwindCSS + shadcn/ui, TanStack Query |
| **Real-time Updates** | Client polling via TanStack Query (no WebSocket needed initially) |
| **Backend API** | FastAPI (Python 3.12+), Pydantic v2 |
| **Async Jobs** | **No Celery, No Redis** — Native PostgreSQL `webhook_jobs` table + Supabase `pg_cron` for scheduling and retries, drained by a lightweight polling worker (`POST /webhooks/jobs/drain`) |
| **GitHub Integration** | PyGithub / GitHub REST API + webhook HMAC-SHA256 signature verification |
| **Auth & Verification** | JWT + GitHub OAuth + **ID card photo upload & server-side QR verification** |
| **Image & QR Processing** | Pillow (image format/size validation) + OpenCV and pyzbar (QR decoding) |
| **Database & Storage** | Supabase Postgres (SQLAlchemy 2.0 + Alembic) + Supabase Storage (private bucket for ID cards) |
| **Caching & Leaderboard** | Plain SQL query with database indexes (no Redis/cache needed) |
| **Hosting & CI/CD** | Vercel (Frontend) + Railway or Render (Backend) + GitHub Actions (CI) |

> **Infra footprint:** Two services total — the FastAPI backend and Supabase (Postgres + Storage + `pg_cron`). No Redis, no Celery, no separate message broker or external object-storage provider.

---

## 👥 Team & Ownership

| Person | Owns |
|---|---|
| **Rudransh** | Entire frontend — every page, UI component, and the API client layer |
| **Abu** | Entire backend logic — issue management, GitHub webhook sync engine, PR/commit/contribution tracking, dashboard aggregation |
| **Aditya** | Auth & student verification system (ID/QR verification + GitHub OAuth + role security), cross-system debugging, deployment & infra |

Auth is the foundation every other module depends on — nothing in the platform works until a student can securely sign up, get verified, and log in. That module, along with catching integration bugs between frontend and backend and keeping the whole system deployed and running, is Aditya's scope.

---

## 🛡️ Auth & Verification Flow (ID + QR)

Verification happens by having the student upload a photo of their official PSIT ID card. The ID card carries a QR code that resolves to the student's record on the PSIT portal — the backend does this scan and cross-check server-side so the client is never trusted.

### Step-by-Step Flow

1. **Basic Signup**: Student submits name + roll number to create a pending account.
2. **ID Card Upload**: Student uploads a photo of their official PSIT ID card (JPEG/PNG, size cap enforced).
3. **Server-Side QR Decode**: Backend processes the image through OpenCV and pyzbar to extract the QR payload.
4. **Portal Cross-Check**: Decoded QR payload resolves to the PSIT portal. The backend fetches the portal record server-side to retrieve official name, roll number, and department.
5. **Match & Decision**:
   - Roll number must match **exactly**.
   - Student name is checked with a **fuzzy-match threshold** (tolerates middle names, casing, spacing).
   - **Match passes** ➔ `verified = true`, account auto-activates (`verification_method = "qr_auto"`).
   - **Match fails, unreadable QR, or portal unreachable** ➔ Account enters `pending_review` status and routes to the admin manual approval queue.
6. **GitHub OAuth Linking**: Once verified, the student links their GitHub account to their platform profile. This is required before claiming issues, as claims are matched to PRs/commits by GitHub username.
7. **JWT Issuance**: Authenticated users receive a JWT scoped by role (`student`, `maintainer`, `admin`).

---

## 🖥️ Frontend Pages (Consolidated IA)

Consolidated down to **10 cohesive screens** using tabs, drawers, and modals:

| # | Page | Scope & Components |
|---|---|---|
| 1 | **Auth Wizard** | Multi-step flow: Landing intro, signup form, ID upload + live QR scan status, auto-verify / pending fallback screen, GitHub OAuth connect |
| 2 | **Student Dashboard** | Tabs: Overview (claimed issues, PR summary, progress), My Issues, My Contributions (timeline: claimed ➔ PR ➔ review ➔ merged) |
| 3 | **Issue Explorer** | Filterable list (repo, difficulty, tech, category, status); detail opens in a slide-over drawer with the Claim button |
| 4 | **Repository Hub** | Tabs: Overview (repo stats), Pull Requests (filterable with detail drawer), Commits feed |
| 5 | **Leaderboard** | Real-time participant rankings by weighted points (Hard=80, Medium=40, Easy=20), PRs, and claims |
| 6 | **Profile** | Unified view/edit profile component with public and private views |
| 7 | **Maintainer Review** | Tabs: Queue (pending PRs needing review), History (reviewed PR archive) |
| 8 | **Admin Console** | Tabs: Overview (event metrics), Participants (search, approve/reject manual verifications), Moderation |
| 9 | **Notifications** | Dropdown panel in navigation with unread count badge and batch mark-all-read |
| 10 | **Settings** | Modal dialog for user preferences and account connection management |

---

## 🗄️ Database Schema (11 Tables)

```
users (1) ───────────┬─────< claims (4) >───────── issues (3) >─── repositories (2)
                     ├─────< pull_requests (5) >──┘      │
                     ├─────< commits (6) >───────────────┘
                     ├─────< contributions (7) >─────────┘
                     ├─────< reviews (8) >─────────────── pull_requests (5)
                     ├─────< notifications (9)
                     └─────< activity_feed (10)

webhook_jobs (11) ── (Independent async ingestion & retry engine)
```

### Table Structure & Fields

- **`users`**: `id`, `name`, `email`, `psit_roll_no`, `github_username`, `github_id`, `role`, `id_card_image_url`, `qr_token`, `portal_snapshot_json`, `verification_method`, `verified`, `verified_at`
- **`repositories`**: `id`, `name`, `github_repo_url`, `platform` (`web` / `android`)
- **`issues`**: `id`, `repo_id`, `github_issue_id`, `title`, `description`, `difficulty`, `category`, `tech_tags`, `labels`, `status`
- **`claims`**: `id`, `issue_id`, `user_id`, `claimed_at`, `status` (`active`, `released`, `expired`, `completed`)
  - *Constraint*: Partial unique index `uq_active_claim_per_issue` on `claims(issue_id) WHERE status = 'active'`
- **`pull_requests`**: `id`, `repo_id`, `github_pr_id`, `issue_id`, `user_id`, `title`, `status`, `reviewer_id`, `created_at`, `updated_at`
- **`commits`**: `id`, `repo_id`, `github_commit_sha`, `user_id`, `message`, `issue_id`, `pr_id`, `committed_at`
- **`contributions`**: `id`, `user_id`, `issue_id`, `pr_id`, `status`, `validation_status`, `timeline_json`
- **`reviews`**: `id`, `pr_id`, `reviewer_id`, `status`, `comment`, `reviewed_at`
- **`notifications`**: `id`, `user_id`, `type`, `payload`, `read`, `created_at`
- **`activity_feed`**: `id`, `type`, `actor_id`, `target_type`, `target_id`, `created_at`
- **`webhook_jobs`**: `id`, `event_type`, `payload_json`, `status` (`pending`/`processing`/`done`/`failed`), `attempts`, `next_attempt_at`, `error_log`, `created_at`, `updated_at`

---

## 📡 System Modules & API Endpoints

### 1. Auth & Verification (`/auth`)
- `POST /auth/signup` — Student registration with official PSIT roll number
- `POST /auth/login` — Authenticate and receive signed JWT with role claims
- `GET /auth/me` — Return current authenticated session profile
- `POST /auth/verify-id` — Upload ID card image & QR payload for server-side verification
- `GET /auth/pending-verifications` — Admin review queue for fallback manual approvals
- `POST /auth/verify-manual/{student_id}` — Admin decision endpoint (approve / reject)
- `GET /auth/github/login` — Get GitHub OAuth authorization URL
- `POST /auth/github/link` — Connect verified student to their GitHub profile

### 2. Issues & Claims (`/issues`)
- `GET /issues` — Filterable issue explorer (by repo, difficulty, category, tech tag, status, keyword)
- `GET /issues/{id}` — Single issue detail with claim metadata
- `POST /issues/{id}/claim` — Atomic issue claiming with row lock (`with_for_update`)
- `POST /issues/{id}/unclaim` — Release an active claim back to open
- `POST /issues/sync` — Trigger manual backfill of issues from GitHub REST API

### 3. GitHub Webhook Engine (`/webhooks`)
- `POST /webhooks/github` — Webhook receiver with HMAC-SHA256 signature verification; enqueues into `webhook_jobs`
- `POST /webhooks/jobs/drain` — Worker sweep endpoint called by Supabase `pg_cron` to drain pending/due jobs
- `GET /webhooks/jobs` — Admin monitoring and audit log of webhook jobs

### 4. Pull Requests & Commits (`/pull-requests`, `/commits`)
- `GET /pull-requests` — List PRs filtered by repository, contributor, or status
- `GET /pull-requests/{id}` — Retrieve single PR with reviewer details
- `GET /commits` — List commits filterable by repository and contributor

### 5. Contribution State Machine (`/contributions`)
- `GET /contributions/my` — Current student's contributions and active progress
- `GET /contributions/{user_id}/timeline` — Complete chronological timeline of contributions
- `PATCH /contributions/{id}/validate` — Maintainer validation status update (`valid`, `duplicate`, `rejected`)

### 6. Dashboards (`/dashboard`)
- `GET /dashboard/student` — Personal metrics: claimed issues, merged PRs, points, and timeline
- `GET /dashboard/maintainer` — Review queue of pending PRs and unassigned issues
- `GET /dashboard/repository/{id}` — Repository-level activity and health statistics
- `GET /dashboard/admin` — Event overview: verified students, pending verifications, PR merge rate

### 7. Contributor Profiles (`/users`)
- `GET /users/{id}` — Public profile (PII safe: roll numbers and private image URLs stripped)
- `GET /users/me` — Authenticated student profile
- `PATCH /users/me` — Update display name or GitHub username

### 8. Engagement Layer (`/leaderboard`, `/notifications`, `/activity`)
- `GET /leaderboard` — Live Postgres aggregated leaderboard (points: Hard=80, Medium=40, Easy=20)
- `GET /notifications` — Paginated notification stream (unread-first)
- `PATCH /notifications/{id}/read` — Mark notification read (user ownership enforced)
- `POST /notifications/read-all` — Single query batch mark-all-read
- `GET /activity` — Global event feed with N+1 safe batch actor/target enrichment

### 9. Unified Search (`/search`)
- `GET /search?q={query}` — Unified multi-entity search across Issues, PRs, Repos, Commits, and Contributors (searchable by Name, GitHub Username, and `psit_roll_no`)

---

## 🔒 Security & Critical Guarantees

1. **Atomic Claim Locking**: Explicit PostgreSQL row locking (`with_for_update()`) + partial unique constraint `uq_active_claim_per_issue`. Double-claims are mathematically impossible.
2. **HMAC-SHA256 Webhook Verification**: All GitHub webhooks verify `X-Hub-Signature-256` before writing to the database. Invalid requests receive `401 Unauthorized`.
3. **Data Privacy & PII Scrubbing**: Uploaded student ID cards, QR tokens, and portal snapshots are strictly private. The global `SensitiveDataFilter` in `app/logging_config.py` automatically scrubs storage paths, student tokens, and portal snapshots from all system logs.
4. **Strict Output Schemas**: Institutional emails, roll numbers, and storage URLs are explicitly omitted from public endpoints (`/users/{id}`, `/leaderboard`, `/search`) and OpenAPI documentation.

---

## 📋 Member Task Breakdown

### Frontend Tasks — Rudransh

#### 1. Auth Wizard
- [ ] Landing step (event intro, CTA)
- [ ] Signup step (roll number + name)
- [ ] ID upload step (crop/compress client-side, upload, live QR-scan status)
- [ ] Result step — auto-verified confirmation or pending-review fallback messaging
- [ ] GitHub OAuth "Connect your GitHub" step

#### 2. Student Dashboard
- [ ] Overview tab (claimed issues, PR summary, progress)
- [ ] My Issues tab
- [ ] My Contributions tab (timeline: claimed ➔ PR ➔ review ➔ merged)

#### 3. Issue Explorer
- [ ] Filterable list (repo, difficulty, tech, category, status)
- [ ] Detail drawer (description, requirements, Claim button)

#### 4. Repository Hub
- [ ] Overview tab (stats: issues, PRs, commits, contributors)
- [ ] Pull Requests tab (filterable, detail drawer)
- [ ] Commits tab

#### 5. Leaderboard Page
- [ ] Live leaderboard view (rank, points, contributions, active claims)

#### 6. Profile Page
- [ ] Profile view/edit toggle component (powers both own profile and public contributor views)

#### 7. Maintainer Review
- [ ] Queue tab (PRs needing review)
- [ ] History tab (reviewed PR archive)

#### 8. Admin Console
- [ ] Overview tab (event-wide metrics)
- [ ] Participants tab (verify/approve unverified students, search)
- [ ] Moderation tab (flagged/duplicate contributions)

#### 9. Shared & Utility
- [ ] Notifications dropdown panel (in top navigation)
- [ ] Command-palette global search (⌘K overlay)
- [ ] Settings modal
- [ ] Shared error boundary & empty states

#### 10. Non-Page Build Work
- [ ] Next.js project structure + routing setup
- [ ] Auth state management (role-based protected routes)
- [ ] Plain JavaScript API client layer (using exported `openapi.json`) — no TypeScript
- [ ] Reusable components: issue card, PR card, status badge, claim button, filter bar, stat card, timeline widget, ID-upload widget
- [ ] Real-time updates via TanStack Query polling
- [ ] Responsive design pass across all pages
- [ ] Loading / empty / error states for every data-driven view

---

### Backend Tasks — Abu

#### 1. Issue Management Module
- [x] Sync issues from GitHub (initial backfill via GitHub REST API)
- [x] List issues endpoint (filterable: repo, difficulty, tech, category, status)
- [x] Get single issue endpoint
- [x] Claim issue endpoint — atomic DB operation (`with_for_update()`) to prevent race conditions
- [x] Release/unclaim endpoint
- [x] Claim-limit enforcement (max active claims per student)

#### 2. GitHub Webhook Sync Engine
- [x] Webhook receiver endpoint (verifies GitHub HMAC-SHA256 signature)
- [x] Event dispatcher for: `issues`, `pull_request`, `push`, `pull_request_review`
- [x] Auto-link PRs to claimed issues via GitHub username match
- [x] `webhook_jobs` table + insert-on-receive from the webhook endpoint
- [x] Lightweight polling worker (`POST /webhooks/jobs/drain`) to drain pending/due rows
- [x] Retry/failure handling via `attempts` + `next_attempt_at` exponential backoff

#### 3. Pull Request & Commit Tracking Module
- [x] List PRs endpoint (filterable by repo/contributor/status)
- [x] Get single PR endpoint
- [x] List commits endpoint (per repo, per contributor)

#### 4. Contribution Tracking Module
- [x] Contribution status state machine (`claimed` ➔ `merged`)
- [x] Get user's full contribution timeline endpoint
- [x] Validation status handling (`valid` / `pending` / `rejected` / `duplicate` / `invalid`)

#### 5. Dashboard Aggregation Endpoints
- [x] Student dashboard summary endpoint
- [x] Maintainer review queue endpoint
- [x] Repository dashboard endpoint
- [x] Admin event overview endpoint

#### 6. Contributor Profile Module
- [x] Get public profile endpoint (PII safe)
- [x] Update own profile endpoint

#### 7. Engagement Module
- [x] Leaderboard endpoint — plain Postgres query, indexed, no separate data store
- [x] Notification creation + delivery (triggered by webhook events)
- [x] Get notifications / mark-as-read endpoints (batch + single)
- [x] Activity feed endpoint (global event stream with batch lookups)

#### 8. Search Module
- [x] Unified search endpoint across issues, PRs, contributors (with `psit_roll_no`), repos, commits

#### 9. Database Build-Out
- [x] Schema design (all 11 tables) + relationships and partial unique index
- [x] Alembic migrations
- [x] Seed data script for local development

---

### Auth, Verification & Infra Tasks — Aditya

#### 1. Auth & Verification Module
- [x] Signup endpoint (roll number + name)
- [x] ID image upload endpoint — validation (file type/size), storage in private Supabase Storage bucket, signed-URL retrieval
- [x] QR decode service (OpenCV preprocessing + pyzbar decode), with clear re-upload error states for unreadable codes
- [x] Server-side PSIT portal fetch from decoded QR token/URL
- [x] Match logic — exact roll number match + fuzzy name match, configurable threshold
- [x] Auto-verify on match; route to `pending_review` on mismatch/unreadable QR/unreachable portal
- [x] Login endpoint (JWT issuance with role claims)
- [x] GitHub OAuth flow (redirect ➔ callback ➔ link GitHub identity to user account)
- [x] Role middleware/guards (`student` / `maintainer` / `admin`)
- [x] Admin manual-approval endpoint (fallback queue — reviews uploaded ID + portal snapshot, approves/rejects)
- [x] Secure handling of the Supabase service-role key, portal fetch credentials, and all other secrets (env vars only, never exposed to frontend, never logged)
- [x] Retention/purge policy for ID images and portal snapshots post-event

#### 2. Cross-System Debugging
- [x] Stress-test the claim-locking mechanism specifically (simultaneous claim attempts under concurrency)
- [x] Verify webhook signature validation correctly rejects spoofed/unauthorized requests (401)
- [x] Verify the QR/portal verification path rejects tampered or mismatched IDs
- [x] Cross-check backend API responses against frontend expectations to catch integration bugs early
- [x] General bug triage across both frontend and backend as features land

#### 3. Infra & Deployment
- [x] Environment variables & secrets management (GitHub App credentials, webhook secret, Supabase service-role key, portal credentials, JWT secret)
- [x] Deployment setup: Vercel (frontend) + Railway/Render (backend) + Supabase (Postgres + Storage + `pg_cron`)
- [x] `pg_cron` schedule for `webhook_jobs` retry sweeps
- [x] CI/CD pipeline via GitHub Actions (auto-deploy on push to main/v2, run tests)

---

## 🏗️ Build Order & Collaboration

```
1. Database Schema (Abu) ────────── Locked first, everything depends on it
   │
2. Auth & ID/QR Verification ───── Unblocks student onboarding & protected endpoints
   │
3. Issue CRUD & Claim Locking ──── Enables Issue Explorer & Claiming UI (Rudransh)
   │
4. Webhook Sync Engine ─────────── Enables PR & Commit tabs in Repo Hub (Rudransh)
   │
5. Dashboard Aggregations ──────── Powers Student, Maintainer, & Admin dashboards (Rudransh)
   │
6. Engagement & Search Layer ───── Completes Leaderboard, Activity Feed, Notifications & ⌘K Search
   │
7. Testing & Deployment ────────── Stress testing, CI/CD checks, and cloud staging
```

---

## 📁 Directory Structure

```
HacktoberFest_Backend_v2/
├── .github/
│   └── workflows/
│       └── ci.yml                     # GitHub Actions Automated CI Pipeline
├── alembic/
│   ├── versions/
│   │   ├── 0001_initial_schema.py     # Initial Database Tables
│   │   └── 0002_v2_schema_updates.py  # ID/QR Verification & Webhook Jobs Schema
│   ├── env.py
│   └── script.py.mako
├── app/
│   ├── models/                        # 11 SQLAlchemy Database Models
│   ├── routers/                       # 10 FastAPI Routers
│   ├── schemas/                       # Pydantic v2 Request & Response Schemas
│   ├── services/                      # Modular Business Logic Layer
│   ├── config.py                      # Pydantic Settings & Environment Parsing
│   ├── db.py                          # SQLAlchemy Session Factory & Engine
│   ├── dependencies.py                # JWT Auth & Role-Based Access Guards
│   ├── logging_config.py              # Sensitive Data Log Filter
│   └── main.py                        # FastAPI Application Entrypoint
├── tests/                             # 14 Pytest Test Suites (61 Test Cases)
├── .env.example                       # Environment Variable Template
├── .gitignore                         # Strict git exclusions (protects .env)
├── alembic.ini                        # Alembic Database Configuration
├── openapi.json                       # Exported OpenAPI 3.1 Contract for Frontend
├── Procfile                           # Production Web Process Definition
├── requirements.txt                   # Pinned Python Dependencies
└── seed.py                            # Local Development Data Seeder
```

---

## 💻 Getting Started & Local Setup

### 1. Prerequisites
- Python 3.12 or newer
- PostgreSQL instance (local or Supabase project)
- Git

### 2. Clone and Setup Environment
```bash
# Clone the repository
git clone https://github.com/AbuAnsari-06/GDGOC-Hacktoberfest-Open-Source-Contribution-Management-Platform.git
cd GDGOC-Hacktoberfest-Open-Source-Contribution-Management-Platform

# Switch to the v2 branch
git checkout v2

# Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` and set your configuration:
```bash
cp .env.example .env
```
Key configuration values in `.env`:
```ini
ENV=development
DATABASE_URL=postgresql://postgres:password@localhost:5432/hacktoberfest
SECRET_KEY=generate-a-strong-random-key-at-least-32-chars
GITHUB_WEBHOOK_SECRET=your-github-webhook-secret
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### 4. Apply Database Migrations
```bash
python -m alembic upgrade head
```

### 5. Seed Test Data (Optional for Local Dev)
```bash
python seed.py
```
This initializes sample students, maintainers, admins, repositories, issues, and claims.

### 6. Start the API Server
```bash
uvicorn app.main:app --reload --port 8000
```
- Interactive Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Alternative ReDoc UI: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🧪 Running Automated Tests

The repository includes a comprehensive test suite of **61 tests across 14 modules** covering business logic, concurrency stress testing, webhook HMAC validation, PII log scrubbing, and OpenAPI contract validation:

```bash
# Run the entire test suite
pytest -v

# Run concurrency claim locking stress test
pytest tests/test_critical_stress_claim.py -v

# Run webhook signature security test
pytest tests/test_critical_webhook_security.py -v

# Run frontend contract & OpenAPI test
pytest tests/test_critical_openapi_and_frontend_contract.py -v
```

---

## 🚀 Deployment & CI/CD

### CI Pipeline
Every push and pull request to `main` and `v2` triggers the [.github/workflows/ci.yml](.github/workflows/ci.yml) workflow:
- Installs dependencies from `requirements.txt`
- Runs all 61 automated tests
- Validates Alembic migration DDL offline (`alembic upgrade head --sql`)

### Supabase pg_cron Scheduling
In Supabase SQL Editor, configure `pg_cron` to call the worker sweep endpoint every minute:
```sql
select cron.schedule(
  'drain-webhook-jobs',
  '* * * * *',
  $$
  select net.http_post(
    url := 'https://your-api-domain.com/webhooks/jobs/drain',
    headers := '{"Content-Type": "application/json"}'::jsonb
  );
  $$
);
```

### Production Hosting (Railway / Render)
The project includes a production [Procfile](Procfile):
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
Set environment variables (`DATABASE_URL`, `SECRET_KEY`, `GITHUB_WEBHOOK_SECRET`, `ALLOWED_ORIGINS`) in your cloud dashboard.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
