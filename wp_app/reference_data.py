from __future__ import annotations

from typing import Any

from openpyxl import load_workbook

from .config import AMOS_DIR
from .database import db
from .matching import AUTO_MATCH, aircraft_from_amp_name, canonical_aircraft, taskcard_core
from .utils import column_map, normalize


def import_amos() -> None:
    with db() as connection:
        total = connection.execute("SELECT COUNT(*) FROM amp_task").fetchone()[0]
        current = connection.execute(
            "SELECT COUNT(*) FROM amp_task WHERE taskcard_core_key IS NOT NULL AND aircraft_model IS NOT NULL"
        ).fetchone()[0]
        if total and current == total:
            return
        if total:
            connection.execute("DELETE FROM amp_task")
    sources = [
        (AMOS_DIR / "ALL AMP Task.xlsx", "VNA", "AMP"),
        (AMOS_DIR / "ALL Customer AMP.xlsx", "CUSTOMER", None),
    ]
    records: list[tuple] = []
    for path, source, sheet in sources:
        if not path.exists():
            continue
        workbook = load_workbook(path, read_only=True, data_only=True)
        worksheet = workbook[sheet] if sheet else workbook.active
        rows = worksheet.iter_rows(values_only=True)
        headers = list(next(rows))
        header_map = column_map(headers)

        def value(row, *names):
            for name in names:
                index = header_map.get(normalize(name))
                if index is not None and index < len(row):
                    return row[index]
            return None

        for row in rows:
            task_no = value(row, "Task No./Rev No.", "Jobcard No.", "Taskcard No./Rev")
            if not task_no:
                continue
            taskcard_no = value(row, "Taskcard No./Rev") if source == "VNA" else value(row, "Jobcard No.")
            taskcard_no = taskcard_no or task_no
            amp_name = value(row, "AMP Name/Rev No.", "AMP Name/ Rev No.")
            aircraft_type = value(row, "A/C Type")
            records.append((
                source, aircraft_type, value(row, "Customer"), str(task_no).strip(), normalize(task_no),
                amp_name, str(taskcard_no).strip(), normalize(taskcard_no), taskcard_core(taskcard_no),
                aircraft_from_amp_name(amp_name, aircraft_type) if source == "VNA" else canonical_aircraft(aircraft_type),
                value(row, "Taskcard Title", "Title"), value(row, "Description"), value(row, "Phase"),
                value(row, "Zone"), value(row, "Area"), value(row, "Panel"), value(row, "Special Code"),
                value(row, "Resource Type"), value(row, "Classification"), value(row, "Type Code"),
                value(row, "Qualification"), value(row, "Planning MHR"), value(row, "Information Skill"),
                value(row, "References"), value(row, "Linked Jobcards"), value(row, "Jobcards Title"),
            ))
    with db() as connection:
        connection.executemany(
            """INSERT INTO amp_task(source,aircraft_type,customer,task_no,task_key,amp_name,taskcard_no,
            taskcard_key,taskcard_core_key,aircraft_model,title,description,
            phase,zone,area,panel,special_code,resource_type,classification,type_code,qualification,planning_mhr,
            information_skill,requirement_link,linked_jobcards,jobcards_title)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            records,
        )


def import_jobcards() -> None:
    with db() as connection:
        if connection.execute("SELECT COUNT(*) FROM jobcard_master").fetchone()[0]:
            return
    path = AMOS_DIR / "All Jobcard.xlsx"
    if not path.exists():
        return
    workbook = load_workbook(path, read_only=True, data_only=True)
    rows = workbook.active.iter_rows(values_only=True)
    header_map = column_map(list(next(rows)))

    def value(row, name):
        index = header_map.get(normalize(name))
        return row[index] if index is not None and index < len(row) else None

    records: list[tuple[Any, ...]] = []
    for row in rows:
        jobcard_no = value(row, "Jobcard No.")
        if not jobcard_no:
            continue
        meta_key = value(row, "Meta Key")
        meta_value = value(row, "Meta Value")
        aircraft_type = meta_value if normalize(meta_key) == "AIRCRAFT TYPE" else None
        records.append((
            meta_key, meta_value, aircraft_type, str(jobcard_no).strip(), normalize(jobcard_no),
            value(row, "Title"), value(row, "Description"), value(row, "Phase"),
            value(row, "Zone"), value(row, "Area"), value(row, "Panel"),
            value(row, "Special Code"), value(row, "Resource Type"), value(row, "Classification"),
            value(row, "Qualification"), value(row, "Planning MHR"), value(row, "Information Skill"),
            value(row, "Information MHR"), value(row, "References"),
        ))
    with db() as connection:
        connection.executemany(
            """INSERT INTO jobcard_master(meta_key,meta_value,aircraft_type,jobcard_no,
            jobcard_key,title,description,phase,zone,area,panel,special_code,resource_type,
            classification,qualification,planning_mhr,information_skill,information_mhr,
            requirement_link) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            records,
        )


def backfill_output_columns() -> None:
    from .services import lookup_amp

    with db() as connection:
        pending = connection.execute("""SELECT i.id,i.task_no,t.customer,t.aircraft_type
          FROM evaluation_item i JOIN evaluation e ON e.id=i.evaluation_id
          JOIN tally_sheet t ON t.id=e.tally_id
          WHERE i.matched=1 AND i.type_code IS NULL AND i.jobcards_title IS NULL""").fetchall()
        for item in pending:
            decision = lookup_amp(connection, item["task_no"], item["customer"], item["aircraft_type"])
            amp = decision.record
            if decision.status == AUTO_MATCH and amp:
                connection.execute(
                    "UPDATE evaluation_item SET type_code=?,jobcards_title=? WHERE id=?",
                    (amp["type_code"], amp["jobcards_title"], item["id"]),
                )
