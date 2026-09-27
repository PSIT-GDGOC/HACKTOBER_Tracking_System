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
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+",
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


# Include Routers — mount both at root and under /api prefix for Vercel serverless rewrites
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

for router in all_routers:
    app.include_router(router)
    app.include_router(router, prefix="/api")


