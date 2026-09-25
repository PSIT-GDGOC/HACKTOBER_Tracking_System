from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "GDGOC Hacktoberfest Backend"
    ENV: str = "development"
    DEBUG: bool = False  # Default False; only True in local dev via .env

    # Database — supports Supabase's postgres:// and standard postgresql:// URLs
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/hacktoberfest_db"

    # Security & Auth
    SECRET_KEY: str = "temporary_secret_key_change_in_production_32bytes_min"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # GitHub Integration
    GITHUB_ACCESS_TOKEN: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    GITHUB_WEB_REPO_URL: str = ""
    GITHUB_ANDROID_REPO_URL: str = ""

    # PSIT ERP Integration
    ERP_API_URL: str = ""
    ERP_API_KEY: str = ""

    # Celery
    CELERY_BROKER_URL: str = "sqla+postgresql://postgres:postgres@localhost:5432/hacktoberfest_db"
    CELERY_RESULT_BACKEND: str = "db+postgresql://postgres:postgres@localhost:5432/hacktoberfest_db"

    # CORS — comma-separated list of allowed origins for production
    ALLOWED_ORIGINS: str = "*"

    # Event Rules
    MAX_ACTIVE_CLAIMS_PER_STUDENT: int = 2

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
        """Parse ALLOWED_ORIGINS env var into a list for CORSMiddleware."""
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()
