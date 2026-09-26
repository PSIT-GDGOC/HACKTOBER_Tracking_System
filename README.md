<div align="center">

<img src="frontend/public/gdg-logo.png" alt="GDG on Campus" height="72" />

# GDGOC Hacktoberfest
### Contribution Tracking System

**A monorepo for GDGOC's Hacktoberfest event — student onboarding, ID card QR verification, password security, atomic issue claiming, GitHub webhook sync, and a live leaderboard.**

[![Frontend](https://img.shields.io/badge/frontend-Vite%20%2B%20React%2019-646CFF?style=for-the-badge&logo=vite&logoColor=white)](./frontend)
[![Backend](https://img.shields.io/badge/backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](./backend)
[![Database](https://img.shields.io/badge/database-PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](#)
[![License](https://img.shields.io/badge/license-MIT-yellow?style=for-the-badge)](#-license)
[![Frontend CI](https://github.com/PSIT-GDGOC/HACKTOBER_Tracking_System/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/PSIT-GDGOC/HACKTOBER_Tracking_System/actions/workflows/frontend-ci.yml)
[![Backend CI](https://github.com/PSIT-GDGOC/HACKTOBER_Tracking_System/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/PSIT-GDGOC/HACKTOBER_Tracking_System/actions/workflows/backend-ci.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](#-contributing)
[![Made with ❤️](https://img.shields.io/badge/made%20with-%E2%9D%A4-red?style=flat-square)](#-team)

[Overview](#-overview) · [Architecture](#-architecture) · [Tech Stack](#-tech-stack) · [Repository Structure](#-repository-structure) · [Quick Start](#-quick-start) · [API](#-api-reference) · [Screenshots](#-screenshots) · [Team](#-team)

</div>

---

## 📖 Overview

**GDGOC Hacktoberfest — Contribution Tracking System** is a production-grade monorepo platform that sits on top of GitHub and manages the entire Hacktoberfest sprint lifecycle for PSIT Kanpur students:

- 🎓 **Student Onboarding & Verification Pipeline**:
  - **Step 1 (Signup):** Deferred roll number uniqueness check (pending signups do not block retry or duplicate attempts; uniqueness is strictly finalized upon verified ID card matching).
  - **Step 2 (ID Verification):** Server-side computer vision pipeline (`OpenCV` + `pyzbar`) that reads the PSIT ID card QR code across 5 contrast/resolution enhancement stages.
  - **Single Card Enforcement:** Enforces physical 1-card-to-1-student uniqueness via partial unique indexing (`WHERE verified = TRUE AND qr_token IS NOT NULL`).
  - **Step 3 (Password Security):** Post-verification strong password creation (min 8 chars, mixed letters & numbers/symbols) hashed with PBKDF2-HMAC-SHA256 and 16-byte random salt.
  - **Step 4 (GitHub Identity):** Live GitHub API verification (`https://api.github.com/users/{username}`) that verifies handle existence before linking to prevent typos and spoofing.
- 🔒 **Atomic Issue Claiming** — row-level PostgreSQL locks ensure no two students can claim the same issue simultaneously.
- 🔔 **Real-Time Sync** — GitHub webhooks push pull request and commit events into the platform automatically with HMAC-SHA256 signature verification.
- 🏆 **Live Leaderboard** — weighted points calculation (`Hard: 80` · `Medium: 40` · `Easy: 20`) with dynamic standings.
- 🛠 **Role-Based Dashboards** — distinct interfaces tailored for students, maintainers (review queue), and administrators (moderation & approvals).

> GitHub remains the source of truth for all source code. This platform is the event-management layer that orchestrates participation and gamification on top of it.

---

## 🏗 Architecture

```mermaid
flowchart TB
    subgraph Client["🌐 Client"]
        Browser["Browser<br/>React 19 + Vite 7 SPA"]
    end

    subgraph Frontend["Frontend (SPA)"]
        Auth4["/auth<br/>4-Step Wizard"]
        Login["/login"]
        Dashboard["/dashboard<br/>role-switched"]
        Issues["/issues<br/>filterable explorer"]
        Leaderboard["/leaderboard"]
        Repos["/repos"]
    end

    subgraph Backend["Backend — FastAPI (Uvicorn ASGI)"]
        AuthSvc["auth_service.py<br/>PBKDF2-HMAC-SHA256 · JWT (HS256)"]
        QRSvc["qr_service.py<br/>5-stage OpenCV/pyzbar CV pipeline"]
        IssueSvc["issue_service.py<br/>SELECT ... FOR UPDATE row locks"]
        WebhookSvc["webhook_service.py<br/>HMAC-SHA256 verify"]
    end

    subgraph External["External Services"]
        GitHubAPI["GitHub API<br/>api.github.com — handle validation"]
        GitHubWebhook["GitHub Webhooks<br/>PR/commit events"]
    end

    subgraph Async["Background Processing"]
        Worker["Celery Worker<br/>PostgreSQL as broker"]
    end

    subgraph Data["Database — Supabase PostgreSQL"]
        PG[("PostgreSQL<br/>port 6543 · transaction pooler<br/>via psycopg2")]
    end

    Browser -- "REST / JSON" --> Auth4
    Browser --> Login
    Browser --> Dashboard
    Browser --> Issues
    Browser --> Leaderboard
    Browser --> Repos

    Auth4 -- "JWT bearer" --> AuthSvc
    Auth4 -- "ID card upload" --> QRSvc
    AuthSvc -- "validate handle" --> GitHubAPI
    Issues -- "claim issue" --> IssueSvc

    GitHubWebhook -- "POST /webhooks/github" --> WebhookSvc
    WebhookSvc -- "enqueue link job" --> Worker
    Worker -- "link PR → claim<br/>award points" --> PG

    AuthSvc --> PG
    QRSvc --> PG
    IssueSvc -- "SQLAlchemy 2.0" --> PG
    WebhookSvc --> PG
    Leaderboard -- "poll (useData hook)" --> PG

    classDef frontend fill:#1a1a2e,stroke:#4ecdc4,color:#fff
    classDef backend fill:#16213e,stroke:#e94560,color:#fff
    classDef external fill:#2d2d2d,stroke:#f9c74f,color:#fff
    classDef data fill:#0f3460,stroke:#48cae4,color:#fff

    class Auth4,Login,Dashboard,Issues,Leaderboard,Repos frontend
    class AuthSvc,QRSvc,IssueSvc,WebhookSvc,Worker backend
    class GitHubAPI,GitHubWebhook external
    class PG data
```

---

## 🧰 Tech Stack

<table>
  <tr>
    <td valign="top" width="50%">
      <h3>🎨 Frontend</h3>
      <ul>
        <li><b>Build Tool:</b> <a href="https://vite.dev/">Vite 7</a></li>
        <li><b>Framework:</b> <a href="https://react.dev/">React 19</a></li>
        <li><b>Language:</b> Plain JavaScript (ES6+, JSX, no TypeScript)</li>
        <li><b>Styling:</b> <a href="https://tailwindcss.com/">Tailwind CSS v4</a> (<code>@tailwindcss/vite</code>)</li>
        <li><b>Routing:</b> <a href="https://reactrouter.com/">React Router DOM v7</a></li>
        <li><b>Utilities:</b> <code>clsx</code>, <code>tailwind-merge</code></li>
        <li><b>Bundler Plugin:</b> <code>vite-plugin-singlefile</code></li>
        <li><b>API Layer:</b> Centralized typed client (<code>src/lib/api.js</code>) with in-memory mock demo adapter</li>
      </ul>
    </td>
    <td valign="top" width="50%">
      <h3>⚙️ Backend</h3>
      <ul>
        <li><b>Framework:</b> <a href="https://fastapi.tiangolo.com/">FastAPI 0.137</a></li>
        <li><b>ASGI Server:</b> <a href="https://www.uvicorn.org/">Uvicorn 0.49</a></li>
        <li><b>Language:</b> Python 3.12+ / 3.14</li>
        <li><b>ORM:</b> <a href="https://www.sqlalchemy.org/">SQLAlchemy 2.0</a></li>
        <li><b>Validation:</b> <a href="https://docs.pydantic.dev/">Pydantic v2</a> &amp; <code>pydantic-settings</code></li>
        <li><b>Migrations:</b> <a href="https://alembic.sqlalchemy.org/">Alembic 1.20</a></li>
        <li><b>Database Driver:</b> <code>psycopg2-binary</code></li>
        <li><b>Computer Vision / QR:</b> OpenCV (<code>opencv-python-headless</code>) + <code>pyzbar</code></li>
        <li><b>Password Hashing:</b> PBKDF2-HMAC-SHA256 (100,000 iterations, 16-byte salt)</li>
        <li><b>Async Tasks:</b> <a href="https://docs.celeryq.dev/">Celery 5.6</a> (PostgreSQL broker transport)</li>
        <li><b>Auth &amp; Security:</b> PyJWT (HS256) + GitHub OAuth &amp; API validation</li>
        <li><b>Image Handling:</b> Pillow 12.3</li>
        <li><b>GitHub Integration:</b> PyGithub 2.2 &amp; HTTPX 0.28</li>
      </ul>
    </td>
  </tr>
</table>

> **Database & Deployment:** PostgreSQL (Supabase pooler on port 6543) · Uvicorn ASGI on Railway / Render · GitHub Actions CI

---

## 📂 Repository Structure

```text
HACKTOBER_Tracking_System/
├── frontend/                 # Vite 7 + React 19 single-page application
│   ├── public/               # Static assets & brand icons (gdg-logo.png)
│   ├── src/                  # Application source code
│   │   ├── assets/           # Media & logo assets
│   │   ├── components/       # UI primitives, domain cards, layout shell
│   │   ├── lib/              # API client, auth context, hooks, formatting
│   │   ├── pages/            # View routes (Auth, Student, Issues, Repos, Engage, Staff, etc.)
│   │   ├── utils/            # Styling utility helpers (cn / clsx / twMerge)
│   │   ├── App.jsx           # App routes & role-based route guards
│   │   ├── index.css         # Neo-brutalist theme & Tailwind CSS v4 setup
│   │   └── main.jsx          # React DOM root entry
│   ├── index.html            # Vite HTML entry point
│   ├── package.json          # Frontend scripts & dependencies
│   ├── package-lock.json     # Dependency lockfile
│   ├── vite.config.js        # Vite & Tailwind CSS v4 configuration
│   └── README.md             # Frontend-specific documentation
├── backend/                  # FastAPI Python REST API server
│   ├── alembic/              # Alembic database migrations
│   │   ├── versions/         # Schema migration revisions
│   │   └── env.py            # Alembic runtime configuration
│   ├── app/                  # Application modules
│   │   ├── models/           # SQLAlchemy ORM models (User, Issue, Claim, PR, Commit, etc.)
│   │   ├── routers/          # FastAPI route endpoints (auth, issues, webhooks, dashboards, etc.)
│   │   ├── schemas/          # Pydantic v2 request & response schemas
│   │   ├── services/         # QR decoding, PSIT portal service, Auth & GitHub linking services
│   │   ├── tasks/            # Celery background tasks
│   │   ├── celery_app.py     # Celery instance configuration
│   │   ├── config.py         # Pydantic BaseSettings application config
│   │   ├── db.py             # Database engine & sessionmaker (Supabase PostgreSQL)
│   │   ├── dependencies.py   # Auth, JWT, & database session dependencies
│   │   ├── logging_config.py # PII-sanitized logging filters
│   │   └── main.py           # FastAPI application entry point
│   ├── tests/                # Pytest test suite (14 test modules, 109 test cases)
│   ├── .env.example          # Backend environment configuration template
│   ├── openapi.json          # Exported OpenAPI 3.1 specification
│   ├── requirements.txt      # Python dependencies
│   ├── seed.py               # Database seeder script
│   └── README.md             # Backend architecture documentation
├── .gitignore                # Root monorepo exclusion rules
└── README.md                 # Unified project documentation
```

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| **Node.js** | `18+` | Frontend package execution and runtime |
| **Python** | `3.12+` | Backend API and worker runtime |
| **PostgreSQL** | `14+` (or Supabase) | Primary relational database |
| **Git** | latest | Version control |

---

### 🎨 Frontend Setup

```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
```

The application will be live at **`http://localhost:5173`**.

<details>
<summary><b>Frontend Configuration Notes</b></summary>

- The frontend network layer lives in `frontend/src/lib/api.js`.
- If running without a backend, the frontend seamlessly defaults to its built-in seeded demo state so the entire UI can be explored locally.
- To build for production: `npm run build`
- To preview the production bundle: `npm run preview`

</details>

---

### ⚙️ Backend Setup

```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env with your DATABASE_URL, SECRET_KEY, and GitHub credentials

# 5. Run database migrations
python -m alembic upgrade head

# 6. Seed initial sample data (optional)
python seed.py

# 7. Start the FastAPI development server
uvicorn app.main:app --reload --port 8000
```

<details>
<summary><b>Environment Variables (<code>backend/.env.example</code>)</b></summary>

```ini
# ============================================================
# GDGOC Hacktoberfest Backend — Environment Variables
# Copy this file to .env for local dev, OR set these directly
# as environment variables in Railway / Render dashboard.
# ============================================================

# Application
APP_NAME=GDGOC Hacktoberfest Backend
ENV=production
DEBUG=False

# ---- DATABASE (Supabase) ------------------------------------
# Copy the "Connection string" from Supabase > Project Settings > Database
# Use the "URI" format. Both postgres:// and postgresql:// are supported.
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres

# ---- CELERY (uses same Supabase DB as broker) ---------------
# sqla+postgresql:// prefix tells Celery to use SQLAlchemy transport (no Redis needed)
CELERY_BROKER_URL=sqla+postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
CELERY_RESULT_BACKEND=db+postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres

# ---- SECURITY -----------------------------------------------
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=replace_with_64_char_hex_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ---- GITHUB -------------------------------------------------
# Create a GitHub Personal Access Token with repo:read scope
GITHUB_ACCESS_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
# Set this in your GitHub repo webhook settings > Secret
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
# Full GitHub repo URLs (used for issue sync)
GITHUB_WEB_REPO_URL=https://github.com/YOUR_ORG/web-repo
GITHUB_ANDROID_REPO_URL=https://github.com/YOUR_ORG/android-repo

# ---- PSIT ERP (Aditya's integration) -----------------------
ERP_API_URL=
ERP_API_KEY=

# ---- CORS ---------------------------------------------------
# Comma-separated list of allowed frontend origins.
# Use * only during development. Set real URLs in production.
ALLOWED_ORIGINS=https://your-frontend.vercel.app,https://your-custom-domain.com

# ---- EVENT RULES --------------------------------------------
MAX_ACTIVE_CLAIMS_PER_STUDENT=2
```

</details>

**Backend endpoints:**
- **API Base:** [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 🔌 API Reference

### Auth & Verification (`/auth`)

| Method | Endpoint | Auth | Description |
|---|---|:---:|---|
| `POST` | `/auth/signup` | — | Register with roll number + name + email (deferred uniqueness check) |
| `POST` | `/auth/login` | — | Authenticate with roll number / email + password, returns JWT |
| `POST` | `/auth/set-password` | ✅ | Set strong account password (min 8 chars, alphanumeric) |
| `GET` | `/auth/me` | ✅ | Fetch current authenticated user session |
| `POST` | `/auth/verify-id` | ✅ | Upload ID card for OpenCV QR decode + 1-card uniqueness check |
| `GET` | `/auth/pending-verifications` | ✅ (Admin) | Queue for fallback manual reviews |
| `POST` | `/auth/verify-manual/{id}` | ✅ (Admin) | Manual approve / reject decision |
| `GET` | `/auth/github/login` | — | Retrieve GitHub OAuth redirect URL |
| `POST` | `/auth/github/callback` | ✅ | GitHub OAuth callback: exchange code & link identity |
| `POST` | `/auth/github/link` | ✅ | Manually link GitHub username (validated against GitHub API) |

### Issues & Claims (`/issues`)

| Method | Endpoint | Auth | Description |
|---|---|:---:|---|
| `GET` | `/issues` | ✅ | Filterable list (repo, difficulty, tech, status) |
| `GET` | `/issues/{issue_id}` | ✅ | Issue detail and claim state |
| `POST` | `/issues/{issue_id}/claim` | ✅ | Atomic claim with PostgreSQL row lock |
| `POST` | `/issues/{issue_id}/unclaim` | ✅ | Release an active claim |
| `POST` | `/issues/sync` | ✅ | Trigger on-demand sync from GitHub repositories |

### Pull Requests & Commits (`/pull-requests`, `/commits`)

| Method | Endpoint | Auth | Description |
|---|---|:---:|---|
| `GET` | `/pull-requests` | ✅ | List pull requests with status and contributor filters |
| `GET` | `/pull-requests/{pr_id}` | ✅ | Individual pull request details |
| `GET` | `/commits` | ✅ | Feed of tracked commits across event repositories |

### Contributions & Moderation (`/contributions`)

| Method | Endpoint | Auth | Description |
|---|---|:---:|---|
| `GET` | `/contributions` | ✅ | List contributions with moderation status filters |
| `GET` | `/contributions/my` | ✅ | Current user's contribution timeline |
| `GET` | `/contributions/{user_id}` | ✅ | Public contributor timeline for a specific student |
| `PATCH` | `/contributions/{id}/validation` | ✅ | Maintainer review: mark valid / duplicate / rejected |
| `PATCH` | `/contributions/{id}/status` | ✅ | Transition contribution state |

### Dashboards & Engagement

| Method | Endpoint | Auth | Description |
|---|---|:---:|---|
| `GET` | `/dashboard/student` | ✅ | Student metrics (active claims, PR summary, progress) |
| `GET` | `/dashboard/maintainer` | ✅ | Maintainer review queue and pending validations |
| `GET` | `/dashboard/repository/{id}` | ✅ | Repository health, stars, open issues, merge rates |
| `GET` | `/dashboard/admin` | ✅ | Overall event metrics and verification backlog |
| `GET` | `/leaderboard` | — | Ranked leaderboard sorted by weighted points |
| `GET` | `/notifications` | ✅ | User notification feed and review alerts |
| `GET` | `/activity` | — | Global activity stream across all repositories |
| `GET` | `/search?q=` | ✅ | Unified search across issues, users, and repositories |

### Webhooks (`/webhooks`)

| Method | Endpoint | Auth | Description |
|---|---|:---:|---|
| `POST` | `/webhooks/github` | HMAC | Ingests verified GitHub webhook events |
| `POST` | `/webhooks/jobs/drain` | ✅ | Drain due webhook jobs (pg_cron sweep) |
| `GET` | `/webhooks/jobs` | ✅ | List queued and completed webhook jobs |

*Full interactive documentation and testing is available at `/docs` (Swagger UI) when the backend is running.*

---

## 🎨 Screenshots

<!-- Replace the placeholder paths once screenshots exist. -->
<table>
  <tr>
    <td><img src="docs/screenshots/auth-wizard.png" alt="Auth Wizard" /></td>
    <td><img src="docs/screenshots/dashboard.png" alt="Student Dashboard" /></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/issues.png" alt="Issue Explorer" /></td>
    <td><img src="docs/screenshots/leaderboard.png" alt="Leaderboard" /></td>
  </tr>
</table>

---

## 👥 Team

<table>
  <tr>
    <td align="center" width="33%">
      <b>Rudransh</b><br/>
      <sub>Frontend — every page, component, API client layer</sub>
    </td>
    <td align="center" width="33%">
      <b>Abu</b><br/>
      <sub>Backend — issues, webhooks, dashboards, schemas</sub>
    </td>
    <td align="center" width="33%">
      <b>Aditya</b><br/>
      <sub>Auth, QR CV verification, password security, infra</sub>
    </td>
  </tr>
</table>

---

## 🤝 Contributing

We welcome contributions from the GDG on Campus PSIT community! Here's how to contribute:

1. **Fork** the repository
2. **Branch**: `git checkout -b feat/your-feature-name`
3. **Commit**: follow [Conventional Commits](https://www.conventionalcommits.org/) format (`feat: ...`, `fix: ...`, `docs: ...`)
4. **Push**: `git push origin feat/your-feature-name`
5. Open a **Pull Request**

### Development Guidelines

- 🚫 **Plain JavaScript only** in the frontend — no TypeScript
- 🧪 **Run tests before pushing**: `cd backend && pytest`
- 🏗 **Build passes locally**: `cd frontend && npm run build`
- 🔐 **Never commit `.env` or secret keys**
- 🎨 **Match the existing Neo-brutalist design system**

---

## 📜 License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

<div align="center">
  <br/>
  <a href="#gdgoc-hacktoberfest">⬆ Back to Top</a>
  <br/><br/>
  <b>Made with ❤️ by GDG on Campus · PSIT Kanpur</b>
</div>
