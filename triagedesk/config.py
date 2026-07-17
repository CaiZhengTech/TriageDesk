import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# Local dev reads the machine-level secrets file; CI/Railway set real env vars
# (a missing env_file is silently ignored by pydantic-settings).
_ENV_FILE = os.environ.get("TRIAGEDESK_ENV_FILE")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    database_url: str = ""
    test_database_url: str = ""
    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    cost_cap_usd: float = 0.10
    admin_token: str = ""


settings = Settings()
