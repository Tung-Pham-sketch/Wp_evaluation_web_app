from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.dashboard import router as dashboard_router
from .api.evaluations import router as evaluations_router
from .api.tallies import router as tallies_router
from .config import STATIC_DIR, TEMPLATES_DIR, ensure_runtime_directories
from .database import init_db
from .reference_data import backfill_output_columns, import_amos, import_jobcards
from .services import (
    migrate_legacy_matching_results,
    migrate_upload_paths,
    migrate_workflows,
    seed_samples,
)


def create_app() -> FastAPI:
    ensure_runtime_directories()
    application = FastAPI(
        title="VAECO Workpack Evaluation",
        version="3.0.0",
        description="Đánh giá Workpack, đối chiếu AMOS và review theo quy trình 5 bước.",
    )
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    application.include_router(dashboard_router)
    application.include_router(tallies_router)
    application.include_router(evaluations_router)

    @application.on_event("startup")
    def startup() -> None:
        init_db()
        migrate_upload_paths()
        import_amos()
        import_jobcards()
        migrate_legacy_matching_results()
        backfill_output_columns()
        if os.environ.get("WP_SKIP_SEED_SAMPLES") != "1":
            seed_samples()
        migrate_workflows()

    @application.get("/", include_in_schema=False)
    def index():
        return FileResponse(TEMPLATES_DIR / "index.html")

    return application


app = create_app()
