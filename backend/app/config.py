from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "GDGOC Hacktoberfest Backend"
    ENV: str = "development"
    DEBUG: bool = False  # Default False; only True in local dev via .env

    # Database — supports Supabase's postgres:// and standard postgresql:// URLs
    DATABASE_URL: str = "postgresql://postgres.mxxejrteunvdmttgkdoq:i51ZNBGa5aOVDKYP@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"

    # Security & Auth
    SECRET_KEY: str = "9f83b2a8d4e5c6b7a8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # GitHub Integration
    GITHUB_ACCESS_TOKEN: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    GITHUB_ORG: str = "PSIT-GDGOC"  # GitHub org to auto-sync repos from
    GITHUB_WEB_REPO_URL: str = "https://github.com/PSIT-GDGOC/hacktoberfest-web"
    GITHUB_ANDROID_REPO_URL: str = "https://github.com/gdgoc-psit/hacktoberfest-android"
    # GitHub OAuth (student GitHub account linking)
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_OAUTH_REDIRECT_URI: str = "https://hacktober-tracking-system-ocai.vercel.app/#/auth/callback"

    # Email / SMTP Settings (for password reset OTPs)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@gdgoc-psit.ac.in"

    # PSIT Portal Integration
    PSIT_PORTAL_BASE_URL: str = "https://www.psit.ac.in/op"
    ERP_API_URL: str = ""
    ERP_API_KEY: str = ""

    # Celery
    CELERY_BROKER_URL: str = "sqla+postgresql://postgres:postgres@localhost:5432/hacktoberfest_db"
    CELERY_RESULT_BACKEND: str = "db+postgresql://postgres:postgres@localhost:5432/hacktoberfest_db"

    # CORS — comma-separated list of allowed origins for production
    ALLOWED_ORIGINS: str = "*"

    # Event Rules
    MAX_ACTIVE_CLAIMS_PER_STUDENT: int = 2

    # Verification Media Storage (Supabase Storage / Local Uploads fallback)
    STORAGE_DIR: str = "uploads"
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "id-cards"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def db_url(self) -> str:
        """Return SQLAlchemy-compatible URL. Supabase provides 'postgres://' which
        SQLAlchemy 2.x requires to be 'postgresql://'."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def celery_broker(self) -> str:
        """Supabase-compatible Celery broker URL."""
        url = self.CELERY_BROKER_URL
        if url.startswith("sqla+postgres://"):
            url = url.replace("sqla+postgres://", "sqla+postgresql://", 1)
        return url

    @property
    def celery_backend(self) -> str:
        """Supabase-compatible Celery result backend URL."""
        url = self.CELERY_RESULT_BACKEND
        if url.startswith("db+postgres://"):
            url = url.replace("db+postgres://", "db+postgresql://", 1)
        return url

    @property
    def allowed_origins_list(self) -> list:
        """Parse ALLOWED_ORIGINS env var into a list for CORSMiddleware.
        Browsers reject wildcard '*' when allow_credentials=True. If '*' or empty,
        return an empty list so allow_origin_regex dynamically matches localhost, Vercel, and Render."""
        if not self.ALLOWED_ORIGINS or self.ALLOWED_ORIGINS.strip() == "*":
            return []
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip() and origin.strip() != "*"]


settings = Settings()
