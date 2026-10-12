import os
import tempfile
import unittest

os.environ.setdefault("WP_DATA_DIR", tempfile.mkdtemp(prefix="wp-test-"))
os.environ.setdefault("WP_SKIP_SEED_SAMPLES", "1")

from wp_app.adapters import adapter_for_customer  # noqa: E402
from wp_app.main import app  # noqa: E402


class AppStructureTest(unittest.TestCase):
    def test_adapter_registry(self):
        self.assertEqual(adapter_for_customer("VA-VJ"), "VietJet")
        self.assertEqual(adapter_for_customer("dlh"), "Lufthansa")
        with self.assertRaises(ValueError):
            adapter_for_customer("UNKNOWN")

    def test_public_routes(self):
        paths = set(app.openapi()["paths"])
        expected = {
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
        self.assertTrue(expected.issubset(paths), expected - paths)
        self.assertNotIn("/api/upload", paths)


if __name__ == "__main__":
    unittest.main()
