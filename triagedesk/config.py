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
    cors_origins: str = ""
    log_json: bool = False
    demo_daily_cap_usd: float = 1.00
    demo_rate_limit_per_hour: int = 5
    # Untrusted ticket intake (POST /api/tickets). A SEPARATE secret from
    # admin_token on purpose: the intake token goes to whatever forwards
    # tickets in (mail gateway, helpdesk webhook), the admin token goes to
    # the human reviewer. Different actors, independent rotation, and a
    # leaked intake token cannot approve a reply. Unset => endpoint 503s.
    intake_token: str = ""
    intake_rate_limit_per_hour: int = 20


settings = Settings()
