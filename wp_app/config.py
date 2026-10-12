# =============================================================================
# config.py – PATHS, ENVIRONMENT VARIABLES, CONSTANTS
# -----------------------------------------------------------------------------
# PROJECT_ROOT   the repository folder (parent of wp_app/)
# DATA_DIR       runtime folder (SQLite + uploads). Env: WP_DATA_DIR,
#                default <repo>/data. Never committed to Git.
# DB_PATH        DATA_DIR/wp_demo.db  – the "MiniDB"
# UPLOADS_DIR    DATA_DIR/uploads     – copies of uploaded Tally Sheets
# AMOS_DIR       ../DATABASE                 (ALL AMP Task, Customer AMP, Jobcard)
# SAMPLES_DIR    ../TALLY SHEET KHACH HANG   (sample Tally Sheets)
#                -> both sit NEXT TO the repository, not inside it.
# MATCH_LOGIC_VERSION
#                stored on every evaluation_item. Increase it whenever the
#                matching result would change; at startup, evaluations with a
#                lower version (and no manual work) are matched again.
#                5 = merged MPD-key layer 1 + fork layers 2–3.
# MAX_UPLOAD_SIZE  30 MB
# ensure_runtime_directories()  creates data/ and data/uploads/.
# =============================================================================

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
MATCH_LOGIC_VERSION = 5  # 5 = merged MPD-key matching (layer 1) + fork layers 2–3
MAX_UPLOAD_SIZE = 30 * 1024 * 1024


def ensure_runtime_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
