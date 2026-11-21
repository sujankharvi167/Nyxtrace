import ctypes
import hashlib
import json
import math
import os
import re
import threading
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from fastapi import HTTPException
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.services.dataset_processor import (
    _find_column,
    _find_id_column,
    load_latest_dataset,
    normalize_label,
)


RANDOM_SEED = 42
CSV_CHUNK_SIZE = 10_000
DEFAULT_THRESHOLD = 0.5
MAX_RESULTS_PAGE_SIZE = 100
MEMORY_BUDGET_CAP = 1024 * 1024 * 1024
TRAINING_MEMORY_MULTIPLIER = 8
PREDICTION_COLUMNS = [
    "transaction_id",
    "predicted_class",
    "illicit_probability",
    "confidence",
    "selected_model",
    "ground_truth_label",
]


def _available_memory_bytes() -> int:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullAvailPhys)
    else:
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            available_pages = os.sysconf("SC_AVPHYS_PAGES")
            return int(page_size * available_pages)
        except (AttributeError, OSError, ValueError):
            pass
    return 2 * 1024 * 1024 * 1024


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    return value


def _is_target_or_identifier(column: str, id_column: str, time_column: Optional[str]) -> bool:
    if column == id_column or column == time_column:
        return True
    normalized = re.sub(r"[^a-z0-9]", "", column.lower())
    return normalized in {
        "id",
        "txid",
        "transactionid",
        "nodeid",
        "class",
        "label",
        "category",
        "target",
        "groundtruth",
        "groundtruthlabel",
        "illicitlabel",
        "transactionclass",
    }


def _stable_hash(identifier: str) -> int:
    digest = hashlib.blake2b(
        f"{RANDOM_SEED}:{identifier}".encode("utf-8"),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def _iter_csv_chunks(*args: Any, **kwargs: Any) -> Iterator[pd.DataFrame]:
    reader = pd.read_csv(*args, **kwargs)
    try:
        yield from reader
    finally:
        reader.close()


def _metrics(y_true: np.ndarray, probabilities: np.ndarray, threshold: float) -> Dict[str, Any]:
    predictions = (probabilities >= threshold).astype(np.int8)
    tn, fp, fn, tp = (
        int(value)
        for value in confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    )
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "confusion_matrix": {
            "true_negative": tn,
            "false_positive": fp,
            "false_negative": fn,
            "true_positive": tp,
        },
        "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "false_negative_rate": float(fn / (fn + tp)) if (fn + tp) else 0.0,
        "threshold": float(threshold),
        "positive_class": "illicit",
    }


class MLEngine:
    def __init__(self, backend_dir: Path):
        self.backend_dir = backend_dir.resolve()
        self.ml_dir = self.backend_dir / "data" / "ml"
        self.status_path = self.ml_dir / "status.json"
        self.results_path = self.ml_dir / "results.json"
        self.model_path = self.ml_dir / "best_model.joblib"
        self.predictions_path = self.ml_dir / "predictions.csv"
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if not self.status_path.exists():
            return {"status": "idle", "progress": 0, "message": "Training has not started."}
        try:
            state = json.loads(self.status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"status": "idle", "progress": 0, "message": "Training has not started."}
        if state.get("status") == "running":
            state.update(
                status="error",
                message="The previous training process stopped before completing.",
                error="Training was interrupted by a backend restart.",
            )
        return state

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(_json_safe(payload), indent=2, allow_nan=False),
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def _set_state(self, **updates: Any) -> Dict[str, Any]:
        with self._lock:
            self._state = {**self._state, **updates, "updated_at": datetime.now(timezone.utc).isoformat()}
            self._write_json(self.status_path, self._state)
            return dict(self._state)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def _latest_paths(self) -> Tuple[Dict[str, Any], Path, Path, Path]:
        manifest = load_latest_dataset(self.backend_dir)
        if not manifest:
            raise HTTPException(status_code=409, detail="Upload a dataset before training a model.")
        batch_id = str(manifest.get("batch_id", ""))
        if not re.fullmatch(r"\d{8}-\d{6}", batch_id):
            raise HTTPException(status_code=409, detail="The latest dataset manifest has an invalid batch identifier.")
        upload_dir = (self.backend_dir / "data" / "uploads" / batch_id).resolve()
        expected_root = (self.backend_dir / "data" / "uploads").resolve()
        if not upload_dir.is_relative_to(expected_root):
            raise HTTPException(status_code=409, detail="The latest dataset upload path is invalid.")

        roles = {str(item.get("role")): item for item in manifest.get("files", [])}
        feature_entry = roles.get("features")
        class_entry = roles.get("classes")
        if not feature_entry or not class_entry:
            raise HTTPException(
                status_code=409,
                detail="Stage 3 requires both txs_features.csv and txs_classes.csv in the latest upload.",
            )
        feature_path = upload_dir / Path(str(feature_entry["filename"])).name
        class_path = upload_dir / Path(str(class_entry["filename"])).name
        if not feature_path.is_file() or not class_path.is_file():
            raise HTTPException(status_code=409, detail="The latest dataset feature or class CSV is missing.")
        return manifest, upload_dir, feature_path, class_path

    def readiness(self) -> Dict[str, Any]:
        try:
            manifest, _, feature_path, class_path = self._latest_paths()
        except HTTPException as exc:
            return {
                "ready": False,
                "message": str(exc.detail),
                "total_transactions": 0,
                "label_counts": {"licit": 0, "illicit": 0, "unknown": 0},
            }
        return {
            "ready": True,
            "message": "Feature and class CSVs are available for supervised training.",
            "batch_id": manifest["batch_id"],
            "total_transactions": int(manifest.get("total_transactions", 0)),
            "label_counts": manifest.get("label_counts", {"licit": 0, "illicit": 0, "unknown": 0}),
            "files": {
                "features": {"name": feature_path.name, "size_bytes": feature_path.stat().st_size},
                "classes": {"name": class_path.name, "size_bytes": class_path.stat().st_size},
            },
            "supervised_labels": ["licit", "illicit"],
            "excluded_label": "unknown",
        }

    def start_training(self, threshold: float = DEFAULT_THRESHOLD) -> Dict[str, Any]:
        if not 0.05 <= threshold <= 0.95:
            raise HTTPException(status_code=422, detail="Classification threshold must be between 0.05 and 0.95.")
        if not self.readiness()["ready"]:
            raise HTTPException(status_code=409, detail=self.readiness()["message"])
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise HTTPException(status_code=409, detail="A model training job is already running.")
            if self._state.get("status") == "running":
                raise HTTPException(status_code=409, detail="A model training job is already running.")
            run_id = uuid.uuid4().hex
            self._state = {
                "run_id": run_id,
                "status": "running",
                "progress": 1,
                "message": "Training job queued.",
                "error": None,
                "classification_threshold": threshold,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            self._write_json(self.status_path, self._state)
            self._thread = threading.Thread(
                target=self._run_training,
                args=(threshold,),
                name=f"nyxtrace-ml-{run_id[:8]}",
                daemon=True,
            )
            self._thread.start()
            return dict(self._state)

    def _run_training(self, threshold: float) -> None:
        try:
            results, bundle = self._train(threshold, self._set_state)
            temporary_model = self.ml_dir / f"best_model.{uuid.uuid4().hex}.tmp"
            joblib.dump(bundle, temporary_model, compress=3)
            os.replace(temporary_model, self.model_path)
            self._write_json(self.results_path, results)
            self._set_state(
                status="completed",
                progress=100,
                message="Model comparison, evaluation, and batch prediction completed.",
                error=None,
                finished_at=datetime.now(timezone.utc).isoformat(),
                best_model=results["best_model"],
                available_records=results["dataset"]["available_supervised_records"],
                trained_records=results["dataset"]["trained_records"],
                evaluated_records=results["dataset"]["evaluated_records"],
            )
        except Exception as exc:
            self._set_state(
                status="error",
                message="Model training failed.",
                error=f"{type(exc).__name__}: {exc}",
                finished_at=datetime.now(timezone.utc).isoformat(),
            )

    def run_training(self, threshold: float = DEFAULT_THRESHOLD) -> Dict[str, Any]:
        if not 0.05 <= threshold <= 0.95:
            raise HTTPException(status_code=422, detail="Classification threshold must be between 0.05 and 0.95.")
        results, bundle = self._train(threshold, self._set_state)
        self.ml_dir.mkdir(parents=True, exist_ok=True)
        temporary_model = self.ml_dir / f"best_model.{uuid.uuid4().hex}.tmp"
        joblib.dump(bundle, temporary_model, compress=3)
        os.replace(temporary_model, self.model_path)
        self._write_json(self.results_path, results)
        self._set_state(
            status="completed",
            progress=100,
            message="Model comparison, evaluation, and batch prediction completed.",
            error=None,
            finished_at=datetime.now(timezone.utc).isoformat(),
            best_model=results["best_model"],
            available_records=results["dataset"]["available_supervised_records"],
            trained_records=results["dataset"]["trained_records"],
            evaluated_records=results["dataset"]["evaluated_records"],
        )
        return results

    def _train(
        self,
        threshold: float,
        progress: Callable[..., Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        manifest, _, feature_path, class_path = self._latest_paths()
        self.ml_dir.mkdir(parents=True, exist_ok=True)
        progress(status="running", progress=5, message="Inspecting dataset identifiers, labels, and feature columns.")

        class_columns = pd.read_csv(class_path, nrows=0).columns.tolist()
        class_id = _find_id_column(class_columns)
        class_label = _find_column(class_columns, ("class", "label", "category"))
        if not class_id or not class_label or class_id == class_label:
            raise ValueError("Could not identify distinct transaction ID and class columns in the class CSV.")
        classes = pd.read_csv(
            class_path,
            usecols=[class_id, class_label],
            dtype={class_id: "string", class_label: "string"},
            keep_default_na=False,
        )
        if classes[class_id].eq("").any():
            raise ValueError("The class CSV contains empty transaction identifiers.")
        if classes[class_id].duplicated().any():
            raise ValueError("The class CSV contains duplicate transaction identifiers.")
        labels = dict(zip(classes[class_id].astype(str), classes[class_label].map(normalize_label)))
        class_distribution = {
            label: int(sum(value == label for value in labels.values()))
            for label in ("licit", "illicit", "unknown")
        }

        feature_columns = pd.read_csv(feature_path, nrows=0).columns.tolist()
        feature_id = _find_id_column(feature_columns)
        if not feature_id:
            raise ValueError("Could not detect a transaction ID column in the feature CSV.")
        time_column = _find_column(feature_columns, ("timestep", "time_step"))
        if time_column == feature_id:
            time_column = None
        candidate_columns = [
            column
            for column in feature_columns
            if not _is_target_or_identifier(column, feature_id, time_column)
        ]
        if not candidate_columns:
            raise ValueError("No potential numeric predictors were found in the feature CSV.")

        valid_numeric: Dict[str, int] = {column: 0 for column in candidate_columns}
        nonmissing_numeric: Dict[str, int] = {column: 0 for column in candidate_columns}
        time_counts: Dict[float, Dict[str, int]] = {}
        time_ids: Dict[float, Dict[str, List[str]]] = {}
        seen_ids: set[str] = set()
        feature_rows = 0
        matched_rows = 0
        matched_supervised_rows = 0
        time_valid_rows = 0
        fallback_ids: Dict[str, List[str]] = {"licit": [], "illicit": []}
        expected_feature_rows = max(int(manifest.get("total_transactions", 0)), 1)
        next_scan_progress = 50_000

        read_dtypes = {feature_id: "string"}
        for chunk in _iter_csv_chunks(
            feature_path,
            dtype=read_dtypes,
            chunksize=CSV_CHUNK_SIZE,
            low_memory=False,
            keep_default_na=False,
        ):
            feature_rows += len(chunk)
            if feature_rows >= next_scan_progress:
                progress(
                    progress=min(20, 5 + int(15 * feature_rows / expected_feature_rows)),
                    message=f"Inspecting dataset schema and labels ({min(feature_rows, expected_feature_rows):,} rows).",
                )
                next_scan_progress += 50_000
            ids = chunk[feature_id].astype(str)
            if ids.eq("").any():
                raise ValueError("The feature CSV contains empty transaction identifiers.")
            if ids.duplicated().any():
                raise ValueError("The feature CSV contains duplicate transaction identifiers.")
            duplicate_across_chunks = next((identifier for identifier in ids if identifier in seen_ids), None)
            if duplicate_across_chunks is not None:
                raise ValueError(f"Duplicate feature transaction ID detected: {duplicate_across_chunks}")
            seen_ids.update(ids.tolist())

            row_labels = ids.map(labels)
            matched_rows += int(row_labels.notna().sum())
            matched_supervised_rows += int(row_labels.isin(["licit", "illicit"]).sum())
            supervised = row_labels.isin(["licit", "illicit"])
            for label in ("licit", "illicit"):
                fallback_ids[label].extend(ids[row_labels.eq(label)].tolist())
            if time_column:
                time_values = pd.to_numeric(chunk[time_column], errors="coerce")
                valid_times = time_values.notna() & np.isfinite(time_values.astype(float))
                time_valid_rows += int(valid_times.sum())
                timeline = pd.DataFrame(
                    {
                        "step": time_values[supervised & valid_times],
                        "label": row_labels[supervised & valid_times],
                        "id": ids[supervised & valid_times],
                    }
                )
                if not timeline.empty:
                    for (step, label), group in timeline.groupby(["step", "label"], sort=False):
                        counts = time_counts.setdefault(float(step), {"licit": 0, "illicit": 0})
                        counts[str(label)] += len(group)
                        time_ids.setdefault(float(step), {"licit": [], "illicit": []})[
                            str(label)
                        ].extend(group["id"].astype(str).tolist())

            for column in candidate_columns:
                raw = chunk[column]
                converted = pd.to_numeric(raw, errors="coerce")
                finite = np.isfinite(converted.to_numpy(dtype=np.float64, na_value=np.nan))
                valid_numeric[column] += int(finite.sum())
                nonmissing_numeric[column] += int(raw.notna().sum())

        numeric_columns = [
            column
            for column in candidate_columns
            if valid_numeric[column] > 0
            and valid_numeric[column] / max(nonmissing_numeric[column], 1) >= 0.80
        ]
        if not numeric_columns:
            raise ValueError("No numeric predictor columns passed numeric-value validation.")

        time_steps = sorted(time_counts)
        split_strategy = "stratified_random"
        time_cutoff: Optional[float] = None
        split_counts = {"train": {"licit": 0, "illicit": 0}, "test": {"licit": 0, "illicit": 0}}
        if time_column and time_valid_rows >= int(feature_rows * 0.95) and len(time_steps) > 1:
            total_supervised = sum(
                time_counts[step]["licit"] + time_counts[step]["illicit"]
                for step in time_steps
            )
            candidates: List[Tuple[float, float, Dict[str, Dict[str, int]]]] = []
            for index in range(1, len(time_steps)):
                cutoff = time_steps[index - 1]
                train_counts = {"licit": 0, "illicit": 0}
                test_counts = {"licit": 0, "illicit": 0}
                for step in time_steps:
                    target = train_counts if step <= cutoff else test_counts
                    for label in target:
                        target[label] += time_counts[step][label]
                if min(train_counts.values()) == 0 or min(test_counts.values()) == 0:
                    continue
                test_count = sum(test_counts.values())
                target_fraction = abs((test_count / max(total_supervised, 1)) - 0.20)
                temporal_fraction = abs((index / len(time_steps)) - 0.80)
                candidates.append(
                    (target_fraction + temporal_fraction * 0.15, cutoff, {"train": train_counts, "test": test_counts})
                )
            if candidates:
                _, time_cutoff, split_counts = min(candidates, key=lambda item: item[0])
                split_strategy = "chronological_time_step"

        fallback_train_ids: set[str] = set()
        fallback_test_ids: set[str] = set()
        split_ids: Dict[str, Dict[str, List[str]]] = {
            "train": {"licit": [], "illicit": []},
            "test": {"licit": [], "illicit": []},
        }
        if split_strategy == "stratified_random":
            from sklearn.model_selection import train_test_split

            split_counts = {"train": {}, "test": {}}
            for label in ("licit", "illicit"):
                identifiers = fallback_ids[label]
                if len(identifiers) < 2:
                    raise ValueError(f"At least two {label} records are required for stratified train/test splitting.")
                train_ids, test_ids = train_test_split(
                    identifiers,
                    test_size=0.20,
                    random_state=RANDOM_SEED,
                    shuffle=True,
                )
                fallback_train_ids.update(train_ids)
                fallback_test_ids.update(test_ids)
                split_ids["train"][label] = train_ids
                split_ids["test"][label] = test_ids
                split_counts["train"][label] = len(train_ids)
                split_counts["test"][label] = len(test_ids)
        else:
            for step, identifiers_by_label in time_ids.items():
                split = "train" if step <= float(time_cutoff) else "test"
                for label in ("licit", "illicit"):
                    split_ids[split][label].extend(identifiers_by_label[label])

        available_supervised = sum(class_distribution[label] for label in ("licit", "illicit"))
        if matched_supervised_rows < available_supervised:
            raise ValueError(
                f"Only {matched_supervised_rows:,} feature rows match licit/illicit labels; "
                f"{available_supervised:,} labeled records were expected."
            )
        if min(split_counts["train"].values()) == 0 or min(split_counts["test"].values()) == 0:
            raise ValueError("The selected train/test split does not contain both supervised classes.")

        memory_budget = min(MEMORY_BUDGET_CAP, max(128 * 1024 * 1024, _available_memory_bytes() // 4))
        estimated_bytes = available_supervised * len(numeric_columns) * 4 * TRAINING_MEMORY_MULTIPLIER
        target_sampling_rate = min(1.0, memory_budget / max(estimated_bytes, 1))
        sampling_targets: Dict[Tuple[str, str], int] = {}
        target_sampled_records = 0
        for split in ("train", "test"):
            for label in ("licit", "illicit"):
                candidates = split_ids[split][label]
                target_count = (
                    len(candidates)
                    if target_sampling_rate >= 1.0
                    else min(len(candidates), max(1, int(len(candidates) * target_sampling_rate)))
                )
                sampling_targets[(split, label)] = target_count
                target_sampled_records += target_count
        splittable_supervised_records = sum(
            split_counts[split][label]
            for split in ("train", "test")
            for label in ("licit", "illicit")
        )
        sampled = target_sampled_records < splittable_supervised_records
        selected_ids: set[str] = set()
        if sampled:
            for split in ("train", "test"):
                for label in ("licit", "illicit"):
                    candidates = split_ids[split][label]
                    target_count = sampling_targets[(split, label)]
                    if target_count < len(candidates):
                        selected_ids.update(
                            sorted(candidates, key=_stable_hash)[:target_count]
                        )
                    else:
                        selected_ids.update(candidates)
        progress(
            progress=25,
            message=(
                f"Preparing {len(numeric_columns)} numeric features; "
                f"{available_supervised:,} labeled records available"
                f"{f'; sampling {target_sampled_records:,} to fit memory' if sampled else ''}."
            ),
            dataset_rows=feature_rows,
        )

        train_features: List[np.ndarray] = []
        test_features: List[np.ndarray] = []
        train_labels: List[np.ndarray] = []
        test_labels: List[np.ndarray] = []
        train_ids: List[str] = []
        test_ids: List[str] = []
        prepared_rows = 0
        next_prepare_progress = 50_000
        for chunk in _iter_csv_chunks(
            feature_path,
            dtype=read_dtypes,
            chunksize=CSV_CHUNK_SIZE,
            low_memory=False,
            keep_default_na=False,
        ):
            prepared_rows += len(chunk)
            if prepared_rows >= next_prepare_progress:
                progress(
                    progress=min(41, 25 + int(16 * prepared_rows / expected_feature_rows)),
                    message=f"Preparing numeric training and held-out rows ({min(prepared_rows, expected_feature_rows):,} rows).",
                )
                next_prepare_progress += 50_000
            ids = chunk[feature_id].astype(str)
            row_labels = ids.map(labels)
            is_licit = row_labels.eq("licit").to_numpy()
            is_illicit = row_labels.eq("illicit").to_numpy()
            is_supervised = is_licit | is_illicit
            if not is_supervised.any():
                continue
            if split_strategy == "chronological_time_step":
                steps = pd.to_numeric(chunk[time_column], errors="coerce").to_numpy(dtype=np.float64)
                in_train = np.isfinite(steps) & (steps <= float(time_cutoff))
                in_test = np.isfinite(steps) & (steps > float(time_cutoff))
            else:
                in_train = ids.isin(fallback_train_ids).to_numpy()
                in_test = ids.isin(fallback_test_ids).to_numpy()
            values = chunk[numeric_columns].apply(pd.to_numeric, errors="coerce").to_numpy(
                dtype=np.float32,
                na_value=np.nan,
            )
            values[~np.isfinite(values)] = np.nan

            for split, mask, feature_list, label_list, id_list in (
                ("train", is_supervised & in_train, train_features, train_labels, train_ids),
                ("test", is_supervised & in_test, test_features, test_labels, test_ids),
            ):
                if not mask.any():
                    continue
                selected = np.flatnonzero(mask)
                if sampled:
                    keep = ids.iloc[selected].isin(selected_ids).to_numpy()
                    if not keep.any():
                        continue
                    selected = selected[keep]
                feature_list.append(values[selected])
                label_list.append(is_illicit[selected].astype(np.int8))
                id_list.extend(ids.iloc[selected].tolist())
            del values

        del seen_ids, fallback_ids, time_counts, time_ids, split_ids, selected_ids
        if not train_features or not test_features:
            raise ValueError("No records remained after applying the selected train/test split.")
        X_train = np.concatenate(train_features, axis=0)
        X_test = np.concatenate(test_features, axis=0)
        y_train = np.concatenate(train_labels)
        y_test = np.concatenate(test_labels)
        del train_features, test_features, train_labels, test_labels
        if len(np.unique(y_train)) != 2 or len(np.unique(y_test)) != 2:
            raise ValueError("The reproducible split/sample does not contain both classes in train and test.")

        train_valid = np.isfinite(X_train)
        valid_counts = train_valid.sum(axis=0)
        safe_min = np.where(train_valid, X_train, np.inf).min(axis=0)
        safe_max = np.where(train_valid, X_train, -np.inf).max(axis=0)
        usable = (valid_counts > 0) & (safe_min != safe_max)
        dropped_features = [
            {"name": name, "reason": "all_missing_in_training"}
            for index, name in enumerate(numeric_columns)
            if valid_counts[index] == 0
        ] + [
            {"name": name, "reason": "constant_in_training"}
            for index, name in enumerate(numeric_columns)
            if valid_counts[index] > 0 and safe_min[index] == safe_max[index]
        ]
        feature_names = [name for name, keep in zip(numeric_columns, usable) if keep]
        X_train = X_train[:, usable]
        X_test = X_test[:, usable]
        if X_train.shape[1] == 0:
            raise ValueError("All candidate numeric features are missing or constant in training data.")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            medians = np.nanmedian(X_train, axis=0).astype(np.float32)
        X_train = np.where(np.isfinite(X_train), X_train, medians).astype(np.float32, copy=False)
        X_test = np.where(np.isfinite(X_test), X_test, medians).astype(np.float32, copy=False)

        del train_ids
        del fallback_train_ids, fallback_test_ids
        progress(
            progress=43,
            message=(
                f"Training on {len(y_train):,} records and holding out {len(y_test):,} "
                f"records using {split_strategy.replace('_', ' ')}."
            ),
        )

        logistic_configuration = {
            "class_weight": "balanced",
            "C": 0.1,
            "max_iter": 400,
            "random_state": RANDOM_SEED,
            "solver": "lbfgs",
        }
        forest_configuration = {
            "n_estimators": 120,
            "max_depth": 20,
            "min_samples_leaf": 3,
            "max_features": "sqrt",
            "class_weight": "balanced_subsample",
            "n_jobs": 2,
            "random_state": RANDOM_SEED,
        }
        model_configuration = {
            "Logistic Regression": {**logistic_configuration, "scaling": "StandardScaler"},
            "Random Forest": forest_configuration,
        }
        models: Dict[str, Any] = {
            "Logistic Regression": make_pipeline(
                StandardScaler(),
                LogisticRegression(**logistic_configuration),
            ),
            "Random Forest": RandomForestClassifier(**forest_configuration),
        }
        model_results: Dict[str, Any] = {}
        estimators: Dict[str, Any] = {}
        for index, (name, estimator) in enumerate(models.items()):
            progress(
                progress=48 + index * 17,
                message=f"Fitting {name} with class-imbalance weighting.",
            )
            estimator.fit(X_train, y_train)
            classes_order = list(estimator.classes_)
            positive_index = classes_order.index(1)
            probabilities = estimator.predict_proba(X_test)[:, positive_index]
            metrics = _metrics(y_test, probabilities, threshold)
            metrics["train_records"] = int(len(y_train))
            metrics["test_records"] = int(len(y_test))
            metrics["test_class_distribution"] = {
                "licit": int(np.count_nonzero(y_test == 0)),
                "illicit": int(np.count_nonzero(y_test == 1)),
            }
            model_results[name] = metrics
            estimators[name] = estimator

        best_model_name = max(
            model_results,
            key=lambda name: (model_results[name]["f1"], model_results[name]["pr_auc"]),
        )
        best_model = estimators[best_model_name]
        metadata = {
            "batch_id": manifest["batch_id"],
            "features_file": feature_path.name,
            "classes_file": class_path.name,
            "feature_rows": int(feature_rows),
            "matched_feature_class_rows": int(matched_rows),
            "available_supervised_records": int(available_supervised),
            "available_class_distribution": class_distribution,
            "sampling_applied": bool(sampled),
            "sampling_rate": float(target_sampled_records / splittable_supervised_records),
            "sampled_supervised_records": int(len(y_train) + len(y_test)),
            "records_excluded_by_time_split": int(available_supervised - splittable_supervised_records),
            "trained_records": int(len(y_train)),
            "evaluated_records": int(len(y_test)),
            "trained_class_distribution": {
                "licit": int(np.count_nonzero(y_train == 0)),
                "illicit": int(np.count_nonzero(y_train == 1)),
            },
            "evaluated_class_distribution": {
                "licit": int(np.count_nonzero(y_test == 0)),
                "illicit": int(np.count_nonzero(y_test == 1)),
            },
            "unknown_records_excluded_from_supervision": int(class_distribution["unknown"]),
            "split_strategy": split_strategy,
            "time_column": time_column if split_strategy == "chronological_time_step" else None,
            "time_cutoff": time_cutoff,
            "train_time_range": (
                [float(time_steps[0]), float(time_cutoff)]
                if split_strategy == "chronological_time_step"
                else None
            ),
            "test_time_range": (
                [
                    float(next(step for step in time_steps if step > float(time_cutoff))),
                    float(time_steps[-1]),
                ]
                if split_strategy == "chronological_time_step"
                else None
            ),
            "random_seed": RANDOM_SEED,
            "feature_count": int(len(feature_names)),
            "feature_names": feature_names,
            "dropped_features": dropped_features,
            "class_weighting": {
                "Logistic Regression": "balanced",
                "Random Forest": "balanced_subsample",
            },
            "threshold": float(threshold),
            "memory_budget_bytes": int(memory_budget),
            "estimated_training_memory_bytes": int(estimated_bytes),
            "id_column": feature_id,
            "class_id_column": class_id,
            "class_label_column": class_label,
        }

        del X_train, X_test, y_train, y_test
        progress(progress=78, message="Writing batched predictions for labeled and unknown transactions.")
        prediction_tmp = self.ml_dir / f"predictions.{uuid.uuid4().hex}.tmp"
        try:
            self._write_predictions(
                feature_path=feature_path,
                id_column=feature_id,
                numeric_columns=numeric_columns,
                feature_names=feature_names,
                medians=medians,
                estimator=best_model,
                threshold=threshold,
                labels=labels,
                selected_model=best_model_name,
                output_path=prediction_tmp,
                progress=progress,
                total_rows=feature_rows,
            )
            os.replace(prediction_tmp, self.predictions_path)
        except Exception:
            prediction_tmp.unlink(missing_ok=True)
            raise

        global_importance = self._feature_importance(
            best_model_name,
            best_model,
            feature_names,
        )
        results = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "best_model": best_model_name,
            "selection_criterion": "Highest held-out illicit-class F1; PR-AUC breaks ties.",
            "dataset": metadata,
            "models": model_results,
            "model_configuration": model_configuration,
            "global_feature_importance": global_importance,
            "prediction_file": str(self.predictions_path),
            "explanation_method": (
                "Model-specific global feature importance and local feature-ablation sensitivity. "
                "Local effects are sensitivity estimates, not causal explanations."
            ),
        }
        bundle = {
            "best_model_name": best_model_name,
            "estimator": best_model,
            "estimators": estimators,
            "feature_names": feature_names,
            "numeric_columns": numeric_columns,
            "medians": medians,
            "labels": {"0": "licit", "1": "illicit"},
            "metadata": metadata,
            "metrics": model_results,
            "model_configuration": model_configuration,
            "threshold": threshold,
            "global_feature_importance": global_importance,
            "id_column": feature_id,
            "time_column": time_column,
            "classes": class_distribution,
        }
        progress(progress=95, message="Saving reproducible model artifacts and evaluation results.")
        return results, bundle

    def _write_predictions(
        self,
        feature_path: Path,
        id_column: str,
        numeric_columns: List[str],
        feature_names: List[str],
        medians: np.ndarray,
        estimator: Any,
        threshold: float,
        labels: Dict[str, str],
        selected_model: str,
        output_path: Path,
        progress: Optional[Callable[..., Any]] = None,
        total_rows: int = 0,
    ) -> None:
        write_header = True
        positive_index = list(estimator.classes_).index(1)
        dtypes = {id_column: "string"}
        selected_indexes = [numeric_columns.index(name) for name in feature_names]
        predicted_rows = 0
        for chunk in _iter_csv_chunks(
            feature_path,
            dtype=dtypes,
            chunksize=CSV_CHUNK_SIZE,
            low_memory=False,
            keep_default_na=False,
        ):
            predicted_rows += len(chunk)
            if progress and total_rows:
                progress(
                    progress=min(94, 78 + int(16 * predicted_rows / total_rows)),
                    message=f"Scoring transaction batches ({min(predicted_rows, total_rows):,} rows).",
                )
            ids = chunk[id_column].astype(str)
            values = chunk[numeric_columns].apply(pd.to_numeric, errors="coerce").to_numpy(
                dtype=np.float32,
                na_value=np.nan,
            )
            values[~np.isfinite(values)] = np.nan
            values = values[:, selected_indexes]
            values = np.where(np.isfinite(values), values, medians).astype(np.float32, copy=False)
            probabilities = estimator.predict_proba(values)[:, positive_index]
            predicted = np.where(probabilities >= threshold, "illicit", "licit")
            predictions = pd.DataFrame(
                {
                    "transaction_id": ids.to_numpy(),
                    "predicted_class": predicted,
                    "illicit_probability": probabilities.astype(np.float32),
                    "confidence": np.maximum(probabilities, 1.0 - probabilities).astype(np.float32),
                    "selected_model": selected_model,
                    "ground_truth_label": ids.map(labels).fillna("unlabeled").to_numpy(),
                },
                columns=PREDICTION_COLUMNS,
            )
            predictions.to_csv(
                output_path,
                index=False,
                mode="w" if write_header else "a",
                header=write_header,
            )
            write_header = False

    @staticmethod
    def _feature_importance(
        model_name: str,
        estimator: Any,
        feature_names: List[str],
    ) -> List[Dict[str, Any]]:
        if model_name == "Logistic Regression":
            coefficients = estimator[-1].coef_[0]
            raw_importances = np.abs(coefficients)
            directions = np.sign(coefficients)
            method = "absolute standardized logistic coefficient"
        elif hasattr(estimator, "feature_importances_"):
            raw_importances = estimator.feature_importances_
            directions = np.zeros_like(raw_importances)
            method = "random-forest impurity-based importance"
        else:
            return []
        order = np.argsort(raw_importances)[::-1][:30]
        return [
            {
                "feature": feature_names[index],
                "importance": float(raw_importances[index]),
                "direction": int(directions[index]),
                "method": method,
            }
            for index in order
        ]

    def _load_results(self) -> Dict[str, Any]:
        if not self.results_path.exists():
            raise HTTPException(status_code=409, detail="No completed model evaluation is available.")
        try:
            return json.loads(self.results_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail="The persisted model results could not be read.") from exc

    def _load_bundle(self) -> Dict[str, Any]:
        if not self.model_path.exists():
            raise HTTPException(status_code=409, detail="No trained model is available. Start training first.")
        try:
            return joblib.load(self.model_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"The persisted model could not be loaded: {exc}") from exc

    def evaluation(self) -> Dict[str, Any]:
        results = self._load_results()
        return {
            "best_model": results["best_model"],
            "selection_criterion": results["selection_criterion"],
            "dataset": results["dataset"],
            "metrics": results["models"][results["best_model"]],
            "models": results["models"],
            "model_configuration": results.get("model_configuration", {}),
            "global_feature_importance": results["global_feature_importance"],
            "explanation_method": results["explanation_method"],
        }

    def model_comparison(self) -> Dict[str, Any]:
        results = self._load_results()
        return {
            "best_model": results["best_model"],
            "selection_criterion": results["selection_criterion"],
            "models": results["models"],
            "model_configuration": results.get("model_configuration", {}),
        }

    def feature_importance(self, limit: int = 20) -> Dict[str, Any]:
        results = self._load_results()
        return {
            "model": results["best_model"],
            "method": results["explanation_method"],
            "features": results["global_feature_importance"][:limit],
        }

    def predictions(
        self,
        page: int = 1,
        page_size: int = 25,
        threshold: float = DEFAULT_THRESHOLD,
        search: Optional[str] = None,
        predicted_class: Optional[str] = None,
        suspicious_only: bool = False,
    ) -> Dict[str, Any]:
        if not 0.0 <= threshold <= 1.0:
            raise HTTPException(status_code=422, detail="Threshold must be between 0 and 1.")
        if page < 1:
            raise HTTPException(status_code=422, detail="Page must be greater than zero.")
        if not 1 <= page_size <= MAX_RESULTS_PAGE_SIZE:
            raise HTTPException(
                status_code=422,
                detail=f"Page size must be between 1 and {MAX_RESULTS_PAGE_SIZE}.",
            )
        if predicted_class not in (None, "licit", "illicit"):
            raise HTTPException(status_code=422, detail="Predicted class must be licit or illicit.")
        if not self.predictions_path.is_file():
            raise HTTPException(status_code=409, detail="No prediction results are available.")

        offset = (page - 1) * page_size
        total = 0
        rows: List[Dict[str, Any]] = []
        with pd.read_csv(
            self.predictions_path,
            dtype={"transaction_id": "string", "ground_truth_label": "string"},
            chunksize=CSV_CHUNK_SIZE,
        ) as reader:
            selected_model = None
            if "selected_model" not in pd.read_csv(self.predictions_path, nrows=0).columns:
                selected_model = self._load_results()["best_model"]
            for chunk in reader:
                if selected_model is not None:
                    chunk["selected_model"] = selected_model
                probabilities = pd.to_numeric(chunk["illicit_probability"], errors="coerce")
                classes = np.where(probabilities >= threshold, "illicit", "licit")
                chunk["predicted_class"] = classes
                mask = probabilities.ge(threshold) if suspicious_only else pd.Series(True, index=chunk.index)
                if predicted_class:
                    mask &= chunk["predicted_class"].eq(predicted_class)
                if search:
                    mask &= chunk["transaction_id"].str.contains(search, case=False, regex=False, na=False)
                selected = chunk.loc[mask, PREDICTION_COLUMNS]
                previous_total = total
                total += len(selected)
                if total > offset and len(rows) < page_size:
                    start = max(0, offset - previous_total)
                    portion = selected.iloc[start : start + page_size - len(rows)]
                    rows.extend(portion.to_dict(orient="records"))

        return {
            "items": _json_safe(rows),
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total else 0,
            "threshold": threshold,
            "positive_class": "illicit",
        }

    def explain(self, transaction_id: str) -> Dict[str, Any]:
        results = self._load_results()
        bundle = self._load_bundle()
        target = None
        with pd.read_csv(
            self.predictions_path,
            dtype={"transaction_id": "string", "ground_truth_label": "string"},
            chunksize=CSV_CHUNK_SIZE,
        ) as reader:
            for chunk in reader:
                matches = chunk[chunk["transaction_id"].eq(transaction_id)]
                if not matches.empty:
                    target = matches.iloc[0].to_dict()
                    break
        if target is None:
            raise HTTPException(status_code=404, detail="The requested transaction was not found in predictions.")

        _, _, feature_path, _ = self._latest_paths()
        id_column = bundle["id_column"]
        feature_names = bundle["feature_names"]
        read_columns = [id_column, *feature_names]
        feature_row: Optional[pd.DataFrame] = None
        with pd.read_csv(
            feature_path,
            usecols=read_columns,
            dtype={id_column: "string"},
            chunksize=CSV_CHUNK_SIZE,
            low_memory=False,
            keep_default_na=False,
        ) as reader:
            for chunk in reader:
                match = chunk.loc[chunk[id_column].eq(transaction_id)]
                if not match.empty:
                    feature_row = match.iloc[[0]]
                    break
        if feature_row is None:
            raise HTTPException(status_code=404, detail="The source feature row for this transaction is missing.")

        values = feature_row[feature_names].apply(pd.to_numeric, errors="coerce").to_numpy(
            dtype=np.float32,
            na_value=np.nan,
        )
        medians = bundle["medians"]
        values[~np.isfinite(values)] = np.nan
        values = np.where(np.isfinite(values), values, medians).astype(np.float32, copy=False)
        estimator = bundle["estimator"]
        positive_index = list(estimator.classes_).index(1)
        original_probability = float(estimator.predict_proba(values)[0, positive_index])
        global_features = results["global_feature_importance"][:20]
        feature_indexes = {name: index for index, name in enumerate(feature_names)}
        explanations: List[Dict[str, Any]] = []
        for item in global_features:
            feature = item["feature"]
            index = feature_indexes[feature]
            ablated = values.copy()
            observed = float(ablated[0, index])
            ablated[0, index] = medians[index]
            probability_without = float(estimator.predict_proba(ablated)[0, positive_index])
            explanations.append(
                {
                    "feature": feature,
                    "observed_value": observed,
                    "training_median": float(medians[index]),
                    "probability_delta": original_probability - probability_without,
                    "global_importance": item["importance"],
                }
            )
        explanations.sort(key=lambda item: abs(item["probability_delta"]), reverse=True)
        return {
            "transaction_id": transaction_id,
            "predicted_class": target["predicted_class"],
            "illicit_probability": original_probability,
            "confidence": float(target["confidence"]),
            "ground_truth_label": target["ground_truth_label"],
            "model": results["best_model"],
            "method": (
                "Local feature-ablation sensitivity on the top 20 globally important features. "
                "Each value is replaced by its training median; effects are not causal."
            ),
            "features": explanations,
        }


BACKEND_DIR = Path(__file__).resolve().parents[2]
ml_engine = MLEngine(BACKEND_DIR)
