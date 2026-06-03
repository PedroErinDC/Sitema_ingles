from __future__ import annotations

import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        self.data_dir = self.project_root / "data"
        self.tmp_ingest_dir = self.data_dir / "tmp_ingest"
        default_sqlite = self.data_dir / "portfolio.db"
        self.database_url = os.getenv("DATABASE_URL", f"sqlite:///{default_sqlite.resolve()}")
        self.cors_origins = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
            ).split(",")
            if origin.strip()
        ]
        self.legacy_learning_db = self.data_dir / "ingles.db"


settings = Settings()
