# GDGOC Hacktoberfest — Contribution Tracking System

> A centralized monorepo platform for PSIT students to discover, claim, track, and manage open-source contributions across GDGOC's official Hacktoberfest repositories.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
  - [Frontend](#frontend)
  - [Backend](#backend)
  - [Database & Async Worker](#database--async-worker)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Frontend Setup](#frontend-setup)
  - [Backend Setup](#backend-setup)
- [Environment Variables](#environment-variables)
  - [Frontend](#frontend-configuration)
  - [Backend (.env.example)](#backend-envexample)
- [API Reference](#api-reference)
- [Team](#team)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The **GDGOC Hacktoberfest Contribution Tracking System** provides a complete event-management solution for students, maintainers, and campus administrators during Hacktoberfest sprints at PSIT Kanpur. GitHub remains the authoritative source of truth for code, commits, and pull requests — this platform serves as the management and gamification layer on top of it.

Key capabilities:
- **Campus Verification & Onboarding**: Multi-step student registration, roll number identity checks, and GitHub account linking.
- **Issue Exploration & Atomic Claim Locking**: Filter issues by repository, tech stack, and difficulty; claims use atomic database locking to prevent duplicate assignments.
- **Webhook Ingestion**: Ingests GitHub push, pull request, and review events to keep contribution records synchronized in near real time.
- **Dynamic Leaderboard & Scoring**: Weighted scoring based on issue complexity (`Hard=80`, `Medium=40`, `Easy=20`) with live rank calculations.
- **Role-Based Workspaces**: Tailored dashboards for students (claims & timeline), maintainers (PR review queue), and administrators (moderation & verification approvals).

---

## Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Vite + React)                         │
│                                                                        │
│   Landing / Auth   │   Student Dashboard   │   Issue Explorer          │
│   Repository Hub   │   Leaderboard         │   Maintainer / Admin      │
│                                                                        │
│   └───────────────────────────────────┬────────────────────────────┘   │
│                                       │ fetch / REST JSON              │
└───────────────────────────────────────┼────────────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI + ASGI)                        │
│                                                                        │
│   Routers:                                                             │
│   • /auth              • /issues           • /pull-requests            │
│   • /commits           • /contributions    • /dashboard                │
│   • /users             • /engagement       • /webhooks                 │
│                                                                        │
│   Core Layers:                                                         │
│   • Pydantic v2 Schema Validation                                      │
│   • Service Layer (Claim locking, validation, scoring algorithms)      │
│   • Celery Worker Tasks (sqla broker)                                  │
│   • SQLAlchemy 2.0 ORM Engine                                          │
└───────────────────────────────────────┬────────────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         PostgreSQL (Supabase)                          │
│                                                                        │
│   Tables:                                                              │
│   • users              • repositories      • issues                    │
│   • claims             • pull_requests     • commits                   │
│   • contributions      • reviews           • notifications             │
│   • activity_feed      • webhook_jobs                                  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Frontend

Verified directly from [`frontend/package.json`](frontend/package.json):

| Category | Technology | Version | Purpose |
|---|---|---|---|
| **Build Tool & Dev Server** | [Vite](https://vite.dev/) | `^7.3.2` | Lightning-fast ESM dev server and production bundler |
| **Framework** | [React](https://react.dev/) | `^19.2.6` | Component-driven UI development |
| **Routing** | [React Router DOM](https://reactrouter.com/) | `^7.18.4` | Client-side routing with role-protected layouts |
| **Styling** | [Tailwind CSS](https://tailwindcss.com/) | `^4.1.17` | Utility-first CSS via `@tailwindcss/vite` |
| **Style Utilities** | `clsx` & `tailwind-merge` | `2.1.1` / `3.4.0` | Safe conditional class merging |
| **Vite Plugins** | `@vitejs/plugin-react` | `^5.1.1` | React Fast Refresh support |
| **Single-File Bundling** | `vite-plugin-singlefile` | `^2.3.0` | Standalone deployable single-bundle support |

### Backend

Verified directly from [`backend/requirements.txt`](backend/requirements.txt):

| Category | Technology | Version | Purpose |
|---|---|---|---|
| **Web Framework** | [FastAPI](https://fastapi.tiangolo.com/) | `0.137.1` | Modern, high-performance async REST API framework |
| **ASGI Server** | [Uvicorn](https://www.uvicorn.org/) | `0.49.0` | Standard production ASGI server |
| **Data Validation** | [Pydantic](https://docs.pydantic.dev/) | `2.13.4` | Data parsing, typing, and schema enforcement |
| **Settings Management** | `pydantic-settings` | `2.15.0` | Environment configuration management |
| **ORM** | [SQLAlchemy](https://www.sqlalchemy.org/) | `2.0.54` | SQL toolkit and Object Relational Mapper |
| **Database Migrations** | [Alembic](https://alembic.sqlalchemy.org/) | `1.20.0` | Database schema migrations |
| **PostgreSQL Driver** | `psycopg2-binary` | `2.9.13` | PostgreSQL adapter for Python |
| **Background Jobs** | [Celery](https://docs.celeryq.dev/) | `5.6.3` | Distributed task execution |
| **GitHub API** | `PyGithub` | `2.2.0` | GitHub REST API client |
| **HTTP Client** | `httpx` | `0.28.1` | Async HTTP requests |
| **Authentication** | `PyJWT` | `2.15.0` | JSON Web Token encoding and verification |
| **Image Processing** | `Pillow` | `12.3.0` | Student ID verification and image handling |
| **Environment Management**| `python-dotenv` | `1.2.2` | Reads `.env` files for local dev |

### Database & Async Worker

- **Database Engine**: PostgreSQL 14+ (hosted via Supabase)
- **Celery Broker & Result Backend**: SQLAlchemy / PostgreSQL transport (`sqla+postgresql://`), eliminating the need for an external Redis server in lightweight deployments.

---

## Repository Structure

```text
HACKTOBER_Tracking_System/
├── frontend/                 # React 19 + Vite 7 SPA
│   ├── public/               # Static assets & brand icons
│   ├── src/
│   │   ├── assets/           # Media & graphics
│   │   ├── components/       # UI primitives, domain cards, layout shell
│   │   ├── lib/              # API client, auth context, hooks, formatting
│   │   ├── pages/            # View routes (Auth, Student, Issues, Repos, Engage, Staff, etc.)
│   │   ├── utils/            # Styling utility helpers (clsx, twMerge)
│   │   ├── App.jsx           # App routes & role-based route guards
│   │   ├── index.css         # Neo-brutalist theme & Tailwind CSS v4 setup
│   │   └── main.jsx          # React DOM root entry
│   ├── index.html            # HTML entry point
│   ├── package.json          # Frontend scripts & dependencies
│   ├── package-lock.json
│   ├── vite.config.js        # Vite & Tailwind CSS v4 configuration
│   └── README.md             # Frontend-specific documentation
├── backend/                  # FastAPI 0.137 Python Backend
│   ├── alembic/              # Alembic database migrations
│   │   ├── versions/         # Schema migration revisions
│   │   └── env.py
│   ├── app/
│   │   ├── models/           # SQLAlchemy ORM models (11 domain tables)
│   │   ├── routers/          # FastAPI APIRouter endpoints
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
│   ├── .gitignore
│   ├── alembic.ini           # Alembic migration configuration
│   ├── built_v2.md           # Architecture build status
│   ├── openapi.json          # Exported OpenAPI 3.1 specification
│   ├── Procfile              # Process definition for deployment
│   ├── README.md             # Backend architecture documentation
│   ├── requirements.txt      # Python dependencies
│   ├── seed.py               # Database seeder script
│   └── tasks_v2.md           # Backend task tracking
├── .gitignore                # Root monorepo exclusion rules
└── README.md                 # Unified repository documentation
```

---

## Getting Started

### Prerequisites

- **Node.js**: 18+ and npm
- **Python**: 3.12+
- **PostgreSQL**: 14+ instance or Supabase project
- **Git**

---

### Frontend Setup

The frontend uses Vite 7 with npm scripts defined in `frontend/package.json`:

```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
```

The application will be available at [http://localhost:5173](http://localhost:5173).

Other available frontend commands:
```bash
# Build production bundle
npm run build

# Preview production build locally
npm run preview
```

---

### Backend Setup

```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate the virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, SECRET_KEY, and GitHub credentials

# 6. Apply database migrations
python -m alembic upgrade head

# 7. Seed sample data (optional)
python seed.py

# 8. Start the FastAPI development server
uvicorn app.main:app --reload --port 8000
```

Once running:
- **API Base**: [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative Docs (ReDoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## Environment Variables

### Frontend Configuration

The frontend network client in `frontend/src/lib/api.js` connects to the FastAPI backend using the API base URL. When run without a configured backend endpoint, the frontend uses its built-in seeded demo state adapter for local development.

### Backend (`.env.example`)

The backend requires configuration according to [`backend/.env.example`](backend/.env.example):

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

---

## API Reference

The backend exposes the following endpoints grouped by domain routers in `backend/app/routers/`:

### Auth & Verification (`/auth`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/signup` | Register as a new student |
| `POST` | `/auth/login` | Authenticate with credentials, returns JWT bearer token |
| `GET` | `/auth/me` | Fetch currently authenticated user session |
| `POST` | `/auth/verify-id` | Submit student ID card & QR token for automated verification |
| `GET` | `/auth/github/login` | Retrieve GitHub OAuth login URL |
| `POST` | `/auth/github/link` | Link authenticated GitHub account to user profile |

### Issues & Claims (`/issues`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/issues` | List open issues with repository, difficulty, and label filters |
| `GET` | `/issues/{issue_id}` | Fetch individual issue details |
| `POST` | `/issues/{issue_id}/claim` | Atomically claim an issue (prevents double claims) |
| `POST` | `/issues/{issue_id}/unclaim` | Release an active issue claim |
| `POST` | `/issues/sync` | Trigger an on-demand sync of issues from GitHub |

### Pull Requests & Commits (`/pull-requests`, `/commits`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/pull-requests` | List pull requests with status and contributor filters |
| `GET` | `/pull-requests/{pr_id}` | Get individual pull request details |
| `GET` | `/commits` | List commits across tracked repositories |

### Contributions & Moderation (`/contributions`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/contributions` | List contributions with moderation and status filters |
| `GET` | `/contributions/my` | Retrieve complete contribution timeline for logged-in user |
| `GET` | `/contributions/{user_id}` | Retrieve public contribution timeline for a student |
| `PATCH` | `/contributions/{id}/validation` | Review and mark contribution status (valid / duplicate / rejected) |
| `PATCH` | `/contributions/{id}/status` | Transition contribution progression state |

### Dashboards (`/dashboard`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/dashboard/student` | Active claims, progress statistics, and recent activity |
| `GET` | `/dashboard/maintainer` | PR review queue and pending validation tasks |
| `GET` | `/dashboard/repository/{id}` | Repository-specific health and contribution metrics |
| `GET` | `/dashboard/admin` | Overall event metrics, verifications, and merge rates |

### Engagement & Search

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/leaderboard` | Ranked student leaderboard sorted by weighted points |
| `GET` | `/notifications` | User notifications and review updates |
| `GET` | `/activity` | Global real-time activity feed |
| `GET` | `/search?q=` | Full-text search across issues, contributors, and repositories |

### Webhooks (`/webhooks`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/webhooks/github` | Ingests verified GitHub webhook events (HMAC-SHA256 signature checked) |
| `POST` | `/webhooks/jobs/drain` | Triggers background processing sweep for queued webhook jobs |
| `GET` | `/webhooks/jobs` | Inspect status of queued and completed webhook jobs |

### System Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Check backend service and configuration status |

---

## Team

| Member | Focus Area |
|---|---|
| **Rudransh** | Frontend Architecture, Vite/React SPA, Neo-brutalist Design System, UI Components |
| **Abu** | Backend Core, Issue Management, GitHub Webhook Engine, Dashboards |
| **Aditya** | Auth & Verification Engine, ID/QR Validation, GitHub OAuth, Infrastructure |

---

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is open-source under the [MIT License](LICENSE).

<p align="center">
  Built with ❤️ by GDG on Campus, PSIT Kanpur
</p>
