from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..adapters import inspect_tally_structure
from ..config import MAX_UPLOAD_SIZE, SAMPLES_DIR, UPLOADS_DIR
from ..database import db, now
from ..services import (
    confirm_tally_inspection,
    create_tally_record,
    evaluate_tally,
    inspect_tally_record,
    resolve_stored_path,
    set_workflow_step,
    workflow_progress,
)
from ..utils import normalize


router = APIRouter()


async def store_upload(file: UploadFile) -> Path:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Chỉ hỗ trợ file Excel .xlsx")
    safe_name = re.sub(r"[^\w.() -]", "_", Path(file.filename).name)
    destination = UPLOADS_DIR / (
        f"{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:5]}-{safe_name}"
    )
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "File vượt quá giới hạn 30 MB")
    destination.write_bytes(content)
    return destination


@router.post("/api/tallies")
async def create_tally(file: UploadFile = File(...), customer: str = Form(...),
                       aircraft_reg: str = Form(""), aircraft_type: str = Form(""),
                       check_type: str = Form(""), description: str = Form(""),
                       uploader: str = Form("Demo User")):
    destination = await store_upload(file)
    try:
        tally_id = create_tally_record(
            destination, file.filename or destination.name, customer, aircraft_reg,
            aircraft_type, check_type, uploader, description,
        )
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc
    return {"tally_id": tally_id, "next_step": 2}


@router.post("/api/tallies/{tally_id}/inspect")
def inspect_tally(tally_id: str):
    return {"inspection": inspect_tally_record(tally_id)}


@router.post("/api/tallies/{tally_id}/inspection/confirm")
def confirm_inspection(tally_id: str):
    return {"inspection": confirm_tally_inspection(tally_id)}


@router.post("/api/tallies/{tally_id}/evaluate")
def run_preliminary_evaluation(tally_id: str):
    evaluation_id, reused = evaluate_tally(tally_id)
    return {"evaluation_id": evaluation_id, "reused": reused}


@router.get("/api/workflows/{tally_id}")
def get_workflow(tally_id: str):
    with db() as connection:
        tally = connection.execute("SELECT * FROM tally_sheet WHERE id=?", (tally_id,)).fetchone()
        if not tally:
            raise HTTPException(404, "Không tìm thấy hồ sơ")
        evaluation = connection.execute(
            "SELECT * FROM evaluation WHERE tally_id=?", (tally_id,)
        ).fetchone()
        summary = None
        if evaluation:
            summary = dict(connection.execute("""SELECT COUNT(*) total,
              COALESCE(SUM(matched),0) matched,
              COALESCE(SUM(not_in_database),0) unmatched,
              COALESCE(SUM(important_job),0) important,
              SUM(CASE WHEN match_status='REVIEW_REQUIRED' THEN 1 ELSE 0 END) review_required,
              SUM(CASE WHEN match_status='NOT_APPLICABLE' THEN 1 ELSE 0 END) not_applicable,
              SUM(CASE WHEN match_layer=1 THEN 1 ELSE 0 END) layer_1,
              SUM(CASE WHEN match_layer=2 THEN 1 ELSE 0 END) layer_2,
              SUM(CASE WHEN match_layer=3 THEN 1 ELSE 0 END) layer_3,
              ROUND(COALESCE(SUM(COALESCE(reviewed_mhr,planning_mhr)),0),2) total_mhr
              FROM evaluation_item WHERE evaluation_id=?""", (evaluation["id"],)).fetchone())
        progress = workflow_progress(connection, tally_id)
        lufthansa_structure = None
        block_summary: list[dict[str, Any]] = []
        if tally["adapter"] == "Lufthansa":
            inspect_step = next(
                (step for step in progress["steps"] if step["code"] == "inspect"), None
            )
            if inspect_step:
                lufthansa_structure = inspect_step["details"].get("structure")
            if not lufthansa_structure:
                source_path = resolve_stored_path(tally["stored_path"], tally["file_name"])
                if not source_path.exists():
                    source_path = SAMPLES_DIR / tally["file_name"]
                if source_path.exists():
                    lufthansa_structure = inspect_tally_structure(tally["adapter"], source_path)
                    if inspect_step:
                        inspect_step["details"]["structure"] = lufthansa_structure

            section_stats: dict[str, dict[str, Any]] = {}
            if evaluation:
                rows = connection.execute("""SELECT section,COUNT(*) evaluated_count,
                  COALESCE(SUM(matched),0) matched,
                  SUM(CASE WHEN match_layer=2 THEN 1 ELSE 0 END) layer_2,
                  SUM(CASE WHEN match_layer=3 THEN 1 ELSE 0 END) layer_3,
                  SUM(CASE WHEN match_status='NOT_FOUND' THEN 1 ELSE 0 END) not_found,
                  SUM(CASE WHEN match_status='NOT_APPLICABLE' THEN 1 ELSE 0 END) not_applicable
                  FROM evaluation_item WHERE evaluation_id=? GROUP BY section""",
                    (evaluation["id"],),
                ).fetchall()
                section_stats = {normalize(row["section"]): dict(row) for row in rows}

            for block in (lufthansa_structure or {}).get("blocks", []):
                stats = section_stats.get(normalize(block["raw_title"]), {})
                evaluated_count = int(stats.get("evaluated_count") or 0)
                matched = int(stats.get("matched") or 0)
                layer_2 = int(stats.get("layer_2") or 0)
                layer_3 = int(stats.get("layer_3") or 0)
                not_found = int(stats.get("not_found") or 0)
                if block["is_taskcard_scope"]:
                    if not evaluation:
                        status = "Chưa đánh giá"
                        result = "Sẽ đối chiếu CRI với Jobcard No. của Customer AMP DLH–A350."
                    elif matched == block["record_count"] and not layer_2 and not layer_3 and not not_found:
                        status = "Hoàn thành"
                        result = (
                            f"{matched}/{block['record_count']} CRI khớp 100% với Jobcard No. "
                            "của Customer AMP DLH–A350."
                        )
                    else:
                        status = "Cần review" if layer_2 or layer_3 else "Đã đánh giá"
                        result = (
                            f"Khớp 100%: {matched}; lớp 2: {layer_2}; lớp 3: {layer_3}; "
                            f"chưa có candidate: {not_found}."
                        )
                elif not block["record_count"]:
                    status = "Không có dữ liệu"
                    result = "Khối có trong biểu mẫu nhưng hồ sơ này không phát sinh bản ghi."
                elif block["category"] == "Nhật ký thay đổi":
                    status = "Đã thống kê"
                    result = "Khối biến động sau thời điểm in; chưa áp dụng logic so taskcard."
                else:
                    status = "Đã nhận diện"
                    result = "Ngoài phạm vi CRI ↔ Jobcard No.; chờ quy tắc đánh giá riêng."
                block_summary.append({
                    **block,
                    "evaluated_count": evaluated_count,
                    "matched": matched,
                    "layer_2": layer_2,
                    "layer_3": layer_3,
                    "not_found": not_found,
                    "status": status,
                    "result": result,
                })
    return {
        "tally": dict(tally),
        "evaluation": dict(evaluation) if evaluation else None,
        "summary": summary,
        "lufthansa_structure": lufthansa_structure,
        "block_summary": block_summary,
        **progress,
    }


class ReviewChecklistUpdate(BaseModel):
    detail: bool = False
    important: bool = False
    database: bool = False


@router.patch("/api/workflows/{tally_id}/review-checklist")
def update_review_checklist(tally_id: str, payload: ReviewChecklistUpdate):
    checklist = payload.model_dump()
    with db() as connection:
        evaluation = connection.execute(
            "SELECT id FROM evaluation WHERE tally_id=?", (tally_id,)
        ).fetchone()
        if not evaluation:
            raise HTTPException(400, "Cần chạy đánh giá sơ bộ trước khi review")
        complete = all(checklist.values())
        set_workflow_step(
            connection,
            tally_id,
            "review",
            "completed" if complete else "in_progress",
            {
                "checklist": checklist,
                "scope": "not_applicable",
                "confirmed_at": now() if complete else None,
            },
        )
        progress = workflow_progress(connection, tally_id)
    return {"ok": True, "review_complete": complete, **progress}
