import json
import sqlite3
import threading
import uuid
import networkx as nx
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException

from app.core.config import settings
from app.services.dataset_processor import load_latest_dataset
from app.services.graph_engine import graph_engine
from app.services.ml_engine import ml_engine


RISK_CATEGORIES = (
    ("critical", 0.90, 1.00),
    ("high", 0.70, 0.89),
    ("medium", 0.40, 0.69),
    ("low", 0.00, 0.39),
)


def risk_category(score: float) -> str:
    if score >= 0.90:
        return "critical"
    if score >= 0.70:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


class RiskEngine:
    def __init__(self, backend_dir: Path):
        self.backend_dir = backend_dir.resolve()
        self.db_path = self.backend_dir / "data" / "investigations.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS risk_assessments (
                    transaction_id TEXT PRIMARY KEY,
                    dataset_batch TEXT NOT NULL,
                    model_batch TEXT NOT NULL,
                    graph_batch TEXT NOT NULL,
                    ml_prediction TEXT,
                    ml_probability REAL,
                    ml_confidence REAL,
                    combined_risk_score REAL NOT NULL,
                    risk_category TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    factors_json TEXT NOT NULL,
                    graph_findings_json TEXT NOT NULL,
                    explanation_json TEXT NOT NULL,
                    assessment_timestamp TEXT NOT NULL,
                    assessment_version TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'current'
                );
                CREATE INDEX IF NOT EXISTS risk_assessment_category_idx
                    ON risk_assessments(risk_category);
                CREATE INDEX IF NOT EXISTS risk_assessment_score_idx
                    ON risk_assessments(combined_risk_score DESC);
                CREATE INDEX IF NOT EXISTS risk_assessment_status_idx
                    ON risk_assessments(status);

                CREATE TABLE IF NOT EXISTS investigation_cases (
                    case_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    primary_transaction_id TEXT,
                    dataset_batch TEXT NOT NULL,
                    model_batch TEXT,
                    risk_assessment_reference TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS investigation_case_status_idx
                    ON investigation_cases(status);

                CREATE TABLE IF NOT EXISTS case_transactions (
                    case_id TEXT NOT NULL,
                    transaction_id TEXT NOT NULL,
                    added_at TEXT NOT NULL,
                    PRIMARY KEY (case_id, transaction_id),
                    FOREIGN KEY (case_id) REFERENCES investigation_cases(case_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS case_transaction_id_idx
                    ON case_transactions(transaction_id);

                CREATE TABLE IF NOT EXISTS investigation_notes (
                    note_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (case_id) REFERENCES investigation_cases(case_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS investigation_note_case_idx
                    ON investigation_notes(case_id, created_at);

                CREATE TABLE IF NOT EXISTS case_activity (
                    activity_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (case_id) REFERENCES investigation_cases(case_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS case_activity_case_idx
                    ON case_activity(case_id, created_at);
                """
            )
            connection.commit()

    def compatibility(self) -> Dict[str, Any]:
        dataset = load_latest_dataset(self.backend_dir)
        dataset_batch = str(dataset.get("batch_id", "")) if dataset else None
        graph_status = graph_engine.get_status()
        ml_status = ml_engine.get_status()
        ml_ready = ml_status.get("status") == "completed" and ml_status.get("dataset_stale") is not True
        ml_batch = None
        if ml_ready:
            try:
                ml_batch = str(ml_engine.evaluation()["dataset"]["batch_id"])
            except HTTPException:
                ml_ready = False
        graph_batch = graph_status.get("dataset_batch")
        graph_ready = graph_status.get("status") == "ready"
        compatible = bool(
            dataset_batch
            and ml_ready
            and graph_ready
            and ml_batch == dataset_batch
            and graph_batch == dataset_batch
            and graph_status.get("ml_predictions_available") is True
        )
        return {
            "compatible": compatible,
            "dataset_batch": dataset_batch,
            "model_batch": ml_batch,
            "prediction_batch": ml_batch if ml_ready else None,
            "graph_batch": graph_batch,
            "assessment_version": settings.RISK_ASSESSMENT_VERSION,
            "message": (
                "Dataset, model, predictions, and graph are compatible."
                if compatible
                else "Risk analysis is unavailable until dataset, model, predictions, and graph use the same batch."
            ),
        }

    def readiness(self) -> Dict[str, Any]:
        compatibility = self.compatibility()
        return {
            "ready": compatibility["compatible"],
            "scoring_version": settings.RISK_ASSESSMENT_VERSION,
            "weights": {
                "ml_probability": settings.RISK_ML_WEIGHT,
                "graph_connectivity": settings.RISK_GRAPH_CONNECTIVITY_WEIGHT,
                "suspicious_neighbors": settings.RISK_GRAPH_SUSPICIOUS_NEIGHBOR_WEIGHT,
                "graph_pattern": settings.RISK_PATTERN_WEIGHT,
            },
            "thresholds": {
                "critical": [0.90, 1.00],
                "high": [0.70, 0.89],
                "medium": [0.40, 0.69],
                "low": [0.00, 0.39],
            },
            **compatibility,
        }

    def invalidate_stale(self) -> int:
        compatibility = self.compatibility()
        with closing(self._connect()) as connection:
            if compatibility["compatible"]:
                cursor = connection.execute(
                    """
                    UPDATE risk_assessments
                    SET status = 'outdated'
                    WHERE status = 'current'
                      AND (dataset_batch != ? OR model_batch != ? OR graph_batch != ?)
                    """,
                    (
                        compatibility["dataset_batch"],
                        compatibility["model_batch"],
                        compatibility["graph_batch"],
                    ),
                )
            else:
                cursor = connection.execute(
                    "UPDATE risk_assessments SET status = 'outdated' WHERE status = 'current'"
                )
            connection.commit()
            return int(cursor.rowcount)

    def _prediction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        compatibility = self.compatibility()
        if not compatibility["compatible"]:
            return None
        results = ml_engine._load_results()
        ml_engine._ensure_prediction_index(results)
        with closing(sqlite3.connect(ml_engine.prediction_index_path)) as connection:
            row = connection.execute(
                """
                SELECT transaction_id, illicit_probability, confidence, selected_model,
                       ground_truth_label
                FROM predictions
                WHERE transaction_id = ?
                """,
                (transaction_id,),
            ).fetchone()
        if row is None:
            return None
        probability = float(row[1])
        return {
            "predicted_class": "illicit" if probability >= 0.5 else "licit",
            "ml_probability": probability,
            "confidence": float(row[2]),
            "model": str(row[3]),
            "ground_truth_label": str(row[4]),
        }

    def assess(self, transaction_id: str) -> Dict[str, Any]:
        compatibility = self.compatibility()
        if not compatibility["compatible"]:
            raise HTTPException(
                status_code=409,
                detail=compatibility["message"],
            )
        graph = graph_engine.load_graph()
        if transaction_id not in graph:
            raise HTTPException(status_code=404, detail="Transaction ID was not found in the current graph.")

        prediction = self._prediction(transaction_id)
        if prediction is None:
            raise HTTPException(
                status_code=409,
                detail="No current model prediction exists for this transaction.",
            )

        node = graph.nodes[transaction_id]
        incoming = list(graph.predecessors(transaction_id))
        outgoing = list(graph.successors(transaction_id))
        suspicious_neighbors = {
            neighbor
            for neighbor in [*incoming, *outgoing]
            if graph.nodes[neighbor].get("predicted_class") == "illicit"
        }
        fan_in = len(incoming) > 1
        fan_out = len(outgoing) > 1
        cluster_member = False
        for component in nx.connected_components(graph.to_undirected(as_view=True)):
            if transaction_id not in component:
                continue
            flagged = sum(
                1
                for node_id in component
                if graph.nodes[node_id].get("predicted_class") == "illicit"
            )
            cluster_member = flagged >= 2
            break

        ml_probability = float(prediction["ml_probability"])
        degree = len(incoming) + len(outgoing)
        connectivity_evidence = min(degree / 20.0, 1.0)
        neighbor_evidence = min(len(suspicious_neighbors) / 5.0, 1.0)
        pattern_count = int(fan_in) + int(fan_out) + int(cluster_member)
        pattern_evidence = min(pattern_count / 3.0, 1.0)

        weighted = (
            settings.RISK_ML_WEIGHT * ml_probability
            + settings.RISK_GRAPH_CONNECTIVITY_WEIGHT * connectivity_evidence
            + settings.RISK_GRAPH_SUSPICIOUS_NEIGHBOR_WEIGHT * neighbor_evidence
            + settings.RISK_PATTERN_WEIGHT * pattern_evidence
        )
        score = round(max(0.0, min(1.0, weighted)), 6)
        category = risk_category(score)

        factors = []
        if ml_probability >= 0.70:
            factors.append("Elevated ML illicit-risk probability")
        elif ml_probability >= 0.40:
            factors.append("Moderate ML illicit-risk probability")
        if fan_in:
            factors.append("Fan-in graph pattern")
        if fan_out:
            factors.append("Fan-out graph pattern")
        if suspicious_neighbors:
            factors.append("Connected to suspicious predicted transactions")
        if cluster_member:
            factors.append("Member of a connected group with multiple ML flags")

        graph_findings = {
            "incoming_count": len(incoming),
            "outgoing_count": len(outgoing),
            "fan_in": fan_in,
            "fan_out": fan_out,
            "suspicious_neighbor_count": len(suspicious_neighbors),
            "cluster_member": cluster_member,
            "cycle_membership": "not_checked",
        }
        evidence = {
            "ml_available": True,
            "graph_available": True,
            "transaction_features_available": False,
            "timestamps_available": False,
            "transaction_amounts_available": False,
        }
        explanation = {
            "summary": (
                f"Transaction {transaction_id} received a {category} investigation risk score "
                f"of {score:.3f}. The assessment includes the ML illicit-risk probability"
                + (f" and {len(factors) - 1} available graph evidence factors." if len(factors) > 1
                   else " and available graph evidence.")
            ),
            "method": "Transparent additive investigation score; not a calibrated criminality probability.",
            "ml_prediction": prediction,
            "graph_findings": graph_findings,
            "missing_evidence": [
                "Transaction amounts",
                "Transaction timestamps",
                "Wallet or account ownership",
            ],
        }
        timestamp = datetime.now(timezone.utc).isoformat()
        assessment = {
            "transaction_id": transaction_id,
            "dataset_batch": compatibility["dataset_batch"],
            "model_batch": compatibility["model_batch"],
            "prediction_batch": compatibility["prediction_batch"],
            "graph_batch": compatibility["graph_batch"],
            "ml_prediction": prediction["predicted_class"],
            "ml_probability": ml_probability,
            "ml_confidence": prediction["confidence"],
            "combined_risk_score": score,
            "risk_category": category,
            "evidence_availability": evidence,
            "contributing_factors": factors,
            "graph_findings": graph_findings,
            "explanation": explanation,
            "assessment_timestamp": timestamp,
            "assessment_version": settings.RISK_ASSESSMENT_VERSION,
            "status": "current",
        }
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO risk_assessments (
                    transaction_id, dataset_batch, model_batch, graph_batch,
                    ml_prediction, ml_probability, ml_confidence, combined_risk_score,
                    risk_category, evidence_json, factors_json, graph_findings_json,
                    explanation_json, assessment_timestamp, assessment_version, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'current')
                ON CONFLICT(transaction_id) DO UPDATE SET
                    dataset_batch=excluded.dataset_batch,
                    model_batch=excluded.model_batch,
                    graph_batch=excluded.graph_batch,
                    ml_prediction=excluded.ml_prediction,
                    ml_probability=excluded.ml_probability,
                    ml_confidence=excluded.ml_confidence,
                    combined_risk_score=excluded.combined_risk_score,
                    risk_category=excluded.risk_category,
                    evidence_json=excluded.evidence_json,
                    factors_json=excluded.factors_json,
                    graph_findings_json=excluded.graph_findings_json,
                    explanation_json=excluded.explanation_json,
                    assessment_timestamp=excluded.assessment_timestamp,
                    assessment_version=excluded.assessment_version,
                    status='current'
                """,
                (
                    transaction_id,
                    compatibility["dataset_batch"],
                    compatibility["model_batch"],
                    compatibility["graph_batch"],
                    prediction["predicted_class"],
                    ml_probability,
                    prediction["confidence"],
                    score,
                    category,
                    json.dumps(evidence),
                    json.dumps(factors),
                    json.dumps(graph_findings),
                    json.dumps(explanation),
                    timestamp,
                    settings.RISK_ASSESSMENT_VERSION,
                ),
            )
            connection.commit()
        return assessment

    def distribution(self) -> Dict[str, Any]:
        compatibility = self.compatibility()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT risk_category, COUNT(*) AS count
                FROM risk_assessments
                WHERE status = 'current'
                GROUP BY risk_category
                """
            ).fetchall()
            assessed = int(connection.execute(
                "SELECT COUNT(*) FROM risk_assessments WHERE status = 'current'"
            ).fetchone()[0])
        categories = {row["risk_category"]: int(row["count"]) for row in rows}
        total = ml_engine.summary()["total_predictions"] if compatibility["compatible"] else 0
        return {
            "total_assessed": assessed,
            "unassessed": max(total - assessed, 0),
            "distribution": {
                "critical": int(categories.get("critical", 0)),
                "high": int(categories.get("high", 0)),
                "medium": int(categories.get("medium", 0)),
                "low": int(categories.get("low", 0)),
            },
        }

    def list_assessments(
        self,
        page: int,
        page_size: int,
        category: Optional[str],
        search: Optional[str],
        sort_by: str,
        sort_order: str,
    ) -> Dict[str, Any]:
        compatibility = self.compatibility()
        if not compatibility["compatible"]:
            raise HTTPException(status_code=409, detail=compatibility["message"])
        conditions = ["status = 'current'"]
        parameters: List[Any] = []
        if category:
            conditions.append("risk_category = ?")
            parameters.append(category)
        if search:
            conditions.append("transaction_id LIKE ?")
            parameters.append(f"%{search}%")
        sort_column = {
            "risk_score": "combined_risk_score",
            "ml_probability": "ml_probability",
            "transaction_id": "transaction_id",
        }.get(sort_by, "combined_risk_score")
        order = "ASC" if sort_order == "asc" else "DESC"
        where = " AND ".join(conditions)
        with closing(self._connect()) as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM risk_assessments WHERE {where}",
                parameters,
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT * FROM risk_assessments
                WHERE {where}
                ORDER BY {sort_column} {order}, transaction_id ASC
                LIMIT ? OFFSET ?
                """,
                [*parameters, page_size, (page - 1) * page_size],
            ).fetchall()
        items = [self._assessment_row(row) for row in rows]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": int(total),
            "total_pages": (int(total) + page_size - 1) // page_size,
        }

    def get_assessment(self, transaction_id: str) -> Dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM risk_assessments WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="No risk assessment exists for this transaction.")
        assessment = self._assessment_row(row)
        compatibility = self.compatibility()
        if row["status"] != "current" or (
            row["dataset_batch"] != compatibility["dataset_batch"]
            or row["model_batch"] != compatibility["model_batch"]
            or row["graph_batch"] != compatibility["graph_batch"]
        ):
            raise HTTPException(
                status_code=409,
                detail="This risk assessment is outdated for the current dataset, model, or graph.",
            )
        return assessment

    @staticmethod
    def _assessment_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "transaction_id": row["transaction_id"],
            "dataset_batch": row["dataset_batch"],
            "model_batch": row["model_batch"],
            "prediction_batch": row["model_batch"],
            "graph_batch": row["graph_batch"],
            "ml_prediction": row["ml_prediction"],
            "ml_probability": row["ml_probability"],
            "ml_confidence": row["ml_confidence"],
            "combined_risk_score": row["combined_risk_score"],
            "risk_category": row["risk_category"],
            "evidence_availability": json.loads(row["evidence_json"]),
            "contributing_factors": json.loads(row["factors_json"]),
            "graph_findings": json.loads(row["graph_findings_json"]),
            "explanation": json.loads(row["explanation_json"]),
            "assessment_timestamp": row["assessment_timestamp"],
            "assessment_version": row["assessment_version"],
            "status": row["status"],
        }

    def create_case(
        self,
        title: str,
        description: str,
        priority: str,
        status: str,
        primary_transaction_id: Optional[str],
        transaction_ids: Iterable[str],
        risk_assessment_reference: Optional[str],
    ) -> Dict[str, Any]:
        if priority not in {"critical", "high", "medium", "low"}:
            raise HTTPException(status_code=422, detail="Invalid case priority.")
        if status not in {"open", "under_review", "escalated", "resolved", "closed"}:
            raise HTTPException(status_code=422, detail="Invalid case status.")
        compatibility = self.compatibility()
        if not compatibility["compatible"]:
            raise HTTPException(status_code=409, detail=compatibility["message"])
        now = datetime.now(timezone.utc).isoformat()
        case_id = f"NYX-{uuid.uuid4().hex[:12].upper()}"
        unique_ids = list(dict.fromkeys(str(value).strip() for value in transaction_ids if str(value).strip()))
        if primary_transaction_id:
            primary_transaction_id = primary_transaction_id.strip()
            if primary_transaction_id not in unique_ids:
                unique_ids.insert(0, primary_transaction_id)
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN")
                connection.execute(
                    """
                    INSERT INTO investigation_cases (
                        case_id, title, description, priority, status,
                        primary_transaction_id, dataset_batch, model_batch,
                        risk_assessment_reference, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        case_id, title, description, priority, status,
                        primary_transaction_id, compatibility["dataset_batch"],
                        compatibility["model_batch"], risk_assessment_reference,
                        now, now,
                    ),
                )
                for transaction_id in unique_ids:
                    connection.execute(
                        "INSERT INTO case_transactions (case_id, transaction_id, added_at) VALUES (?, ?, ?)",
                        (case_id, transaction_id, now),
                    )
                activity_id = uuid.uuid4().hex
                connection.execute(
                    """
                    INSERT INTO case_activity (activity_id, case_id, action, details, created_at)
                    VALUES (?, ?, 'case_created', ?, ?)
                    """,
                    (activity_id, case_id, "Investigation case created.", now),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.get_case(case_id)

    def list_cases(self, page: int, page_size: int, status: Optional[str], priority: Optional[str]) -> Dict[str, Any]:
        conditions: List[str] = []
        parameters: List[Any] = []
        if status:
            conditions.append("status = ?")
            parameters.append(status)
        if priority:
            conditions.append("priority = ?")
            parameters.append(priority)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        with closing(self._connect()) as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM investigation_cases{where}",
                parameters,
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT * FROM investigation_cases{where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                [*parameters, page_size, (page - 1) * page_size],
            ).fetchall()
        items = [self._case_summary(row, connection=None) for row in rows]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": int(total),
            "total_pages": (int(total) + page_size - 1) // page_size,
        }

    def _case_summary(self, row: sqlite3.Row, connection: Optional[sqlite3.Connection]) -> Dict[str, Any]:
        if connection is None:
            with closing(self._connect()) as local_connection:
                transactions = local_connection.execute(
                    "SELECT transaction_id FROM case_transactions WHERE case_id = ? ORDER BY added_at",
                    (row["case_id"],),
                ).fetchall()
        else:
            transactions = connection.execute(
                "SELECT transaction_id FROM case_transactions WHERE case_id = ? ORDER BY added_at",
                (row["case_id"],),
            ).fetchall()
        return {
            "case_id": row["case_id"],
            "title": row["title"],
            "description": row["description"],
            "priority": row["priority"],
            "status": row["status"],
            "primary_transaction_id": row["primary_transaction_id"],
            "associated_transaction_ids": [item["transaction_id"] for item in transactions],
            "dataset_batch": row["dataset_batch"],
            "model_batch": row["model_batch"],
            "risk_assessment_reference": row["risk_assessment_reference"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_case(self, case_id: str) -> Dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM investigation_cases WHERE case_id = ?",
                (case_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Investigation case was not found.")
            case = self._case_summary(row, connection)
            notes = connection.execute(
                "SELECT * FROM investigation_notes WHERE case_id = ? ORDER BY created_at ASC",
                (case_id,),
            ).fetchall()
            activity = connection.execute(
                "SELECT * FROM case_activity WHERE case_id = ? ORDER BY created_at ASC",
                (case_id,),
            ).fetchall()
            assessments = connection.execute(
                """
                SELECT * FROM risk_assessments
                WHERE transaction_id IN (
                    SELECT transaction_id FROM case_transactions WHERE case_id = ?
                )
                """,
                (case_id,),
            ).fetchall()
        case["notes"] = [
            {
                "note_id": item["note_id"],
                "content": item["content"],
                "author": item["author"],
                "created_at": item["created_at"],
                "updated_at": item["updated_at"],
            }
            for item in notes
        ]
        case["activity"] = [
            {
                "activity_id": item["activity_id"],
                "action": item["action"],
                "details": item["details"],
                "created_at": item["created_at"],
            }
            for item in activity
        ]
        case["assessments"] = [self._assessment_row(item) for item in assessments]
        return case

    def update_case(
        self,
        case_id: str,
        title: Optional[str],
        description: Optional[str],
        priority: Optional[str],
        status: Optional[str],
    ) -> Dict[str, Any]:
        if priority is not None and priority not in {"critical", "high", "medium", "low"}:
            raise HTTPException(status_code=422, detail="Invalid case priority.")
        if status is not None and status not in {"open", "under_review", "escalated", "resolved", "closed"}:
            raise HTTPException(status_code=422, detail="Invalid case status.")
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM investigation_cases WHERE case_id = ?",
                (case_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Investigation case was not found.")
            updates: Dict[str, Any] = {}
            if title is not None:
                updates["title"] = title
            if description is not None:
                updates["description"] = description
            if priority is not None:
                updates["priority"] = priority
            if status is not None:
                updates["status"] = status
            if updates:
                assignments = ", ".join(f"{key} = ?" for key in updates)
                connection.execute(
                    f"UPDATE investigation_cases SET {assignments}, updated_at = ? WHERE case_id = ?",
                    [*updates.values(), now, case_id],
                )
                for key, value in updates.items():
                    connection.execute(
                        """
                        INSERT INTO case_activity (activity_id, case_id, action, details, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            uuid.uuid4().hex,
                            case_id,
                            f"{key}_changed",
                            f"{key} changed to {value}.",
                            now,
                        ),
                    )
                connection.commit()
        return self.get_case(case_id)

    def add_transaction(self, case_id: str, transaction_id: str) -> Dict[str, Any]:
        transaction_id = transaction_id.strip()
        if not transaction_id:
            raise HTTPException(status_code=422, detail="Transaction ID is required.")
        compatibility = self.compatibility()
        graph = graph_engine.load_graph()
        if transaction_id not in graph:
            raise HTTPException(status_code=404, detail="Transaction ID was not found in the current graph.")
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            if not connection.execute(
                "SELECT 1 FROM investigation_cases WHERE case_id = ?",
                (case_id,),
            ).fetchone():
                raise HTTPException(status_code=404, detail="Investigation case was not found.")
            try:
                connection.execute(
                    "INSERT INTO case_transactions (case_id, transaction_id, added_at) VALUES (?, ?, ?)",
                    (case_id, transaction_id, now),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(
                    status_code=409,
                    detail="Transaction is already associated with this case.",
                ) from exc
            connection.execute(
                """
                INSERT INTO case_activity (activity_id, case_id, action, details, created_at)
                VALUES (?, ?, 'transaction_added', ?, ?)
                """,
                (uuid.uuid4().hex, case_id, f"Transaction {transaction_id} added.", now),
            )
            connection.execute(
                "UPDATE investigation_cases SET updated_at = ? WHERE case_id = ?",
                (now, case_id),
            )
            connection.commit()
        return self.get_case(case_id)

    def remove_transaction(self, case_id: str, transaction_id: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT 1 FROM case_transactions WHERE case_id = ? AND transaction_id = ?",
                (case_id, transaction_id),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Transaction is not associated with this case.")
            connection.execute(
                "DELETE FROM case_transactions WHERE case_id = ? AND transaction_id = ?",
                (case_id, transaction_id),
            )
            connection.execute(
                """
                INSERT INTO case_activity (activity_id, case_id, action, details, created_at)
                VALUES (?, ?, 'transaction_removed', ?, ?)
                """,
                (uuid.uuid4().hex, case_id, f"Transaction {transaction_id} removed.", now),
            )
            connection.execute(
                "UPDATE investigation_cases SET updated_at = ? WHERE case_id = ?",
                (now, case_id),
            )
            connection.commit()
        return self.get_case(case_id)

    def add_note(self, case_id: str, content: str, author: Optional[str]) -> Dict[str, Any]:
        content = content.strip()
        if not content:
            raise HTTPException(status_code=422, detail="Investigation note content is required.")
        now = datetime.now(timezone.utc).isoformat()
        note_id = uuid.uuid4().hex
        with closing(self._connect()) as connection:
            if not connection.execute(
                "SELECT 1 FROM investigation_cases WHERE case_id = ?",
                (case_id,),
            ).fetchone():
                raise HTTPException(status_code=404, detail="Investigation case was not found.")
            connection.execute(
                """
                INSERT INTO investigation_notes (note_id, case_id, content, author, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (note_id, case_id, content, author.strip() if author else None, now, now),
            )
            connection.execute(
                """
                INSERT INTO case_activity (activity_id, case_id, action, details, created_at)
                VALUES (?, ?, 'note_added', 'Investigation note added.', ?)
                """,
                (uuid.uuid4().hex, case_id, now),
            )
            connection.execute(
                "UPDATE investigation_cases SET updated_at = ? WHERE case_id = ?",
                (now, case_id),
            )
            connection.commit()
        return self.get_case(case_id)

risk_engine = RiskEngine(Path(__file__).resolve().parents[2])
