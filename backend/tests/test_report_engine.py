import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from app.services.report_engine import ReportEngine


class ReportEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.engine = ReportEngine(Path(self.temp_dir.name))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_report_types_are_complete(self):
        types = {item["type"] for item in self.engine.list_types()}
        self.assertEqual(
            types,
            {
                "transaction_summary",
                "ml_detection",
                "network_analysis",
                "investigation_brief",
                "risk_dashboard",
                "compliance_export",
            },
        )

    def test_transaction_summary_generates_pdf_and_persists_metadata(self):
        report = self.engine.generate(
            "Empty Dataset Review",
            "transaction_summary",
            None,
            [],
        )
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["report_type"], "transaction_summary")
        path = self.engine.get_download_path(report["report_id"])
        self.assertTrue(path.is_file())
        self.assertGreater(path.stat().st_size, 500)
        with path.open("rb") as file:
            self.assertEqual(file.read(4), b"%PDF")

        listed = self.engine.list_reports()
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["items"][0]["report_id"], report["report_id"])

    def test_investigation_brief_requires_case_id_and_invalid_type_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            self.engine.generate("Case Brief", "investigation_brief", None, [])
        self.assertEqual(context.exception.status_code, 422)

        with self.assertRaises(HTTPException) as context:
            self.engine.generate("Invalid", "unknown", None, [])
        self.assertEqual(context.exception.status_code, 422)

    def test_download_rejects_missing_report(self):
        with self.assertRaises(HTTPException) as context:
            self.engine.get_report("RPT-does-not-exist")
        self.assertEqual(context.exception.status_code, 404)

    def test_all_data_capable_report_types_generate_valid_pdfs_without_data(self):
        for report_type in (
            "transaction_summary",
            "ml_detection",
            "network_analysis",
            "risk_dashboard",
            "compliance_export",
        ):
            report = self.engine.generate(
                f"Empty {report_type}",
                report_type,
                None,
                [],
            )
            self.assertEqual(report["status"], "completed")
            path = self.engine.get_download_path(report["report_id"])
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 500)
            with path.open("rb") as file:
                self.assertEqual(file.read(4), b"%PDF")

    def test_failed_generation_does_not_leave_a_completed_record(self):
        with self.assertRaises(HTTPException):
            self.engine.generate("Missing Case", "investigation_brief", None, [])
        reports = self.engine.list_reports(report_type="investigation_brief")
        self.assertTrue(reports["total"] >= 1)
        self.assertTrue(
            all(report["status"] == "failed" for report in reports["items"])
        )



if __name__ == "__main__":
    unittest.main()
