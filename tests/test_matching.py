import sqlite3
import unittest
from pathlib import Path

from wp_app.matching import (
    AUTO_MATCH,
    REVIEW_REQUIRED,
    aircraft_from_amp_name,
    canonical_aircraft,
    is_match_eligible,
    prefix_similarity,
    resolve_candidates,
    taskcard_core,
    title_similarity,
)
from wp_app.services import lookup_amp


class MatchingHelpersTest(unittest.TestCase):
    def test_taskcard_core_strips_revision(self):
        self.assertEqual(taskcard_core("274000-01-1/00"), "274000-01-1")

    def test_similarity(self):
        self.assertEqual(prefix_similarity("274000-01-9", "274000-01-2"), 90.9)
        self.assertEqual(title_similarity("(1) Check engine oil level", "CHECK ENGINE OIL LEVEL"), 100.0)

    def test_aircraft_model(self):
        self.assertEqual(aircraft_from_amp_name("KHV-A320"), "A320")
        self.assertEqual(aircraft_from_amp_name("KHV-A321"), "A321")
        self.assertEqual(aircraft_from_amp_name("HVN-A320/A321"), "A32S")
        self.assertEqual(canonical_aircraft("350"), "A350")

    def test_only_vietjet_block_taskcard_is_mpd_eligible(self):
        self.assertTrue(is_match_eligible("VietJet", "Block Taskcard"))
        self.assertFalse(is_match_eligible("VietJet", "Defect"))
        self.assertTrue(is_match_eligible("Lufthansa", "MS Item"))
        self.assertTrue(is_match_eligible("DLH", "MS Item"))
        self.assertFalse(is_match_eligible("Lufthansa", "2. CHECKS"))

    def test_resolve_candidates_collapses_without_summing(self):
        rows = [
            {"aircraft_model": "A320", "title": "T", "planning_mhr": "1:00", "zone": "100"},
            {"aircraft_model": "A320", "title": "T", "planning_mhr": "1:00", "zone": "200"},
        ]
        result = resolve_candidates(rows, "A320")
        self.assertEqual(result.status, AUTO_MATCH)
        self.assertEqual(result.record["zone"], "100; 200")
        self.assertEqual(result.record["planning_mhr"], "1:00")

    def test_resolve_candidates_conflict_needs_review(self):
        rows = [
            {"aircraft_model": "A320", "title": "T1", "planning_mhr": "1:00"},
            {"aircraft_model": "A320", "title": "T2", "planning_mhr": "2:00"},
        ]
        self.assertEqual(resolve_candidates(rows, "A320").status, REVIEW_REQUIRED)


class LookupAmpTest(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("""CREATE TABLE amp_task (id INTEGER PRIMARY KEY, source TEXT,
          taskcard_core_key TEXT, taskcard_key TEXT, customer TEXT, aircraft_model TEXT,
          title TEXT, planning_mhr TEXT)""")
        self.connection.executemany(
            "INSERT INTO amp_task VALUES (?,?,?,?,?,?,?,?)",
            [
                (1, "VNA", "274000-01-9", "274000-01-9/00", None, "A320", "CHECK ENGINE OIL LEVEL", "1:00"),
                (2, "CUSTOMER", "CR-100", "CR-100", "DLH", "A350", "INSPECT CABIN", "0:30"),
            ],
        )

    def tearDown(self):
        self.connection.close()

    def test_vna_taskcard(self):
        decision = lookup_amp(self.connection, "274000-01-9/00", "VA-VJ", "A320")
        self.assertEqual((decision.status, decision.method), (AUTO_MATCH, "VNA_TASKCARD"))

    def test_customer_first_dlh_a350(self):
        decision = lookup_amp(self.connection, "CR-100", "DLH", "A350")
        self.assertEqual((decision.status, decision.method), (AUTO_MATCH, "CR_DLH_A350"))

    def test_prefix_layer(self):
        decision = lookup_amp(self.connection, "274000-01-2", "VA-VJ", "A320")
        self.assertEqual((decision.method, decision.layer, decision.score), ("PREFIX_VNA", 2, 90.9))
        self.assertEqual(decision.status, REVIEW_REQUIRED)

    def test_title_layer(self):
        decision = lookup_amp(self.connection, "999999-99", "VA-VJ", "A320", "Check engine oil level")
        self.assertEqual((decision.method, decision.layer, decision.score), ("TITLE_VNA", 3, 100.0))

    def test_prefix_customer_first(self):
        decision = lookup_amp(self.connection, "CR-101", "DLH", "A350")
        self.assertEqual((decision.method, decision.layer), ("PREFIX_CR_DLH_A350", 2))

    def test_suggestions_only_skip_exact_layer(self):
        decision = lookup_amp(self.connection, "274000-01-9/00", "VA-VJ", "A320", include_exact=False)
        self.assertNotEqual(decision.layer, 1)


SAMPLES = Path(__file__).resolve().parents[2] / "TALLY SHEET KHACH HANG"
VJ_SAMPLE = SAMPLES / "(Sample) TALLY SHEET WP VJC-A699-24MT2026 REV02.xlsx"
DLH_SAMPLE = SAMPLES / "(Sample) Workpackage-Summary for D-AIXB_H-25-29102025.xlsx"


@unittest.skipUnless(VJ_SAMPLE.exists() and DLH_SAMPLE.exists(), "sample Tally Sheets not available")
class ParserRegressionTest(unittest.TestCase):
    def test_vietjet(self):
        from wp_app.parsers import parse_vietjet
        rows = parse_vietjet(VJ_SAMPLE)
        self.assertEqual(len(rows), 128)
        self.assertEqual(sum(is_match_eligible("VietJet", row["event_type"]) for row in rows), 87)

    def test_lufthansa(self):
        from wp_app.parsers import inspect_lufthansa_structure, parse_lufthansa
        self.assertEqual(len(parse_lufthansa(DLH_SAMPLE)), 309)
        structure = inspect_lufthansa_structure(DLH_SAMPLE)
        self.assertEqual(structure["dimension"], "A1:I463")
        self.assertEqual(structure["block_count"], 9)
        self.assertEqual(structure["total_record_count"], 445)
        self.assertEqual(structure["ms_item_count"], 298)
        self.assertEqual([b["record_count"] for b in structure["blocks"]], [5, 298, 27, 35, 0, 29, 6, 6, 39])


if __name__ == "__main__":
    unittest.main()
