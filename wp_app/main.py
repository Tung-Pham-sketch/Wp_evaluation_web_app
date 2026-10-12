# =============================================================================
# main.py – BUILDS THE FASTAPI APPLICATION
# -----------------------------------------------------------------------------
# create_app()
#   - mounts /static and serves templates/index.html at "/"
#   - registers the 4 routers: dashboard, tallies, evaluations, records
#   - startup() runs, IN THIS ORDER, every time the server starts:
#       1. init_db()                         create tables / add missing columns
#       2. migrate_upload_paths()            make stored_path relative to data/
#       3. import_amos()                     load AMP Excel into amp_task (once,
#                                            or again if the MiniDB is outdated)
#       4. import_jobcards()                 load All Jobcard.xlsx (once)
#       5. migrate_legacy_matching_results() re-match evaluations made by an
#                                            older MATCH_LOGIC_VERSION (only if
#                                            no manual work was done on them)
#       6. migrate_legacy_status_labels()    "Đã khớp"/"Chưa khớp" -> status codes
#       7. backfill_output_columns()         fork legacy fix (Type Code etc.)
#       8. seed_samples()                    create 2 demo dossiers if DB is empty
#                                            (skipped when WP_SKIP_SEED_SAMPLES=1)
#       9. migrate_workflows()               make sure every tally has 5 steps
#   All steps are idempotent: safe to run on every restart.
#
# To add a new API module: create the router in wp_app/api/ and
# include_router() it here.
# =============================================================================

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.dashboard import router as dashboard_router
from .api.evaluations import router as evaluations_router
from .api.records import router as records_router
from .api.tallies import router as tallies_router
from .config import STATIC_DIR, TEMPLATES_DIR, ensure_runtime_directories
from .database import init_db
from .reference_data import backfill_output_columns, import_amos, import_jobcards
from .services import (
    migrate_legacy_matching_results,
    migrate_legacy_status_labels,
    migrate_upload_paths,
    migrate_workflows,
    seed_samples,
)


def create_app() -> FastAPI:
    ensure_runtime_directories()
    application = FastAPI(
        title="VAECO Workpack Evaluation",
        version="3.1.0",
        description="Đánh giá Workpack, đối chiếu AMOS theo MPD key và review theo quy trình 5 bước.",
    )
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    application.include_router(dashboard_router)
    application.include_router(tallies_router)
    application.include_router(evaluations_router)
    application.include_router(records_router)

    @application.on_event("startup")
    def startup() -> None:
        init_db()
        migrate_upload_paths()
        import_amos()
        import_jobcards()
        migrate_legacy_matching_results()
        migrate_legacy_status_labels()
        backfill_output_columns()
        if os.environ.get("WP_SKIP_SEED_SAMPLES") != "1":
            seed_samples()
        migrate_workflows()

    @application.get("/", include_in_schema=False)
    def index():
        return FileResponse(TEMPLATES_DIR / "index.html")

    return application


app = create_app()
