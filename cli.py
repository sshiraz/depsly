"""Depsly CLI — dependency risk intelligence from the command line."""

from __future__ import annotations

from pathlib import Path

import click

from core.analyze import analyze_graph, GraphReport
from core.graph import build_graph
from core.ingestion import parse_package_lock


def _format_report(report: GraphReport) -> str:
    """Format a GraphReport into human-readable output."""
    lines: list[str] = []

    # Project name (strip version from root key)
    project = "unknown"
    if report.root_package_key:
        parts = report.root_package_key.rsplit("@", 1)
        project = parts[0] if parts else report.root_package_key
    lines.append(f"Project: {project}")

    # Dependencies
    lines.append("")
    lines.append("Dependencies:")
    lines.append(f"  - Total: {report.total_nodes}")
    lines.append(f"  - Direct: {report.direct_dependency_count}")
    lines.append(f"  - Transitive: {report.transitive_dependency_count}")
    lines.append(f"  - Max depth: {report.max_depth}")

    # Key risks
    risks: list[str] = []
    if report.unresolved_dependency_count > 0:
        risks.append(
            f"{report.unresolved_dependency_count} unresolved dependencies"
        )
    if report.has_cycle:
        risks.append("Circular dependency detected")
    # Concentration: packages whose fanout covers a large share of the graph
    if report.total_nodes > 1 and report.top_packages_by_fanout:
        top_fanout = [
            (key, count)
            for key, count in report.top_packages_by_fanout
            if count > 0
        ]
        # Find packages that together control >= 50% of total edges
        dominant: list[tuple[str, int]] = []
        edge_sum = 0
        for key, count in top_fanout:
            dominant.append((key, count))
            edge_sum += count
            if edge_sum >= report.total_edges * 0.5:
                break
        if dominant and report.total_edges > 0:
            pct = round(edge_sum / report.total_edges * 100)
            risks.append(
                f"{len(dominant)} packages control {pct}% of the graph"
            )
    if report.max_depth >= 5:
        risks.append(f"Deep dependency chain detected (depth {report.max_depth})")

    if risks:
        lines.append("")
        lines.append("Key risks:")
        for risk in risks:
            lines.append(f"  - {risk}")

    # Top packages by fanout
    top = [(k, c) for k, c in report.top_packages_by_fanout if c > 0][:5]
    if top:
        lines.append("")
        lines.append("Top packages by fanout:")
        for key, count in top:
            lines.append(f"  - {key} ({count} deps)")

    return "\n".join(lines)


@click.group()
def cli() -> None:
    """Depsly — dependency risk intelligence."""


@cli.command()
@click.argument("lockfile", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--include-dev/--no-dev",
    default=True,
    help="Include devDependencies (default: yes).",
)
@click.option(
    "--fanout-limit",
    default=10,
    type=int,
    help="Max packages in fanout ranking (default: 10).",
)
def analyze(lockfile: Path, include_dev: bool, fanout_limit: int) -> None:
    """Analyze a package-lock.json file."""
    try:
        normalized = parse_package_lock(lockfile, include_dev=include_dev)
        graph = build_graph(normalized)
        report = analyze_graph(graph, fanout_limit=fanout_limit)
        click.echo(_format_report(report))
    except Exception as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    cli()
