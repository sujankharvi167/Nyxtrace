import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.services.risk_engine import RiskEngine, risk_category


class RiskEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.engine = RiskEngine(Path(self.temp_dir.name))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_category_boundaries_are_deterministic(self):
        self.assertEqual(risk_category(0.0), "low")
        self.assertEqual(risk_category(0.39), "low")
        self.assertEqual(risk_category(0.40), "medium")
        self.assertEqual(risk_category(0.69), "medium")
        self.assertEqual(risk_category(0.70), "high")
        self.assertEqual(risk_category(0.89), "high")
        self.assertEqual(risk_category(0.90), "critical")
        self.assertEqual(risk_category(1.0), "critical")

    def test_case_persistence_notes_history_and_duplicate_transaction(self):
        compatibility = {
            "compatible": True,
            "dataset_batch": "batch-current",
            "model_batch": "batch-current",
            "prediction_batch": "batch-current",
            "graph_batch": "batch-current",
            "message": "compatible",
        }
        with patch.object(self.engine, "compatibility", return_value=compatibility):
            case = self.engine.create_case(
                title="Test investigation",
                description="Analyst-created test case",
                priority="high",
                status="open",
                primary_transaction_id="tx-1",
                transaction_ids=["tx-1"],
                risk_assessment_reference="assessment-1",
            )
            case_id = case["case_id"]
            updated = self.engine.update_case(
                case_id,
                title=None,
                description=None,
                priority="critical",
                status="under_review",
            )
            self.assertEqual(updated["priority"], "critical")
            self.assertEqual(updated["status"], "under_review")
            self.engine.add_note(case_id, "A real analyst note.", None)

            stored = self.engine.get_case(case_id)
            self.assertEqual(stored["associated_transaction_ids"], ["tx-1"])
            self.assertEqual(len(stored["notes"]), 1)
            self.assertGreaterEqual(len(stored["activity"]), 2)

    def test_duplicate_transaction_and_unknown_case_are_rejected(self):
        compatibility = {
            "compatible": True,
            "dataset_batch": "batch-current",
            "model_batch": "batch-current",
            "prediction_batch": "batch-current",
            "graph_batch": "batch-current",
            "message": "compatible",
        }
        with patch.object(self.engine, "compatibility", return_value=compatibility):
            case = self.engine.create_case(
                "Duplicate test",
                "Test duplicate association",
                "medium",
                "open",
                "tx-1",
                ["tx-1"],
                None,
            )
            with patch("app.services.risk_engine.graph_engine.load_graph") as load_graph:
                graph = load_graph.return_value
                graph.__contains__.side_effect = lambda transaction_id: transaction_id in {"tx-1"}
                with self.assertRaises(HTTPException) as context:
                    self.engine.add_transaction(case["case_id"], "tx-1")
                self.assertEqual(context.exception.status_code, 409)

            restored = RiskEngine(Path(self.temp_dir.name))
            persisted = restored.get_case(case["case_id"])
            self.assertEqual(persisted["associated_transaction_ids"], ["tx-1"])


if __name__ == "__main__":
    unittest.main()
