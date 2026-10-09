from __future__ import annotations

import io
import json
import re
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
DB_PATH = DATA / "wp_demo.db"
AMOS_DIR = PROJECT / "DATABASE"
SAMPLES_DIR = PROJECT / "TALLY SHEET KHACH HANG"
DATA.mkdir(exist_ok=True)
UPLOADS.mkdir(exist_ok=True)

app = FastAPI(title="VAECO Workpack Evaluation", version="1.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


def mhr_hours(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    text = str(value).strip()
    if ":" in text:
        try:
            hours, minutes = text.split(":", 1)
            return round(float(hours) + float(minutes) / 60, 2)
        except ValueError:
            return 0.0
    try:
        return round(float(text), 2)
    except ValueError:
        return 0.0


def canonical_aircraft(value: str) -> str:
    text = norm(value).replace("AIRBUS", "").replace("BOEING", "").replace("-", "").strip()
    aliases = {"A320": "320", "A321": "321", "A350": "350", "B787": "787", "ATR72": "ATR"}
    return aliases.get(text, text)


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS amp_task (
              id INTEGER PRIMARY KEY, source TEXT NOT NULL, aircraft_type TEXT,
              customer TEXT, task_no TEXT NOT NULL, task_key TEXT NOT NULL,
              title TEXT, description TEXT, phase TEXT, zone TEXT, area TEXT,
              panel TEXT, special_code TEXT, resource_type TEXT, classification TEXT,
              type_code TEXT, qualification TEXT, planning_mhr TEXT, information_skill TEXT,
              requirement_link TEXT, linked_jobcards TEXT, jobcards_title TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_amp_key ON amp_task(task_key);
            CREATE INDEX IF NOT EXISTS idx_amp_customer ON amp_task(customer, task_key);
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
              review_reason TEXT, updated_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_items_eval ON evaluation_item(evaluation_id);
            CREATE TABLE IF NOT EXISTS change_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT, evaluation_id TEXT, item_id INTEGER,
              field_name TEXT, old_value TEXT, new_value TEXT, reason TEXT,
              changed_by TEXT, changed_at TEXT
            );
            """
        )
        # Keep existing demo databases compatible when the output specification gains columns.
        for table, column in (("amp_task", "type_code"), ("amp_task", "jobcards_title"),
                              ("evaluation_item", "type_code"), ("evaluation_item", "jobcards_title")):
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
        if not conn.execute("SELECT COUNT(*) FROM external_data").fetchone()[0]:
            seed_rows = [
                ("Mapping khách hàng", "VA-VJ", "VietJet", None, "VA-VJ", "Mẫu Tally Sheet VietJet", "Chuẩn hóa mã khách hàng"),
                ("Mapping khách hàng", "DLH", "Lufthansa", None, "DLH", "Mẫu Workpackage Summary Lufthansa", "Chuẩn hóa mã khách hàng"),
                ("Mapping loại tàu bay", "A320", "320", "A320", None, "Airbus A320", "Chuẩn hóa định danh loại tàu bay"),
                ("Mapping loại tàu bay", "A321", "321", "A321", None, "Airbus A321", "Chuẩn hóa định danh loại tàu bay"),
                ("Mapping loại tàu bay", "A350", "350", "A350", None, "Airbus A350", "Chuẩn hóa định danh loại tàu bay"),
                ("Mapping loại tàu bay", "B787", "787", "B787", None, "Boeing 787", "Chuẩn hóa định danh loại tàu bay"),
            ]
            conn.executemany("""INSERT INTO external_data(category,code,canonical_value,aircraft_type,
              customer,description,reason,updated_at) VALUES (?,?,?,?,?,?,?,?)""",
              [(*row, now()) for row in seed_rows])


def cellmap(headers: list[Any]) -> dict[str, int]:
    return {norm(value): idx for idx, value in enumerate(headers) if value not in (None, "")}


def import_amos() -> None:
    with db() as conn:
        if conn.execute("SELECT COUNT(*) FROM amp_task").fetchone()[0]:
            return
    sources = [
        (AMOS_DIR / "ALL AMP Task.xlsx", "VNA", "AMP"),
        (AMOS_DIR / "ALL Customer AMP.xlsx", "CUSTOMER", None),
    ]
    records: list[tuple] = []
    for path, source, sheet in sources:
        if not path.exists():
            continue
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet] if sheet else wb.active
        rows = ws.iter_rows(values_only=True)
        headers = list(next(rows))
        h = cellmap(headers)
        def get(row, *names):
            for name in names:
                idx = h.get(norm(name))
                if idx is not None and idx < len(row):
                    return row[idx]
            return None
        for row in rows:
            task_no = get(row, "Task No./Rev No.", "Jobcard No.", "Taskcard No./Rev")
            if not task_no:
                continue
            records.append((
                source, get(row, "A/C Type"), get(row, "Customer"), str(task_no).strip(), norm(task_no),
                get(row, "Taskcard Title", "Title"), get(row, "Description"), get(row, "Phase"),
                get(row, "Zone"), get(row, "Area"), get(row, "Panel"), get(row, "Special Code"),
                get(row, "Resource Type"), get(row, "Classification"), get(row, "Type Code"), get(row, "Qualification"),
                get(row, "Planning MHR"), get(row, "Information Skill"), get(row, "References"),
                get(row, "Linked Jobcards"), get(row, "Jobcards Title"),
            ))
    with db() as conn:
        conn.executemany(
            """INSERT INTO amp_task(source,aircraft_type,customer,task_no,task_key,title,description,
            phase,zone,area,panel,special_code,resource_type,classification,type_code,qualification,planning_mhr,
            information_skill,requirement_link,linked_jobcards,jobcards_title) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            records,
        )


def backfill_output_columns() -> None:
    """Populate fields added by the approved output workbook in existing demo data."""
    with db() as conn:
        missing_amp = conn.execute(
            "SELECT COUNT(*) FROM amp_task WHERE type_code IS NULL AND jobcards_title IS NULL"
        ).fetchone()[0]
    if missing_amp:
        updates: list[tuple[Any, Any, str, str]] = []
        for path, source, sheet in ((AMOS_DIR / "ALL AMP Task.xlsx", "VNA", "AMP"),
                                    (AMOS_DIR / "ALL Customer AMP.xlsx", "CUSTOMER", None)):
            if not path.exists():
                continue
            wb = load_workbook(path, read_only=True, data_only=True)
            ws = wb[sheet] if sheet else wb.active
            rows = ws.iter_rows(values_only=True); headers = list(next(rows)); h = cellmap(headers)
            for row in rows:
                def value(name: str):
                    idx = h.get(norm(name)); return row[idx] if idx is not None and idx < len(row) else None
                task_no = value("Task No./Rev No.") or value("Jobcard No.") or value("Taskcard No./Rev")
                if task_no:
                    updates.append((value("Type Code"), value("Jobcards Title"), source, norm(task_no)))
        with db() as conn:
            conn.executemany(
                "UPDATE amp_task SET type_code=?,jobcards_title=? WHERE source=? AND task_key=?",
                updates,
            )
    with db() as conn:
        pending = conn.execute("""SELECT i.id,i.task_no,t.customer,t.aircraft_type
          FROM evaluation_item i JOIN evaluation e ON e.id=i.evaluation_id
          JOIN tally_sheet t ON t.id=e.tally_id
          WHERE i.matched=1 AND i.type_code IS NULL AND i.jobcards_title IS NULL""").fetchall()
        for item in pending:
            amp = lookup_amp(conn, item["task_no"], item["customer"], item["aircraft_type"])
            if amp:
                conn.execute("UPDATE evaluation_item SET type_code=?,jobcards_title=? WHERE id=?",
                             (amp["type_code"], amp["jobcards_title"], item["id"]))


def parse_vietjet(path: Path) -> list[dict[str, Any]]:
    ws = load_workbook(path, read_only=True, data_only=True).active
    rows = ws.iter_rows(values_only=True)
    headers = list(next(rows))
    h = cellmap(headers)
    required = ["WORK STEP / EVENT NUMBER", "TITLE", "EVENT"]
    if any(key not in h for key in required):
        raise ValueError("Không nhận diện được cấu trúc VietJet: thiếu Work Step / Event Number, Title hoặc Event.")
    output = []
    for row in rows:
        task = row[h["WORK STEP / EVENT NUMBER"]]
        if task in (None, ""):
            continue
        def val(name):
            idx = h.get(name)
            return row[idx] if idx is not None and idx < len(row) else None
        output.append({"seq": val("SEQ. NO."), "section": "TALLY SHEET", "task_no": task,
                       "source_title": val("TITLE"), "event_type": val("EVENT"),
                       "rii": val("RII"), "source_note": val("NOTE")})
    return output


def parse_lufthansa(path: Path) -> list[dict[str, Any]]:
    ws = load_workbook(path, read_only=True, data_only=True).active
    matrix = [list(row) for row in ws.iter_rows(values_only=True)]
    output: list[dict[str, Any]] = []
    section = ""
    headers: dict[str, int] = {}
    for row in matrix:
        first = str(row[0]).strip() if row and row[0] not in (None, "") else ""
        if re.match(r"^\d+\.\s", first):
            section = first
            headers = {}
            continue
        rowmap = cellmap(row)
        if "CRI" in rowmap and ("TITEL" in rowmap or "TITLE" in rowmap):
            headers = rowmap
            continue
        if not headers or "CRI" not in headers:
            continue
        cri_idx = headers["CRI"]
        cri = row[cri_idx] if cri_idx < len(row) else None
        if cri in (None, "", "CRI"):
            continue
        def val(*names):
            for name in names:
                idx = headers.get(name)
                if idx is not None and idx < len(row):
                    return row[idx]
            return None
        output.append({"seq": len(output) + 1, "section": section or "OTHER", "task_no": cri,
                       "source_title": val("TITEL", "TITLE", "MS DESCRIPTION"),
                       "event_type": "MS Item" if "MS ITEMS" in section.upper() else section,
                       "rii": None, "source_note": val("MS DESCRIPTION", "DESCRIPTION"),
                       "source_zone": val("ZONE"), "source_ata": val("ATA")})
    if not output:
        raise ValueError("Không nhận diện được các section có cột CRI trong file Lufthansa.")
    return output


def lookup_amp(conn: sqlite3.Connection, task_no: Any, customer: str, aircraft_type: str) -> sqlite3.Row | None:
    key = norm(task_no)
    preferred_source = "CUSTOMER" if customer in {"VA-VJ", "DLH"} else "VNA"
    aircraft_key = canonical_aircraft(aircraft_type)
    return conn.execute(
        """SELECT * FROM amp_task WHERE task_key=?
        ORDER BY CASE WHEN source=? THEN 0 ELSE 1 END,
        CASE WHEN UPPER(COALESCE(customer,''))=UPPER(?) THEN 0 ELSE 1 END,
        CASE WHEN UPPER(COALESCE(aircraft_type,''))=UPPER(?) THEN 0 ELSE 1 END,
        id ASC LIMIT 1""",
        (key, preferred_source, customer, aircraft_key),
    ).fetchone()


def create_evaluation(path: Path, file_name: str, customer: str, aircraft_reg: str,
                      aircraft_type: str, check_type: str, uploader: str) -> str:
    adapter = "VietJet" if customer == "VA-VJ" else "Lufthansa"
    parsed = parse_vietjet(path) if adapter == "VietJet" else parse_lufthansa(path)
    tally_id = f"TS-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:5].upper()}"
    evaluation_id = f"EV-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:5].upper()}"
    matched = 0
    with db() as conn:
        conn.execute("""INSERT INTO tally_sheet(id,file_name,stored_path,customer,aircraft_reg,aircraft_type,
                     check_type,adapter,uploader,uploaded_at,row_count) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                     (tally_id,file_name,str(path),customer,aircraft_reg,aircraft_type,check_type,adapter,uploader,now(),len(parsed)))
        conn.execute("""INSERT INTO evaluation(id,tally_id,revision,created_at,updated_at)
                     VALUES (?,?,?,?,?)""", (evaluation_id,tally_id,"REV00",now(),now()))
        for item in parsed:
            amp = lookup_amp(conn, item["task_no"], customer, aircraft_type)
            if amp:
                matched += 1
                important = 1 if norm(amp["classification"]) == "WATCH ITEM" else 0
                values = (1, amp["source"], amp["title"], amp["description"], amp["phase"],
                          amp["zone"] or item.get("source_zone"), amp["area"], amp["panel"], amp["special_code"],
                          amp["resource_type"], amp["classification"], amp["qualification"],
                          mhr_hours(amp["planning_mhr"]), amp["information_skill"], amp["requirement_link"],
                          amp["linked_jobcards"], amp["type_code"], amp["jobcards_title"],
                          important, "AMOS Watch Item" if important else None, 0)
            else:
                values = (0,None,item.get("source_title"),item.get("source_note"),None,item.get("source_zone"),
                          None,None,None,None,None,None,0,None,None,None,None,None,0,None,1)
            conn.execute("""INSERT INTO evaluation_item(evaluation_id,seq,section,task_no,source_title,event_type,rii,
              source_note,matched,amp_source,title,description,phase,zone,area,panel,special_code,resource_type,
              classification,qualification,planning_mhr,information_skill,requirement_link,linked_jobcards,
              type_code,jobcards_title,important_job,important_source,not_in_database,updated_at)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (evaluation_id,item.get("seq"),item.get("section"),str(item["task_no"]),item.get("source_title"),
               item.get("event_type"),item.get("rii"),item.get("source_note"),*values,now()))
        conn.execute("UPDATE tally_sheet SET matched_count=? WHERE id=?", (matched,tally_id))
    return evaluation_id


def seed_samples() -> None:
    with db() as conn:
        if conn.execute("SELECT COUNT(*) FROM tally_sheet").fetchone()[0]:
            return
    samples = [
        ("(Sample) TALLY SHEET WP VJC-A699-24MT2026 REV02.xlsx", "VA-VJ", "VJC-A699", "A320", "24MT"),
        ("(Sample) Workpackage-Summary for D-AIXB_H-25-29102025.xlsx", "DLH", "D-AIXB", "A350", "H-CHECK"),
    ]
    for name, customer, reg, aircraft, check in samples:
        src = SAMPLES_DIR / name
        if src.exists():
            dest = UPLOADS / f"sample-{name}"
            shutil.copy2(src, dest)
            create_evaluation(dest, name, customer, reg, aircraft, check, "Dữ liệu mẫu")


@app.on_event("startup")
def startup():
    init_db()
    import_amos()
    backfill_output_columns()
    seed_samples()


@app.get("/")
def index():
    return FileResponse(ROOT / "templates" / "index.html")


@app.get("/api/dashboard")
def dashboard():
    with db() as conn:
        totals = conn.execute("""SELECT COUNT(*) tally_count, SUM(row_count) item_count,
          SUM(matched_count) matched_count FROM tally_sheet""").fetchone()
        evaluations = [dict(r) for r in conn.execute("""SELECT e.*,t.file_name,t.customer,t.aircraft_reg,t.aircraft_type,
          t.check_type,t.adapter,t.row_count,t.matched_count,t.uploaded_at
          FROM evaluation e JOIN tally_sheet t ON t.id=e.tally_id ORDER BY e.created_at DESC""")]
        amp_count = conn.execute("SELECT COUNT(*) FROM amp_task").fetchone()[0]
    return {"totals": dict(totals), "amp_count": amp_count, "evaluations": evaluations}


@app.get("/api/data/amos")
def browse_amos(q: str = "", source: str = "all", aircraft_type: str = "all",
                customer: str = "all", classification: str = "all", page: int = 1,
                page_size: int = 40):
    page = max(1, page); page_size = min(max(10, page_size), 100)
    where = ["1=1"]; params: list[Any] = []
    if q.strip():
        where.append("(task_no LIKE ? OR title LIKE ? OR description LIKE ? OR special_code LIKE ?)")
        params.extend([f"%{q.strip()}%"] * 4)
    for column, value in (("source", source), ("aircraft_type", aircraft_type),
                          ("customer", customer), ("classification", classification)):
        if value != "all":
            where.append(f"COALESCE({column},'')=?"); params.append(value)
    predicate = " AND ".join(where)
    with db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM amp_task WHERE {predicate}", params).fetchone()[0]
        rows = [dict(r) for r in conn.execute(f"""SELECT id,source,aircraft_type,customer,task_no,title,
          phase,zone,special_code,classification,planning_mhr,qualification,description,area,panel,
          resource_type,information_skill,requirement_link,linked_jobcards FROM amp_task
          WHERE {predicate} ORDER BY task_no LIMIT ? OFFSET ?""",
          (*params, page_size, (page - 1) * page_size))]
        def distinct(column: str, limit: int = 80):
            return [r[0] for r in conn.execute(f"""SELECT DISTINCT {column} FROM amp_task
              WHERE {column} IS NOT NULL AND TRIM({column})<>'' ORDER BY {column} LIMIT ?""", (limit,))]
        filters = {"sources": distinct("source"), "aircraft_types": distinct("aircraft_type"),
                   "customers": distinct("customer"), "classifications": distinct("classification")}
        stats = dict(conn.execute("""SELECT COUNT(*) total,
          SUM(CASE WHEN source='VNA' THEN 1 ELSE 0 END) vna,
          SUM(CASE WHEN source='CUSTOMER' THEN 1 ELSE 0 END) customer,
          SUM(CASE WHEN UPPER(COALESCE(classification,''))='WATCH ITEM' THEN 1 ELSE 0 END) watch_items
          FROM amp_task""").fetchone())
    return {"items": rows, "total": total, "page": page, "page_size": page_size,
            "filters": filters, "stats": stats}


@app.get("/api/data/external")
def browse_external(q: str = "", category: str = "all", status: str = "all",
                    page: int = 1, page_size: int = 40):
    page = max(1, page); page_size = min(max(10, page_size), 100)
    where = ["1=1"]; params: list[Any] = []
    if q.strip():
        where.append("(code LIKE ? OR canonical_value LIKE ? OR description LIKE ? OR reason LIKE ?)")
        params.extend([f"%{q.strip()}%"] * 4)
    if category != "all": where.append("category=?"); params.append(category)
    if status != "all": where.append("status=?"); params.append(status)
    predicate = " AND ".join(where)
    with db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM external_data WHERE {predicate}", params).fetchone()[0]
        rows = [dict(r) for r in conn.execute(f"""SELECT * FROM external_data WHERE {predicate}
          ORDER BY category,code LIMIT ? OFFSET ?""", (*params,page_size,(page-1)*page_size))]
        categories = [r[0] for r in conn.execute("SELECT DISTINCT category FROM external_data ORDER BY category")]
        statuses = [r[0] for r in conn.execute("SELECT DISTINCT status FROM external_data ORDER BY status")]
        category_counts = [dict(r) for r in conn.execute("""SELECT category,COUNT(*) record_count
          FROM external_data GROUP BY category ORDER BY category""")]
    return {"items":rows,"total":total,"page":page,"page_size":page_size,
            "filters":{"categories":categories,"statuses":statuses},"category_counts":category_counts}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), customer: str = Form(...), aircraft_reg: str = Form(""),
                 aircraft_type: str = Form(""), check_type: str = Form(""), uploader: str = Form("Demo User")):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Chỉ hỗ trợ file Excel .xlsx")
    safe_name = re.sub(r"[^\w.() -]", "_", Path(file.filename).name)
    dest = UPLOADS / f"{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:5]}-{safe_name}"
    content = await file.read()
    if len(content) > 30 * 1024 * 1024:
        raise HTTPException(400, "File vượt quá giới hạn 30 MB")
    dest.write_bytes(content)
    try:
        evaluation_id = create_evaluation(dest, file.filename, customer, aircraft_reg, aircraft_type, check_type, uploader)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc
    return {"evaluation_id": evaluation_id}


@app.get("/api/evaluations/{evaluation_id}")
def evaluation_detail(evaluation_id: str, q: str = "", status: str = "all", page: int = 1,
                      page_size: int = 50, sort_by: str = "seq", sort_dir: str = "asc"):
    page = max(1, page); page_size = min(max(10,page_size),200)
    where = ["i.evaluation_id=?"]; params: list[Any] = [evaluation_id]
    if q:
        where.append("(i.task_no LIKE ? OR i.title LIKE ? OR i.description LIKE ?)")
        params.extend([f"%{q}%"] * 3)
    if status == "matched": where.append("i.matched=1")
    if status == "unmatched": where.append("i.matched=0")
    if status == "important": where.append("i.important_job=1")
    predicate = " AND ".join(where)
    with db() as conn:
        header = conn.execute("""SELECT e.*,t.file_name,t.customer,t.aircraft_reg,t.aircraft_type,t.check_type,
          t.adapter,t.version,t.uploaded_at,t.uploader FROM evaluation e JOIN tally_sheet t ON t.id=e.tally_id WHERE e.id=?""",
          (evaluation_id,)).fetchone()
        if not header: raise HTTPException(404, "Không tìm thấy lần đánh giá")
        total = conn.execute(f"SELECT COUNT(*) FROM evaluation_item i WHERE {predicate}", params).fetchone()[0]
        sortable = {"task_no", "title", "description", "phase", "zone", "area", "panel", "special_code",
                    "resource_type", "classification", "type_code", "qualification", "planning_mhr",
                    "information_skill", "requirement_link", "linked_jobcards", "jobcards_title",
                    "important_job", "not_in_database", "seq"}
        order_col = sort_by if sort_by in sortable else "seq"
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
        items = [dict(r) for r in conn.execute(f"SELECT i.* FROM evaluation_item i WHERE {predicate} ORDER BY i.{order_col} {direction},i.id ASC LIMIT ? OFFSET ?",
                 (*params,page_size,(page-1)*page_size))]
        summary = dict(conn.execute("""SELECT COUNT(*) total, SUM(matched) matched, SUM(not_in_database) unmatched,
          SUM(important_job) important, ROUND(SUM(COALESCE(reviewed_mhr,planning_mhr)),2) total_mhr
          FROM evaluation_item WHERE evaluation_id=?""", (evaluation_id,)).fetchone())
        special = [dict(r) for r in conn.execute("""SELECT COALESCE(NULLIF(special_code,''),'Chưa phân loại') special_code,
          COUNT(*) task_count,ROUND(SUM(COALESCE(reviewed_mhr,planning_mhr)),2) mhr FROM evaluation_item
          WHERE evaluation_id=? GROUP BY 1 ORDER BY mhr DESC LIMIT 12""", (evaluation_id,))]
    return {"header":dict(header),"summary":summary,"items":items,"special_codes":special,"filtered_total":total,"page":page,"page_size":page_size}


class ItemUpdate(BaseModel):
    reviewed_mhr: float | None = None
    important_job: bool | None = None
    review_note: str | None = None
    reason: str
    changed_by: str = "Demo User"


@app.patch("/api/items/{item_id}")
def update_item(item_id: int, payload: ItemUpdate):
    if not payload.reason.strip(): raise HTTPException(400,"Bắt buộc nhập lý do thay đổi")
    with db() as conn:
        row = conn.execute("SELECT * FROM evaluation_item WHERE id=?",(item_id,)).fetchone()
        if not row: raise HTTPException(404,"Không tìm thấy task")
        changes = {k:v for k,v in {"reviewed_mhr":payload.reviewed_mhr,"important_job":int(payload.important_job) if payload.important_job is not None else None,"review_note":payload.review_note}.items() if v is not None}
        for field,value in changes.items():
            if str(row[field] or "") != str(value):
                conn.execute("INSERT INTO change_log(evaluation_id,item_id,field_name,old_value,new_value,reason,changed_by,changed_at) VALUES (?,?,?,?,?,?,?,?)",
                             (row["evaluation_id"],item_id,field,row[field],value,payload.reason,payload.changed_by,now()))
                conn.execute(f"UPDATE evaluation_item SET {field}=?,updated_at=? WHERE id=?",(value,now(),item_id))
        conn.execute("UPDATE evaluation SET updated_at=? WHERE id=?",(now(),row["evaluation_id"]))
    return {"ok":True}


class EvaluationUpdate(BaseModel):
    tat_review: str | None = None
    assumptions: str | None = None
    notes: str | None = None
    prepared_by: str | None = None
    approved_by: str | None = None
    status: str | None = None


@app.patch("/api/evaluations/{evaluation_id}")
def update_evaluation(evaluation_id: str, payload: EvaluationUpdate):
    values = payload.model_dump(exclude_none=True)
    if values:
        fields = ",".join(f"{key}=?" for key in values)
        with db() as conn:
            conn.execute(f"UPDATE evaluation SET {fields},updated_at=? WHERE id=?",(*values.values(),now(),evaluation_id))
    return {"ok":True}


@app.get("/api/evaluations/{evaluation_id}/report/{kind}")
def report(evaluation_id: str, kind: str):
    conditions = {"important":"important_job=1","database":"not_in_database=1","scope":"0"}
    if kind not in conditions: raise HTTPException(404,"Báo cáo không tồn tại")
    with db() as conn:
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM evaluation_item WHERE evaluation_id=? AND {conditions[kind]} ORDER BY id",(evaluation_id,))]
    return {"items":rows,"available":kind != "scope","message":"Chưa có dữ liệu Task–Check/Linked Check để đánh giá tự động." if kind=="scope" else None}


def style_sheet(ws):
    blue = "003B71"; gold = "C89B3C"
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor=blue); cell.font=Font(color="FFFFFF",bold=True)
        cell.alignment=Alignment(wrap_text=True,vertical="center")
    ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
    for col in range(1,ws.max_column+1):
        width=min(42,max(12,max(len(str(ws.cell(r,col).value or "")) for r in range(1,min(ws.max_row,80)+1))+2))
        ws.column_dimensions[get_column_letter(col)].width=width
    ws.sheet_properties.tabColor=gold


@app.get("/api/evaluations/{evaluation_id}/export")
def export_excel(evaluation_id: str):
    with db() as conn:
        header=conn.execute("""SELECT e.*,t.* FROM evaluation e JOIN tally_sheet t ON t.id=e.tally_id WHERE e.id=?""",(evaluation_id,)).fetchone()
        if not header: raise HTTPException(404,"Không tìm thấy lần đánh giá")
        items=[dict(r) for r in conn.execute("SELECT * FROM evaluation_item WHERE evaluation_id=? ORDER BY id",(evaluation_id,))]
    wb=Workbook(); wb.remove(wb.active)
    columns=[("Task No.","task_no"),("Taskcard Title","title"),("Description","description"),("Phase","phase"),("Zone","zone"),("Area","area"),("Panel","panel"),("Special Code","special_code"),("Resource Type","resource_type"),("Classification","classification"),("Type Code","type_code"),("Qualification","qualification"),("Planning MHR","planning_mhr"),("Information Skill","information_skill"),("Requirement Link","requirement_link"),("Linked Jobcards","linked_jobcards"),("Jobcards Title","jobcards_title"),("Important Job","important_job"),("Not included in Database","not_in_database")]
    for title, subset in [("Detailed Task List",items),("Important Jobs",[x for x in items if x["important_job"]]),("Task out of Check Type Scope",[]) ,("Database to be Updated",[x for x in items if x["not_in_database"]])]:
        ws=wb.create_sheet(title); ws.append([c[0] for c in columns])
        for item in subset: ws.append(["X" if key in {"important_job","not_in_database"} and item[key] else item[key] for _,key in columns])
        if title=="Task out of Check Type Scope": ws.append(["Chưa có dữ liệu Task–Check/Linked Check để đánh giá tự động."])
        style_sheet(ws)
    ws=wb.create_sheet("FINAL EVALUATION",0)
    ws.append(["FINAL EVALUATION",""]); ws.append(["Thông tin","Giá trị"])
    fields=[("Khách hàng",header["customer"]),("Số đăng ký",header["aircraft_reg"]),("Loại tàu bay",header["aircraft_type"]),("Check Type",header["check_type"]),("Workpack revision",header["revision"]),("TAT review",header["tat_review"]),("Tổng task",len(items)),("Task khớp",sum(x["matched"] for x in items)),("Task thiếu DB",sum(x["not_in_database"] for x in items)),("Important Job",sum(x["important_job"] for x in items)),("Tổng MHR",round(sum(x["reviewed_mhr"] if x["reviewed_mhr"] is not None else x["planning_mhr"] for x in items),2)),("Giả định",header["assumptions"]),("Ghi chú",header["notes"]),("Người lập",header["prepared_by"]),("Người phê duyệt",header["approved_by"])]
    for row in fields: ws.append(row)
    ws["A1"].fill=PatternFill("solid",fgColor="003B71"); ws["A1"].font=Font(color="FFFFFF",bold=True,size=16); ws.merge_cells("A1:B1"); ws.column_dimensions["A"].width=28; ws.column_dimensions["B"].width=60
    stream=io.BytesIO(); wb.save(stream); stream.seek(0)
    name=f"VAECO_WP_Evaluation_{evaluation_id}.xlsx"
    return StreamingResponse(stream,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f'attachment; filename="{name}"'})


@app.get("/api/tally/{tally_id}/download")
def download_tally(tally_id: str):
    with db() as conn: row=conn.execute("SELECT * FROM tally_sheet WHERE id=?",(tally_id,)).fetchone()
    if not row or not Path(row["stored_path"]).exists(): raise HTTPException(404,"Không tìm thấy file gốc")
    return FileResponse(row["stored_path"],filename=row["file_name"])


@app.get("/api/evaluations/{evaluation_id}/history")
def history(evaluation_id: str):
    with db() as conn: rows=[dict(r) for r in conn.execute("SELECT * FROM change_log WHERE evaluation_id=? ORDER BY changed_at DESC",(evaluation_id,))]
    return {"items":rows}
