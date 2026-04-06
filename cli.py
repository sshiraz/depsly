"""Depsly CLI — dependency risk intelligence from the command line."""

from __future__ import annotations

from pathlib import Path

import click

from core.analyze import analyze_graph, GraphReport
from core.graph import build_graph
from core.ingestion import parse_package_lock


def _compute_risk_score(report: GraphReport) -> tuple[int, list[tuple[str, int, str]]]:
    """Compute a 0-100 risk score with breakdown.

    Returns (total_score, breakdown) where breakdown is a list of
    (category, points, reason) tuples.
    """
    breakdown: list[tuple[str, int, str]] = []

    # Depth contribution (0-25)
    depth_pts = 0
    if report.max_depth >= 10:
        depth_pts = 25
    elif report.max_depth >= 7:
        depth_pts = 20
    elif report.max_depth >= 5:
        depth_pts = 15
    elif report.max_depth >= 3:
        depth_pts = 8
    breakdown.append(("Depth risk", depth_pts, f"depth {report.max_depth}"))

    # Concentration (0-25)
    concentration_pts = 0
    if report.total_edges > 0 and report.top_packages_by_fanout:
        top3_edges = sum(c for _, c in report.top_packages_by_fanout[:3])
        concentration = top3_edges / report.total_edges
        if concentration >= 0.5:
            concentration_pts = 25
        elif concentration >= 0.4:
            concentration_pts = 20
        elif concentration >= 0.3:
            concentration_pts = 15
        elif concentration >= 0.15:
            concentration_pts = 8
    breakdown.append(("Centralization risk", concentration_pts, "top packages dominate"))

    # Size (0-15)
    size_pts = 0
    if report.total_nodes >= 500:
        size_pts = 15
    elif report.total_nodes >= 300:
        size_pts = 12
    elif report.total_nodes >= 200:
        size_pts = 10
    elif report.total_nodes >= 100:
        size_pts = 5
    breakdown.append(("Size risk", size_pts, f"{report.total_nodes} dependencies"))

    # Transitive ratio (0-25)
    transitive_pts = 0
    if report.direct_dependency_count > 0:
        ratio = report.transitive_dependency_count / report.direct_dependency_count
        if ratio >= 20:
            transitive_pts = 25
        elif ratio >= 12:
            transitive_pts = 20
        elif ratio >= 8:
            transitive_pts = 15
        elif ratio >= 4:
            transitive_pts = 10
    breakdown.append(("Transitive risk", transitive_pts, f"{report.transitive_dependency_count} indirect deps"))

    # Unresolved dependencies (0-15)
    unresolved_pts = 0
    if report.unresolved_dependency_count >= 5:
        unresolved_pts = 15
    elif report.unresolved_dependency_count >= 2:
        unresolved_pts = 10
    elif report.unresolved_dependency_count >= 1:
        unresolved_pts = 5
    breakdown.append(("Unresolved dependencies", unresolved_pts, f"{report.unresolved_dependency_count} missing"))

    # Cycles (0-10)
    cycle_pts = 10 if report.has_cycle else 0
    breakdown.append(("Cycle risk", cycle_pts, "circular dependency" if report.has_cycle else "none"))

    total = min(sum(pts for _, pts, _ in breakdown), 100)
    return total, breakdown


_RISK_COLORS = {"CRITICAL": "red", "HIGH": "red", "MODERATE": "yellow", "LOW": "green"}


def _risk_label(score: int) -> str:
    """Return a human-readable risk label."""
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MODERATE"
    return "LOW"


def _styled_risk(label: str, score: int) -> str:
    """Format risk label with color and /100 scale."""
    color = _RISK_COLORS.get(label, "white")
    return click.style(f"{label} RISK ({score}/100)", fg=color, bold=True)


def _build_summary(report: GraphReport) -> str:
    """Build a one-line interpretive summary."""
    traits: list[str] = []
    if report.max_depth >= 5:
        traits.append("deep")
    if report.total_edges > 0 and report.top_packages_by_fanout:
        top3 = sum(c for _, c in report.top_packages_by_fanout[:3])
        concentration = top3 / report.total_edges
        if concentration >= 0.5:
            traits.append("highly concentrated")
        elif concentration >= 0.2:
            traits.append("moderately concentrated")
    if report.total_nodes >= 200:
        traits.append("large")

    if not traits:
        structure = "a compact dependency structure"
    else:
        structure = f"a {' and '.join(traits)} dependency structure"

    advice: list[str] = []
    if report.max_depth >= 5:
        advice.append("reducing depth")
    if report.top_packages_by_fanout and report.top_packages_by_fanout[0][1] >= 10:
        advice.append("reviewing high-fanout packages")
    if report.unresolved_dependency_count > 0:
        advice.append("resolving missing dependencies")

    summary = f"Your project has {structure}."
    if advice:
        summary += f"\nConsider {' and '.join(advice)} where possible."
    return summary


def _format_report(report: GraphReport) -> str:
    """Format a GraphReport into human-readable output."""
    lines: list[str] = []

    # Headline: Project Risk score
    score, breakdown = _compute_risk_score(report)
    label = _risk_label(score)
    project = "unknown"
    if report.root_package_key:
        parts = report.root_package_key.rsplit("@", 1)
        project = parts[0] if parts else report.root_package_key
    lines.append(f"Project Risk: {_styled_risk(label, score)}")
    lines.append(f"Project: {project}")

    # Dependencies
    lines.append("")
    lines.append("Dependencies:")
    lines.append(f"  - Total: {report.total_nodes}")
    lines.append(f"  - Direct: {report.direct_dependency_count}")
    lines.append(f"  - Transitive: {report.transitive_dependency_count}")
    lines.append(f"  - Max depth: {report.max_depth}")

    # Standout metric: dependency concentration
    if report.total_edges > 0 and report.top_packages_by_fanout:
        top_fanout = [
            (key, count)
            for key, count in report.top_packages_by_fanout
            if count > 0
        ]
        top_n = min(10, len(top_fanout))
        top_edges = sum(c for _, c in top_fanout[:top_n])
        pct = round(top_edges / report.total_edges * 100)
        lines.append("")
        lines.append("Dependency concentration:")
        lines.append(f"  Top {top_n} packages control {pct}% of your graph")

    # Score breakdown
    lines.append("")
    lines.append("Score breakdown:")
    for category, pts, reason in breakdown:
        lines.append(f"  - {category}: +{pts} ({reason})")

    # Key risks — opinionated interpretation
    risks: list[str] = []
    if report.unresolved_dependency_count > 0:
        risks.append(
            f"{report.unresolved_dependency_count} unresolved dependencies — "
            "these cannot be audited or tracked"
        )
    if report.has_cycle:
        risks.append(
            "Circular dependency detected — increases fragility and "
            "complicates updates"
        )
    # Concentration
    if report.total_nodes > 1 and report.top_packages_by_fanout:
        top_fanout = [
            (key, count)
            for key, count in report.top_packages_by_fanout
            if count > 0
        ]
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
                f"High centralization: {len(dominant)} packages control "
                f"{pct}% of your dependency graph, increasing systemic risk"
            )
    # Transitive exposure
    if report.transitive_dependency_count >= 100:
        risks.append(
            f"High transitive exposure: {report.transitive_dependency_count} "
            "indirect dependencies significantly increase your attack surface"
        )
    if report.max_depth >= 5:
        risks.append(
            f"Deep dependency chain (depth {report.max_depth}) increases "
            "fragility and risk"
        )

    if risks:
        lines.append("")
        lines.append("Key risks:")
        for risk in risks:
            lines.append(f"  - {risk}")

    # Most connected packages
    top = [(k, c) for k, c in report.top_packages_by_fanout if c > 0][:5]
    if top:
        lines.append("")
        lines.append("Most connected packages (highest influence on your graph):")
        for key, count in top:
            lines.append(f"  - {key} ({count} deps)")

    # Summary
    lines.append("")
    lines.append("Summary:")
    lines.append(_build_summary(report))

    # Suggested actions
    actions: list[str] = []
    if report.top_packages_by_fanout and report.top_packages_by_fanout[0][1] >= 5:
        actions.append("Review top connected packages for necessity and trustworthiness")
    if report.max_depth >= 5:
        actions.append("Reduce dependency depth where possible")
    if report.transitive_dependency_count >= 50:
        actions.append("Audit transitive dependencies introduced by major packages")
    if report.unresolved_dependency_count > 0:
        actions.append("Investigate and resolve missing dependencies")
    if report.has_cycle:
        actions.append("Break circular dependency chains to simplify upgrades")
    if actions:
        lines.append("")
        lines.append("Suggested actions:")
        for action in actions:
            lines.append(f"  - {action}")

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
