from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    """从项目根 / backend/.env 加载本地密钥，不覆盖已有环境变量。"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / ".env",  # repo root when installed as backend/app/core
        here.parents[2] / ".env",  # backend/.env
        Path.cwd() / ".env",
        Path.cwd() / "backend" / ".env",
    ]
    for p in candidates:
        if p.is_file():
            load_dotenv(p, override=False)


_load_dotenv()


class Settings:
    app_name: str = "AShare Lab API"
    api_prefix: str = "/api/v1"

    @property
    def demo_mode(self) -> bool:
        return os.getenv("ASHARE_DEMO_MODE", "0").strip() in ("1", "true", "TRUE", "yes")

    @property
    def cache_ttl(self) -> int:
        return int(os.getenv("ASHARE_CACHE_TTL", "120"))

    @property
    def cors_origins(self) -> list[str]:
        return [
            o.strip()
            for o in os.getenv("ASHARE_CORS_ORIGINS", "*").split(",")
            if o.strip()
        ]

    @property
    def data_dir(self) -> str:
        return os.getenv("ASHARE_DATA_DIR", "./data")

    @property
    def llm_api_key(self) -> str:
        return (
            os.getenv("LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("ASHARE_LLM_API_KEY")
            or ""
        ).strip()

    @property
    def llm_base_url(self) -> str:
        return (
            os.getenv("LLM_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).strip()

    @property
    def llm_model(self) -> str:
        return (os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "").strip()

    @property
    def llm_provider(self) -> str:
        return (os.getenv("LLM_PROVIDER") or "openai_compatible").strip()


settings = Settings()
