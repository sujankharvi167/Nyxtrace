import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

import app.api.ml as ml_api
from app.main import app
from app.services.ml_engine import MLEngine, _metrics


class MLEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backend_dir = Path(self.temp_dir.name)
        batch_id = "20261203-111111"
        upload_dir = self.backend_dir / "data" / "uploads" / batch_id
        processed_dir = self.backend_dir / "data" / "processed"
        upload_dir.mkdir(parents=True)
        processed_dir.mkdir(parents=True)

        with (upload_dir / "txs_features.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["txId", "Time step", "signal", "noisy", "constant", "class", "all_missing"])
            for step in range(1, 6):
                for index in range(10):
                    writer.writerow([f"{step}-l-{index}", step, index / 20, index % 3, 5, 2, ""])
                for index in range(2):
                    writer.writerow([f"{step}-i-{index}", step, 10 + index, index % 2, 5, 1, ""])
                for index in range(3):
                    writer.writerow([f"{step}-u-{index}", step, 4 + index, index, 5, 3, ""])

        with (upload_dir / "txs_classes.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["txId", "class"])
            for step in range(1, 6):
                for index in range(10):
                    writer.writerow([f"{step}-l-{index}", 2])
                for index in range(2):
                    writer.writerow([f"{step}-i-{index}", 1])
                for index in range(3):
                    writer.writerow([f"{step}-u-{index}", 3])

        manifest = {
            "batch_id": batch_id,
            "total_transactions": 75,
            "label_counts": {"licit": 50, "illicit": 10, "unknown": 15},
            "files": [
                {"filename": "txs_features.csv", "role": "features"},
                {"filename": "txs_classes.csv", "role": "classes"},
            ],
        }
        (processed_dir / "latest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        self.engine = MLEngine(self.backend_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_training_persists_models_and_held_out_metrics(self):
        results = self.engine.run_training()
        self.assertEqual(results["dataset"]["feature_rows"], 75)
        self.assertEqual(results["dataset"]["available_supervised_records"], 60)
        self.assertEqual(results["dataset"]["unknown_records_excluded_from_supervision"], 15)
        self.assertEqual(results["dataset"]["split_strategy"], "chronological_time_step")
        self.assertEqual(results["dataset"]["time_cutoff"], 4)
        self.assertEqual(results["dataset"]["trained_records"], 48)
        self.assertEqual(results["dataset"]["evaluated_records"], 12)
        self.assertNotIn("txId", results["dataset"]["feature_names"])
        self.assertNotIn("Time step", results["dataset"]["feature_names"])
        self.assertNotIn("class", results["dataset"]["feature_names"])
        self.assertNotIn("constant", results["dataset"]["feature_names"])
        self.assertNotIn("all_missing", results["dataset"]["feature_names"])
        self.assertIn("Logistic Regression", results["models"])
        self.assertIn("Random Forest", results["models"])
        self.assertIn("model_configuration", results)
        self.assertEqual(
            results["model_configuration"]["Random Forest"]["n_estimators"],
            120,
        )
        self.assertIn("model_configuration", self.engine.evaluation())
        self.assertEqual(results["models"][results["best_model"]]["positive_class"], "illicit")
        self.assertTrue(self.engine.model_path.is_file())
        self.assertTrue(self.engine.predictions_path.is_file())

    def test_predictions_preserve_ids_labels_pagination_and_threshold(self):
        self.engine.run_training()
        page = self.engine.predictions(page=1, page_size=10, threshold=0.5)
        self.assertEqual(len(page["items"]), 10)
        self.assertEqual(page["total"], 75)
        self.assertIn("transaction_id", page["items"][0])
        self.assertEqual(page["items"][0]["selected_model"], self.engine.evaluation()["best_model"])
        self.assertIn(page["items"][0]["ground_truth_label"], {"licit", "illicit", "unknown"})
        second_page = self.engine.predictions(page=2, page_size=10, threshold=0.5)
        self.assertNotEqual(
            page["items"][0]["transaction_id"],
            second_page["items"][0]["transaction_id"],
        )
        suspicious = self.engine.predictions(
            page=1,
            page_size=100,
            threshold=0.99,
            suspicious_only=True,
        )
        self.assertEqual(suspicious["total"], 0)

    def test_single_class_holdout_metrics_are_reported_as_unavailable(self):
        metrics = _metrics(np.array([0, 0]), np.array([0.1, 0.8]), 0.5)
        self.assertIsNone(metrics["roc_auc"])
        self.assertIsNone(metrics["pr_auc"])
        self.assertIsNone(metrics["recall"])
        self.assertIsNone(metrics["false_negative_rate"])
        self.assertIsNotNone(metrics["false_positive_rate"])
        self.assertIn("require both classes", metrics["unavailable_metric_reason"])

    def test_training_supports_a_single_rare_class_without_fabricating_metrics(self):
        class_path = self.backend_dir / "data" / "uploads" / "20261203-111111" / "txs_classes.csv"
        with class_path.open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        retained_illicit = False
        for row in rows:
            if row["class"] == "1":
                if retained_illicit:
                    row["class"] = "2"
                else:
                    retained_illicit = True
        with class_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["txId", "class"])
            writer.writeheader()
            writer.writerows(rows)

        results = self.engine.run_training()
        metrics = results["models"][results["best_model"]]
        self.assertEqual(results["dataset"]["trained_class_distribution"]["illicit"], 1)
        self.assertEqual(results["dataset"]["evaluated_class_distribution"]["illicit"], 0)
        self.assertIsNone(metrics["roc_auc"])
        self.assertIsNone(metrics["pr_auc"])
        self.assertIsNone(metrics["recall"])
        self.assertIsNone(metrics["false_negative_rate"])

    def test_predictions_support_global_sorting_and_summary_statistics(self):
        self.engine.run_training()
        page = self.engine.predictions(
            page=1,
            page_size=20,
            sort_by="illicit_probability",
            sort_order="desc",
        )
        probabilities = [item["illicit_probability"] for item in page["items"]]
        self.assertEqual(probabilities, sorted(probabilities, reverse=True))
        summary = self.engine.summary(0.5)
        self.assertEqual(summary["total_predictions"], 75)
        self.assertEqual(
            summary["prediction_distribution"]["licit"] + summary["prediction_distribution"]["illicit"],
            75,
        )
        self.assertEqual(
            summary["suspicious_count"],
            summary["prediction_distribution"]["illicit"],
        )

    def test_results_are_invalidated_when_dataset_changes(self):
        self.engine.run_training()
        manifest_path = self.backend_dir / "data" / "processed" / "latest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["batch_id"] = "20261204-111111"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        self.assertEqual(self.engine.get_status()["status"], "stale")
        with self.assertRaises(Exception) as context:
            self.engine.evaluation()
        self.assertEqual(context.exception.status_code, 409)

    def test_stratified_memory_sampling_keeps_both_labels_in_each_split(self):
        with patch("app.services.ml_engine.MEMORY_BUDGET_CAP", 2):
            results = self.engine.run_training()
        dataset = results["dataset"]
        self.assertTrue(dataset["sampling_applied"])
        self.assertEqual(dataset["sampled_supervised_records"], 4)
        self.assertGreater(dataset["trained_class_distribution"]["licit"], 0)
        self.assertGreater(dataset["trained_class_distribution"]["illicit"], 0)
        self.assertGreater(dataset["evaluated_class_distribution"]["licit"], 0)
        self.assertGreater(dataset["evaluated_class_distribution"]["illicit"], 0)

    def test_legacy_prediction_files_report_selected_model(self):
        results = self.engine.run_training()
        with self.engine.predictions_path.open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        with self.engine.predictions_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "transaction_id",
                    "predicted_class",
                    "illicit_probability",
                    "confidence",
                    "ground_truth_label",
                ],
            )
            writer.writeheader()
            writer.writerows(
                {key: value for key, value in row.items() if key != "selected_model"}
                for row in rows
            )
        page = self.engine.predictions(page_size=1)
        self.assertEqual(page["items"][0]["selected_model"], results["best_model"])

    def test_model_restore_evaluation_and_local_explanations(self):
        results = self.engine.run_training()
        restored = MLEngine(self.backend_dir)
        self.assertEqual(restored.evaluation()["best_model"], results["best_model"])
        self.assertGreater(len(restored.feature_importance()["features"]), 0)
        transaction_id = restored.predictions(page=1, page_size=1)["items"][0]["transaction_id"]
        explanation = restored.explain(transaction_id)
        self.assertEqual(explanation["transaction_id"], transaction_id)
        self.assertLessEqual(len(explanation["features"]), 20)
        with patch.object(ml_api, "ml_engine", restored):
            client = TestClient(app)
            self.assertEqual(client.get("/api/ml/status").status_code, 200)
            self.assertEqual(client.get("/api/ml/evaluation").status_code, 200)
            self.assertEqual(client.get("/api/ml/models").status_code, 200)
            self.assertEqual(client.get("/api/ml/summary").status_code, 200)
            self.assertEqual(client.get("/api/ml/feature-importance").status_code, 200)
            self.assertEqual(client.get("/api/ml/predictions?page=1&page_size=5").status_code, 200)
            sorted_predictions = client.get(
                "/api/ml/predictions?page=1&page_size=5&sort_by=illicit_probability&sort_order=desc"
            )
            self.assertEqual(sorted_predictions.status_code, 200)
            self.assertEqual(
                client.get("/api/ml/predictions?sort_by=invalid").status_code,
                422,
            )
            self.assertEqual(client.get("/api/ml/suspicious?threshold=0.25").status_code, 200)
            self.assertEqual(
                client.get(f"/api/ml/transactions/{transaction_id}/explanation").status_code,
                200,
            )

    def test_readiness_and_unknown_label_behavior(self):
        readiness = self.engine.readiness()
        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["label_counts"]["unknown"], 15)

    def test_api_readiness_training_validation_and_no_model_errors(self):
        with patch.object(ml_api, "ml_engine", self.engine):
            client = TestClient(app)
            readiness = client.get("/api/ml/readiness")
            self.assertEqual(readiness.status_code, 200)
            self.assertTrue(readiness.json()["data"]["ready"])

            invalid_threshold = client.post(
                "/api/ml/train",
                json={"classification_threshold": 1.2},
            )
            self.assertEqual(invalid_threshold.status_code, 422)

            evaluation = client.get("/api/ml/evaluation")
            self.assertEqual(evaluation.status_code, 409)

            with patch.object(
                self.engine,
                "start_training",
                return_value={"status": "running", "progress": 1, "message": "Training job queued."},
            ):
                started = client.post(
                    "/api/ml/train",
                    json={"classification_threshold": 0.5},
                )
            self.assertEqual(started.status_code, 200)
            self.assertEqual(started.json()["data"]["status"], "running")


if __name__ == "__main__":
    unittest.main()
