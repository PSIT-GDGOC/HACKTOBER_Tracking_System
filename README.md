<div align="center">

<img src="frontend/public/gdg-logo.png" alt="GDG on Campus" height="72" />

# GDGOC Hacktoberfest
### Contribution Tracking System

**A monorepo for GDGOC's Hacktoberfest event — student onboarding, atomic issue claiming, GitHub webhook sync, and a live leaderboard.**

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

- 🎓 **Student onboarding** — registration → roll number identity check → ID card upload & QR verification → GitHub OAuth
- 🔒 **Atomic issue claiming** — row-level PostgreSQL locks ensure no two students can claim the same issue simultaneously
- 🔔 **Real-time sync** — GitHub webhooks push pull request and commit events into the platform automatically with HMAC-SHA256 signature verification
- 🏆 **Live leaderboard** — weighted points calculation (`Hard: 80` · `Medium: 40` · `Easy: 20`) with dynamic standings
- 🛠 **Role-based dashboards** — distinct interfaces tailored for students, maintainers (review queue), and administrators (moderation & approvals)

> GitHub remains the source of truth for all source code. This platform is the event-management layer that orchestrates participation and gamification on top of it.

---

## 🏗 Architecture

```mermaid
flowchart LR
    subgraph Client["🖥 Browser"]
        UI["Frontend<br/>(Vite 7 + React 19)"]
    end

    subgraph API["⚙ Backend (FastAPI)"]
        AUTH["/auth"]
        ISSUES["/issues"]
        HOOKS["/webhooks"]
        DASH["/dashboard"]
        CONTR["/contributions"]
    end

    subgraph Workers["⚡ Background Workers"]
        CELERY["Celery Worker<br/>(sqla broker)"]
    end

    subgraph Data["🗄 Storage"]
        PG[("PostgreSQL (Supabase)")]
    end

    GH["🐙 GitHub"]

    UI -- "REST / JSON" --> API
    API -- "SQLAlchemy 2.0" --> PG
    GH -- "Webhooks (HMAC-SHA256)" --> HOOKS
    HOOKS -. "Async Jobs" .-> CELERY
    CELERY --> PG
    API -- "PyGithub / HTTPX" --> GH
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
        <li><b>Language:</b> Python 3.12+</li>
        <li><b>ORM:</b> <a href="https://www.sqlalchemy.org/">SQLAlchemy 2.0</a></li>
        <li><b>Validation:</b> <a href="https://docs.pydantic.dev/">Pydantic v2</a> &amp; <code>pydantic-settings</code></li>
        <li><b>Migrations:</b> <a href="https://alembic.sqlalchemy.org/">Alembic 1.20</a></li>
        <li><b>Database Driver:</b> <code>psycopg2-binary</code></li>
        <li><b>Async Tasks:</b> <a href="https://docs.celeryq.dev/">Celery 5.6</a> (PostgreSQL broker transport)</li>
        <li><b>Auth &amp; Security:</b> PyJWT (HS256) + GitHub OAuth</li>
        <li><b>Image Handling:</b> Pillow 12.3</li>
        <li><b>GitHub Integration:</b> PyGithub 2.2 &amp; HTTPX 0.28</li>
      </ul>
    </td>
  </tr>
</table>

> **Database & Deployment:** PostgreSQL (Supabase) · Uvicorn ASGI on Railway / Render · GitHub Actions CI

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
├── backend/                  # FastAPI 0.137 Python REST API server
│   ├── alembic/              # Alembic database migrations
│   │   ├── versions/         # Schema migration revisions (0001, 0002)
│   │   └── env.py            # Alembic runtime configuration
│   ├── app/                  # Application modules
│   │   ├── models/           # SQLAlchemy ORM models (11 domain tables)
│   │   ├── routers/          # FastAPI route endpoints
│   │   ├── schemas/          # Pydantic v2 request & response schemas
│   │   ├── services/         # Core business logic & database service layer
│   │   ├── tasks/            # Celery background tasks
│   │   ├── celery_app.py     # Celery instance configuration
│   │   ├── config.py         # Pydantic BaseSettings application config
│   │   ├── db.py             # Database engine & sessionmaker
│   │   ├── dependencies.py   # Auth, JWT, & database session dependencies
│   │   ├── logging_config.py # PII-sanitized logging filters
│   │   └── main.py           # FastAPI application entry point
│   ├── tests/                # Pytest test suite (14 test modules)
│   ├── .env.example          # Backend environment configuration template
│   ├── .gitignore            # Backend gitignore
│   ├── alembic.ini           # Alembic migration configuration
│   ├── built_v2.md           # Architecture build status
│   ├── openapi.json          # Exported OpenAPI 3.1 specification
│   ├── Procfile              # Process definition for deployment
│   ├── README.md             # Backend architecture documentation
│   ├── requirements.txt      # Python dependencies
│   ├── seed.py               # Database seeder script
│   └── tasks_v2.md           # Backend task tracking
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
| `POST` | `/auth/signup` | — | Register with roll number + name + email |
| `POST` | `/auth/login` | — | Authenticate with credentials, returns JWT |
| `GET` | `/auth/me` | ✅ | Fetch current authenticated user session |
| `POST` | `/auth/verify-id` | ✅ | Upload ID card for automated QR code verification |
| `GET` | `/auth/github/login` | — | Retrieve GitHub OAuth redirect URL |
| `POST` | `/auth/github/link` | ✅ | Link GitHub account to student profile |

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
      <sub>Auth, QR verification, infra, deployment</sub>
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
