import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.logging_config import configure_logging

# Apply sensitive-data log filter globally before anything else can log
configure_logging()

logger = logging.getLogger(__name__)

# ─── Org Repo Sync Background Task ────────────────────────────────────────────
ORG_SYNC_INTERVAL_SECONDS = 300  # re-sync every 5 minutes


async def _org_sync_loop():
    """Background loop: syncs PSIT-GDGOC org repos every 5 minutes."""
    from app.db import SessionLocal
    from app.services.org_sync_service import sync_org_repos

    await asyncio.sleep(10)  # small delay after startup so DB is ready
    while True:
        try:
            db = SessionLocal()
            result = await sync_org_repos(db)
            logger.info("OrgSync background: %s", result)
        except Exception as e:
            logger.error("OrgSync background error: %s", e)
        finally:
            try:
                db.close()
            except Exception:
                pass
        await asyncio.sleep(ORG_SYNC_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: run startup org sync then launch periodic background sync."""
    from app.db import SessionLocal
    from app.services.org_sync_service import sync_org_repos

    # ── Startup: self-heal DB schema (BIGINT columns, delivery_id) ────────────
    from app.db import engine
    from sqlalchemy import text
    try:
        if engine.dialect.name == "postgresql":
            logger.info("Startup DB check: ensuring BigInteger columns on PostgreSQL...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE issues ALTER COLUMN github_issue_id TYPE BIGINT;"))
                conn.execute(text("ALTER TABLE pull_requests ALTER COLUMN github_pr_id TYPE BIGINT;"))
                conn.execute(text("ALTER TABLE webhook_jobs ADD COLUMN IF NOT EXISTS delivery_id VARCHAR(100);"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_webhook_jobs_delivery_id ON webhook_jobs (delivery_id);"))
                conn.commit()
                logger.info("Startup DB check: Schema auto-migrations applied successfully.")
    except Exception as e:
        logger.warning("Startup DB check (non-fatal): %s", e)

    # ── Startup: immediate one-shot sync ──────────────────────────────────────
    logger.info("Startup: Running initial PSIT-GDGOC org repo sync...")
    try:
        db = SessionLocal()
        result = await sync_org_repos(db)
        logger.info("Startup OrgSync complete: %s", result)
    except Exception as e:
        logger.error("Startup OrgSync failed (non-fatal): %s", e)
    finally:
        try:
            db.close()
        except Exception:
            pass

    # ── Launch periodic background sync ───────────────────────────────────────
    sync_task = asyncio.create_task(_org_sync_loop())
    logger.info("OrgSync background task started (interval: %ds)", ORG_SYNC_INTERVAL_SECONDS)

    yield  # app is running

    # ── Shutdown: cancel background task ──────────────────────────────────────
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    logger.info("OrgSync background task stopped.")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Event-management API for GDGOC Hacktoberfest open-source contribution tracking.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration — set ALLOWED_ORIGINS env var in production (comma-separated URLs)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://.*\.vercel\.app$|^https://.*\.onrender\.com$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["System"])
@app.get("/api", tags=["System"])
def root():
    """Root endpoint for status check."""
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "environment": settings.ENV,
        "docs": "/docs",
        "api_docs": "/api/docs",
        "health": "/api/health",
    }


@app.get("/health", tags=["System"])
@app.get("/api/health", tags=["System"])
def health_check():
    """Health check endpoint to verify backend service status."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.ENV,
    }


@app.get("/test-db", tags=["System"])
@app.get("/api/test-db", tags=["System"])
def test_db():
    """Diagnostic endpoint to inspect DB connection status on serverless."""
    try:
        from app.db import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        res = db.execute(text("SELECT 1")).scalar()
        db.close()
        return {"db": "connected", "result": res}
    except Exception as e:
        import traceback
        return {"db": "error", "error": str(e), "traceback": traceback.format_exc()}


@app.get("/debug/sync-issues", tags=["System"])
def debug_sync_issues():
    """Temporary debug: run issues sync and return real error if 500."""
    import traceback
    try:
        from app.db import SessionLocal
        from app.services.issue_service import sync_issues_from_github
        db = SessionLocal()
        result = sync_issues_from_github(db=db)
        db.close()
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


@app.get("/debug/db-schema", tags=["System"])
def debug_db_schema():
    """Temporary debug: inspect actual columns in the issues table on live DB."""
    import traceback
    try:
        from app.db import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        rows = db.execute(text(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name='issues' ORDER BY ordinal_position"
        )).fetchall()
        db.close()
        return {"issues_columns": [dict(r._mapping) for r in rows]}
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}


# Include Routers — dual-mount on root and /api for Vercel reverse proxy and direct backend compatibility
from app.routers import (
    admin,
    auth,
    issues,
    webhooks,
    pull_requests,
    commits,
    contributions,
    dashboard,
    users,
    engagement,
    search,
)

all_routers = [
    admin.router,
    auth.router,
    issues.router,
    webhooks.router,
    pull_requests.router,
    commits.router,
    contributions.router,
    dashboard.router,
    users.router,
    engagement.router,
    search.router,
]

# 1. Mount directly on root (e.g. /auth, /issues, /dashboard)
for r in all_routers:
    app.include_router(r)

# 2. Mount under /api prefix for reverse proxy setups (e.g. /api/auth, /api/issues)
for r in all_routers:
    app.include_router(r, prefix="/api")
