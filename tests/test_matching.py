from __future__ import annotations

import sqlite3
import unittest

from wp_app.config import SAMPLES_DIR
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
from wp_app.parsers import inspect_lufthansa_structure, parse_lufthansa, parse_vietjet
from wp_app.services import lookup_amp


class MatchingRulesTest(unittest.TestCase):
    def test_taskcard_core_removes_only_slash_revision(self):
        self.assertEqual(taskcard_core("274000-01-1/00"), "274000-01-1")
        self.assertEqual(taskcard_core("ZL-831-01-1-2"), "ZL-831-01-1-2")

    def test_prefix_and_title_scores_are_explainable_percentages(self):
        self.assertEqual(prefix_similarity("274000-01-9", "274000-01-2"), 90.9)
        self.assertEqual(title_similarity("(2) Hydraulic pump inspection", "Hydraulic pump inspection"), 100.0)

    def test_amp_name_defines_a320_a321_model(self):
        self.assertEqual(aircraft_from_amp_name("KHV-A320/08/00", "32S"), "A320")
        self.assertEqual(aircraft_from_amp_name("KHV-A321/14/00", "32S"), "A321")
        self.assertEqual(aircraft_from_amp_name("HVN-A320/A321/24/01", "32S"), "A32S")
        self.assertEqual(canonical_aircraft("350"), "A350")

    def test_only_vietjet_block_taskcard_is_mpd_eligible(self):
        self.assertTrue(is_match_eligible("VietJet", "Block Taskcard"))
        self.assertFalse(is_match_eligible("VietJet", "Single Running Taskcard"))
        self.assertFalse(is_match_eligible("VietJet", "Document"))
        self.assertTrue(is_match_eligible("Lufthansa", "MS Item"))
        self.assertTrue(is_match_eligible("DLH", "MS Item"))
        self.assertFalse(is_match_eligible("Lufthansa", "1. CHECKS"))
        self.assertFalse(is_match_eligible("Lufthansa", "7. List of Jobcards"))

    def test_item_rows_are_collapsed_without_summing_mhr(self):
        rows = [
            {"id": 1, "aircraft_model": "A320", "title": "TASK", "planning_mhr": "01:30", "zone": "100"},
            {"id": 2, "aircraft_model": "A320", "title": "TASK", "planning_mhr": "01:30", "zone": "200"},
        ]
        result = resolve_candidates(rows, "A320")
        self.assertEqual(result.status, AUTO_MATCH)
        self.assertEqual(result.candidate_count, 2)
        self.assertEqual(result.record["planning_mhr"], "01:30")
        self.assertEqual(result.record["zone"], "100; 200")

    def test_conflicting_title_or_mhr_requires_review(self):
        rows = [
            {"id": 1, "aircraft_model": "A320", "title": "TASK A", "planning_mhr": "00:30"},
            {"id": 2, "aircraft_model": "A320", "title": "TASK B", "planning_mhr": "00:45"},
        ]
        self.assertEqual(resolve_candidates(rows, "A320").status, REVIEW_REQUIRED)

    def test_vna_precedes_cr_and_dlh_a350_uses_cr_only(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE amp_task(
            id INTEGER PRIMARY KEY, source TEXT, taskcard_core_key TEXT, taskcard_key TEXT,
            customer TEXT, aircraft_model TEXT, title TEXT, planning_mhr TEXT)""")
        conn.executemany(
            """INSERT INTO amp_task(source,taskcard_core_key,taskcard_key,customer,
            aircraft_model,title,planning_mhr) VALUES (?,?,?,?,?,?,?)""",
            [
                ("VNA", "274000-01-1", "274000-01-1/00", None, "A320", "VNA title", "00:08"),
                ("CUSTOMER", "274000-01-1", "274000-01-1", "VA-VJ", "A320", "CR title", "00:10"),
                ("VNA", "DLH-001", "DLH-001", None, "A350", "VNA DLH", "00:20"),
                ("CUSTOMER", "DLH-001", "DLH-001", "DLH", "A350", "CR DLH", "00:30"),
                ("VNA", "274000-01-2", "274000-01-2/00", None, "A320", "Prefix candidate", "00:12"),
                ("VNA", "AAA-001", "AAA-001/00", None, "A320", "Hydraulic pump inspection", "00:40"),
            ],
        )
        vjc = lookup_amp(conn, "274000-01-1", "VA-VJ", "A320")
        dlh = lookup_amp(conn, "DLH-001", "DLH", "A350")
        self.assertEqual(vjc.method, "VNA_TASKCARD")
        self.assertEqual(vjc.record["title"], "VNA title")
        self.assertEqual(dlh.method, "CR_DLH_A350")
        self.assertEqual(dlh.record["title"], "CR DLH")
        prefix = lookup_amp(conn, "274000-01-9", "VA-VJ", "A320", "Unrelated title")
        title = lookup_amp(conn, "ZZZ-999", "VA-VJ", "A320", "Hydraulic pump inspection")
        dlh_review = lookup_amp(conn, "DLH-009", "DLH", "A350", "VNA DLH")
        self.assertEqual((prefix.layer, prefix.status, prefix.method), (2, REVIEW_REQUIRED, "PREFIX_VNA"))
        self.assertEqual(prefix.score, 90.9)
        self.assertEqual((title.layer, title.status, title.method), (3, REVIEW_REQUIRED, "TITLE_VNA"))
        self.assertEqual(title.score, 100.0)
        self.assertEqual(dlh_review.method, "PREFIX_CR_DLH_A350")
        self.assertEqual(dlh_review.record["title"], "CR DLH")
        conn.close()


class ParserRegressionTest(unittest.TestCase):
    def test_sample_row_counts(self):
        vjc = SAMPLES_DIR / "(Sample) TALLY SHEET WP VJC-A699-24MT2026 REV02.xlsx"
        dlh = SAMPLES_DIR / "(Sample) Workpackage-Summary for D-AIXB_H-25-29102025.xlsx"
        if not vjc.exists() or not dlh.exists():
            self.skipTest("Sample tally workbooks are not available")
        vietjet_rows = parse_vietjet(vjc)
        lufthansa_rows = parse_lufthansa(dlh)
        self.assertEqual(len(vietjet_rows), 128)
        self.assertEqual(sum(is_match_eligible("VietJet", row["event_type"]) for row in vietjet_rows), 87)
        self.assertEqual(len(lufthansa_rows), 309)

    def test_lufthansa_structure_contains_every_major_block(self):
        dlh = SAMPLES_DIR / "(Sample) Workpackage-Summary for D-AIXB_H-25-29102025.xlsx"
        if not dlh.exists():
            self.skipTest("Sample Lufthansa workbook is not available")
        structure = inspect_lufthansa_structure(dlh)
        self.assertEqual(structure["dimension"], "A1:I463")
        self.assertEqual(structure["block_count"], 9)
        self.assertEqual(structure["total_record_count"], 445)
        self.assertEqual(structure["ms_item_count"], 298)
        self.assertEqual(
            [block["record_count"] for block in structure["blocks"]],
            [5, 298, 27, 35, 0, 29, 6, 6, 39],
        )
        ms_item = next(block for block in structure["blocks"] if block["is_taskcard_scope"])
        self.assertEqual(
            ms_item["fields"],
            ["Typ", "Event ID", "ATA", "CRI", "Collected from", "Zone", "Titel", "AAR", "MS Description"],
        )


if __name__ == "__main__":
    unittest.main()
