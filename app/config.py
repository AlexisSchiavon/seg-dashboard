from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SECRET_KEY: str  # required — app fails to start if missing
    DATABASE_URL: str = "sqlite:///./seg.db"
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    COOKIE_SECURE: bool = True

    # Placeholders for M2-M5 (per ARCHITECTURE.md M1 build-order guidance — define now, unused until later)
    PIPEDRIVE_API_TOKEN: str = ""
    PIPEDRIVE_DOMAIN: str = ""
    PIPEDRIVE_PIPELINE_ID: int | None = None
    PIPEDRIVE_STAGE_CONTRATO_ID: int | None = None
    GOOGLE_SHEETS_ID: str = ""
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    TRELLO_API_KEY: str = ""
    TRELLO_TOKEN: str = ""
    TRELLO_BOARD_IDS: str = ""
    TRELLO_ORG_ID: str = ""
    TRELLO_WORKSPACE_NAME: str = ""
    ANTHROPIC_API_KEY: str = ""


settings = Settings()
