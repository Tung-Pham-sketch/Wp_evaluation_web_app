from __future__ import annotations

import unittest

from wp_app.adapters import adapter_for_customer
from wp_app.main import app


class AppStructureTest(unittest.TestCase):
    def test_customer_adapter_registry(self):
        self.assertEqual(adapter_for_customer("VA-VJ"), "VietJet")
        self.assertEqual(adapter_for_customer("dlh"), "Lufthansa")
        with self.assertRaises(ValueError):
            adapter_for_customer("UNKNOWN")

    def test_openapi_contract_contains_current_routes_only(self):
        paths = app.openapi()["paths"]
        required = {
            "/api/dashboard",
            "/api/data/amos",
            "/api/data/jobcards",
            "/api/data/external",
            "/api/tallies",
            "/api/tallies/{tally_id}/inspect",
            "/api/tallies/{tally_id}/inspection/confirm",
            "/api/tallies/{tally_id}/evaluate",
            "/api/workflows/{tally_id}",
            "/api/workflows/{tally_id}/review-checklist",
            "/api/evaluations/{evaluation_id}",
            "/api/items/{item_id}",
            "/api/evaluations/{evaluation_id}/export",
            "/api/evaluations/{evaluation_id}/history",
            "/api/tally/{tally_id}/download",
        }
        self.assertTrue(required.issubset(paths))
        self.assertNotIn("/api/upload", paths)


if __name__ == "__main__":
    unittest.main()
