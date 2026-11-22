import json
import os
import re
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from app.core.config import settings
from app.services.dataset_processor import load_latest_dataset
from app.services.graph_engine import graph_engine
from app.services.ml_engine import ml_engine
from app.services.risk_engine import risk_engine


REPORT_TYPES = {
    "transaction_summary": "Transaction Summary Report",
    "ml_detection": "ML Detection Report",
    "network_analysis": "Network Analysis Report",
    "investigation_brief": "Investigation Brief",
    "risk_dashboard": "Risk Dashboard Report",
    "compliance_export": "Compliance Preparation Export",
}


class ReportEngine:
    def __init__(self, backend_dir: Path):
        self.backend_dir = backend_dir.resolve()
        self.db_path = self.backend_dir / "data" / "investigations.sqlite3"
        self.report_dir = self.backend_dir / "data" / "reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY,
                    report_name TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    dataset_batch TEXT,
                    model_batch TEXT,
                    graph_batch TEXT,
                    risk_assessment_version TEXT,
                    investigation_case_id TEXT,
                    status TEXT NOT NULL,
                    file_location TEXT,
                    file_format TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    error_message TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS reports_created_idx ON reports(created_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS reports_type_idx ON reports(report_type)"
            )
            connection.commit()

    def list_types(self) -> List[Dict[str, str]]:
        descriptions = {
            "transaction_summary": "Dataset, validation, preprocessing, and batch compatibility summary.",
            "ml_detection": "Model evaluation, predictions, feature importance, and limitations.",
            "network_analysis": "Graph topology, fan patterns, cycles, clusters, and selected relationships.",
            "investigation_brief": "A consolidated report for an existing investigation case.",
            "risk_dashboard": "Risk distribution, assessment methodology, and highest-risk transactions.",
            "compliance_export": "A structured investigative evidence export, not a SAR or legal conclusion.",
        }
        return [
            {"type": report_type, "title": title, "description": descriptions[report_type], "format": "pdf"}
            for report_type, title in REPORT_TYPES.items()
        ]

    def _safe_report_name(self, report_name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "-", report_name.strip())
        cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._-")
        if not cleaned:
            cleaned = "NyxTrace_Report"
        return cleaned[:120]

    def compatibility(self) -> Dict[str, Optional[str]]:
        dataset = load_latest_dataset(self.backend_dir)
        ml_status = ml_engine.get_status()
        graph_status = graph_engine.get_status()
        dataset_batch = str(dataset.get("batch_id", "")) if dataset else None
        model_batch = None
        prediction_batch = None
        if ml_status.get("status") == "completed":
            try:
                ml_results = ml_engine.evaluation()
                model_batch = str(ml_results["dataset"]["batch_id"])
                prediction_batch = model_batch
            except HTTPException as exc:
                pass
        graph_batch = graph_status.get("dataset_batch")
        return {
            "dataset_batch": dataset_batch,
            "model_batch": model_batch,
            "prediction_batch": prediction_batch,
            "graph_batch": graph_batch,
        }

    def _collect_data(
        self,
        report_type: str,
        transaction_ids: Iterable[str],
        case_id: Optional[str],
    ) -> Dict[str, Any]:
        dataset = load_latest_dataset(self.backend_dir)
        compatibility = self.compatibility()
        timestamp = datetime.now(timezone.utc).isoformat()
        data: Dict[str, Any] = {
            "generated_at": timestamp,
            "report_type": report_type,
            "compatibility": compatibility,
            "dataset": dataset,
            "limitations": [],
        }

        if not dataset:
            data["limitations"].append("No processed dataset is available.")

        if report_type in {
            "ml_detection",
            "risk_dashboard",
            "compliance_export",
            "investigation_brief",
        }:
            ml_status = ml_engine.get_status()
            ml_available = (
                ml_status.get("status") == "completed"
                and compatibility["dataset_batch"]
                and compatibility["model_batch"] == compatibility["dataset_batch"]
                and compatibility["prediction_batch"] == compatibility["dataset_batch"]
            )
            if ml_available:
                data["ml_evaluation"] = ml_engine.evaluation()
                data["ml_summary"] = ml_engine.summary(0.5)
                data["feature_importance"] = ml_engine.feature_importance(30)
                data["suspicious_predictions"] = ml_engine.predictions(
                    page=1,
                    page_size=100,
                    threshold=0.5,
                    suspicious_only=True,
                    sort_by="illicit_probability",
                    sort_order="desc",
                )
            else:
                data["ml_evaluation"] = None
                data["ml_summary"] = None
                data["feature_importance"] = None
                data["suspicious_predictions"] = None
                data["limitations"].append(
                    "ML evidence is unavailable or stale; no predictions were substituted."
                )

        if report_type in {
            "network_analysis",
            "compliance_export",
            "investigation_brief",
            "risk_dashboard",
        }:
            graph_status = graph_engine.get_status()
            graph_available = (
                graph_status.get("status") == "ready"
                and graph_status.get("ml_predictions_available") is True
                and graph_status.get("dataset_batch") == compatibility["dataset_batch"]
            )
            if graph_available:
                data["graph_status"] = graph_status
                data["graph_statistics"] = graph_engine.statistics()
                data["fan_in"] = graph_engine.fan_in(25)
                data["fan_out"] = graph_engine.fan_out(25)
                data["cycles"] = graph_engine.cycles(25)
                data["clusters"] = graph_engine.suspicious_clusters(25)
            else:
                data["graph_status"] = graph_status
                data["graph_statistics"] = None
                data["fan_in"] = None
                data["fan_out"] = None
                data["cycles"] = None
                data["clusters"] = None
                data["limitations"].append(
                    "Graph evidence is unavailable or not compatible with the current dataset and ML batch."
                )

        if report_type in {"investigation_brief", "compliance_export", "risk_dashboard"}:
            risk_compatibility = risk_engine.compatibility()
            data["risk_readiness"] = risk_engine.readiness()
            try:
                data["risk_distribution"] = risk_engine.distribution()
                data["risk_assessments"] = risk_engine.list_assessments(
                    page=1,
                    page_size=100,
                    category=None,
                    search=None,
                    sort_by="risk_score",
                    sort_order="desc",
                )
            except HTTPException as exc:
                data["risk_distribution"] = {
                    "total_assessed": 0,
                    "unassessed": 0,
                    "distribution": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                }
                data["risk_assessments"] = None
                data["limitations"].append(
                    "Risk assessment evidence is unavailable or stale."
                )

        if report_type == "investigation_brief":
            if not case_id:
                raise HTTPException(
                    status_code=422,
                    detail="An investigation case ID is required for an Investigation Brief.",
                )
            case = risk_engine.get_case(case_id)
            case_dataset_batch = str(case.get("dataset_batch", ""))
            current_dataset_batch = compatibility["dataset_batch"]
            case_model_batch = case.get("model_batch")
            if not current_dataset_batch or case_dataset_batch != current_dataset_batch:
                raise HTTPException(
                    status_code=409,
                    detail="The investigation case belongs to a different dataset batch.",
                )
            if case_model_batch and compatibility["model_batch"] != case_model_batch:
                raise HTTPException(
                    status_code=409,
                    detail="The investigation case belongs to a different model batch.",
                )
            data["case"] = case
            data["selected_transactions"] = []

        if transaction_ids:
            unique_ids = list(dict.fromkeys(str(value).strip() for value in transaction_ids if str(value).strip()))
            data["selected_transactions"] = []
            for transaction_id in unique_ids[:500]:
                item: Dict[str, Any] = {"transaction_id": transaction_id}
                try:
                    item["node"] = graph_engine.node_details(transaction_id)
                except HTTPException as exc:
                    item["node"] = None
                    item["node_error"] = str(exc.detail)
                try:
                    item["ml_explanation"] = ml_engine.explain(transaction_id)
                except HTTPException as exc:
                    item["ml_explanation"] = None
                    item["ml_explanation_error"] = str(exc.detail)
                try:
                    item["risk_assessment"] = risk_engine.get_assessment(transaction_id)
                except HTTPException as exc:
                    item["risk_assessment"] = None
                    item["risk_assessment_error"] = str(exc.detail)
                data["selected_transactions"].append(item)

        data["risk_assessment_version"] = settings.RISK_ASSESSMENT_VERSION
        return data

    @staticmethod
    def _table(
        story: List[Any],
        title: str,
        rows: Iterable[Iterable[Any]],
        col_widths: Optional[List[Any]] = None,
    ) -> None:
        styles = getSampleStyleSheet()
        story.append(Paragraph(title, styles["Heading2"]))
        cell_style = ParagraphStyle(
            "ReportTableCell",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
        )
        table_rows = [
            [Paragraph(str(cell), cell_style) for cell in row]
            for row in rows
        ]
        if not table_rows:
            story.append(Paragraph("No data is available.", styles["BodyText"]))
            return
        table = Table(table_rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e2d4a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#94a3b8")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 8))

    def _build_pdf(
        self,
        report_id: str,
        report_name: str,
        report_type: str,
        data: Dict[str, Any],
        output_path: Path,
    ) -> None:
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="BrandTitle",
                parent=styles["Title"],
                alignment=TA_CENTER,
                textColor=colors.HexColor("#1e3a8a"),
                fontSize=20,
                leading=24,
                spaceAfter=12,
            )
        )
        story: List[Any] = [
            Paragraph("NYXTRACE", styles["BrandTitle"]),
            Paragraph(report_name, styles["Heading1"]),
            Spacer(1, 6),
            Paragraph(
                f"Report type: {REPORT_TYPES[report_type]}",
                styles["BodyText"],
            ),
            Paragraph(f"Report ID: {report_id}", styles["BodyText"]),
            Paragraph(f"Generated: {data['generated_at']}", styles["BodyText"]),
            Spacer(1, 12),
            Paragraph("Executive Summary", styles["Heading1"]),
        ]

        compatibility = data["compatibility"]
        story.append(
            Paragraph(
                "This report contains application-generated evidence for analyst review. "
                "It does not establish confirmed criminal activity or provide a legal conclusion.",
                styles["BodyText"],
            )
        )
        self._table(
            story,
            "Data and Model Metadata",
            [
                ["Item", "Batch or version"],
                ["Dataset batch", compatibility.get("dataset_batch") or "Unavailable"],
                ["Model batch", compatibility.get("model_batch") or "Unavailable"],
                ["Prediction batch", compatibility.get("prediction_batch") or "Unavailable"],
                ["Graph batch", compatibility.get("graph_batch") or "Unavailable"],
                ["Risk assessment version", data["risk_assessment_version"]],
            ],
            [2.0 * inch, 4.5 * inch],
        )

        dataset = data.get("dataset")
        if report_type == "transaction_summary":
            story.append(Paragraph("Dataset Summary", styles["Heading1"]))
            if dataset:
                self._table(
                    story,
                    "Dataset Statistics",
                    [
                        ["Metric", "Value"],
                        ["Batch ID", dataset.get("batch_id", "Unavailable")],
                        ["Uploaded at", dataset.get("uploaded_at", "Unavailable")],
                        ["Transactions", dataset.get("total_transactions", 0)],
                        ["Edges", dataset.get("total_edges", 0)],
                        ["Missing values", dataset.get("missing_values", 0)],
                        ["Duplicate rows", dataset.get("duplicate_rows", 0)],
                        ["Label counts", json.dumps(dataset.get("label_counts", {}), sort_keys=True)],
                    ],
                    [2.2 * inch, 4.3 * inch],
                )
            else:
                story.append(Paragraph("No processed dataset is available.", styles["BodyText"]))

        ml_evaluation = data.get("ml_evaluation")
        if report_type in {"ml_detection", "compliance_export"} and ml_evaluation:
            story.append(Paragraph("ML Detection", styles["Heading1"]))
            metrics = ml_evaluation["metrics"]
            self._table(
                story,
                "Held-Out Evaluation",
                [
                    ["Metric", "Value"],
                    ["Selected model", ml_evaluation["best_model"]],
                    ["Model/report version", settings.APP_VERSION],
                    ["Accuracy", f"{metrics['accuracy']:.6f}"],
                    ["Precision", "Unavailable" if metrics["precision"] is None else f"{metrics['precision']:.6f}"],
                    ["Recall", "Unavailable" if metrics["recall"] is None else f"{metrics['recall']:.6f}"],
                    ["F1-score", f"{metrics['f1']:.6f}"],
                    ["ROC-AUC", "Unavailable" if metrics["roc_auc"] is None else f"{metrics['roc_auc']:.6f}"],
                    ["PR-AUC", "Unavailable" if metrics["pr_auc"] is None else f"{metrics['pr_auc']:.6f}"],
                    ["False-positive rate", "Unavailable" if metrics["false_positive_rate"] is None else f"{metrics['false_positive_rate']:.6f}"],
                    ["False-negative rate", "Unavailable" if metrics["false_negative_rate"] is None else f"{metrics['false_negative_rate']:.6f}"],
                ],
                [2.2 * inch, 4.3 * inch],
            )
            matrix = metrics["confusion_matrix"]
            self._table(
                story,
                "Confusion Matrix",
                [
                    ["", "Predicted licit", "Predicted illicit"],
                    ["Actual licit", matrix["true_negative"], matrix["false_positive"]],
                    ["Actual illicit", matrix["false_negative"], matrix["true_positive"]],
                ],
                [2.2 * inch, 2.1 * inch, 2.1 * inch],
            )

            importance = data.get("feature_importance")
            if importance and importance.get("features"):
                self._table(
                    story,
                    "Global Feature Importance",
                    [["Feature", "Importance"]]
                    + [
                        [item["feature"], f"{item['importance']:.6f}"]
                        for item in importance["features"][:20]
                    ],
                    [4.5 * inch, 2.0 * inch],
                )
        elif report_type in {"ml_detection", "compliance_export"}:
            story.append(Paragraph("ML evidence is unavailable or stale.", styles["BodyText"]))

        if report_type == "network_analysis" and data.get("graph_statistics"):
            story.append(Paragraph("Network Analysis", styles["Heading1"]))
            statistics = data["graph_statistics"]
            self._table(
                story,
                "Graph Statistics",
                [["Metric", "Value"]]
                + [[key.replace("_", " ").title(), str(value)] for key, value in statistics.items()],
                [3.0 * inch, 3.5 * inch],
            )
            for title, key in (
                ("Fan-In Findings", "fan_in"),
                ("Fan-Out Findings", "fan_out"),
                ("Cycle Findings", "cycles"),
                ("Suspicious Cluster Findings", "clusters"),
            ):
                result = data.get(key)
                if result:
                    items = result.get("items", [])[:25]
                    if items:
                        if key == "fan_in":
                            rows = [["Transaction ID", "Incoming", "ML risk"]]
                            for item in items:
                                ml_probability = item.get("illicit_probability")
                                rows.append([
                                    item.get("transaction_id", "Unavailable"),
                                    item.get("incoming_count", 0),
                                    "Unavailable" if ml_probability is None else f"{float(ml_probability):.6f}",
                                ])
                        elif key == "fan_out":
                            rows = [["Transaction ID", "Outgoing", "ML risk"]]
                            for item in items:
                                ml_probability = item.get("illicit_probability")
                                rows.append([
                                    item.get("transaction_id", "Unavailable"),
                                    item.get("outgoing_count", 0),
                                    "Unavailable" if ml_probability is None else f"{float(ml_probability):.6f}",
                                ])
                        elif key == "cycles":
                            rows = [["Cycle length", "Participants", "ML flagged"]]
                            for item in items:
                                participants = item.get("cycle", item.get("related_transaction_ids", []))
                                sample = ", ".join(str(value) for value in participants[:10])
                                if len(participants) > 10:
                                    sample += ", ..."
                                rows.append([
                                    item.get("cycle_length", len(participants)),
                                    sample or "Unavailable",
                                    "Yes" if item.get("ml_flagged") else "No",
                                ])
                        else:
                            rows = [["Cluster", "Transactions", "ML flagged", "Highest risk"]]
                            for item in items:
                                highest = item.get("highest_illicit_probability")
                                rows.append([
                                    item.get("cluster_id", "Unavailable"),
                                    item.get("transaction_count", 0),
                                    item.get("flagged_count", 0),
                                    "Unavailable" if highest is None else f"{float(highest):.6f}",
                                ])
                        self._table(story, title, rows)
                    else:
                        story.append(Paragraph(f"{title}: No findings are available.", styles["BodyText"]))

        if report_type in {"risk_dashboard", "investigation_brief", "compliance_export"}:
            story.append(Paragraph("Risk Intelligence", styles["Heading1"]))
            distribution = data.get("risk_distribution")
            if distribution:
                self._table(
                    story,
                    "Risk Distribution",
                    [["Category", "Count"]]
                    + [[category.title(), count] for category, count in distribution["distribution"].items()]
                    + [["Total assessed", distribution["total_assessed"]]],
                    [3.0 * inch, 3.5 * inch],
                )
            assessments = data.get("risk_assessments")
            if assessments and assessments.get("items"):
                self._table(
                    story,
                    "Highest-Risk Transactions",
                    [["Transaction ID", "ML probability", "Risk score", "Category"]]
                    + [
                        [
                            item["transaction_id"],
                            f"{item['ml_probability']:.6f}",
                            f"{item['combined_risk_score']:.6f}",
                            item["risk_category"],
                        ]
                        for item in assessments["items"][:100]
                    ],
                    [2.5 * inch, 1.3 * inch, 1.3 * inch, 1.0 * inch],
                )

        if report_type == "investigation_brief" and data.get("case"):
            case = data["case"]
            story.append(Paragraph("Investigation Case", styles["Heading1"]))
            self._table(
                story,
                "Case Metadata",
                [
                    ["Item", "Value"],
                    ["Case ID", case["case_id"]],
                    ["Title", case["title"]],
                    ["Description", case["description"] or "Unavailable"],
                    ["Priority", case["priority"]],
                    ["Status", case["status"]],
                    ["Created", case["created_at"]],
                    ["Updated", case["updated_at"]],
                    ["Dataset batch", case["dataset_batch"]],
                    ["Model batch", case["model_batch"] or "Unavailable"],
                    ["Associated transactions", ", ".join(case["associated_transaction_ids"]) or "None"],
                ],
                [2.2 * inch, 4.3 * inch],
            )
            if case.get("assessments"):
                self._table(
                    story,
                    "Transaction Risk Assessments",
                    [["Transaction ID", "ML probability", "Risk score", "Category"]]
                    + [
                        [
                            item["transaction_id"],
                            f"{item['ml_probability']:.6f}",
                            f"{item['combined_risk_score']:.6f}",
                            item["risk_category"],
                        ]
                        for item in case["assessments"]
                    ],
                    [2.5 * inch, 1.3 * inch, 1.3 * inch, 1.0 * inch],
                )
            if case.get("notes"):
                self._table(
                    story,
                    "Analyst Notes",
                    [["Timestamp", "Author", "Note"]]
                    + [
                        [
                            item["created_at"],
                            item["author"] or "Not attributed",
                            item["content"],
                        ]
                        for item in case["notes"]
                    ],
                    [1.7 * inch, 1.2 * inch, 3.6 * inch],
                )
            if case.get("activity"):
                self._table(
                    story,
                    "Chronological Activity",
                    [["Timestamp", "Action", "Details"]]
                    + [
                        [item["created_at"], item["action"], item["details"]]
                        for item in case["activity"]
                    ],
                    [1.7 * inch, 1.4 * inch, 3.4 * inch],
                )

        if data.get("selected_transactions"):
            story.append(Paragraph("Selected Transactions", styles["Heading1"]))
            rows = [["Transaction ID", "ML prediction", "ML probability", "Risk score", "Risk category"]]
            for item in data["selected_transactions"]:
                node = item.get("node")
                explanation = item.get("ml_explanation")
                assessment = item.get("risk_assessment")
                ml_probability = (
                    explanation["illicit_probability"]
                    if explanation
                    else (node["illicit_probability"] if node else None)
                )
                ml_prediction = (
                    explanation["predicted_class"]
                    if explanation
                    else (node["predicted_class"] if node else "Unavailable")
                )
                rows.append(
                    [
                        item["transaction_id"],
                        ml_prediction or "Unavailable",
                        "Unavailable" if ml_probability is None else f"{float(ml_probability):.6f}",
                        "Unavailable" if not assessment else f"{assessment['combined_risk_score']:.6f}",
                        "Unavailable" if not assessment else assessment["risk_category"],
                    ]
                )
            self._table(story, "Transaction Evidence", rows, [1.7 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch, 1.0 * inch])

        story.append(PageBreak())
        story.append(Paragraph("Limitations and Analyst Disclaimer", styles["Heading1"]))
        limitations = data["limitations"] or ["No known evidence limitations were recorded."]
        for limitation in limitations:
            story.append(Paragraph(f"- {limitation}", styles["BodyText"]))
        story.append(
            Paragraph(
                "- The Elliptic++ relationship data describes transaction relationships; "
                "it does not itself verify account ownership or fund-transfer amounts.",
                styles["BodyText"],
            )
        )
        story.append(
            Paragraph(
                "- ML predictions and investigation risk scores are analytical indicators "
                "requiring human review. They are not proof of money laundering or regulatory violations.",
                styles["BodyText"],
            )
        )
        if report_type == "compliance_export":
            story.append(
                Paragraph(
                    "This compliance preparation export is an investigative evidence document. "
                    "It is not an automatically generated regulatory SAR and contains no legal conclusion.",
                    styles["BodyText"],
                )
            )

        def page_number(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.drawRightString(A4[0] - 36, 24, f"NyxTrace - Page {doc.page}")
            canvas.restoreState()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        document = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
            title=report_name,
        )
        document.build(story, onFirstPage=page_number, onLaterPages=page_number)

    def generate(
        self,
        report_name: str,
        report_type: str,
        case_id: Optional[str] = None,
        transaction_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        if report_type not in REPORT_TYPES:
            raise HTTPException(status_code=422, detail="Unsupported report type.")
        report_name = report_name.strip()
        if not report_name:
            raise HTTPException(status_code=422, detail="Report name is required.")
        if len(report_name) > 200:
            raise HTTPException(status_code=422, detail="Report name must not exceed 200 characters.")
        if case_id is not None:
            case_id = case_id.strip()
            if len(case_id) > 128:
                raise HTTPException(status_code=422, detail="Investigation case ID is too long.")
        normalized_transaction_ids = list(
            dict.fromkeys(
                str(transaction_id).strip()
                for transaction_id in (transaction_ids or [])
                if str(transaction_id).strip()
            )
        )
        if len(normalized_transaction_ids) > 500:
            raise HTTPException(status_code=422, detail="A maximum of 500 transaction IDs is supported.")

        compatibility = self.compatibility()
        report_id = f"RPT-{uuid.uuid4().hex[:12].upper()}"
        safe_name = self._safe_report_name(report_name)
        filename = f"{report_id}_{safe_name}.pdf"
        file_path = self.report_dir / filename
        created_at = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO reports (
                    report_id, report_name, report_type, created_at,
                    dataset_batch, model_batch, graph_batch,
                    risk_assessment_version, investigation_case_id,
                    status, file_location, file_format, metadata_json, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'generating', ?, 'pdf', ?, NULL)
                """,
                (
                    report_id,
                    report_name,
                    report_type,
                    created_at,
                    compatibility["dataset_batch"],
                    compatibility["model_batch"],
                    compatibility["graph_batch"],
                    settings.RISK_ASSESSMENT_VERSION,
                    case_id,
                    str(file_path),
                    json.dumps(
                        {
                            "transaction_ids": list(transaction_ids or []),
                            "normalized_transaction_ids": normalized_transaction_ids,
                            "compatibility": compatibility,
                        }
                    ),
                ),
            )
            connection.commit()

        try:
            data = self._collect_data(report_type, normalized_transaction_ids, case_id)
            self._build_pdf(report_id, report_name, report_type, data, file_path)
            metadata = {
                "transaction_ids": normalized_transaction_ids,
                "compatibility": compatibility,
                "generated_data": data,
            }
            with closing(self._connect()) as connection:
                connection.execute(
                    """
                    UPDATE reports
                    SET status = 'completed',
                        metadata_json = ?
                    WHERE report_id = ?
                    """,
                    (
                        json.dumps(
                            {
                                "transaction_ids": normalized_transaction_ids,
                                "compatibility": compatibility,
                            },
                            default=str,
                        ),
                        report_id,
                    ),
                )
                connection.commit()
        except HTTPException as exc:
            file_path.unlink(missing_ok=True)
            with closing(self._connect()) as connection:
                connection.execute(
                    "UPDATE reports SET status = 'failed', error_message = ? WHERE report_id = ?",
                    (str(getattr(exc, "detail", "Report generation could not be completed.")), report_id),
                )
                connection.commit()
            raise
        except Exception as exc:
            file_path.unlink(missing_ok=True)
            with closing(self._connect()) as connection:
                connection.execute(
                    "UPDATE reports SET status = 'failed', error_message = ? WHERE report_id = ?",
                    (f"{type(exc).__name__}: {exc}", report_id),
                )
                connection.commit()
            raise HTTPException(status_code=500, detail="Could not generate the PDF report.") from exc

        return self.get_report(report_id)

    def list_reports(
        self,
        page: int = 1,
        page_size: int = 25,
        report_type: Optional[str] = None,
        case_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        conditions: List[str] = []
        parameters: List[Any] = []
        if report_type:
            conditions.append("report_type = ?")
            parameters.append(report_type)
        if case_id:
            conditions.append("investigation_case_id = ?")
            parameters.append(case_id)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        with closing(self._connect()) as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM reports{where}",
                    parameters,
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM reports{where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                [*parameters, page_size, (page - 1) * page_size],
            ).fetchall()
        return {
            "items": [self._report_row(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        }

    def get_report(self, report_id: str) -> Dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Report was not found.")
        return self._report_row(row)

    def _report_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        return {
            "report_id": row["report_id"],
            "report_name": row["report_name"],
            "report_type": row["report_type"],
            "report_title": REPORT_TYPES.get(row["report_type"], row["report_type"]),
            "created_at": row["created_at"],
            "dataset_batch": row["dataset_batch"],
            "model_batch": row["model_batch"],
            "graph_batch": row["graph_batch"],
            "risk_assessment_version": row["risk_assessment_version"],
            "investigation_case_id": row["investigation_case_id"],
            "status": row["status"],
            "file_format": row["file_format"],
            "metadata": metadata,
            "error_message": row["error_message"],
        }

    def get_download_path(self, report_id: str) -> Path:
        report = self.get_report(report_id)
        if report["status"] != "completed":
            raise HTTPException(status_code=409, detail="The report PDF is not available.")
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT file_location FROM reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        if not row or not row["file_location"]:
            raise HTTPException(status_code=404, detail="Report PDF location was not found.")
        path = Path(row["file_location"]).resolve()
        report_root = self.report_dir.resolve()
        if not path.is_relative_to(report_root):
            raise HTTPException(status_code=403, detail="Report file is outside the permitted report directory.")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Report PDF file was not found.")
        return path


report_engine = ReportEngine(Path(__file__).resolve().parents[2])
