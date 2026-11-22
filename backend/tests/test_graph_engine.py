import csv
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app.services.graph_engine import GraphEngine


class GraphEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backend_dir = Path(self.temp_dir.name)
        self.batch_id = "20261222-120000"
        processed = self.backend_dir / "data" / "processed" / self.batch_id
        processed.mkdir(parents=True)

        with (processed / "txs_edgelist.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["txId1", "txId2"])
            writer.writerows([
                ["1", "2"],
                ["2", "3"],
                ["3", "1"],
                ["2", "4"],
                ["2", "4"],
                ["4", "2"],
                ["", "5"],
            ])

        with (processed / "txs_classes.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["txId", "class"])
            writer.writerows([
                ["1", 2],
                ["2", 1],
                ["3", 3],
                ["4", 2],
                ["6", 2],
            ])

        manifest = {
            "batch_id": self.batch_id,
            "uploaded_at": "2026-12-22T12:00:00+00:00",
            "status": "processed",
            "total_transactions": 5,
            "total_edges": 6,
            "total_files": 2,
            "label_counts": {"licit": 2, "illicit": 1, "unknown": 1},
            "files": [],
        }
        (processed / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (self.backend_dir / "data" / "processed" / "latest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        self.engine = GraphEngine(self.backend_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_build_creates_nodes_edges_labels_and_statistics(self):
        manifest = self.engine.build()
        self.assertEqual(manifest["nodes"], 5)
        self.assertEqual(manifest["edges"], 5)
        self.assertEqual(manifest["duplicate_edges_skipped"], 1)

        graph = self.engine.load_graph()
        self.assertTrue(graph.has_edge("1", "2"))
        self.assertEqual(graph.nodes["1"]["ground_truth_label"], "licit")
        self.assertEqual(graph.nodes["2"]["ground_truth_label"], "illicit")
        self.assertEqual(graph.nodes["3"]["ground_truth_label"], "unknown")
        self.assertFalse(manifest["ml_predictions_available"])

        stats = self.engine.statistics()
        self.assertEqual(stats["nodes"], 5)
        self.assertEqual(stats["edges"], 5)
        self.assertGreaterEqual(stats["connected_components"], 1)

    def test_fan_in_fan_out_and_cycles(self):
        self.engine.build()
        fan_in = self.engine.fan_in()
        fan_out = self.engine.fan_out()
        cycles = self.engine.cycles()

        fan_in_ids = {item["transaction_id"] for item in fan_in["items"]}
        fan_out_ids = {item["transaction_id"] for item in fan_out["items"]}
        self.assertIn("2", fan_in_ids)
        self.assertIn("2", fan_out_ids)
        self.assertTrue(cycles["items"])
        self.assertIn(
            cycles["items"][0]["cycle_length"],
            {2, 3},
        )

    def test_path_missing_and_upstream_downstream(self):
        self.engine.build()
        path = self.engine.shortest_path("1", "4")
        self.assertTrue(path["path_found"])
        self.assertEqual(path["transaction_ids"], ["1", "2", "4"])
        missing = self.engine.shortest_path("4", "6")
        self.assertFalse(missing["path_found"])

        upstream = self.engine.neighborhood("2", depth=2, limit=100, direction="upstream")
        downstream = self.engine.neighborhood("2", depth=2, limit=100, direction="downstream")
        upstream_ids = {node["transaction_id"] for node in upstream["nodes"]}
        downstream_ids = {node["transaction_id"] for node in downstream["nodes"]}
        self.assertIn("1", upstream_ids)
        self.assertIn("3", downstream_ids)

    def test_missing_and_empty_edgelist_are_rejected(self):
        (self.backend_dir / "data" / "processed" / self.batch_id / "txs_edgelist.csv").unlink()
        with self.assertRaises(HTTPException) as context:
            self.engine.build()
        self.assertEqual(context.exception.status_code, 409)

        empty_path = self.backend_dir / "data" / "processed" / self.batch_id / "txs_edgelist.csv"
        empty_path.write_text("txId1,txId2\n", encoding="utf-8")
        manifest = self.engine.build()
        self.assertEqual(manifest["nodes"], 5)
        self.assertEqual(manifest["edges"], 0)


if __name__ == "__main__":
    unittest.main()
