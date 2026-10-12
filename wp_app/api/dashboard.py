from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..database import db
from ..services import workflow_progress


router = APIRouter()


@router.get("/api/dashboard")
def dashboard():
    with db() as connection:
        totals = connection.execute("""SELECT COUNT(*) tally_count,
          COALESCE(SUM(row_count),0) item_count,
          COALESCE(SUM(matched_count),0) matched_count FROM tally_sheet""").fetchone()
        records = connection.execute("""SELECT t.id tally_id,t.file_name,t.description,t.customer,
          t.aircraft_reg,t.aircraft_type,t.check_type,t.adapter,t.row_count,t.matched_count,
          t.uploaded_at,t.status tally_status,e.id evaluation_id,e.status evaluation_status,
          e.created_at,e.updated_at FROM tally_sheet t LEFT JOIN evaluation e ON e.tally_id=t.id
          ORDER BY t.uploaded_at DESC""").fetchall()
        workflows = []
        for record in records:
            item = dict(record)
            item.update(workflow_progress(connection, record["tally_id"]))
            item["status"] = record["evaluation_status"] or record["tally_status"]
            workflows.append(item)
        evaluations = [item for item in workflows if item["evaluation_id"]]
        amp_count = connection.execute("SELECT COUNT(*) FROM amp_task").fetchone()[0]
    return {
        "totals": dict(totals),
        "amp_count": amp_count,
        "workflows": workflows,
        "evaluations": evaluations,
    }


@router.get("/api/data/amos")
def browse_amos(q: str = "", source: str = "all", aircraft_type: str = "all",
                customer: str = "all", classification: str = "all", origin: str = "all",
                page: int = 1, page_size: int = 40):
    page = max(1, page)
    page_size = min(max(10, page_size), 100)
    where = ["1=1"]
    params: list[Any] = []
    if q.strip():
        where.append("""(task_no LIKE ? OR taskcard_no LIKE ? OR title LIKE ?
          OR description LIKE ? OR special_code LIKE ?)""")
        params.extend([f"%{q.strip()}%"] * 5)
    for column, value in (
        ("source", source),
        ("aircraft_type", aircraft_type),
        ("customer", customer),
        ("classification", classification),
    ):
        if value != "all":
            where.append(f"COALESCE({column},'')=?")
            params.append(value)
    # Merged: origin of the record in the MiniDB
    if origin == "manual":
        where.append("origin='MANUAL'")
    elif origin == "edited":
        where.append("COALESCE(edited,0)=1")
    elif origin == "amos":
        where.append("COALESCE(origin,'AMOS')='AMOS' AND COALESCE(edited,0)=0")
    predicate = " AND ".join(where)
    with db() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM amp_task WHERE {predicate}", params
        ).fetchone()[0]
        rows = [
            dict(row)
            for row in connection.execute(
                f"""SELECT id,source,aircraft_type,customer,task_no,title,
                phase,zone,special_code,classification,planning_mhr,qualification,description,area,panel,
                resource_type,information_skill,requirement_link,linked_jobcards,
                amp_name,amp_date,mp_name,taskcard_no,taskcard_ident,task_type,mpd_key,effectivity,
                type_code,jobcards_title,information_mhr,origin,edited,updated_at,updated_by FROM amp_task
                WHERE {predicate} ORDER BY task_no LIMIT ? OFFSET ?""",
                (*params, page_size, (page - 1) * page_size),
            )
        ]

        def distinct(column: str, limit: int = 80):
            return [
                row[0]
                for row in connection.execute(
                    f"""SELECT DISTINCT {column} FROM amp_task
                    WHERE {column} IS NOT NULL AND TRIM({column})<>'' ORDER BY {column} LIMIT ?""",
                    (limit,),
                )
            ]

        filters = {
            "sources": distinct("source"),
            "aircraft_types": distinct("aircraft_type"),
            "customers": distinct("customer"),
            "classifications": distinct("classification"),
        }
        stats = dict(connection.execute("""SELECT COUNT(*) total,
          SUM(CASE WHEN source='VNA' THEN 1 ELSE 0 END) vna,
          SUM(CASE WHEN source='CUSTOMER' THEN 1 ELSE 0 END) customer,
          SUM(CASE WHEN UPPER(COALESCE(classification,'')) LIKE '%WATCH ITEM%' THEN 1 ELSE 0 END) watch_items,
          SUM(CASE WHEN origin='MANUAL' THEN 1 ELSE 0 END) manual,
          SUM(CASE WHEN COALESCE(edited,0)=1 THEN 1 ELSE 0 END) edited
          FROM amp_task""").fetchone())
    return {
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "filters": filters,
        "stats": stats,
    }


@router.get("/api/data/jobcards")
def browse_jobcards(q: str = "", aircraft_type: str = "all",
                    classification: str = "all", page: int = 1,
                    page_size: int = 40):
    page = max(1, page)
    page_size = min(max(10, page_size), 100)
    where = ["1=1"]
    params: list[Any] = []
    if q.strip():
        where.append("(jobcard_no LIKE ? OR title LIKE ? OR description LIKE ? OR special_code LIKE ?)")
        params.extend([f"%{q.strip()}%"] * 4)
    for column, value in (("aircraft_type", aircraft_type), ("classification", classification)):
        if value != "all":
            where.append(f"COALESCE({column},'')=?")
            params.append(value)
    predicate = " AND ".join(where)
    with db() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM jobcard_master WHERE {predicate}", params
        ).fetchone()[0]
        rows = [
            dict(row)
            for row in connection.execute(
                f"""SELECT id,'JOBCARD' source,aircraft_type,
                NULL customer,jobcard_no task_no,title,description,phase,zone,area,panel,special_code,
                resource_type,classification,qualification,planning_mhr,information_skill,
                information_mhr,requirement_link FROM jobcard_master
                WHERE {predicate} ORDER BY jobcard_no LIMIT ? OFFSET ?""",
                (*params, page_size, (page - 1) * page_size),
            )
        ]

        def distinct(column: str, limit: int = 80):
            return [
                row[0]
                for row in connection.execute(
                    f"""SELECT DISTINCT {column} FROM jobcard_master
                    WHERE {column} IS NOT NULL AND TRIM({column})<>'' ORDER BY {column} LIMIT ?""",
                    (limit,),
                )
            ]

        filters = {
            "aircraft_types": distinct("aircraft_type"),
            "classifications": distinct("classification"),
        }
        stats = dict(connection.execute("""SELECT COUNT(*) total,
          SUM(CASE WHEN UPPER(COALESCE(classification,''))='WATCH ITEM' THEN 1 ELSE 0 END) watch_items
          FROM jobcard_master""").fetchone())
    return {
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "filters": filters,
        "stats": stats,
    }


@router.get("/api/data/external")
def browse_external(q: str = "", category: str = "all", status: str = "all",
                    page: int = 1, page_size: int = 40):
    page = max(1, page)
    page_size = min(max(10, page_size), 100)
    where = ["1=1"]
    params: list[Any] = []
    if q.strip():
        where.append("(code LIKE ? OR canonical_value LIKE ? OR description LIKE ? OR reason LIKE ?)")
        params.extend([f"%{q.strip()}%"] * 4)
    if category != "all":
        where.append("category=?")
        params.append(category)
    if status != "all":
        where.append("status=?")
        params.append(status)
    predicate = " AND ".join(where)
    with db() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM external_data WHERE {predicate}", params
        ).fetchone()[0]
        rows = [
            dict(row)
            for row in connection.execute(
                f"""SELECT * FROM external_data WHERE {predicate}
                ORDER BY category,code LIMIT ? OFFSET ?""",
                (*params, page_size, (page - 1) * page_size),
            )
        ]
        categories = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT category FROM external_data ORDER BY category"
            )
        ]
        statuses = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT status FROM external_data ORDER BY status"
            )
        ]
        category_counts = [
            dict(row)
            for row in connection.execute(
                "SELECT category,COUNT(*) record_count FROM external_data GROUP BY category ORDER BY category"
            )
        ]
    return {
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "filters": {"categories": categories, "statuses": statuses},
        "category_counts": category_counts,
    }
