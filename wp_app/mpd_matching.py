"""Layer 1 matching: Tally Sheet task -> AMOS records by MPD key.

This is the main matching flow of the merged program (``services.populate_evaluation_items``
runs it first). The fork's prefix / Title layers (``services.lookup_amp`` with
``include_exact=False``) only run for rows that this flow cannot match, and only
as suggestions without MHR.

Order of the sources (see ``matching_plan``):
  [Customer AMP of the customer, if configured in matching_config.CUSTOMER_FIRST]
  -> ALL AMP Task (VNA), HVN AMP Name first, then newest AMP Date
  -> Customer AMP of the same customer (exact Jobcard No.)
  -> Customer AMP of another customer (exact Jobcard No., always last)
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime
from typing import Any

from .matching import canonical_customer, normalize, parse_mhr
from .matching_config import CUSTOMER_ALIASES, CUSTOMER_FIRST


SOURCE_LABEL = {"VNA": "ALL AMP Task", "CUSTOMER": "Customer AMP"}

# Matching steps (tried in order, see matching_plan)
STEP_CUSTOMER_FIRST = "CUSTOMER_FIRST"   # Customer AMP of this customer, MPD key, shared like VNA items
STEP_VNA = "VNA"                         # ALL AMP Task, MPD key, HVN first then newest AMP Date
STEP_CUSTOMER_SAME = "CUSTOMER_SAME"     # Customer AMP of this customer, exact number
STEP_CUSTOMER_OTHER = "CUSTOMER_OTHER"   # Customer AMP of any other customer, exact number (always last)
GROUP_STEPS = {STEP_CUSTOMER_FIRST, STEP_VNA}   # steps that share items among Tally rows of one MPD key
STEP_LABEL = {
    STEP_CUSTOMER_FIRST: "Customer AMP của khách hàng (ưu tiên trước ALL AMP Task) – theo MPD key",
    STEP_VNA: "ALL AMP Task – theo MPD key, ưu tiên AMP Name bắt đầu bằng HVN, sau đó AMP Date mới nhất",
    STEP_CUSTOMER_SAME: "Customer AMP của khách hàng – số Jobcard khớp chính xác",
    STEP_CUSTOMER_OTHER: "Customer AMP của khách hàng khác – số Jobcard khớp chính xác",
}
# Value stored in evaluation_item.match_method for each step
STEP_METHOD = {
    STEP_CUSTOMER_FIRST: "MPD_CUSTOMER_FIRST",
    STEP_VNA: "MPD_VNA",
    STEP_CUSTOMER_SAME: "CR_SAME_CUSTOMER",
    STEP_CUSTOMER_OTHER: "CR_OTHER_CUSTOMER",
}
METHOD_STEP = {method: step for step, method in STEP_METHOD.items()}


# ---------------------------------------------------------------------------
# Keys and helpers
# ---------------------------------------------------------------------------
# MPD task number = the part of the number given by the manufacturer.
# Everything after it (operator sub-numbers such as -1, -1-1, -VJC, -ENG1, /rev)
# is ignored. Longer A350 formats are tried before the A320 format.
MPD_PATTERNS = [
    re.compile(r"^(ZL-\d{3}-[A-Z0-9]{5}-\d{2})(?![A-Z0-9])"),   # A350 zonal: ZL-455-00Z01-01
    re.compile(r"^(\d{6}-[A-Z0-9]{5}-\d{2})(?![A-Z0-9])"),      # A350: 271400-00M10-01
    re.compile(r"^(\d{6}-[A-Z0-9]{2})(?![A-Z0-9])"),            # A320 family: 253000-02, 722000-C3
]

# VietJet Title format: "TASKNO (REV) / TITLE"
TITLE_REF = re.compile(r"^\s*([^\s/(]+)\s*\(([^)]*)\)\s*/\s*(.*)$", re.S)


def mpd_key(value: Any) -> str | None:
    """MPD task number of a task/taskcard number, or None if it has no MPD format."""
    text = normalize(value).replace(" ", "")
    for pattern in MPD_PATTERNS:
        found = pattern.match(text)
        if found:
            return found.group(1)
    return None


def base_key(value: Any) -> str:
    """Full number without the '/revision' part (used for exact matching)."""
    return normalize(value).replace(" ", "").split("/")[0]


def match_key(value: Any) -> str:
    """Grouping key of a Tally row: MPD key, or the full number without revision."""
    return mpd_key(value) or base_key(value)


def aircraft_family(value: Any) -> str | None:
    text = normalize(value).replace("AIRBUS", "").replace("BOEING", "").replace("-", "").replace(" ", "")
    if not text:
        return None
    if "350" in text:
        return "350"
    if "787" in text:
        return "787"
    if "ATR" in text:
        return "ATR"
    if text.startswith(("A32", "A31", "A21", "32", "31")):
        return "32S"
    return None


def side_of(*texts: Any) -> str | None:
    """L / R position hint from engine number or LH/RH wording; None if absent or ambiguous."""
    text = " ".join(normalize(t) for t in texts if t)
    left = bool(re.search(r"ENG\s*#?\s*1\b|\bLH\b|\bLEFT\b", text))
    right = bool(re.search(r"ENG\s*#?\s*2\b|\bRH\b|\bRIGHT\b", text))
    if left and not right:
        return "L"
    if right and not left:
        return "R"
    return None


def iso_date(value: Any) -> str | None:
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    text = str(value or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def mhr_value(value: Any) -> float:
    return parse_mhr(value) or 0.0


def split_tokens(value: Any) -> list[str]:
    return [t.strip() for t in re.split(r"[,\n]", str(value or "")) if t.strip()]


def tally_title_text(title: Any) -> str:
    """Title without the 'TASKNO (REV) /' prefix."""
    found = TITLE_REF.match(str(title or ""))
    return (found.group(3) if found else str(title or "")).strip()


# ---------------------------------------------------------------------------
# Which Tally rows are matched, and with which task number
# ---------------------------------------------------------------------------
def prepare_row(adapter: Any, row: dict[str, Any]) -> dict[str, Any]:
    """Add task_ref (number used for matching), side and eligible to a parsed Tally row.

    VietJet: the Title reads "TASKNO (REV) / TITLE". For a Block Taskcard the task
    number is in Work Step / Event Number; for other events that column holds an
    AMOS event ID, so the task number is taken from the Title. An event with no
    task number in its Title has nothing to match (NOT_APPLICABLE).
    Other layouts (Lufthansa): CRI is the task number of every row.
    """
    title = row.get("source_title")
    task_no = str(row.get("task_no") or "").strip()
    if normalize(adapter) == "VIETJET":
        found = TITLE_REF.match(str(title or ""))
        is_block = normalize(row.get("event_type")) == "BLOCK TASKCARD"
        row["task_ref"] = found.group(1) if found else task_no
        row["eligible"] = bool(found) or is_block
        row["side"] = side_of(title)
    else:
        row["task_ref"] = task_no
        row["eligible"] = bool(task_no)
        row["side"] = side_of(task_no, title)
    row["match_key"] = match_key(row["task_ref"])
    return row


# ---------------------------------------------------------------------------
# Source order
# ---------------------------------------------------------------------------
def customer_codes(customer: Any) -> set[str]:
    """All spellings that mean this customer in ALL Customer AMP."""
    key = canonical_customer(customer)
    if not key:
        return set()
    aliases = next((v for k, v in CUSTOMER_ALIASES.items() if normalize(k) == key), set())
    return {key} | {normalize(a) for a in aliases}


def is_customer_first(customer: Any, aircraft_type: Any) -> bool:
    families = next((v for k, v in CUSTOMER_FIRST.items()
                     if canonical_customer(k) == canonical_customer(customer)), None)
    return families is not None and aircraft_family(aircraft_type) in families


def matching_plan(customer: Any, aircraft_type: Any) -> list[str]:
    """Order in which the sources are searched for this Tally Sheet."""
    first = [STEP_CUSTOMER_FIRST] if is_customer_first(customer, aircraft_type) else []
    return first + [STEP_VNA, STEP_CUSTOMER_SAME, STEP_CUSTOMER_OTHER]


def key_condition(task_ref: Any) -> tuple[str, str]:
    """MPD key when the number has one, otherwise the full number without revision."""
    key = mpd_key(task_ref)
    return ("mpd_key", key) if key else ("task_base", base_key(task_ref))


def customer_filter(codes: set[str], same: bool) -> tuple[str, list[str]]:
    marks = ",".join("?" * len(codes)) or "''"
    op = "IN" if same else "NOT IN"
    return f"UPPER(TRIM(COALESCE(customer,''))) {op} ({marks})", sorted(codes)


def amp_candidates(conn: sqlite3.Connection, task_ref: Any, family: str | None) -> list[sqlite3.Row]:
    """Every ALL AMP Task row for this task, in priority order (HVN first, then newest AMP Date)."""
    column, value = key_condition(task_ref)
    sql = f"SELECT * FROM amp_task WHERE source='VNA' AND {column}=?"
    params: list[Any] = [value]
    if family:
        sql += " AND aircraft_family=?"
        params.append(family)
    sql += """ ORDER BY CASE WHEN UPPER(COALESCE(amp_name,'')) LIKE 'HVN%' THEN 0 ELSE 1 END,
              COALESCE(amp_date,'') DESC, amp_name, taskcard_no, id"""
    return conn.execute(sql, params).fetchall()


def customer_candidates(conn: sqlite3.Connection, task_ref: Any, codes: set[str] | None,
                        family: str | None) -> list[sqlite3.Row]:
    """Customer AMP rows with the same MPD key (only these customers if codes is given)."""
    column, value = key_condition(task_ref)
    sql = f"SELECT * FROM amp_task WHERE source='CUSTOMER' AND {column}=?"
    params: list[Any] = [value]
    if codes is not None:
        condition, values = customer_filter(codes, same=True)
        sql += f" AND {condition}"
        params += values
    if family:
        sql += " AND aircraft_family=?"
        params.append(family)
    return conn.execute(sql + " ORDER BY task_no, id", params).fetchall()


def find_group_items(conn: sqlite3.Connection, step: str, task_ref: Any, codes: set[str],
                     family: str | None) -> list[sqlite3.Row]:
    """Items of ONE source for an MPD key; they are then shared among the Tally rows."""
    if step == STEP_VNA:
        candidates = amp_candidates(conn, task_ref, family)
        if not candidates:
            return []
        chosen = candidates[0]["amp_name"]
        return [c for c in candidates if c["amp_name"] == chosen]
    if step == STEP_CUSTOMER_FIRST:
        # one row per Jobcard No. (duplicate rows of the same jobcard would double the MHR)
        items, seen = [], set()
        for c in customer_candidates(conn, task_ref, codes, family):
            if normalize(c["task_no"]) not in seen:
                seen.add(normalize(c["task_no"]))
                items.append(c)
        return items
    return []


def find_exact_customer_row(conn: sqlite3.Connection, step: str, task_ref: Any, codes: set[str],
                            family: str | None) -> sqlite3.Row | None:
    """Customer AMP fallback: exact Jobcard No. of this customer (SAME) or of other customers (OTHER)."""
    condition, values = customer_filter(codes, same=step == STEP_CUSTOMER_SAME)
    return conn.execute(
        f"""SELECT * FROM amp_task WHERE source='CUSTOMER' AND task_key=? AND {condition}
        ORDER BY CASE WHEN aircraft_family=? THEN 0 ELSE 1 END, id LIMIT 1""",
        (normalize(task_ref), *values, family),
    ).fetchone()


# ---------------------------------------------------------------------------
# Sharing the items of one AMP among the Tally rows of one MPD key
# ---------------------------------------------------------------------------
SIDE_ORDER = {"L": 0, "R": 1}


def item_number(item: sqlite3.Row) -> int:
    found = re.search(r"\d+", str(item["taskcard_ident"] or ""))
    return int(found.group()) if found else 99


def item_side(item: sqlite3.Row) -> str | None:
    """LH/RH of an AMP item: from Ident./Area, or from the jobcard number (e.g. -ENG1)."""
    return item["side"] or side_of(item["task_no"])


def distribute(rows: list[dict], items: list[sqlite3.Row]) -> list[tuple[list[sqlite3.Row], str | None]]:
    """Share the items of the chosen AMP among the Tally rows with the same MPD key."""
    n, m = len(rows), len(items)
    if m == 1:
        note = "Nhiều dòng Tally dùng chung 1 item AMP – kiểm tra MHR trùng" if n > 1 else None
        return [([items[0]], note) for _ in rows]
    if n == 1:
        return [(list(items), None)]
    row_order = sorted(range(n), key=lambda i: (SIDE_ORDER.get(rows[i].get("side"), 2), i))
    item_order = sorted(items, key=lambda it: (SIDE_ORDER.get(item_side(it), 2), item_number(it),
                                               str(it["taskcard_no"] or it["task_no"] or "")))
    result: list[tuple[list[sqlite3.Row], str | None]] = [([], None)] * n
    for pos, i in enumerate(row_order):
        assigned = [item_order[min(pos, m - 1)]]
        if pos == n - 1 and m > n:
            assigned += item_order[n:]
        sides_ok = all(rows[i].get("side") and item_side(it) == rows[i].get("side") for it in assigned)
        if n != m:
            note = f"Số dòng Tally ({n}) khác số item AMP ({m}) – cần review"
        elif not sides_ok:
            note = "Ghép theo thứ tự ITEM (không xác định được LH/RH) – cần kiểm tra"
        else:
            note = None
        result[i] = (assigned, note)
    return result


# Natural key of an AMP record: stays valid when the MiniDB is rebuilt (row ids change).
NATURAL_KEY_FIELDS = ("source", "amp_name", "taskcard_no", "taskcard_ident", "task_no",
                      "customer", "effectivity", "aircraft_type")


def natural_key(item: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {field: item[field] for field in NATURAL_KEY_FIELDS}


def find_by_natural_key(conn: sqlite3.Connection, key: dict[str, Any]) -> sqlite3.Row | None:
    where = " AND ".join(f"{field} IS ?" for field in NATURAL_KEY_FIELDS)
    return conn.execute(f"SELECT * FROM amp_task WHERE {where} ORDER BY id LIMIT 1",
                        tuple(key.get(field) for field in NATURAL_KEY_FIELDS)).fetchone()


def amos_reference(item: sqlite3.Row) -> str:
    source = SOURCE_LABEL.get(item["source"], item["source"])
    if item["source"] == "VNA":
        parts = [source, item["amp_name"], item["taskcard_no"] or item["task_no"], item["taskcard_ident"]]
    else:
        parts = [source, item["customer"] or "—", item["task_no"]]
    return " | ".join(str(p) for p in parts if p not in (None, ""))


def merge_items(items: list[sqlite3.Row]) -> dict[str, Any]:
    """Combine one or more AMP items into the values of one Tally row."""
    def distinct(field: str, sep: str = ", ", tokens: bool = False) -> str | None:
        seen: list[str] = []
        for it in items:
            if tokens:
                parts = split_tokens(it[field])
            else:
                parts = [str(it[field]).strip()] if it[field] not in (None, "") else []
            for part in parts:
                if part and part not in seen:
                    seen.append(part)
        return sep.join(seen) or None

    first = items[0]
    classification = distinct("classification", tokens=True)
    important = "WATCH ITEM" in [normalize(t) for t in split_tokens(classification)]
    return {
        "amp_source": first["source"],
        "amos_reference": "; ".join(amos_reference(it) for it in items),
        "amp_refs": json.dumps([natural_key(it) for it in items], ensure_ascii=False),
        "title": first["title"], "description": distinct("description", sep="\n"),
        "phase": distinct("phase"), "zone": distinct("zone", tokens=True),
        "area": distinct("area", tokens=True), "panel": distinct("panel", tokens=True),
        "special_code": distinct("special_code", tokens=True),
        "resource_type": distinct("resource_type", tokens=True), "classification": classification,
        "qualification": distinct("qualification", sep="; "),
        "planning_mhr": round(sum(mhr_value(it["planning_mhr"]) for it in items), 2),
        "information_skill": distinct("information_skill", sep="; "),
        "requirement_link": distinct("requirement_link", sep="\n"),
        "linked_jobcards": distinct("linked_jobcards", tokens=True),
        "type_code": distinct("type_code", tokens=True), "jobcards_title": distinct("jobcards_title", sep="; "),
        "important_job": 1 if important else 0, "important_source": "AMOS Watch Item" if important else None,
        # bookkeeping for the fork's columns
        "match_source_id": first["id"],
        "match_candidate_count": len(items),
        "suggested_task_no": first["taskcard_no"] or first["task_no"],
        "suggested_title": first["title"],
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def match_rows(conn: sqlite3.Connection, parsed: list[dict], customer: str, aircraft_type: str) -> list[dict]:
    """Return the matching result for every prepared Tally row (same order).

    Rows must have task_ref / side (see prepare_row). An empty dict means "no match".
    A result has the merged AMOS values plus:
      match_rule  – step that found it (STEP_*),
      match_note  – reason why the row needs review (None if not),
      info_note   – information only (e.g. task number taken from the Title).
    """
    family = aircraft_family(aircraft_type)
    codes = customer_codes(customer)
    plan = matching_plan(customer, aircraft_type)
    results: list[dict] = [{} for _ in parsed]
    groups: dict[str, list[int]] = {}
    for i, row in enumerate(parsed):
        key = match_key(row["task_ref"])
        row["match_key"] = key
        groups.setdefault(key, []).append(i)

    for key, idxs in groups.items():
        if not key:
            continue
        rows = [parsed[i] for i in idxs]
        for step in plan:
            if step in GROUP_STEPS:
                items = find_group_items(conn, step, rows[0]["task_ref"], codes, family)
                if items:
                    for i, (assigned, note) in zip(idxs, distribute(rows, items)):
                        results[i] = {**merge_items(assigned), "match_note": note, "match_rule": step}
                    break
                continue
            for i in idxs:
                if results[i]:
                    continue
                amp = find_exact_customer_row(conn, step, parsed[i]["task_ref"], codes, family)
                if amp:
                    note = None
                    if step == STEP_CUSTOMER_OTHER:
                        note = f"Lấy từ Customer AMP của khách hàng khác ({amp['customer'] or 'trống'})"
                    results[i] = {**merge_items([amp]), "match_note": note, "match_rule": step}
            if all(results[i] for i in idxs):
                break

    for i, row in enumerate(parsed):
        if results[i] and normalize(row["task_ref"]) != normalize(row["task_no"]):
            results[i]["info_note"] = f"Mã task lấy từ Title: {row['task_ref']}"
    return results


def combined_note(*notes: Any) -> str | None:
    return "; ".join(str(n) for n in notes if n) or None
