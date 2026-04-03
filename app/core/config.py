from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # — Telegram —
    bot_token: str

    # — Database (boontar_market — single DB for everything) —
    db_host_market: str = "host.docker.internal"
    db_port_market: int = 3306
    db_username_market: str = "root"
    db_password_market: str = ""
    db_database_market: str = "boontar_market"

    # — Logging —
    log_level: str = "INFO"

    # — Internal API —
    api_port: int = 8080
    api_token: str = ""

    # — Admin —
    admin_telegram_id: int = 1917662916

    # — Alerts —
    alert_chat_id: int | None = None
    alert_min_bikes: int = 3
    alert_repair_max_days: int = 3
    alert_breakdown_max_monthly: int = 3
    alert_check_minutes: int = 30

    # — Hidden stores (inactive, excluded from all selections) —
    hidden_store_ids: list[int] = [63, 66]

    @property
    def database_url_market(self) -> str:
        credentials = self.db_username_market
        if self.db_password_market:
            credentials += f":{self.db_password_market}"
        return (
            f"mysql+asyncmy://{credentials}"
            f"@{self.db_host_market}:{self.db_port_market}/{self.db_database_market}"
        )


settings = Settings()  # type: ignore[call-arg]
