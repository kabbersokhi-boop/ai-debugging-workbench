from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # Runtime services use explicit environment variables. The runner never reads a secret file.
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "postgresql+asyncpg://workbench:workbench@127.0.0.1:54329/workbench"
    runner_url: str = "http://127.0.0.1:8011"
    artifact_dir: Path = ROOT / "artifacts"
    fixture_dir: Path = ROOT / "fixtures/retail"
    frontend_dir: Path = ROOT / "frontend/dist"
    run_timeout_seconds: int = 60
    max_active_runs: int = 2
    chat_model: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    embedding_model: str = "nvidia/nemotron-3-embed-1b"
    rerank_model: str = "nvidia/llama-nemotron-rerank-vl-1b-v2"
    rerank_url: str = (
        "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-vl-1b-v2/reranking"
    )
    provider_timeout_seconds: float = Field(default=45, gt=0, le=120)
    provider_retries: int = Field(default=1, ge=0, le=2)
    provider_max_requests: int = Field(default=12, ge=1, le=30)
    diagnosis_timeout_seconds: int = Field(default=180, ge=10, le=300)
    context_token_budget: int = Field(default=4000, ge=500, le=16000)
    model_input_token_limit: int = Field(default=32768, ge=4000, le=64000)
    model_output_token_limit: int = Field(default=1400, ge=200, le=3000)


class ProviderSettings(Settings):
    model_config = SettingsConfigDict(env_file=ROOT / "backend/.env", extra="ignore")
    nvidia_api_key: SecretStr | None = None


settings = Settings()
