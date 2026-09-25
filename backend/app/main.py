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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint to verify backend service status."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.ENV
    }


# Include Routers
from app.routers import auth, issues, webhooks, pull_requests, commits, contributions, dashboard, users, engagement, search
app.include_router(auth.router)
app.include_router(issues.router)
app.include_router(webhooks.router)
app.include_router(pull_requests.router)
app.include_router(commits.router)
app.include_router(contributions.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(engagement.router)
app.include_router(search.router)

