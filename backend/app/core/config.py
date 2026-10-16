from __future__ import annotations

import os


class Settings:
    app_name: str = "AShare Lab API"
    api_prefix: str = "/api/v1"

    @property
    def demo_mode(self) -> bool:
        # 默认实盘；仅显式打开演示模式
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


settings = Settings()
