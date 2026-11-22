import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import networkx as nx
import pandas as pd
from fastapi import HTTPException

from app.services.dataset_processor import load_latest_dataset
from app.services.ml_engine import ml_engine


MAX_GRAPH_DEPTH = 10
MAX_GRAPH_LIMIT = 500
MAX_CYCLES = 25
MAX_CYCLE_COMPONENT_NODES = 20


class GraphEngine:
    def __init__(self, backend_dir: Path):
        self.backend_dir = backend_dir.resolve()
        self.graph_dir = self.backend_dir / "data" / "graph"
        self.status_path = self.graph_dir / "status.json"
        self.graph_path = self.graph_dir / "graph.joblib"
        self.manifest_path = self.graph_dir / "manifest.json"
        self._lock = threading.Lock()
        self._graph: Optional[nx.DiGraph] = None
        self._status = self._load_status()

    def _load_status(self) -> Dict[str, Any]:
        if not self.status_path.exists():
            return {
                "status": "idle",
                "progress": 0,
                "message": "Graph has not been built.",
            }
        try:
            state = json.loads(self.status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"status": "idle", "progress": 0, "message": "Graph has not been built."}
        if state.get("status") == "running":
            state.update(
                status="error",
                message="Graph construction stopped before completion.",
                error="The graph build was interrupted by a backend restart.",
            )
            self._write_status(state)
        return state

    def _write_status(self, state: Dict[str, Any]) -> None:
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.status_path.with_suffix(
            self.status_path.suffix + f".{uuid.uuid4().hex}.tmp"
        )
        temporary.write_text(
            json.dumps(state, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        os.replace(temporary, self.status_path)

    def _set_status(self, **updates: Any) -> Dict[str, Any]:
        with self._lock:
            self._status = {
                **self._status,
                **updates,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._write_status(self._status)
            return dict(self._status)

    def get_status(self) -> Dict[str, Any]:
        latest = load_latest_dataset(self.backend_dir)
        if not latest:
            return {
                **self._status,
                "status": "idle",
                "dataset_available": False,
                "dataset_stale": False,
                "message": "Upload a dataset before building the graph.",
            }

        if not self.manifest_path.exists():
            return {
                **self._status,
                "status": "idle",
                "dataset_available": True,
                "dataset_stale": False,
                "message": "Graph construction has not been completed.",
            }

        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                **self._status,
                "status": "error",
                "dataset_available": True,
                "dataset_stale": False,
                "message": "The persisted graph manifest could not be read.",
            }

        stale = manifest.get("dataset_batch") != latest.get("batch_id")
        if stale:
            return {
                **self._status,
                "status": "stale",
                "dataset_available": True,
                "dataset_stale": True,
                "message": "The graph belongs to an older dataset. Rebuild the graph.",
            }

        ml_predictions_available = False
        ml_batch = None
        ml_status = "idle"
        try:
            ml_status = ml_engine.get_status().get("status", "idle")
            ml_results = ml_engine.evaluation()
            ml_batch = str(ml_results["dataset"]["batch_id"])
            ml_predictions_available = ml_status == "completed" and ml_batch == latest.get("batch_id")
        except HTTPException:
            ml_predictions_available = False

        manifest_predictions_available = bool(manifest.get("ml_predictions_available"))
        manifest_ml_batch = manifest.get("ml_batch")
        prediction_state_stale = (
            manifest_predictions_available != ml_predictions_available
            or (
                ml_predictions_available
                and manifest_ml_batch != ml_batch
            )
        )
        if prediction_state_stale:
            return {
                **self._status,
                "status": "stale",
                "dataset_available": True,
                "dataset_stale": False,
                "message": (
                    "The graph was built with incompatible ML prediction state. "
                    "Rebuild the graph to attach current model predictions."
                ),
                "graph_ready": False,
                "ml_predictions_available": ml_predictions_available,
                "dataset_batch": manifest.get("dataset_batch"),
                "ml_batch": ml_batch,
            }
        if not self.graph_path.is_file():
            return {
                **self._status,
                "status": "error",
                "dataset_available": True,
                "dataset_stale": False,
                "message": "The graph manifest exists but the persisted graph is missing.",
            }
        return {
            **self._status,
            "status": "ready",
            "dataset_available": True,
            "dataset_stale": False,
            "message": "Graph construction is complete.",
            "graph_ready": True,
            "ml_predictions_available": bool(manifest.get("ml_predictions_available")),
            "dataset_batch": manifest.get("dataset_batch"),
            "ml_batch": manifest.get("ml_batch"),
        }

    def load_graph(self) -> nx.DiGraph:
        status = self.get_status()
        if status["status"] != "ready":
            raise HTTPException(
                status_code=409,
                detail=status["message"],
            )
        if self._graph is not None:
            return self._graph
        try:
            import joblib

            graph = joblib.load(self.graph_path)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"The persisted graph could not be loaded: {exc}",
            ) from exc
        if not isinstance(graph, nx.DiGraph):
            raise HTTPException(status_code=500, detail="The persisted graph has an invalid format.")
        self._graph = graph
        return graph

    def build(self) -> Dict[str, Any]:
        if self._status.get("status") == "running":
            raise HTTPException(status_code=409, detail="A graph build is already in progress.")

        latest = load_latest_dataset(self.backend_dir)
        if not latest:
            raise HTTPException(status_code=409, detail="Upload a dataset before building the graph.")

        batch_id = str(latest.get("batch_id", ""))
        batch_dir = self.backend_dir / "data" / "processed" / batch_id
        edgelist_path = batch_dir / "txs_edgelist.csv"
        classes_path = batch_dir / "txs_classes.csv"
        if not edgelist_path.is_file():
            raise HTTPException(status_code=409, detail="The latest dataset has no txs_edgelist.csv.")

        run_id = uuid.uuid4().hex
        self._status = {
            "run_id": run_id,
            "status": "running",
            "progress": 1,
            "message": "Starting graph construction.",
            "error": None,
        }
        self._write_status(self._status)

        try:
            graph = nx.DiGraph()

            ground_truth: Dict[str, str] = {}
            if classes_path.is_file():
                classes = pd.read_csv(
                    classes_path,
                    dtype={"txId": "string"},
                    low_memory=False,
                )
                id_column = next(
                    (column for column in classes.columns if column.lower() in {"txid", "transactionid", "id"}),
                    None,
                )
                label_column = next(
                    (column for column in classes.columns if column.lower() in {"class", "label", "category"}),
                    None,
                )
                if id_column and label_column:
                    from app.services.dataset_processor import normalize_label

                    ground_truth = {
                        str(identifier): normalize_label(label)
                        for identifier, label in zip(
                            classes[id_column].astype(str),
                            classes[label_column],
                        )
                    }
                    for identifier, label in ground_truth.items():
                        graph.add_node(identifier, ground_truth_label=label)
                del classes

            predictions: Dict[str, Dict[str, Any]] = {}
            ml_batch: Optional[str] = None
            ml_predictions_available = False
            try:
                ml_status = ml_engine.get_status()
                ml_results = ml_engine.evaluation()
                ml_batch = str(ml_results["dataset"]["batch_id"])
                if ml_status["status"] == "completed" and ml_batch == batch_id:
                    for chunk in pd.read_csv(
                        ml_engine.predictions_path,
                        usecols=[
                            "transaction_id",
                            "predicted_class",
                            "illicit_probability",
                            "confidence",
                            "selected_model",
                            "ground_truth_label",
                        ],
                        dtype={"transaction_id": "string"},
                        chunksize=50_000,
                    ):
                        for row in chunk.itertuples(index=False):
                            predictions[str(row.transaction_id)] = {
                                "predicted_class": str(row.predicted_class),
                                "illicit_probability": float(row.illicit_probability),
                                "confidence": float(row.confidence),
                                "selected_model": str(row.selected_model),
                            }
                    ml_predictions_available = True
            except HTTPException:
                ml_predictions_available = False

            edge_count = 0
            duplicate_edges = 0
            for chunk in pd.read_csv(
                edgelist_path,
                dtype={"txId1": "string", "txId2": "string"},
                chunksize=100_000,
                low_memory=False,
            ):
                if not {"txId1", "txId2"}.issubset(set(chunk.columns)):
                    normalized = {
                        "".join(character for character in str(column).lower() if character.isalnum()):
                        column
                        for column in chunk.columns
                    }
                    source = normalized.get("txid1") or normalized.get("source") or normalized.get("from")
                    target = normalized.get("txid2") or normalized.get("target") or normalized.get("to")
                    if not source or not target:
                        raise HTTPException(
                            status_code=422,
                            detail="txs_edgelist.csv must contain source and destination transaction IDs.",
                        )
                else:
                    source = "txId1"
                    target = "txId2"
                for source_id, target_id in zip(
                    chunk[source].astype(str),
                    chunk[target].astype(str),
                ):
                    source_id = source_id.strip()
                    target_id = target_id.strip()
                    missing_markers = {"", "nan", "<na>", "none", "null", "nat"}
                    if source_id.lower() in missing_markers or target_id.lower() in missing_markers:
                        continue
                    if graph.has_edge(source_id, target_id):
                        duplicate_edges += 1
                        continue
                    graph.add_edge(source_id, target_id)
                    edge_count += 1

            for identifier in graph.nodes:
                label = ground_truth.get(str(identifier), "unknown")
                prediction = predictions.get(str(identifier), {})
                graph.nodes[identifier]["ground_truth_label"] = label
                graph.nodes[identifier]["predicted_class"] = prediction.get("predicted_class")
                graph.nodes[identifier]["illicit_probability"] = prediction.get("illicit_probability")
                graph.nodes[identifier]["confidence"] = prediction.get("confidence")
                graph.nodes[identifier]["selected_model"] = prediction.get("selected_model")

            self.graph_dir.mkdir(parents=True, exist_ok=True)
            import joblib

            joblib.dump(graph, self.graph_path, compress=3)
            manifest = {
                "dataset_batch": batch_id,
                "ml_batch": ml_batch,
                "ml_predictions_available": ml_predictions_available,
                "model_status": ml_engine.get_status().get("status"),
                "built_at": datetime.now(timezone.utc).isoformat(),
                "nodes": int(graph.number_of_nodes()),
                "edges": int(graph.number_of_edges()),
                "duplicate_edges_skipped": duplicate_edges,
                "edgelist_file": edgelist_path.name,
                "classes_file": classes_path.name if classes_path.is_file() else None,
            }
            temporary = self.manifest_path.with_suffix(
                self.manifest_path.suffix + f".{uuid.uuid4().hex}.tmp"
            )
            temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            os.replace(temporary, self.manifest_path)
            self._graph = graph
            self._set_status(
                status="ready",
                progress=100,
                message="Graph construction completed.",
                error=None,
                graph_ready=True,
                nodes=manifest["nodes"],
                edges=manifest["edges"],
                ml_predictions_available=ml_predictions_available,
            )
            return manifest
        except Exception as exc:
            self._graph = None
            self._set_status(
                status="error",
                progress=0,
                message="Graph construction failed.",
                error=f"{type(exc).__name__}: {exc}",
            )
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(
                status_code=500,
                detail=f"Graph construction failed: {exc}",
            ) from exc

    def statistics(self) -> Dict[str, Any]:
        graph = self.load_graph()
        undirected = graph.to_undirected(as_view=True)
        isolated = sum(1 for node, degree in graph.degree() if degree == 0)
        suspicious = sum(
            1
            for _, attributes in graph.nodes(data=True)
            if attributes.get("predicted_class") == "illicit"
        )
        connected = list(nx.connected_components(undirected))
        density = nx.density(graph) if graph.number_of_nodes() <= 500_000 else None
        return {
            "nodes": int(graph.number_of_nodes()),
            "edges": int(graph.number_of_edges()),
            "connected_components": int(len(connected)),
            "average_degree": float(sum(dict(graph.degree()).values()) / graph.number_of_nodes())
            if graph.number_of_nodes()
            else 0.0,
            "isolated_transactions": int(isolated),
            "density": float(density) if density is not None else None,
            "ml_flagged_transactions": int(suspicious),
        }

    def node_details(self, transaction_id: str) -> Dict[str, Any]:
        graph = self.load_graph()
        if transaction_id not in graph:
            raise HTTPException(status_code=404, detail="Transaction ID was not found in the graph.")
        attributes = graph.nodes[transaction_id]
        incoming = sorted(graph.predecessors(transaction_id), key=str)
        outgoing = sorted(graph.successors(transaction_id), key=str)
        return {
            "transaction_id": transaction_id,
            "predicted_class": attributes.get("predicted_class"),
            "illicit_probability": attributes.get("illicit_probability"),
            "confidence": attributes.get("confidence"),
            "selected_model": attributes.get("selected_model"),
            "ground_truth_label": attributes.get("ground_truth_label", "unknown"),
            "incoming_count": len(incoming),
            "outgoing_count": len(outgoing),
            "incoming_transaction_ids": incoming[:MAX_GRAPH_LIMIT],
            "outgoing_transaction_ids": outgoing[:MAX_GRAPH_LIMIT],
        }

    def neighborhood(
        self,
        transaction_id: str,
        depth: int = 2,
        limit: int = 100,
        direction: str = "all",
    ) -> Dict[str, Any]:
        graph = self.load_graph()
        if transaction_id not in graph:
            raise HTTPException(status_code=404, detail="Transaction ID was not found in the graph.")
        depth = min(max(depth, 1), MAX_GRAPH_DEPTH)
        limit = min(max(limit, 1), MAX_GRAPH_LIMIT)

        if direction == "upstream":
            subgraph = nx.DiGraph()
            visited = {transaction_id}
            frontier = {transaction_id}
            for _ in range(depth):
                neighbors = set()
                for node in frontier:
                    neighbors.update(graph.predecessors(node))
                neighbors -= visited
                if not neighbors:
                    break
                visited.update(neighbors)
                frontier = neighbors
            selected = list(visited)[:limit]
            subgraph = graph.subgraph(selected).copy()
        elif direction == "downstream":
            subgraph = nx.DiGraph()
            visited = {transaction_id}
            frontier = {transaction_id}
            for _ in range(depth):
                neighbors = set()
                for node in frontier:
                    neighbors.update(graph.successors(node))
                neighbors -= visited
                if not neighbors:
                    break
                visited.update(neighbors)
                frontier = neighbors
            selected = list(visited)[:limit]
            subgraph = graph.subgraph(selected).copy()
        else:
            undirected = graph.to_undirected(as_view=True)
            selected = {transaction_id}
            frontier = {transaction_id}
            for _ in range(depth):
                neighbors = set()
                for node in frontier:
                    neighbors.update(undirected.neighbors(node))
                neighbors -= selected
                if not neighbors:
                    break
                selected.update(neighbors)
                frontier = neighbors
                if len(selected) >= limit:
                    break
            subgraph = graph.subgraph(list(selected)[:limit]).copy()

        nodes = [self._node_payload(node, graph.nodes[node]) for node in subgraph.nodes]
        edges = [
            {"source": source, "target": target}
            for source, target in subgraph.edges
        ]
        return {
            "transaction_id": transaction_id,
            "direction": direction,
            "depth": depth,
            "nodes": nodes,
            "edges": edges,
        }

    @staticmethod
    def _node_payload(transaction_id: str, attributes: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "transaction_id": transaction_id,
            "predicted_class": attributes.get("predicted_class"),
            "illicit_probability": attributes.get("illicit_probability"),
            "confidence": attributes.get("confidence"),
            "ground_truth_label": attributes.get("ground_truth_label", "unknown"),
        }

    def fan_in(self, limit: int = 25) -> Dict[str, Any]:
        graph = self.load_graph()
        ranked = sorted(
            (
                (node, list(graph.predecessors(node)))
                for node in graph.nodes
                if graph.in_degree(node) > 1
            ),
            key=lambda item: (-len(item[1]), str(item[0])) ,
        )[:min(max(limit, 1), MAX_GRAPH_LIMIT)]
        return {
            "items": [
                {
                    **self._node_payload(node, graph.nodes[node]),
                    "incoming_count": len(predecessors),
                    "related_transaction_ids": predecessors[:MAX_GRAPH_LIMIT],
                }
                for node, predecessors in ranked
            ],
            "total": sum(1 for node in graph.nodes if graph.in_degree(node) > 1),
        }

    def fan_out(self, limit: int = 25) -> Dict[str, Any]:
        graph = self.load_graph()
        ranked = sorted(
            (
                (node, list(graph.successors(node)))
                for node in graph.nodes
                if graph.out_degree(node) > 1
            ),
            key=lambda item: (-len(item[1]), str(item[0])) ,
        )[:min(max(limit, 1), MAX_GRAPH_LIMIT)]
        return {
            "items": [
                {
                    **self._node_payload(node, graph.nodes[node]),
                    "outgoing_count": len(successors),
                    "related_transaction_ids": successors[:MAX_GRAPH_LIMIT],
                }
                for node, successors in ranked
            ],
            "total": sum(1 for node in graph.nodes if graph.out_degree(node) > 1),
        }

    def cycles(self, limit: int = 25) -> Dict[str, Any]:
        graph = self.load_graph()
        results: List[Dict[str, Any]] = []
        for component in nx.strongly_connected_components(graph):
            if len(component) < 2 or len(component) > MAX_CYCLE_COMPONENT_NODES:
                continue
            subgraph = graph.subgraph(component)
            for cycle in nx.simple_cycles(subgraph, length_bound=MAX_CYCLE_COMPONENT_NODES):
                participants = [str(node) for node in cycle]
                flagged = [
                    node
                    for node in participants
                    if graph.nodes[node].get("predicted_class") == "illicit"
                ]
                results.append(
                    {
                        "cycle": participants,
                        "cycle_length": len(participants),
                        "related_transaction_ids": participants,
                        "ml_flagged": bool(flagged),
                        "ml_flagged_transaction_ids": flagged,
                    }
                )
                if len(results) >= min(max(limit, 1), MAX_CYCLES):
                    break
            if len(results) >= min(max(limit, 1), MAX_CYCLES):
                break
        return {"items": results, "total": len(results), "limited": len(results) >= MAX_CYCLES}

    def suspicious_clusters(self, limit: int = 25) -> Dict[str, Any]:
        graph = self.load_graph()
        undirected = graph.to_undirected(as_view=True)
        clusters: List[Dict[str, Any]] = []
        for index, component in enumerate(nx.connected_components(undirected), start=1):
            if len(component) < 2:
                continue
            flagged = [
                node
                for node in component
                if graph.nodes[node].get("predicted_class") == "illicit"
            ]
            if len(flagged) < 2:
                continue
            probabilities = [
                graph.nodes[node].get("illicit_probability")
                for node in flagged
                if graph.nodes[node].get("illicit_probability") is not None
            ]
            transaction_ids = sorted(component, key=str)[:MAX_GRAPH_LIMIT]
            clusters.append(
                {
                    "cluster_id": f"cluster-{index}",
                    "transaction_count": len(component),
                    "flagged_count": len(flagged),
                    "highest_illicit_probability": max(probabilities) if probabilities else None,
                    "relevant_transaction_ids": transaction_ids,
                    "ml_flagged_transaction_ids": sorted(flagged, key=str)[:MAX_GRAPH_LIMIT],
                }
            )
            if len(clusters) >= min(max(limit, 1), MAX_GRAPH_LIMIT):
                break
        return {"items": clusters, "total": len(clusters)}

    def shortest_path(
        self,
        source: str,
        destination: str,
        limit: int = 100,
    ) -> Dict[str, Any]:
        graph = self.load_graph()
        if source not in graph:
            raise HTTPException(status_code=404, detail=f"Source transaction '{source}' was not found.")
        if destination not in graph:
            raise HTTPException(status_code=404, detail=f"Destination transaction '{destination}' was not found.")
        try:
            path = nx.shortest_path(graph, source, destination)
        except nx.NetworkXNoPath:
            return {
                "source": source,
                "destination": destination,
                "path_found": False,
                "transaction_ids": [],
                "hops": None,
                "ml_flagged_transaction_ids": [],
            }
        path = path[:min(max(limit, 1), MAX_GRAPH_LIMIT)]
        flagged = [
            node
            for node in path
            if graph.nodes[node].get("predicted_class") == "illicit"
        ]
        return {
            "source": source,
            "destination": destination,
            "path_found": True,
            "transaction_ids": path,
            "hops": len(path) - 1,
            "ml_flagged_transaction_ids": flagged,
            "nodes": [self._node_payload(node, graph.nodes[node]) for node in path],
        }


graph_engine = GraphEngine(Path(__file__).resolve().parents[2])
