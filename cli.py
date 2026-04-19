"""Depsly CLI — dependency risk intelligence from the command line."""

from __future__ import annotations

import json as json_mod
import webbrowser
from pathlib import Path

import click

from core.analyze import analyze_graph, analyze_removal_impact, GraphReport, RemovalSimulationReport
from core.classify import classify_all_packages
from core.export import (
    ANALYZE_SCHEMA_VERSION,
    SIMULATE_REMOVE_SCHEMA_VERSION,
    TRACE_SCHEMA_VERSION,
    export_command_meta,
    export_recommendations,
)
from core.graph import build_graph
from core.ingestion import parse_package_lock
from core.recommend import recommend_packages
from core.resolve import resolve_package_key
from core.scan import build_recommendation_scan
from core.scoring import PACKAGE_SCORING_VERSION, score_project
from core.simulate import simulate_remove as simulate_remove_result
from core.storage import save_scan_export
from core.storage import compare_scan_exports, list_saved_scans, load_scan_export
from core.trace import trace_package
from core.visualize import write_graph_html


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


def _package_scope_label(classification) -> str:
    """Format direct/transitive labeling for human output."""
    if classification and classification.is_direct_dependency:
        return "direct"
    if classification and classification.is_transitive_dependency:
        return "transitive"
    return "unknown"


def _hero_action(recommendation) -> str:
    """Translate recommendation type into one clear next action."""
    if recommendation.recommendation_type == "REMOVE":
        return f"Remove or replace {recommendation.package_key} if not required."
    if recommendation.recommendation_type == "TRACE_UPSTREAM":
        return f"Trace the parent introducing {recommendation.package_key} before acting directly."
    if recommendation.recommendation_type == "REVIEW":
        return f"Review {recommendation.package_key} first; remove it if it is not required."
    return f"Defer changes to {recommendation.package_key} for now."


def _impact_pct(recommendation) -> int:
    return round(recommendation.impact_score * 100)


def _hero_why_lines(report: GraphReport, recommendation, removed_count: int, after_report: GraphReport) -> list[str]:
    """Build 1-2 human explanation lines for the hero insight."""
    lines: list[str] = []
    if recommendation.classification.is_direct_dependency and recommendation.classification.is_dev_dependency is True:
        lines.append("Large dev dependency under direct team control")
    elif recommendation.classification.is_direct_dependency:
        lines.append("Direct dependency under direct team control")
    elif recommendation.classification.is_transitive_dependency:
        lines.append("Transitive dependency with meaningful upstream impact")

    if after_report.max_depth < report.max_depth:
        lines.append(
            f"Deep dependency chains increase fragility; this cuts max depth from {report.max_depth} to {after_report.max_depth}"
        )
    elif recommendation.impact_score >= 0.15:
        lines.append(f"This one change would remove {removed_count} packages from the current reachable graph")
    elif report.transitive_dependency_count >= 100:
        lines.append("Indirect dependency exposure is already high, so small removals matter less")

    return lines[:2]


def _hero_insight_lines(graph, report: GraphReport, normalized_data: dict) -> list[str]:
    """Build the top-of-report hero insight from existing recommendation/simulation logic."""
    recommendations = recommend_packages(
        graph,
        normalized_data=normalized_data,
        limit=max(len(graph.nodes), 1),
    )
    if not recommendations:
        return []

    top_recommendation = recommendations[0]
    largest_impact = sorted(
        recommendations,
        key=lambda recommendation: (-recommendation.impact_score, recommendation.package_key),
    )[0]
    removal_reports: dict[str, RemovalSimulationReport] = {}

    def removal_report_for(package_key: str):
        if package_key not in removal_reports:
            removal_reports[package_key] = analyze_removal_impact(
                graph,
                package_key,
                before_report=report,
            )
        return removal_reports[package_key]

    top_recommendation_report = removal_report_for(top_recommendation.package_key)
    simulation_report = removal_report_for(largest_impact.package_key)
    trace_result = trace_package(graph, largest_impact.package_key, max_paths=1)

    reachable_before = report.direct_dependency_count + report.transitive_dependency_count
    reachable_after = (
        simulation_report.after_report.direct_dependency_count
        + simulation_report.after_report.transitive_dependency_count
    )

    lines: list[str] = []
    lines.append("")
    lines.append("Top Recommendation")
    lines.append("(ranked by risk model)")
    lines.append(f"  {top_recommendation.package_key}")
    lines.append(
        f"  -> Eliminates {top_recommendation_report.removed_subgraph_node_count} packages ({_impact_pct(top_recommendation)}% of your graph)"
    )
    if top_recommendation.package_key == largest_impact.package_key:
        lines.append("  -> Removing this has the biggest structural impact")
        if simulation_report.after_report.max_depth < report.max_depth:
            lines.append(
                f"  -> Reduces max depth from {report.max_depth} to {simulation_report.after_report.max_depth}"
            )
        else:
            lines.append(
                f"  -> Reduces root-reachable total from {reachable_before} to {reachable_after}"
            )
    else:
        lines.append("")
        lines.append("Largest Structural Impact")
        lines.append(f"  {largest_impact.package_key}")
        lines.append(
            f"  -> Removing this has the biggest structural impact"
        )
        lines.append(
            f"  -> Eliminates {simulation_report.removed_subgraph_node_count} packages ({_impact_pct(largest_impact)}% of your graph)"
        )
        if simulation_report.after_report.max_depth < report.max_depth:
            lines.append(
                f"  -> Reduces max depth from {report.max_depth} to {simulation_report.after_report.max_depth}"
            )
        else:
            lines.append(
                f"  -> Reduces root-reachable total from {reachable_before} to {reachable_after}"
            )

    lines.append("")
    lines.append("Proof:")
    lines.append("")
    lines.append("Before:")
    lines.append(f"  - Root-reachable total: {reachable_before}")
    lines.append(f"  - Max depth: {report.max_depth}")
    lines.append("")
    lines.append(f"After removing {largest_impact.package_key}:")
    lines.append(f"  - Root-reachable total: {reachable_after}")
    lines.append(f"  - Max depth: {simulation_report.after_report.max_depth}")

    why_lines = _hero_why_lines(
        report,
        largest_impact,
        simulation_report.removed_subgraph_node_count,
        simulation_report.after_report,
    )
    if why_lines:
        lines.append("")
        lines.append("Why this matters:")
        for line in why_lines:
            lines.append(f"  - {line}")

    if trace_result.paths:
        lines.append("")
        lines.append("Trace:")
        lines.append(f"  {trace_result.paths[0][0]} -> {' -> '.join(trace_result.paths[0][1:])}")

    lines.append("")
    lines.append("Recommended action:")
    lines.append(f"  {_hero_action(top_recommendation)}")
    lines.append("")
    lines.append("  Heuristic-based analysis. Validate with tests.")
    return lines


def _format_report(
    report: GraphReport,
    *,
    classifications: dict | None = None,
    lockfile: Path | None = None,
    graph=None,
    normalized_data: dict | None = None,
) -> str:
    """Format a GraphReport into human-readable output."""
    lines: list[str] = []

    # Headline: Project Risk score
    proj_score = score_project(report)
    score = proj_score.total
    label = proj_score.label
    lines.append(f"Project Risk: {_styled_risk(label, score)}")
    lines.append(f"Project: {_project_name(report)}")

    if graph is not None and normalized_data is not None:
        lines.extend(_hero_insight_lines(graph, report, normalized_data))

    # Dependencies
    reachable_total = (
        report.direct_dependency_count + report.transitive_dependency_count
        if report.root_package_key is not None
        else 0
    )
    lines.append("")
    lines.append("Dependencies:")
    lines.append(f"  - Graph nodes: {report.total_nodes}")
    lines.append(f"  - Root-reachable direct: {report.direct_dependency_count}")
    lines.append(f"  - Root-reachable transitive: {report.transitive_dependency_count}")
    if reachable_total > 0:
        lines.append(f"  - Root-reachable total: {reachable_total}")
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
            if pct >= 50:
                risks.append(
                    f"High centralization: {len(dominant)} packages control "
                    f"{pct}% of your dependency graph, increasing systemic risk"
                )
            elif pct >= 30:
                risks.append(
                    f"Moderate concentration: {len(dominant)} packages control "
                    f"{pct}% of your dependency graph"
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
        lines.append("  Direct packages are usually actionable; transitive packages often need tracing upstream.")
        for i, (key, count, frac) in enumerate(blast, 1):
            pct = round(frac * 100)
            classification = classifications.get(key) if classifications else None
            scope = _package_scope_label(classification)
            lines.append(f"  {i}. {key} [{scope}] -> affects {count} packages ({pct}%)")

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

    if lockfile is not None:
        transitive_target = None
        if classifications:
            for key, _, _ in blast:
                classification = classifications.get(key)
                if classification and classification.is_transitive_dependency:
                    transitive_target = key
                    break
        lines.append("")
        lines.append("Next steps:")
        lines.append(f"  - Use `depsly recommend {lockfile}` for prioritized actions.")
        if transitive_target:
            lines.append(f"  - Use `depsly trace {lockfile} {transitive_target}` to see why this transitive package exists.")

    return "\n".join(lines)


def _classification_summary(recommendation) -> str:
    """Build a short classification summary for a recommendation."""
    if recommendation.classification.is_direct_dependency and recommendation.classification.is_dev_dependency is True:
        return "Direct (root dev dependency)"
    if recommendation.classification.is_direct_dependency:
        return "Direct"
    if recommendation.classification.is_transitive_dependency:
        return "Transitive"
    return "Unknown"


def _display_reasons(recommendation) -> list[str]:
    """Build slightly more concrete user-facing rationale lines."""
    reasons: list[str] = []

    if recommendation.classification.is_direct_dependency and recommendation.classification.is_dev_dependency is True:
        reasons.append("Direct dependency from root devDependencies")
    elif recommendation.classification.is_direct_dependency:
        reasons.append("Direct dependency (user-controlled)")
    elif recommendation.classification.is_transitive_dependency:
        reasons.append("Transitive dependency (introduced by parent package)")

    impact_pct = round(recommendation.impact_score * 100)
    removed_count_hint = None
    for reason in recommendation.rationale:
        if "packages)" in reason:
            removed_count_hint = reason.split("(")[-1].rstrip(")")
            break
    impact_line = f"Structural impact: {impact_pct}%"
    if removed_count_hint:
        impact_line = f"{impact_line} ({removed_count_hint})"

    if recommendation.recommendation_type == "REMOVE":
        reasons.append(f"{impact_line}. Review whether this dependency is still required before removing it")
        return reasons[:2]
    if recommendation.recommendation_type == "REVIEW":
        reasons.append(f"{impact_line}. Verify whether this dependency is still required")
        return reasons[:2]
    reasons.append(impact_line)
    if recommendation.recommendation_type == "DEFER":
        reasons.append("Easy to change, but low payoff right now")
    elif recommendation.recommendation_type == "TRACE_UPSTREAM":
        reasons.append("Trace upstream before treating as directly removable")
    elif recommendation.reason_confidence == "HIGH":
        reasons.append("Strong structural signal, but usage still needs verification")

    return reasons[:2]


def _recommended_focus(recommendations: list) -> str:
    """Summarize how much immediate attention the top recommendation deserves."""
    top = recommendations[0]
    if top.impact_score >= 0.2:
        return "HIGH"
    if top.impact_score >= 0.08:
        return "MEDIUM"
    return "LOW"


def _recommendation_summary(recommendations: list) -> list[str]:
    """Build a short orientation summary for the recommendation list."""
    high_impact_recommendations = sum(
        1 for recommendation in recommendations
        if recommendation.impact_score >= 0.15
    )
    trace_upstream = sum(
        1 for recommendation in recommendations
        if recommendation.recommendation_type == "TRACE_UPSTREAM"
    )
    low_impact = sum(
        1 for recommendation in recommendations
        if recommendation.recommendation_type == "DEFER"
    )

    def _count_phrase(count: int, singular: str, plural: str) -> str:
        return singular if count == 1 else plural

    lines: list[str] = ["Summary:"]
    lines.append(
        f"- {high_impact_recommendations} "
        f"{_count_phrase(high_impact_recommendations, 'high-impact recommendation', 'high-impact recommendations')}"
    )
    lines.append(
        f"- {trace_upstream} "
        f"{_count_phrase(trace_upstream, 'transitive dependency requires upstream change', 'transitive dependencies require upstream change')}"
    )
    lines.append(
        f"- {low_impact} "
        f"{_count_phrase(low_impact, 'remaining item is low impact', 'remaining items are low impact')}"
    )
    return lines


def _recommend_project_name(graph) -> str:
    """Extract the actual project name from the root package when available."""
    if graph.root is not None:
        return graph.root.name
    return "unknown"


def _format_recommendations(recommendations: list, lockfile: Path, package_count: int, project_name: str) -> str:
    """Format package recommendations for terminal output."""
    if not recommendations:
        return "No package recommendations available."

    lines: list[str] = []
    lines.append("Depsly Recommendations")
    lines.append(f"Project: {project_name}")
    lines.append(f"Packages analyzed: {package_count}")
    lines.append(f"Scoring version: {PACKAGE_SCORING_VERSION}")
    lines.append(f"Recommended focus: {_recommended_focus(recommendations)}")
    lines.append("")
    lines.extend(_recommendation_summary(recommendations))
    lines.append("")
    lines.append("Recommendations:")

    for index, recommendation in enumerate(recommendations, 1):
        impact_pct = round(recommendation.impact_score * 100)
        actionability = recommendation.actionability
        if recommendation.recommendation_type == "DEFER" and recommendation.actionability != "LOW":
            actionability = f"{recommendation.actionability} (low impact)"
        lines.append("")
        lines.append(f"{index}. {recommendation.package_key}")
        if index <= 2 and recommendation.impact_score >= 0.15:
            lines.append("   Priority: HIGH")
        lines.append(f"   Action: {recommendation.recommendation_type}")
        lines.append(f"   Actionability: {actionability}")
        lines.append(f"   Reason confidence: {recommendation.reason_confidence}")
        lines.append(f"   Impact: {impact_pct}%")
        lines.append(f"   Classification: {_classification_summary(recommendation)}")
        lines.append("   Why:")
        for reason in _display_reasons(recommendation):
            lines.append(f"   - {reason}")

    trace_target = next(
        (r.package_key for r in recommendations if r.recommendation_type == "TRACE_UPSTREAM"),
        recommendations[0].package_key,
    )
    simulate_target = recommendations[0].package_key
    lines.append("")
    lines.append("Next steps:")
    lines.append(f"depsly trace {lockfile} {trace_target}")
    lines.append(f"depsly simulate-remove {lockfile} {simulate_target}")

    return "\n".join(lines)


def _build_recommendation_export(lockfile: Path, include_dev: bool, limit: int) -> dict:
    """Build the stable recommendation export used by JSON and persistence flows."""
    return build_recommendation_scan(lockfile, include_dev=include_dev, limit=limit)


def _graph_report_json(report: GraphReport) -> dict:
    """Serialize a GraphReport into a stable machine-readable shape."""
    return {
        "total_nodes": report.total_nodes,
        "total_edges": report.total_edges,
        "max_depth": report.max_depth,
        "has_cycle": report.has_cycle,
        "direct_dependency_count": report.direct_dependency_count,
        "transitive_dependency_count": report.transitive_dependency_count,
        "unresolved_dependency_count": report.unresolved_dependency_count,
        "leaf_package_count": report.leaf_package_count,
        "top_packages_by_fanout": [
            {"package_key": package_key, "count": count}
            for package_key, count in report.top_packages_by_fanout
        ],
        "top_packages_by_blast_radius": [
            {
                "package_key": package_key,
                "affected_count": count,
                "affected_fraction": round(fraction, 6),
            }
            for package_key, count, fraction in report.top_packages_by_blast_radius
        ],
    }


def _trace_result_json(result, *, include_dev: bool, max_paths: int) -> dict:
    """Serialize a TraceResult into a stable machine-readable shape."""
    return {
        "meta": export_command_meta(
            command="trace",
            schema_version=TRACE_SCHEMA_VERSION,
            include_dev=include_dev,
            max_paths=max_paths,
        ),
        "result": {
            "package_key": result.package_key,
            "package_found": result.package_found,
            "reachable_from_root": result.reachable_from_root,
            "path_count": len(result.paths),
            "paths": [list(path) for path in result.paths],
        },
    }


def _simulate_remove_json(
    simulation,
    removal_report: RemovalSimulationReport,
    *,
    include_dev: bool,
    requested_package_key: str,
    resolved_package_key: str,
) -> dict:
    """Serialize structural removal analysis into a stable machine-readable shape."""
    return {
        "meta": export_command_meta(
            command="simulate-remove",
            schema_version=SIMULATE_REMOVE_SCHEMA_VERSION,
            include_dev=include_dev,
        ),
        "result": {
            "requested_package_key": requested_package_key,
            "resolved_package_key": resolved_package_key,
            "package_found": simulation.package_found,
            "removed_keys": list(simulation.removed_keys),
            "removed_count": simulation.removed_count,
            "percent_removed": round(simulation.percent_removed, 6),
            "impacted_packages": [
                {"package_key": package_key, "lost_count": lost_count}
                for package_key, lost_count in simulation.impacted_packages
            ],
            "before": _graph_report_json(removal_report.before_report),
            "after": _graph_report_json(removal_report.after_report),
            "disclaimer": simulation.disclaimer,
        },
    }


def _format_trace_result(result) -> str:
    """Format root-to-target trace paths for terminal output."""
    if not result.package_found:
        return f"Package '{result.package_key}' not found in the dependency graph."
    if not result.reachable_from_root or not result.paths:
        return f"Package '{result.package_key}' is not reachable from the root package."

    lines: list[str] = []
    lines.append(f"Trace for: {result.package_key}")
    lines.append("")
    lines.append("Paths:")
    for index, path in enumerate(result.paths, 1):
        lines.append(f"{index}. {' -> '.join(path)}")
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
                "meta": export_command_meta(
                    command="analyze",
                    schema_version=ANALYZE_SCHEMA_VERSION,
                    include_dev=include_dev,
                    fanout_limit=fanout_limit,
                ),
                "project": {
                    "name": _project_name(report),
                },
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
            classifications = classify_all_packages(graph, normalized_data=normalized)
            click.echo(
                _format_report(
                    report,
                    classifications=classifications,
                    lockfile=lockfile,
                    graph=graph,
                    normalized_data=normalized,
                )
            )
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument("lockfile", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--include-dev/--no-dev",
    default=True,
    help="Include devDependencies (default: yes).",
)
@click.option(
    "--limit",
    default=10,
    type=int,
    help="Max recommendations to show (default: 10).",
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def recommend(lockfile: Path, include_dev: bool, limit: int, as_json: bool) -> None:
    """Recommend package actions for a package-lock.json file."""
    try:
        if as_json:
            output = _build_recommendation_export(lockfile, include_dev, limit)
            click.echo(json_mod.dumps(output, indent=2))
        else:
            normalized = parse_package_lock(lockfile, include_dev=include_dev)
            graph = build_graph(normalized)
            recommendations = recommend_packages(graph, normalized_data=normalized, limit=limit)
            project_name = _recommend_project_name(graph)
            click.echo(_format_recommendations(
                recommendations,
                lockfile,
                len(graph.nodes),
                project_name,
            ))
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command("save-scan")
@click.argument("lockfile", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--include-dev/--no-dev",
    default=True,
    help="Include devDependencies (default: yes).",
)
@click.option(
    "--limit",
    default=10,
    type=int,
    help="Max recommendations to save (default: 10).",
)
def save_scan(lockfile: Path, include_dev: bool, limit: int) -> None:
    """Persist a normalized recommendation scan locally."""
    try:
        output = _build_recommendation_export(lockfile, include_dev, limit)
        saved_path = save_scan_export(output)
        click.echo(f"Saved scan: {saved_path}")
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command("list-scans")
@click.option("--project", "project_name", help="Filter saved scans by project name.")
def list_scans(project_name: str | None) -> None:
    """List saved local scan files."""
    try:
        scan_paths = list_saved_scans(project_name)
        if not scan_paths:
            click.echo("No saved scans found.")
            return

        for path in scan_paths:
            scan = load_scan_export(path)
            click.echo(
                f"{path} | {scan['project']['name']} | {scan['scan']['timestamp']}"
            )
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command("compare-scans")
@click.argument("before_scan", type=click.Path(exists=True, path_type=Path))
@click.argument("after_scan", type=click.Path(exists=True, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def compare_scans(before_scan: Path, after_scan: Path, as_json: bool) -> None:
    """Compare two saved normalized scan files."""
    try:
        comparison = compare_scan_exports(load_scan_export(before_scan), load_scan_export(after_scan))
        if as_json:
            click.echo(json_mod.dumps(comparison, indent=2))
            return

        lines: list[str] = []
        lines.append("Scan Comparison")
        lines.append(f"Project: {comparison['project']['before']} -> {comparison['project']['after']}")
        lines.append(
            f"Scans: {comparison['scan']['before_timestamp']} -> {comparison['scan']['after_timestamp']}"
        )
        lines.append("")
        lines.append("Dependency changes:")
        lines.append(
            f"  - Total: {comparison['dependencies']['before_total']} -> {comparison['dependencies']['after_total']} "
            f"({comparison['dependencies']['delta_total']:+d})"
        )
        lines.append(
            f"  - Direct: {comparison['dependencies']['before_direct']} -> {comparison['dependencies']['after_direct']} "
            f"({comparison['dependencies']['delta_direct']:+d})"
        )
        lines.append(
            "  - Transitive: "
            f"{comparison['dependencies']['before_transitive']} -> {comparison['dependencies']['after_transitive']} "
            f"({comparison['dependencies']['delta_transitive']:+d})"
        )
        lines.append(
            f"  - Max depth: {comparison['dependencies']['before_max_depth']} -> {comparison['dependencies']['after_max_depth']} "
            f"({comparison['dependencies']['delta_max_depth']:+d})"
        )
        lines.append("")
        lines.append("Top recommendation:")
        lines.append(f"  - Before: {comparison['recommendations']['before_top'] or 'none'}")
        lines.append(f"  - After: {comparison['recommendations']['after_top'] or 'none'}")
        lines.append(
            f"  - Changed: {'yes' if comparison['recommendations']['changed'] else 'no'}"
        )
        click.echo("\n".join(lines))
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command("graph-html")
@click.argument("lockfile", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--include-dev/--no-dev",
    default=True,
    help="Include devDependencies (default: yes).",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Output HTML path (default: <lockfile-dir>/depsly-graph.html).",
)
@click.option(
    "--open/--no-open",
    "open_browser",
    default=False,
    help="Open the generated HTML in your default browser.",
)
def graph_html(lockfile: Path, include_dev: bool, output_path: Path | None, open_browser: bool) -> None:
    """Generate an interactive HTML dependency graph explorer."""
    try:
        normalized = parse_package_lock(lockfile, include_dev=include_dev)
        graph = build_graph(normalized)
        destination = output_path or lockfile.parent / "depsly-graph.html"
        written_path = write_graph_html(
            graph,
            lockfile=lockfile,
            normalized_data=normalized,
            output_path=destination,
        )
        click.echo(f"Graph HTML written to: {written_path}")
        if open_browser:
            webbrowser.open(written_path.resolve().as_uri())
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument("lockfile", type=click.Path(exists=True, path_type=Path))
@click.argument("package_key")
@click.option(
    "--include-dev/--no-dev",
    default=True,
    help="Include devDependencies (default: yes).",
)
@click.option(
    "--max-paths",
    default=3,
    type=int,
    help="Max shortest paths to show (default: 3).",
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def trace(lockfile: Path, package_key: str, include_dev: bool, max_paths: int, as_json: bool) -> None:
    """Explain why a package exists by tracing shortest root-to-target paths."""
    try:
        normalized = parse_package_lock(lockfile, include_dev=include_dev)
        graph = build_graph(normalized)
        result = trace_package(graph, package_key, max_paths=max_paths)
        if as_json:
            click.echo(
                json_mod.dumps(
                    _trace_result_json(result, include_dev=include_dev, max_paths=max_paths),
                    indent=2,
                )
            )
        else:
            click.echo(_format_trace_result(result))
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
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def simulate_remove(lockfile: Path, package_key: str, include_dev: bool, as_json: bool) -> None:
    """Simulate removing a package and show the impact."""
    try:
        normalized = parse_package_lock(lockfile, include_dev=include_dev)
        graph = build_graph(normalized)
        resolved_package_key = resolve_package_key(graph, package_key, normalized_data=normalized)

        if resolved_package_key is None:
            raise click.ClickException(
                f"Package '{package_key}' not found in the dependency graph."
            )

        simulation = simulate_remove_result(graph, resolved_package_key)
        result = analyze_removal_impact(graph, resolved_package_key)

        if not simulation.package_found:
            raise click.ClickException(
                f"Package '{package_key}' not found in the dependency graph."
            )

        if as_json:
            click.echo(
                json_mod.dumps(
                    _simulate_remove_json(
                        simulation,
                        result,
                        include_dev=include_dev,
                        requested_package_key=package_key,
                        resolved_package_key=resolved_package_key,
                    ),
                    indent=2,
                )
            )
            return

        before = result.before_report
        after = result.after_report

        lines: list[str] = []
        lines.append(f"Simulating removal: {resolved_package_key}")
        if resolved_package_key != package_key:
            lines.append(f"Resolved '{package_key}' to '{resolved_package_key}'")
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
                f"  - High impact: removing {resolved_package_key} removes "
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
