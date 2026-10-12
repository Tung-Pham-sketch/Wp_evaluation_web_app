"""Tests of the merged matching flow (layer 1 = MPD key, layers 2–3 = suggestions)
and of the MiniDB maintenance features."""
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("WP_DATA_DIR", tempfile.mkdtemp(prefix="wp-test-"))
os.environ.setdefault("WP_SKIP_SEED_SAMPLES", "1")

import wp_app.database as database  # noqa: E402
from wp_app import minidb  # noqa: E402
from wp_app.matching import AUTO_MATCH, NOT_APPLICABLE, NOT_FOUND, REVIEW_REQUIRED  # noqa: E402
from wp_app.mpd_matching import (  # noqa: E402
    STEP_CUSTOMER_FIRST,
    STEP_VNA,
    match_rows,
    matching_plan,
    mpd_key,
    prepare_row,
    side_of,
)
from wp_app.reference_data import AMP_COLUMNS, ORIGIN_AMOS, derived_amp_fields  # noqa: E402
from wp_app.services import populate_evaluation_items  # noqa: E402


def amp(source, task_no, **values):
    record = {column: None for column in AMP_COLUMNS}
    record.update({"source": source, "task_no": task_no, "origin": ORIGIN_AMOS, **values})
    record.update(derived_amp_fields(record))
    return record


AMP_ROWS = [
    # 253000-02: an older KHV AMP, a newer KHV AMP and the HVN AMP -> HVN wins
    amp("VNA", "253000-02-1-1", amp_name="KHV-A320/09/00", amp_date="2025-01-01", aircraft_type="32S",
        taskcard_no="253000-02-1-1/01", taskcard_ident="ITEM 1", title="GALLEY", planning_mhr="9:00"),
    amp("VNA", "253000-02-1-1", amp_name="HVN-A320/A321/24/01", amp_date="2024-01-01", aircraft_type="32S",
        taskcard_no="253000-02-1-1/02", taskcard_ident="ITEM 1", title="GALLEY", planning_mhr="6:00"),
    # 361100-01: two items of one AMP, one per engine
    amp("VNA", "361100-01-1", amp_name="HVN-A320/A321/24/01", amp_date="2024-01-01", aircraft_type="32S",
        taskcard_no="361100-01-1-2/01", taskcard_ident="ITEM 2", area="RH ENGINE", title="BLEED",
        planning_mhr="2:36"),
    amp("VNA", "361100-01-1", amp_name="HVN-A320/A321/24/01", amp_date="2024-01-01", aircraft_type="32S",
        taskcard_no="361100-01-1-1/01", taskcard_ident="ITEM 1", area="LH ENGINE", title="BLEED",
        planning_mhr="2:36"),
    # 999900-01: used for the prefix suggestion (layer 2)
    amp("VNA", "999900-01-1", amp_name="KHV-A320/08/00", amp_date="2023-01-01", aircraft_type="A320",
        taskcard_no="999900-01-1/00", taskcard_ident="ITEM 1", title="ONLY TEST", planning_mhr="2:00"),
    # Customer AMP
    amp("CUSTOMER", "281100-05-1", customer="VA-PAL", aircraft_type="A320", title="FUEL", planning_mhr="0:18"),
    amp("CUSTOMER", "ZL-415-00Z01-01-ENG1", customer="dlh", aircraft_type="350", title="GVI ENG 1",
        planning_mhr="1:00", classification="WATCH ITEM"),
    amp("CUSTOMER", "ZL-415-00Z01-01-ENG2", customer="DLH", aircraft_type="350", title="GVI ENG 2",
        planning_mhr="1:30"),
]


def vj_row(task_no, title, event="Block Taskcard"):
    return {"task_no": task_no, "source_title": title, "event_type": event, "section": "TALLY SHEET"}


class KeysTest(unittest.TestCase):
    def test_mpd_key(self):
        self.assertEqual(mpd_key("253000-02-1"), "253000-02")
        self.assertEqual(mpd_key("361100-01-1-VJC"), "361100-01")
        self.assertEqual(mpd_key("722000-C3-1"), "722000-C3")
        self.assertEqual(mpd_key("271400-00M10-01-1"), "271400-00M10-01")
        self.assertEqual(mpd_key("ZL-455-00Z01-01-ENG1"), "ZL-455-00Z01-01")
        self.assertIsNone(mpd_key("51077"))

    def test_side(self):
        self.assertEqual(side_of("ENGINE BLEED - ENG #1"), "L")
        self.assertEqual(side_of("RH WING"), "R")
        self.assertIsNone(side_of("ENG #1 AND ENG #2"))

    def test_prepare_row_vietjet(self):
        block = prepare_row("VietJet", vj_row("253000-02-1", "253000-02-1 (02) / GALLEY"))
        self.assertTrue(block["eligible"])
        self.assertEqual(block["match_key"], "253000-02")
        other = prepare_row("VietJet", vj_row("5729999", "999900-01-1 (0) / ONLY TEST", "Single Running Taskcard"))
        self.assertTrue(other["eligible"])
        self.assertEqual(other["task_ref"], "999900-01-1")
        check = prepare_row("VietJet", vj_row("5853497", "24MT-A320/24MT CHECK", "Check"))
        self.assertFalse(check["eligible"])

    def test_plan_from_configuration(self):
        self.assertEqual(matching_plan("DLH", "A350")[0], STEP_CUSTOMER_FIRST)
        self.assertEqual(matching_plan("Lufthansa", "350")[0], STEP_CUSTOMER_FIRST)
        self.assertEqual(matching_plan("DLH", "A320")[0], STEP_VNA)
        self.assertEqual(matching_plan("VA-VJ", "A350")[0], STEP_VNA)


class MergedFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._db_path = database.DB_PATH
        database.DB_PATH = Path(self.tmp.name) / "test.db"
        database.init_db()
        with database.db() as connection:
            connection.executemany(
                f"INSERT INTO amp_task({','.join(AMP_COLUMNS)}) VALUES ({','.join('?' * len(AMP_COLUMNS))})",
                [tuple(row[column] for column in AMP_COLUMNS) for row in AMP_ROWS],
            )

    def tearDown(self):
        database.DB_PATH = self._db_path
        self.tmp.cleanup()

    def evaluate(self, adapter, customer, aircraft, rows):
        with database.db() as connection:
            connection.execute(
                """INSERT INTO tally_sheet(id,file_name,stored_path,customer,aircraft_type,adapter,uploaded_at)
                VALUES ('TS-1','t.xlsx','t.xlsx',?,?,?, '2026-01-01')""", (customer, aircraft, adapter))
            connection.execute("""INSERT INTO evaluation(id,tally_id,created_at,updated_at)
                VALUES ('EV-1','TS-1','2026-01-01','2026-01-01')""")
            tally = connection.execute("SELECT * FROM tally_sheet WHERE id='TS-1'").fetchone()
            matched, counts = populate_evaluation_items(connection, "EV-1", tally, rows)
            items = {row["task_no"]: dict(row) for row in connection.execute(
                "SELECT * FROM evaluation_item WHERE evaluation_id='EV-1' ORDER BY id")}
        return matched, counts, items

    def test_vietjet_layers(self):
        rows = [
            vj_row("253000-02-1", "253000-02-1 (02) / GALLEY"),
            vj_row("361100-01-1-VJC", "361100-01-1-VJC (1) / BLEED - ENG #1"),
            vj_row("361100-01-2-VJC", "361100-01-2-VJC (1) / BLEED - ENG #2"),
            vj_row("281100-05-1", "281100-05-1 (0) / FUEL"),
            vj_row("2421599", "999900-02-1 (0) / SOMETHING ELSE", "Workorder"),
            vj_row("5853497", "24MT-A320/24MT CHECK", "Check"),
        ]
        matched, counts, items = self.evaluate("VietJet", "VA-VJ", "A320", rows)
        self.assertEqual(matched, 4)
        # HVN AMP chosen before the newer KHV AMP
        self.assertIn("HVN-A320/A321/24/01", items["253000-02-1"]["amos_reference"])
        self.assertEqual(items["253000-02-1"]["planning_mhr"], 6.0)
        self.assertEqual(items["253000-02-1"]["match_status"], AUTO_MATCH)
        self.assertEqual(items["253000-02-1"]["match_method"], "MPD_VNA")
        # ENG #1 -> LH item, ENG #2 -> RH item
        self.assertIn("ITEM 1", items["361100-01-1-VJC"]["amos_reference"])
        self.assertIn("ITEM 2", items["361100-01-2-VJC"]["amos_reference"])
        # another customer's Customer AMP -> matched, but needs review
        self.assertEqual(items["281100-05-1"]["match_status"], REVIEW_REQUIRED)
        self.assertEqual(items["281100-05-1"]["matched"], 1)
        # layer 2: suggestion only, no MHR
        suggestion = items["2421599"]
        self.assertEqual((suggestion["match_status"], suggestion["match_layer"]), (REVIEW_REQUIRED, 2))
        self.assertEqual(suggestion["matched"], 0)
        self.assertIsNone(suggestion["planning_mhr"])
        self.assertEqual(suggestion["suggested_mhr"], 2.0)
        # no task number at all
        self.assertEqual(items["5853497"]["match_status"], NOT_APPLICABLE)
        self.assertEqual(items["5853497"]["not_in_database"], 0)
        self.assertEqual(counts[NOT_APPLICABLE], 1)

    def test_shared_item_needs_review(self):
        rows = [vj_row("253000-02-1", "253000-02-1 (02) / GALLEY"),
                vj_row("253000-02-2", "253000-02-2 (02) / GALLEY")]
        _, _, items = self.evaluate("VietJet", "VA-VJ", "A320", rows)
        for item in items.values():
            self.assertEqual(item["match_status"], REVIEW_REQUIRED)
            self.assertIn("dùng chung", item["match_note"])

    def test_customer_first_and_add_to_database(self):
        rows = [
            {"task_no": "ZL-415-00Z01-01-ENG1", "source_title": "GVI ENGINE 1", "event_type": "MS Item"},
            {"task_no": "ZL-415-00Z01-01-ENG2", "source_title": "GVI ENGINE 2", "event_type": "MS Item"},
            {"task_no": "ZL-777-00Z01-01", "source_title": "NEW TASK", "event_type": "MS Item"},
        ]
        _, _, items = self.evaluate("Lufthansa", "DLH", "A350", rows)
        first = items["ZL-415-00Z01-01-ENG1"]
        self.assertEqual((first["match_status"], first["match_method"]), (AUTO_MATCH, "MPD_CUSTOMER_FIRST"))
        self.assertEqual(first["important_job"], 1)      # WATCH ITEM
        missing = items["ZL-777-00Z01-01"]
        self.assertEqual((missing["match_status"], missing["not_in_database"]), (NOT_FOUND, 1))

        # "Thêm vào Database": the row is matched again and the change is logged
        result = minidb.add_to_database(
            missing["id"], "CUSTOMER",
            {"task_no": "ZL-777-00Z01-01", "aircraft_type": "350", "customer": "DLH",
             "title": "NEW TASK", "planning_mhr": "0:45"},
            "Task mới", "Tester",
        )
        self.assertEqual(result["rematched"], 1)
        with database.db() as connection:
            row = connection.execute("SELECT * FROM evaluation_item WHERE id=?", (missing["id"],)).fetchone()
            self.assertEqual((row["matched"], row["match_status"], row["added_to_db"]), (1, AUTO_MATCH, 1))
            self.assertEqual(row["planning_mhr"], 0.75)
            self.assertTrue(connection.execute("SELECT COUNT(*) FROM amp_change").fetchone()[0])

        # "Sửa bản ghi": identity fields are locked, other fields are changed and logged
        ref = json.loads(first["amp_refs"])[0]
        with database.db() as connection:
            record = connection.execute(
                "SELECT id FROM amp_task WHERE task_no=?", (ref["task_no"],)).fetchone()
        edit = minidb.edit_amp_record(record["id"], {"task_no": "CHANGED", "planning_mhr": "1:15"},
                                      "Sửa MHR", first["id"], "Tester")
        self.assertEqual(edit["changed"], 1)
        with database.db() as connection:
            record = connection.execute("SELECT * FROM amp_task WHERE id=?", (record["id"],)).fetchone()
            item = connection.execute("SELECT * FROM evaluation_item WHERE id=?", (first["id"],)).fetchone()
        self.assertEqual((record["task_no"], record["planning_mhr"], record["edited"]),
                         ("ZL-415-00Z01-01-ENG1", "1:15", 1))
        self.assertEqual(item["planning_mhr"], 1.25)

    def test_popup_for_match_and_suggestion(self):
        rows = [vj_row("253000-02-1", "253000-02-1 (02) / GALLEY"),
                vj_row("2421599", "999900-02-1 (0) / SOMETHING ELSE", "Workorder")]
        _, _, items = self.evaluate("VietJet", "VA-VJ", "A320", rows)
        detail = minidb.item_amos_detail(items["253000-02-1"]["id"])
        self.assertEqual(len(detail["selected"]), 1)
        self.assertTrue(any(other["source"] == "VNA" for other in detail["others"]))
        suggestion = minidb.item_amos_detail(items["2421599"]["id"])
        self.assertTrue(suggestion["is_suggestion"])


if __name__ == "__main__":
    unittest.main()
