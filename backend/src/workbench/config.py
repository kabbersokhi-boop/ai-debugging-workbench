from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://workbench:workbench@127.0.0.1:54329/workbench"
    runner_url: str = "http://127.0.0.1:8011"
    artifact_dir: Path = Path("../artifacts")
    fixture_dir: Path = Path("../fixtures/retail")
    frontend_dir: Path = Path("../frontend/dist")
    run_timeout_seconds: int = 60
    max_active_runs: int = 2


settings = Settings()
