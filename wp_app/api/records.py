"""Merged routes: upload options, matching plan, AMOS popup, MiniDB records, delete."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import minidb
from ..adapters import ADAPTERS, tally_format_names
from ..database import db
from ..matching_config import CUSTOMER_ALIASES, CUSTOMER_FIRST, DEFAULT_TALLY_FORMAT
from ..mpd_matching import STEP_LABEL, matching_plan
from ..services import delete_tally
from ..utils import normalize


router = APIRouter()


@router.get("/api/upload-options")
def upload_options():
    """Values for the upload form dropdowns, taken from the MiniDB (Kho dữ liệu)."""
    with db() as connection:
        customers = {normalize(row[0]) for row in connection.execute(
            "SELECT DISTINCT customer FROM amp_task WHERE source='CUSTOMER' AND TRIM(COALESCE(customer,''))<>''")}
        customers |= {normalize(row[0]) for row in connection.execute(
            "SELECT DISTINCT customer FROM external_data WHERE TRIM(COALESCE(customer,''))<>''")}
        aircraft_types = [row[0] for row in connection.execute(
            """SELECT DISTINCT TRIM(aircraft_type) FROM amp_task
               WHERE TRIM(COALESCE(aircraft_type,''))<>'' ORDER BY 1""")]
    customers |= {normalize(key) for key in CUSTOMER_FIRST} | {normalize(key) for key in CUSTOMER_ALIASES}
    by_customer = {
        normalize(code): adapter.name for adapter in ADAPTERS for code in adapter.customer_codes
    }
    return {
        "customers": sorted(customers),
        "aircraft_types": aircraft_types,
        "tally_formats": tally_format_names(),
        "default_tally_format": DEFAULT_TALLY_FORMAT,
        "tally_format_by_customer": by_customer,
    }


@router.get("/api/matching-plan")
def matching_plan_api(customer: str = "", aircraft_type: str = ""):
    """Search order that will be used for this customer / aircraft type (shown in the upload form)."""
    return {"steps": [STEP_LABEL[step] for step in matching_plan(customer, aircraft_type)]}


@router.get("/api/items/{item_id}/amos")
def item_amos(item_id: int):
    return minidb.item_amos_detail(item_id)


@router.get("/api/amp-fields")
def amp_fields():
    return minidb.field_definitions()


@router.get("/api/items/{item_id}/add-form")
def add_form(item_id: int):
    return minidb.add_form_defaults(item_id)


class AddRecord(BaseModel):
    target: str
    values: dict[str, Any]
    reason: str
    changed_by: str = "Demo User"


@router.post("/api/items/{item_id}/add-to-database")
def add_to_database(item_id: int, payload: AddRecord):
    return minidb.add_to_database(item_id, payload.target, payload.values, payload.reason, payload.changed_by)


class EditRecord(BaseModel):
    values: dict[str, Any]
    reason: str
    item_id: int | None = None
    changed_by: str = "Demo User"


@router.get("/api/amp/{amp_id}")
def get_amp(amp_id: int):
    return minidb.get_amp_record(amp_id)


@router.patch("/api/amp/{amp_id}")
def edit_amp(amp_id: int, payload: EditRecord):
    return minidb.edit_amp_record(amp_id, payload.values, payload.reason, payload.item_id, payload.changed_by)


@router.get("/api/amp-changes/export")
def export_amp_changes():
    stream, name = minidb.export_amp_changes()
    return StreamingResponse(
        stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.delete("/api/evaluations/{evaluation_id}")
def delete_evaluation(evaluation_id: str):
    """Delete the Tally Sheet behind an evaluation (same as DELETE /api/tallies/{id})."""
    with db() as connection:
        row = connection.execute("SELECT tally_id FROM evaluation WHERE id=?", (evaluation_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy lần đánh giá")
    return delete_tally(row["tally_id"])
