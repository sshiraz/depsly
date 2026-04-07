"""Depsly CLI — dependency risk intelligence from the command line."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import click

from core.analyze import analyze_graph, analyze_removal_impact, GraphReport
from core.graph import build_graph
from core.ingestion import parse_package_lock
from core.scoring import score_project
from core.simulate import simulate_remove as simulate_remove_result


_RISK_COLORS = {"CRITICAL": "red", "HIGH": "red", "MODERATE": "yellow", "LOW": "green"}


def _project_name(report: GraphReport) -> str:
    """Extract project name from root package key."""
    if report.root_package_key:
        parts = report.root_package_key.rsplit("@", 1)
        return parts[0] if parts else report.root_package_key
    return "unknown"


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
    proj_score = score_project(report)
    score = proj_score.total
    label = proj_score.label
    lines.append(f"Project Risk: {_styled_risk(label, score)}")
    lines.append(f"Project: {_project_name(report)}")

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
    for comp in proj_score.components:
        lines.append(f"  - {comp.category}: +{comp.points} ({comp.reason})")

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

    # Highest blast radius packages
    blast = [(k, cnt, f) for k, cnt, f in report.top_packages_by_blast_radius if cnt > 0][:5]
    if blast:
        lines.append("")
        lines.append("Highest blast radius packages:")
        for i, (key, count, frac) in enumerate(blast, 1):
            pct = round(frac * 100)
            lines.append(f"  {i}. {key} -> affects {count} packages ({pct}%)")

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
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def analyze(lockfile: Path, include_dev: bool, fanout_limit: int, as_json: bool) -> None:
    """Analyze a package-lock.json file."""
    try:
        normalized = parse_package_lock(lockfile, include_dev=include_dev)
        graph = build_graph(normalized)
        report = analyze_graph(graph, fanout_limit=fanout_limit)
        if as_json:
            proj_score = score_project(report)
            output = {
                "project": _project_name(report),
                "risk": {
                    "score": proj_score.total,
                    "label": proj_score.label,
                    "components": [
                        {"category": c.category, "points": c.points, "reason": c.reason}
                        for c in proj_score.components
                    ],
                },
                "dependencies": {
                    "total": report.total_nodes,
                    "direct": report.direct_dependency_count,
                    "transitive": report.transitive_dependency_count,
                    "max_depth": report.max_depth,
                },
                "flags": {
                    "has_cycle": report.has_cycle,
                    "unresolved_count": report.unresolved_dependency_count,
                },
                "top_packages_by_fanout": [
                    {"key": k, "count": c} for k, c in report.top_packages_by_fanout if c > 0
                ],
                "top_packages_by_blast_radius": [
                    {"key": k, "count": cnt, "fraction": round(f, 4)}
                    for k, cnt, f in report.top_packages_by_blast_radius
                ],
            }
            click.echo(json_mod.dumps(output, indent=2))
        else:
            click.echo(_format_report(report))
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command("simulate-remove")
@click.argument("lockfile", type=click.Path(exists=True, path_type=Path))
@click.argument("package_key")
@click.option(
    "--include-dev/--no-dev",
    default=True,
    help="Include devDependencies (default: yes).",
)
def simulate_remove(lockfile: Path, package_key: str, include_dev: bool) -> None:
    """Simulate removing a package and show the impact."""
    try:
        normalized = parse_package_lock(lockfile, include_dev=include_dev)
        graph = build_graph(normalized)
        simulation = simulate_remove_result(graph, package_key)
        result = analyze_removal_impact(graph, package_key)

        if not simulation.package_found:
            raise click.ClickException(
                f"Package '{package_key}' not found in the dependency graph."
            )

        before = result.before_report
        after = result.after_report

        lines: list[str] = []
        lines.append(f"Simulating removal: {package_key}")
        lines.append("")
        lines.append("Before:")
        lines.append(f"  - Total dependencies: {before.total_nodes}")
        lines.append(f"  - Max depth: {before.max_depth}")
        lines.append(f"  - Transitive dependencies: {before.transitive_dependency_count}")
        lines.append("")
        lines.append("After:")
        lines.append(f"  - Total dependencies: {after.total_nodes}")
        lines.append(f"  - Max depth: {after.max_depth}")
        lines.append(f"  - Transitive dependencies: {after.transitive_dependency_count}")
        lines.append("")
        lines.append("Impact:")

        node_diff = simulation.removed_count
        pct = round(simulation.percent_removed * 100)
        lines.append(f"  - {node_diff} packages removed from the reachable graph ({pct}%)")

        if pct >= 40:
            lines.append(
                f"  - High impact: removing {package_key} removes "
                f"{pct}% of the dependency graph"
            )

        depth_diff = before.max_depth - after.max_depth
        if depth_diff > 0:
            lines.append(f"  - Max depth reduced by {depth_diff} ({before.max_depth} -> {after.max_depth})")
        elif depth_diff < 0:
            lines.append(f"  - Max depth increased by {-depth_diff} ({before.max_depth} -> {after.max_depth})")
        else:
            lines.append(
                f"  - Deepest remaining path is unchanged (depth {after.max_depth}) "
                "— the removed package was not on the longest chain"
            )

        trans_diff = before.transitive_dependency_count - after.transitive_dependency_count
        if trans_diff > 0:
            lines.append(f"  - Transitive dependency count reduced by {trans_diff}")
        elif trans_diff < 0:
            lines.append(f"  - Transitive dependency count increased by {-trans_diff}")
        else:
            lines.append("  - Transitive dependency count unchanged")

        if simulation.impacted_packages:
            lines.append("")
            lines.append("Top impacted packages:")
            for key, lost in simulation.impacted_packages:
                lines.append(f"  - {key} -> {lost} packages lost")

        lines.append("")
        lines.append(simulation.disclaimer)

        click.echo("\n".join(lines))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    cli()
