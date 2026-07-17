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

    # --- Trello auto-create (Fase 10 / Módulo 4) -------------------------
    # Master kill switch. MUST stay False until Phase C sandbox validation
    # passes. Enabling this is the formal reversal of the old "permanent"
    # TRELLO_AUTO_CREATE_ENABLED=False decision (see CLAUDE.md).
    TRELLO_AUTO_CREATE_ENABLED: bool = False
    # Target list for auto-created cards. Empty → code default CONTRATO_LIST_ID
    # (prod). Set to a sandbox list id for Phase C controlled testing.
    TRELLO_AUTOCREATE_LIST_ID: str = ""
    # FAIL-SAFE date floor (YYYY-MM-DD). The AUTOMATIC reconciliation only
    # considers won deals with won_time >= this date. Empty/unset → the
    # reconciliation creates NOTHING (prevents a mass-backfill of all historical
    # won deals — many of which already have manual cards — when the flag is
    # first enabled in prod). The targeted backfill script bypasses this on
    # purpose for its explicit, manually-approved id list.
    TRELLO_AUTOCREATE_MIN_WON_DATE: str = ""

    ANTHROPIC_API_KEY: str = ""

    # Prompt 3 Feature 1 — audit log retention (days). Weekly cleanup job.
    AUDIT_LOG_RETENTION_DAYS: int = 90


settings = Settings()
