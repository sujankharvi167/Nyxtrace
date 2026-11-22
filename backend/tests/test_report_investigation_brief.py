import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.report_engine import ReportEngine


class ReportInvestigationBriefTests(unittest.TestCase):
    def test_isolated_case_brief_generates_pdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = ReportEngine(Path(temp_dir))
            compatibility = {
                "compatible": True,
                "dataset_batch": "20261121-191413-6829c2ed",
                "model_batch": "20261121-191413-6829c2ed",
                "prediction_batch": "20261121-191413-6829c2ed",
                "graph_batch": "20261121-191413-6829c2ed",
            }
            test_case = {
                "case_id": "NYX-TEMP-FIXTURE",
                "title": "Temporary Stage 6 Verification Case",
                "description": "Isolated test fixture; not a production investigation.",
                "priority": "medium",
                "status": "under_review",
                "primary_transaction_id": "230425980",
                "associated_transaction_ids": ["230425980"],
                "dataset_batch": "20261121-191413-6829c2ed",
                "model_batch": "20261121-191413-6829c2ed",
                "risk_assessment_reference": "temporary-assessment",
                "created_at": "2026-11-22T00:00:00+00:00",
                "updated_at": "2026-11-22T00:00:00+00:00",
                "notes": [
                    {
                        "note_id": "note-temp",
                        "content": "Temporary verification note.",
                        "author": None,
                        "created_at": "2026-11-22T00:00:00+00:00",
                        "updated_at": "2026-11-22T00:00:00+00:00",
                    }
                ],
                "activity": [
                    {
                        "activity_id": "activity-temp",
                        "action": "case_created",
                        "details": "Temporary case created.",
                        "created_at": "2026-11-22T00:00:00+00:00",
                    }
                ],
                "assessments": [],
            }
            with patch.object(
                __import__("app.services.report_engine", fromlist=["risk_engine"]).risk_engine,
                "get_case",
                return_value=test_case,
            ), patch.object(
                __import__("app.services.report_engine", fromlist=["risk_engine"]).risk_engine,
                "compatibility",
                return_value=compatibility,
            ), patch.object(
                engine,
                "compatibility",
                return_value={
                    "dataset_batch": "20261121-191413-6829c2ed",
                    "model_batch": "20261121-191413-6829c2ed",
                    "prediction_batch": "20261121-191413-6829c2ed",
                    "graph_batch": "20261121-191413-6829c2ed",
                },
            ):
                report = engine.generate(
                    "Temporary Investigation Brief",
                    "investigation_brief",
                    "NYX-TEMP-FIXTURE",
                    ["230425980"],
                )
            self.assertEqual(report["status"], "completed")
            path = engine.get_download_path(report["report_id"])
            self.assertTrue(path.is_file())
            with path.open("rb") as file:
                self.assertEqual(file.read(4), b"%PDF")


if __name__ == "__main__":
    unittest.main()
