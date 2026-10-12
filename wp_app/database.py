# =============================================================================
# database.py – SQLITE CONNECTION, SCHEMA AND COLUMN MIGRATIONS
# -----------------------------------------------------------------------------
# db()      context manager: opens DB_PATH, rows behave like dicts
#           (sqlite3.Row), foreign keys ON, COMMIT on success, always closes.
#           Usage:  with db() as connection: connection.execute(...)
# now()     ISO timestamp used in every *_at column.
#
# init_db() creates the tables if missing, then adds missing columns
# (ALTER TABLE) so an older database keeps working. Safe to run repeatedly.
#
# Tables
#   amp_task         the MiniDB copy of AMOS: source = 'VNA' (ALL AMP Task) or
#                    'CUSTOMER' (Customer AMP). Key columns for matching:
#                    mpd_key, task_base, task_key, aircraft_family (layer 1);
#                    taskcard_key, taskcard_core_key, aircraft_model (layers 2–3);
#                    origin = 'AMOS' | 'MANUAL', edited = 1 after "Sửa bản ghi".
#   jobcard_master   All Jobcard.xlsx (read-only browse).
#   external_data    mappings / rules managed outside AMOS.
#   tally_sheet      one uploaded file + its metadata (customer, A/C, adapter).
#   workflow_step    5 rows per tally (intake/inspect/evaluate/review/finalize).
#   evaluation       one per tally (unique index) – Final Evaluation header.
#   evaluation_item  one per Tally row – the matching result + review values.
#                    match_status = AUTO_MATCH | REVIEW_REQUIRED | NOT_FOUND |
#                    NOT_APPLICABLE; amp_refs = JSON natural keys of the AMOS
#                    records used (survives a MiniDB rebuild).
#   change_log       manual review changes (MHR, Important Job, note) + reason.
#   amp_change       manual MiniDB changes (ADD / EDIT) + reason. Kept when a
#                    tally is deleted; exported to Excel.
#
# MERGED_MIGRATIONS (bottom of file): columns added by the merge. To add a new
# column later, append (table, column, type) to this tuple.
# =============================================================================

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime

from .config import DB_PATH, ensure_runtime_directories


@contextmanager
def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_db() -> None:
    ensure_runtime_directories()
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS amp_task (
              id INTEGER PRIMARY KEY, source TEXT NOT NULL, aircraft_type TEXT,
              customer TEXT, task_no TEXT NOT NULL, task_key TEXT NOT NULL,
              amp_name TEXT, taskcard_no TEXT, taskcard_key TEXT,
              taskcard_core_key TEXT, aircraft_model TEXT,
              title TEXT, description TEXT, phase TEXT, zone TEXT, area TEXT,
              panel TEXT, special_code TEXT, resource_type TEXT, classification TEXT,
              type_code TEXT, qualification TEXT, planning_mhr TEXT, information_skill TEXT,
              requirement_link TEXT, linked_jobcards TEXT, jobcards_title TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_amp_key ON amp_task(task_key);
            CREATE INDEX IF NOT EXISTS idx_amp_customer ON amp_task(customer, task_key);
            CREATE TABLE IF NOT EXISTS jobcard_master (
              id INTEGER PRIMARY KEY, meta_key TEXT, meta_value TEXT,
              aircraft_type TEXT, jobcard_no TEXT NOT NULL, jobcard_key TEXT NOT NULL,
              title TEXT, description TEXT, phase TEXT, zone TEXT, area TEXT,
              panel TEXT, special_code TEXT, resource_type TEXT, classification TEXT,
              qualification TEXT, planning_mhr TEXT, information_skill TEXT,
              information_mhr TEXT, requirement_link TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_jobcard_key ON jobcard_master(jobcard_key);
            CREATE TABLE IF NOT EXISTS external_data (
              id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
              code TEXT NOT NULL, canonical_value TEXT, aircraft_type TEXT,
              customer TEXT, description TEXT, reason TEXT,
              status TEXT DEFAULT 'Có hiệu lực', updated_by TEXT DEFAULT 'Quản trị dữ liệu',
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tally_sheet (
              id TEXT PRIMARY KEY, file_name TEXT NOT NULL, stored_path TEXT NOT NULL,
              customer TEXT NOT NULL, aircraft_reg TEXT, aircraft_type TEXT,
              check_type TEXT, adapter TEXT NOT NULL, version INTEGER DEFAULT 1,
              status TEXT DEFAULT 'Đã xử lý', uploader TEXT DEFAULT 'Demo User',
              uploaded_at TEXT NOT NULL, row_count INTEGER DEFAULT 0,
              matched_count INTEGER DEFAULT 0, error_message TEXT
            );
            CREATE TABLE IF NOT EXISTS evaluation (
              id TEXT PRIMARY KEY, tally_id TEXT NOT NULL REFERENCES tally_sheet(id),
              status TEXT DEFAULT 'Đang review', revision TEXT, tat_review TEXT,
              assumptions TEXT, notes TEXT, prepared_by TEXT, approved_by TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evaluation_item (
              id INTEGER PRIMARY KEY AUTOINCREMENT, evaluation_id TEXT NOT NULL REFERENCES evaluation(id),
              seq TEXT, section TEXT, task_no TEXT, source_title TEXT, event_type TEXT,
              rii TEXT, source_note TEXT, matched INTEGER DEFAULT 0, amp_source TEXT,
              title TEXT, description TEXT, phase TEXT, zone TEXT, area TEXT, panel TEXT,
              special_code TEXT, resource_type TEXT, classification TEXT, qualification TEXT,
              planning_mhr REAL DEFAULT 0, reviewed_mhr REAL, information_skill TEXT,
              requirement_link TEXT, linked_jobcards TEXT, type_code TEXT, jobcards_title TEXT,
              important_job INTEGER DEFAULT 0,
              important_source TEXT, not_in_database INTEGER DEFAULT 0, review_note TEXT,
              review_reason TEXT, match_status TEXT, match_method TEXT,
              match_candidate_count INTEGER DEFAULT 0, match_source_id INTEGER,
              match_note TEXT, match_layer INTEGER, match_score REAL,
              suggested_task_no TEXT, suggested_title TEXT, suggested_mhr REAL,
              match_logic_version INTEGER DEFAULT 4, updated_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_items_eval ON evaluation_item(evaluation_id);
            CREATE TABLE IF NOT EXISTS change_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT, evaluation_id TEXT, item_id INTEGER,
              field_name TEXT, old_value TEXT, new_value TEXT, reason TEXT,
              changed_by TEXT, changed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS workflow_step (
              tally_id TEXT NOT NULL REFERENCES tally_sheet(id) ON DELETE CASCADE,
              step_code TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'not_started',
              details_json TEXT NOT NULL DEFAULT '{}', completed_at TEXT,
              updated_at TEXT NOT NULL,
              PRIMARY KEY (tally_id, step_code)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_evaluation_tally ON evaluation(tally_id);
            -- Merged: manual changes to the MiniDB ("Thêm vào Database" / "Sửa bản ghi").
            -- Kept when a Tally Sheet is deleted; exportable to Excel.
            CREATE TABLE IF NOT EXISTS amp_change (
              id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, amp_id INTEGER,
              source TEXT, record_key TEXT, task_no TEXT, field_name TEXT, old_value TEXT, new_value TEXT,
              reason TEXT, changed_by TEXT, changed_at TEXT, evaluation_id TEXT, tally_task_no TEXT
            );
            """
        )
        migrations = (
            ("amp_task", "type_code", "TEXT"),
            ("amp_task", "jobcards_title", "TEXT"),
            ("amp_task", "amp_name", "TEXT"),
            ("amp_task", "taskcard_no", "TEXT"),
            ("amp_task", "taskcard_key", "TEXT"),
            ("amp_task", "taskcard_core_key", "TEXT"),
            ("amp_task", "aircraft_model", "TEXT"),
            ("evaluation_item", "type_code", "TEXT"),
            ("evaluation_item", "jobcards_title", "TEXT"),
            ("evaluation_item", "match_status", "TEXT"),
            ("evaluation_item", "match_method", "TEXT"),
            ("evaluation_item", "match_candidate_count", "INTEGER DEFAULT 0"),
            ("evaluation_item", "match_source_id", "INTEGER"),
            ("evaluation_item", "match_note", "TEXT"),
            ("evaluation_item", "match_layer", "INTEGER"),
            ("evaluation_item", "match_score", "REAL"),
            ("evaluation_item", "suggested_task_no", "TEXT"),
            ("evaluation_item", "suggested_title", "TEXT"),
            ("evaluation_item", "suggested_mhr", "REAL"),
            ("evaluation_item", "match_logic_version", "INTEGER"),
            ("tally_sheet", "description", "TEXT"),
        ) + MERGED_MIGRATIONS
        for table, column, definition in migrations:
            existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_amp_taskcard_core ON amp_task(source,taskcard_core_key)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_amp_taskcard_key ON amp_task(source,taskcard_key)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_amp_taskcard_customer "
            "ON amp_task(source,customer,taskcard_key)"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_amp_mpd ON amp_task(source, mpd_key)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_amp_base ON amp_task(source, task_base)")
        if not connection.execute("SELECT COUNT(*) FROM external_data").fetchone()[0]:
            seed_rows = [
                ("Mapping khách hàng", "VA-VJ", "VietJet", None, "VA-VJ", "Mẫu Tally Sheet VietJet", "Chuẩn hóa mã khách hàng"),
                ("Mapping khách hàng", "DLH", "Lufthansa", None, "DLH", "Mẫu Workpackage Summary Lufthansa", "Chuẩn hóa mã khách hàng"),
                ("Mapping loại tàu bay", "A320", "320", "A320", None, "Airbus A320", "Chuẩn hóa định danh loại tàu bay"),
                ("Mapping loại tàu bay", "A321", "321", "A321", None, "Airbus A321", "Chuẩn hóa định danh loại tàu bay"),
                ("Mapping loại tàu bay", "A350", "350", "A350", None, "Airbus A350", "Chuẩn hóa định danh loại tàu bay"),
                ("Mapping loại tàu bay", "B787", "787", "B787", None, "Boeing 787", "Chuẩn hóa định danh loại tàu bay"),
            ]
            connection.executemany(
                """INSERT INTO external_data(category,code,canonical_value,aircraft_type,
                customer,description,reason,updated_at) VALUES (?,?,?,?,?,?,?,?)""",
                [(*row, now()) for row in seed_rows],
            )


# Merged: columns of the MPD-key matching and of the MiniDB maintenance.
MERGED_MIGRATIONS = (
    # amp_task – AMOS fields used by MPD matching and the AMOS popup
    ("amp_task", "aircraft_family", "TEXT"),
    ("amp_task", "effectivity", "TEXT"),
    ("amp_task", "amp_date", "TEXT"),
    ("amp_task", "mp_name", "TEXT"),
    ("amp_task", "taskcard_ident", "TEXT"),
    ("amp_task", "task_type", "TEXT"),
    ("amp_task", "task_base", "TEXT"),
    ("amp_task", "mpd_key", "TEXT"),
    ("amp_task", "side", "TEXT"),
    ("amp_task", "information_mhr", "TEXT"),
    # amp_task – manual work in the MiniDB (AMOS itself is never changed)
    ("amp_task", "origin", "TEXT"),
    ("amp_task", "edited", "INTEGER DEFAULT 0"),
    ("amp_task", "updated_at", "TEXT"),
    ("amp_task", "updated_by", "TEXT"),
    # evaluation_item – MPD matching result
    ("evaluation_item", "amos_reference", "TEXT"),
    ("evaluation_item", "match_key", "TEXT"),
    ("evaluation_item", "amp_refs", "TEXT"),
    ("evaluation_item", "task_ref", "TEXT"),
    ("evaluation_item", "source_zone", "TEXT"),
    ("evaluation_item", "match_rule", "TEXT"),
    ("evaluation_item", "added_to_db", "INTEGER DEFAULT 0"),
)
