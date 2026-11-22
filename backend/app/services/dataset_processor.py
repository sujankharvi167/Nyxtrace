import asyncio
import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
from fastapi import HTTPException, UploadFile


MAX_FILE_SIZE_BYTES = 750 * 1024 * 1024
MAX_TOTAL_UPLOAD_SIZE_BYTES = 800 * 1024 * 1024
MAX_FILES = 3
ALLOWED_SUFFIX = ".csv"
CSV_CHUNK_SIZE = 100_000
STREAM_CHUNK_SIZE = 1024 * 1024
MINIMUM_UPLOAD_DISK_RESERVE_BYTES = 100 * 1024 * 1024


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _find_column(columns: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    normalized = {_normalized(column): column for column in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    for column in columns:
        name = _normalized(column)
        if any(candidate in name for candidate in candidates):
            return column
    return None


def _write_json_atomically(path: Path, payload: Dict[str, object]) -> None:
    temporary_path = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    try:
        temporary_path.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )
        os.replace(temporary_path, path)
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        if exc.errno == 28 or getattr(exc, "winerror", None) == 112:
            raise HTTPException(
                status_code=507,
                detail="Insufficient disk space while saving the dataset manifest.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail=f"Could not persist the dataset manifest: {exc.strerror or exc}.",
        ) from exc


def detect_file_role(filename: str) -> str:
    name = _normalized(Path(filename).stem)
    if "feature" in name or "txsfeature" in name:
        return "features"
    if "class" in name or "label" in name:
        return "classes"
    if "edge" in name or "edgelist" in name:
        return "edgelist"
    return "custom"


def normalize_label(value: object) -> str:
    if pd.isna(value):
        return "unknown"
    text = str(value).strip().lower()
    if text in {"1", "illicit", "illegal", "fraudulent"}:
        return "illicit"
    if text in {"2", "licit", "legal", "legitimate"}:
        return "licit"
    return "unknown"


def _find_id_column(columns: Iterable[str]) -> Optional[str]:
    for candidate in ("txid", "transactionid", "nodeid", "id"):
        column = _find_column(columns, (candidate,))
        if column:
            return column
    return None


def _validate_structure(
    role: str,
    df: pd.DataFrame,
    filename: str,
) -> Tuple[List[str], Dict[str, str]]:
    errors: List[str] = []
    detected: Dict[str, str] = {}

    if df.empty:
        errors.append("The CSV contains no data rows.")
    if len(df.columns) == 0:
        errors.append("The CSV contains no columns.")

    if role == "features":
        id_column = _find_id_column(df.columns)
        if not id_column:
            errors.append("Could not detect a transaction ID column.")
        else:
            detected["transaction_id"] = id_column
    elif role == "classes":
        id_column = _find_id_column(df.columns)
        label_column = _find_column(df.columns, ("class", "label", "category"))
        if not id_column:
            errors.append("Could not detect a transaction ID column.")
        if not label_column:
            errors.append("Could not detect a class or label column.")
        if id_column:
            detected["transaction_id"] = id_column
        if label_column:
            detected["label"] = label_column
    elif role == "edgelist":
        source = _find_column(df.columns, ("txid1", "source", "from", "fromtxid", "sender"))
        target = _find_column(df.columns, ("txid2", "target", "to", "totxid", "receiver"))
        if not source:
            errors.append("Could not detect an edge source column.")
        if not target:
            errors.append("Could not detect an edge target column.")
        if source:
            detected["source"] = source
        if target:
            detected["target"] = target

    if df.columns.duplicated().any():
        errors.append("The CSV contains duplicate column names.")

    return errors, detected


def _preprocess(df: pd.DataFrame, role: str, detected: Dict[str, str]) -> pd.DataFrame:
    processed = df.copy()
    processed.columns = [str(column).strip() for column in processed.columns]
    processed = processed.replace(r"^\s*$", pd.NA, regex=True)

    id_columns = {
        detected[key]
        for key in ("transaction_id", "source", "target")
        if key in detected
    }

    if role == "features":
        for column in processed.columns:
            if column in id_columns:
                continue
            numeric = pd.to_numeric(processed[column], errors="coerce")
            valid_ratio = numeric.notna().sum() / max(processed[column].notna().sum(), 1)
            if valid_ratio >= 0.80:
                processed[column] = numeric
                if numeric.isna().any():
                    processed[column] = numeric.fillna(numeric.median())

    for column in processed.select_dtypes(include=["object"]).columns:
        if column not in id_columns:
            processed[column] = processed[column].fillna("unknown")

    return processed


def _column_info(df: pd.DataFrame) -> List[Dict[str, object]]:
    return [
        {
            "name": str(column),
            "dtype": str(df[column].dtype),
            "missing": int(df[column].isna().sum()),
            "unique": int(df[column].nunique(dropna=True)),
        }
        for column in df.columns
    ]


def _preview(df: pd.DataFrame, limit: int = 20) -> List[Dict[str, object]]:
    return [
        {str(key): (None if pd.isna(value) else value.item() if hasattr(value, "item") else value)
         for key, value in row.items()}
        for row in df.head(limit).to_dict(orient="records")
    ]


async def _stream_upload(upload: UploadFile, destination: Path) -> int:
    written = 0
    try:
        with destination.open("xb") as output:
            while True:
                chunk = await upload.read(STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"{destination.name}: file exceeds the 750 MB individual size limit.",
                    )
                output.write(chunk)
    except HTTPException:
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise
    except OSError as exc:
        if destination.exists():
            destination.unlink(missing_ok=True)
        if exc.errno == 28 or getattr(exc, "winerror", None) == 112:
            raise HTTPException(
                status_code=507,
                detail="Insufficient disk space while saving the uploaded CSV.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail=f"Could not save uploaded file {destination.name}: {exc.strerror or exc}.",
        ) from exc
    except BaseException:
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise

    if written == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"{destination.name}: the file is empty.")
    return written


def _disk_space_error(backend_dir: Path, required_bytes: int) -> Optional[HTTPException]:
    try:
        free_bytes = shutil.disk_usage(backend_dir).free
    except OSError as exc:
        return HTTPException(
            status_code=500,
            detail=f"Could not verify available upload storage at {backend_dir}: {exc}.",
        )
    if free_bytes < required_bytes:
        return HTTPException(
            status_code=507,
            detail=(
                "Insufficient disk space. The upload requires approximately "
                f"{required_bytes // (1024 * 1024)} MB and only "
                f"{free_bytes // (1024 * 1024)} MB is available."
            ),
        )
    return None


def _process_csv_in_chunks(
        source_path: Path,
        processed_path: Path,
        role: str,
        filename: str,
) -> Tuple[Dict[str, object], Dict[str, int], Dict[str, object]]:
        original_rows = 0
        duplicate_rows = 0
        missing_values: Dict[str, int] = {}
        dtypes: Dict[str, str] = {}
        original_columns: List[str] = []
        detected: Dict[str, str] = {}
        errors: List[str] = []
        preview_rows: List[Dict[str, object]] = []
        seen_rows: set[int] = set()
        label_counts = {"licit": 0, "illicit": 0, "unknown": 0}
        unique_counts: Dict[str, int] = {}

        first_chunk = True
        write_header = True

        try:
            with pd.read_csv(source_path, chunksize=CSV_CHUNK_SIZE) as reader:
                for chunk in reader:
                    if first_chunk:
                        original_columns = [str(column) for column in chunk.columns]
                        missing_values = {str(column): 0 for column in chunk.columns}
                        dtypes = {str(column): str(chunk[column].dtype) for column in chunk.columns}
                        unique_counts = {str(column): 0 for column in chunk.columns}
                        errors, detected = _validate_structure(role, chunk, filename)
                        if chunk.empty:
                            errors.append("The CSV contains no data rows.")
                        first_chunk = False

                    original_rows += int(len(chunk))
                    for column in chunk.columns:
                        missing_values[str(column)] += int(chunk[column].isna().sum())

                    keep_rows: List[bool] = []
                    for row_hash in pd.util.hash_pandas_object(chunk, index=False):
                        hash_key = int(row_hash)
                        is_duplicate = hash_key in seen_rows
                        keep_rows.append(not is_duplicate)
                        if not is_duplicate:
                            seen_rows.add(hash_key)

                    duplicate_rows += int(sum(not keep for keep in keep_rows))
                    unique_chunk = chunk.loc[keep_rows].copy()

                    processed_chunk = _preprocess(unique_chunk, role, detected)
                    processed_chunk = processed_chunk.replace(r"^\s*$", pd.NA, regex=True)
                    processed_chunk = processed_chunk.drop_duplicates()
                    for column in processed_chunk.columns:
                        current = int(processed_chunk[column].nunique(dropna=True))
                        unique_counts[str(column)] = max(unique_counts.get(str(column), 0), current)

                    if role == "classes" and "label" in detected:
                        label_column = detected["label"]
                        normalized = processed_chunk[label_column].map(normalize_label)
                        for label in ("licit", "illicit", "unknown"):
                            label_counts[label] += int(normalized.eq(label).sum())

                    if len(preview_rows) < 20:
                        needed = 20 - len(preview_rows)
                        preview_rows.extend(_preview(processed_chunk, needed))

                    processed_chunk.to_csv(
                        processed_path,
                        index=False,
                        mode="w" if write_header else "a",
                        header=write_header,
                    )
                    write_header = False
                    dtypes = {
                        str(column): str(processed_chunk[column].dtype)
                        for column in processed_chunk.columns
                    }
        except pd.errors.EmptyDataError:
            errors.append("The CSV contains no data rows.")
        except (pd.errors.ParserError, UnicodeDecodeError) as exc:
            errors.append(f"Could not parse CSV: {exc}")
        except OSError as exc:
            if exc.errno == 28 or getattr(exc, "winerror", None) == 112:
                raise HTTPException(
                    status_code=507,
                    detail="Insufficient disk space while preprocessing the uploaded CSV.",
                ) from exc
            raise HTTPException(
                status_code=500,
                detail=f"Could not write the processed CSV {processed_path.name}: {exc.strerror or exc}.",
            ) from exc

        if first_chunk:
            errors.append("The CSV contains no data rows.")

        result: Dict[str, object] = {
            "original_rows": original_rows,
            "processed_rows": original_rows - duplicate_rows,
            "total_columns": len(original_columns),
            "duplicate_rows": duplicate_rows,
            "missing_values": missing_values,
            "dtypes": dtypes,
            "unique": unique_counts,
            "columns": original_columns,
            "preview": preview_rows,
            "detected_columns": detected,
            "validation_errors": errors,
        }
        return result, label_counts, {"errors": errors}


async def process_uploads(
    backend_dir: Path,
    uploads: List[UploadFile],
) -> Dict[str, object]:
    if not uploads:
        raise HTTPException(status_code=400, detail="No CSV files were uploaded.")
    if len(uploads) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"A maximum of {MAX_FILES} CSV files is allowed.",
        )

    announced_total = 0
    filenames: set[str] = set()
    for upload in uploads:
        filename = Path(upload.filename or "unnamed.csv").name
        if not filename.lower().endswith(ALLOWED_SUFFIX):
            raise HTTPException(status_code=422, detail=f"{filename}: only .csv files are accepted.")
        if filename.casefold() in filenames:
            raise HTTPException(
                status_code=422,
                detail=f"Multiple uploaded files use the same filename: {filename}.",
            )
        filenames.add(filename.casefold())
        announced_size = getattr(upload, "size", None)
        if isinstance(announced_size, int):
            if announced_size > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"{filename}: file exceeds the 750 MB individual size limit.",
                )
            announced_total += announced_size

    if announced_total > MAX_TOTAL_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="The combined upload exceeds the 800 MB total size limit.",
        )

    estimated_backend_usage = max(
        announced_total * 2 + MINIMUM_UPLOAD_DISK_RESERVE_BYTES,
        MINIMUM_UPLOAD_DISK_RESERVE_BYTES,
    )
    disk_error = _disk_space_error(backend_dir, estimated_backend_usage)
    if disk_error:
        raise disk_error
    estimated_temp_usage = max(announced_total, MINIMUM_UPLOAD_DISK_RESERVE_BYTES)
    temp_disk_error = _disk_space_error(
        Path(tempfile.gettempdir()),
        estimated_temp_usage,
    )
    if temp_disk_error:
        raise temp_disk_error

    upload_dir = backend_dir / "data" / "uploads"
    processed_dir = backend_dir / "data" / "processed"
    upload_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc)
    batch_id = f"{timestamp.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    batch_upload_dir = upload_dir / batch_id
    batch_processed_dir = processed_dir / batch_id
    batch_upload_dir.mkdir(parents=True)
    batch_processed_dir.mkdir(parents=True)

    files: List[Dict[str, object]] = []
    combined_errors: List[str] = []
    role_counts: Dict[str, int] = {}
    label_counts = {"licit": 0, "illicit": 0, "unknown": 0}
    uploaded_bytes = 0

    for upload in uploads:
        filename = Path(upload.filename or "unnamed.csv").name
        if not filename.lower().endswith(ALLOWED_SUFFIX):
            combined_errors.append(f"{filename}: only .csv files are accepted.")
            continue

        source_path = batch_upload_dir / filename
        try:
            written = await _stream_upload(upload, source_path)
        except asyncio.CancelledError:
            shutil.rmtree(batch_upload_dir, ignore_errors=True)
            shutil.rmtree(batch_processed_dir, ignore_errors=True)
            raise
        except HTTPException as exc:
            if exc.status_code != 422:
                shutil.rmtree(batch_upload_dir, ignore_errors=True)
                shutil.rmtree(batch_processed_dir, ignore_errors=True)
                raise
            combined_errors.append(f"{filename}: {exc.detail}")
            continue
        except BaseException:
            shutil.rmtree(batch_upload_dir, ignore_errors=True)
            shutil.rmtree(batch_processed_dir, ignore_errors=True)
            raise

        if uploaded_bytes + written > MAX_TOTAL_UPLOAD_SIZE_BYTES:
            shutil.rmtree(batch_upload_dir, ignore_errors=True)
            shutil.rmtree(batch_processed_dir, ignore_errors=True)
            raise HTTPException(
                status_code=413,
                detail=f"{filename}: the combined upload exceeds the 800 MB total size limit.",
            )
        uploaded_bytes += written

        role = detect_file_role(filename)
        processed_path = batch_processed_dir / filename
        try:
            summary, chunk_label_counts, _ = _process_csv_in_chunks(
                source_path,
                processed_path,
                role,
                filename,
            )
        except HTTPException as exc:
            if exc.status_code != 422:
                shutil.rmtree(batch_upload_dir, ignore_errors=True)
                shutil.rmtree(batch_processed_dir, ignore_errors=True)
                raise
            combined_errors.append(f"{filename}: {exc.detail}")
            continue
        except BaseException:
            shutil.rmtree(batch_upload_dir, ignore_errors=True)
            shutil.rmtree(batch_processed_dir, ignore_errors=True)
            raise

        errors = summary["validation_errors"]
        if errors:
            combined_errors.extend([f"{filename}: {error}" for error in errors])

        for label in ("licit", "illicit", "unknown"):
            label_counts[label] += chunk_label_counts[label]

        role_counts[role] = role_counts.get(role, 0) + int(summary["processed_rows"])

        files.append(
            {
                "filename": filename,
                "role": role,
                "original_rows": int(summary["original_rows"]),
                "processed_rows": int(summary["processed_rows"]),
                "total_columns": int(summary["total_columns"]),
                "duplicate_rows": int(summary["duplicate_rows"]),
                "missing_values": summary["missing_values"],
                "dtypes": summary["dtypes"],
                "columns": summary["columns"],
                "column_info": [
                    {
                        "name": str(column),
                        "dtype": str(summary["dtypes"].get(str(column), "unknown")),
                        "missing": int(summary["missing_values"].get(str(column), 0)),
                        "unique": int(summary["unique"].get(str(column), 0)),
                    }
                    for column in summary["columns"]
                ],
                "preview": summary["preview"],
                "detected_columns": summary["detected_columns"],
                "validation_errors": summary["validation_errors"],
            }
        )

    if combined_errors:
        shutil.rmtree(batch_upload_dir, ignore_errors=True)
        shutil.rmtree(batch_processed_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail="Dataset validation failed: " + " | ".join(combined_errors))

    if not files:
        shutil.rmtree(batch_upload_dir, ignore_errors=True)
        shutil.rmtree(batch_processed_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail="Dataset validation failed: no valid CSV files.")

    feature_rows = next(
        (int(item["processed_rows"]) for item in files if item["role"] == "features"),
        0,
    )
    class_rows = next(
        (int(item["processed_rows"]) for item in files if item["role"] == "classes"),
        0,
    )
    edge_rows = next(
        (int(item["processed_rows"]) for item in files if item["role"] == "edgelist"),
        0,
    )
    custom_rows = sum(
        int(item["processed_rows"]) for item in files if item["role"] == "custom"
    )

    total_transactions = feature_rows or class_rows or custom_rows or 0
    missing_count = sum(
        sum(int(value) for value in item["missing_values"].values())
        for item in files
    )
    duplicate_count = sum(int(item["duplicate_rows"]) for item in files)

    result: Dict[str, object] = {
        "batch_id": batch_id,
        "uploaded_at": timestamp.isoformat(),
        "status": "processed",
        "message": "Dataset files uploaded and preprocessed successfully.",
        "total_transactions": total_transactions,
        "total_edges": edge_rows,
        "total_files": len(files),
        "missing_values": missing_count,
        "duplicate_rows": duplicate_count,
        "label_counts": label_counts,
        "files": files,
        "processed_directory": str(batch_processed_dir),
    }

    manifest_path = processed_dir / "latest.json"
    try:
        _write_json_atomically(batch_processed_dir / "manifest.json", result)
        _write_json_atomically(manifest_path, result)
    except BaseException:
        shutil.rmtree(batch_upload_dir, ignore_errors=True)
        shutil.rmtree(batch_processed_dir, ignore_errors=True)
        raise

    return result


def load_latest_dataset(backend_dir: Path) -> Optional[Dict[str, object]]:
    manifest_path = backend_dir / "data" / "processed" / "latest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
