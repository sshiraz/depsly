"""Shared scan-building workflows reused by CLI and batch scripts."""

from __future__ import annotations

from pathlib import Path

from core.analyze import analyze_graph
from core.export import export_recommendations
from core.graph import build_graph
from core.ingestion import parse_lockfile
from core.recommend import recommend_packages


def build_recommendation_scan(lockfile: Path, include_dev: bool = True, limit: int = 10) -> dict:
    """Build the normalized recommendation scan for a lockfile."""
    normalized = parse_lockfile(lockfile, include_dev=include_dev)
    graph = build_graph(normalized)
    report = analyze_graph(graph)
    recommendations = recommend_packages(graph, normalized_data=normalized, limit=limit)
    project_name = graph.root.name if graph.root is not None else "unknown"
    return export_recommendations(
        lockfile=lockfile,
        project_name=project_name,
        report=report,
        recommendations=recommendations,
        include_dev=include_dev,
        limit=limit,
    )
