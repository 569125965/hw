from __future__ import annotations

import os


class Settings:
    app_name: str = "AShare Lab API"
    api_prefix: str = "/api/v1"
    demo_mode: bool = os.getenv("ASHARE_DEMO_MODE", "0") == "1"
    cache_ttl: int = int(os.getenv("ASHARE_CACHE_TTL", "300"))
    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv("ASHARE_CORS_ORIGINS", "*").split(",")
        if o.strip()
    ]
    data_dir: str = os.getenv("ASHARE_DATA_DIR", "./data")


settings = Settings()
