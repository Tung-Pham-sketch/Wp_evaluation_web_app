from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("WP_DATA_DIR", PROJECT_ROOT / "data")).resolve()
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "wp_demo.db"
AMOS_DIR = PROJECT_ROOT.parent / "DATABASE"
SAMPLES_DIR = PROJECT_ROOT.parent / "TALLY SHEET KHACH HANG"
STATIC_DIR = PROJECT_ROOT / "static"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
MATCH_LOGIC_VERSION = 4
MAX_UPLOAD_SIZE = 30 * 1024 * 1024


def ensure_runtime_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
