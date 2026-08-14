from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "РПО Сервер"
    secret_key: str = "dev-only-change-me"
    database_url: str = "sqlite:///./data/rpo.db"
    admin_username: str = "admin"
    admin_password: str = "ChangeMe123!"

    mail_mode: str = "file"  # file | smtp
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "rpo@example.ru"
    smtp_starttls: bool = True

    export_dir: str = "./data/exports"
    outbox_dir: str = "./data/outbox"

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    def ensure_dirs(self) -> None:
        Path(self.export_dir).mkdir(parents=True, exist_ok=True)
        Path(self.outbox_dir).mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite"):
            Path("./data").mkdir(parents=True, exist_ok=True)


settings = Settings()
