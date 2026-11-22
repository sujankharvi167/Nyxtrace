import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

import app.api.analysis as analysis_api
import app.api.ml as ml_api
from app.main import app
from app.services.dataset_processor import (
    MAX_FILE_SIZE_BYTES,
    MAX_TOTAL_UPLOAD_SIZE_BYTES,
    load_latest_dataset,
    normalize_label,
    process_uploads,
)


class DatasetProcessorTests(unittest.TestCase):
    def test_upload_and_preprocess_elliptic_files(self):
        features = (
            "txId,TimeStep,feature_1,feature_2\n"
            "1,1,10,20\n"
            "2,1,15,\n"
            "3,2,12,25\n"
            "3,2,12,25\n"
        )
        classes = "txId,class\n1,1\n2,2\n3,unknown\n"
        edgelist = "txId1,txId2\n1,2\n2,3\n"

        uploads = [
            UploadFile(filename="txs_features.csv", file=io.BytesIO(features.encode())),
            UploadFile(filename="txs_classes.csv", file=io.BytesIO(classes.encode())),
            UploadFile(filename="txs_edgelist.csv", file=io.BytesIO(edgelist.encode())),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            backend_dir = Path(temp_dir)
            result = asyncio.run(process_uploads(backend_dir, uploads))

            self.assertEqual(result["status"], "processed")
            self.assertEqual(result["total_transactions"], 3)
            self.assertEqual(result["duplicate_rows"], 1)
            self.assertEqual(result["label_counts"]["illicit"], 1)
            self.assertEqual(result["label_counts"]["licit"], 1)
            self.assertEqual(result["label_counts"]["unknown"], 1)
            self.assertEqual(len(result["files"]), 3)
            self.assertIsNotNone(load_latest_dataset(backend_dir))

    def test_unknown_label_is_never_mapped_to_licit(self):
        self.assertEqual(normalize_label("unknown"), "unknown")
        self.assertEqual(normalize_label("3"), "unknown")
        self.assertEqual(normalize_label("1"), "illicit")
        self.assertEqual(normalize_label("2"), "licit")

    def test_invalid_csv_structure_is_rejected(self):
        classes = "wrong_id,value\n1,hello\n"
        upload = UploadFile(filename="txs_classes.csv", file=io.BytesIO(classes.encode()))

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(Exception) as context:
                asyncio.run(process_uploads(Path(temp_dir), [upload]))
            self.assertIn("Could not detect", str(context.exception))

    def test_individual_file_limit_is_750_mb(self):
        self.assertEqual(MAX_FILE_SIZE_BYTES, 750 * 1024 * 1024)

    def test_total_upload_limit_is_800_mb(self):
        self.assertEqual(MAX_TOTAL_UPLOAD_SIZE_BYTES, 800 * 1024 * 1024)

    def test_backend_rejects_announced_oversized_file(self):
        upload = UploadFile(filename="txs_features.csv", file=io.BytesIO(b"txId\n1\n"))
        upload.size = MAX_FILE_SIZE_BYTES + 1

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(Exception) as context:
                asyncio.run(process_uploads(Path(temp_dir), [upload]))
            self.assertIn("750 MB", str(context.exception))
            self.assertEqual(context.exception.status_code, 413)

    def test_backend_rejects_combined_upload_above_800_mb(self):
        uploads = [
            UploadFile(filename=f"part_{index}.csv", file=io.BytesIO(b"id\n1\n"))
            for index in range(3)
        ]
        for upload in uploads:
            upload.size = 300 * 1024 * 1024

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(Exception) as context:
                asyncio.run(process_uploads(Path(temp_dir), uploads))
            self.assertIn("800 MB total size limit", str(context.exception))
            self.assertEqual(context.exception.status_code, 413)

    def test_streamed_size_limit_cleans_incomplete_batch(self):
        upload = UploadFile(filename="txs_features.csv", file=io.BytesIO(b"txId\n123\n"))
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.services.dataset_processor.MAX_FILE_SIZE_BYTES", 5), patch(
                "app.services.dataset_processor.STREAM_CHUNK_SIZE", 4
            ):
                with self.assertRaises(HTTPException) as context:
                    asyncio.run(process_uploads(Path(temp_dir), [upload]))
            self.assertEqual(context.exception.status_code, 413)
            upload_root = Path(temp_dir) / "data" / "uploads"
            self.assertEqual(list(upload_root.iterdir()), [])

    def test_interrupted_stream_removes_partial_upload_and_batch(self):
        upload = UploadFile(filename="txs_features.csv", file=io.BytesIO(b"txId\n123\n"))
        read_count = 0

        async def interrupted_read(size):
            nonlocal read_count
            read_count += 1
            if read_count == 1:
                return b"txId"
            raise asyncio.CancelledError()

        upload.read = interrupted_read
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.services.dataset_processor.STREAM_CHUNK_SIZE", 4):
                with self.assertRaises(asyncio.CancelledError):
                    asyncio.run(process_uploads(Path(temp_dir), [upload]))
            upload_root = Path(temp_dir) / "data" / "uploads"
            self.assertEqual(list(upload_root.iterdir()), [])

    def test_upload_endpoint_persists_dataset_and_reports_readiness(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backend_dir = Path(temp_dir)
            engine = __import__("app.services.ml_engine", fromlist=["MLEngine"]).MLEngine(backend_dir)
            files = [
                ("files", ("txs_features.csv", b"txId,signal\n1,0.2\n2,0.8\n", "text/csv")),
                ("files", ("txs_classes.csv", b"txId,class\n1,2\n2,1\n", "text/csv")),
            ]
            with patch.object(analysis_api, "BACKEND_DIR", backend_dir), patch.object(
                analysis_api, "ml_engine", engine
            ), patch.object(ml_api, "ml_engine", engine):
                client = TestClient(app)
                response = client.post("/api/analysis/upload", files=files)
                self.assertEqual(response.status_code, 200, response.text)
                batch_id = response.json()["data"]["batch_id"]
                dataset = client.get("/api/analysis/dataset").json()["data"]
                readiness = client.get("/api/ml/readiness").json()["data"]
                status = client.get("/api/analysis/status").json()["data"]

            self.assertEqual(dataset["batch_id"], batch_id)
            self.assertTrue(readiness["ready"])
            self.assertEqual(readiness["label_counts"]["unknown"], 0)
            self.assertEqual(status["batch_id"], batch_id)
            self.assertEqual(status["ml_pipeline"], "idle")


if __name__ == "__main__":
    unittest.main()
