"""Application settings.

Only the Livespace integration is modeled here today — every other env var
in the project (DATABASE_URL, FRONTEND_ORIGIN, SQL_ECHO) stays on the
existing ad hoc os.getenv() pattern in app/core/database.py / app/api/main.py.
This is the first feature whose config is a cohesive, validated group rather
than one or two independent flags, which is what BaseSettings is for.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # All three optional: any missing => the integration is disabled rather
    # than crashing FastAPI at startup. See Settings.livespace_enabled.
    livespace_subdomain: str | None = None
    livespace_api_key: str | None = None
    livespace_api_secret: str | None = None

    livespace_timeout_seconds: float = 10.0
    livespace_max_concurrency: int = 3
    livespace_cache_ttl_minutes: int = 60
    livespace_sweep_interval_minutes: int = 240

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def livespace_base_url(self) -> str | None:
        if not self.livespace_subdomain:
            return None
        # Tolerate either "proidea" or the full "proidea.livespace.io" —
        # an easy value to paste in either form from the Livespace admin UI.
        subdomain = self.livespace_subdomain.removesuffix(".livespace.io")
        return f"https://{subdomain}.livespace.io/api/public/json"

    @property
    def livespace_enabled(self) -> bool:
        return bool(self.livespace_subdomain and self.livespace_api_key and self.livespace_api_secret)


settings = Settings()
