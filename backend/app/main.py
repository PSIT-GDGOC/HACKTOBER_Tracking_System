from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.logging_config import configure_logging

# Apply sensitive-data log filter globally before anything else can log
configure_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Event-management API for GDGOC Hacktoberfest open-source contribution tracking.",
    docs_url="/docs",
    redoc_url="/redoc"
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


# Include Routers — dual-mount on root and /api for Vercel reverse proxy and direct backend compatibility
from fastapi import APIRouter
from app.routers import auth, issues, webhooks, pull_requests, commits, contributions, dashboard, users, engagement, search

all_routers = [
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
api_router = APIRouter(prefix="/api")
api_router.add_api_route("/health", health_check, methods=["GET"], tags=["System"], include_in_schema=False)
for r in all_routers:
    api_router.include_router(r)
app.include_router(api_router)

