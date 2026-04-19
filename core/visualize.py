"""Self-contained HTML graph visualization for dependency graphs."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from core.analyze import analyze_graph
from core.classify import classify_all_packages
from core.graph import DependencyGraph, parent_counts, shortest_depths_from_root


def _node_tone(classification) -> str:
    if classification.is_root:
        return "root"
    if classification.is_direct_dependency and classification.is_dev_dependency is True:
        return "direct-dev"
    if classification.is_direct_dependency:
        return "direct"
    if classification.is_transitive_dependency:
        return "transitive"
    return "other"


def build_graph_view_model(graph: DependencyGraph, normalized_data: dict | None = None) -> dict:
    """Build a stable view model for HTML graph rendering."""
    report = analyze_graph(graph)
    classifications = classify_all_packages(graph, normalized_data=normalized_data)
    depths = shortest_depths_from_root(graph)
    parents = parent_counts(graph)

    ordered_keys = sorted(
        graph.nodes,
        key=lambda key: (
            depths.get(key, 10**9),
            -len(graph.nodes[key].dependents),
            key,
        ),
    )

    nodes: list[dict] = []
    for key in ordered_keys:
        node = graph.nodes[key]
        classification = classifications[key]
        nodes.append(
            {
                "key": key,
                "name": node.name,
                "version": node.version,
                "depth": depths.get(key),
                "parent_count": parents.get(key, 0),
                "dependency_count": len(node.dependencies),
                "dependent_count": len(node.dependents),
                "scope": (
                    "root"
                    if classification.is_root
                    else "direct"
                    if classification.is_direct_dependency
                    else "transitive"
                    if classification.is_transitive_dependency
                    else "unknown"
                ),
                "is_dev_dependency": classification.is_dev_dependency,
                "tone": _node_tone(classification),
            }
        )

    edges = sorted(
        [
            {"source": node.key, "target": dep.key}
            for node in graph.nodes.values()
            for dep in node.dependencies
        ],
        key=lambda edge: (edge["source"], edge["target"]),
    )

    return {
        "project": {
            "name": graph.root.name if graph.root is not None else "unknown",
            "root_key": graph.root_key,
        },
        "summary": {
            "nodes": report.total_nodes,
            "reachable": report.direct_dependency_count + report.transitive_dependency_count,
            "direct": report.direct_dependency_count,
            "transitive": report.transitive_dependency_count,
            "max_depth": report.max_depth,
            "has_cycle": report.has_cycle,
        },
        "nodes": nodes,
        "edges": edges,
    }


def render_graph_html(view_model: dict, *, source_lockfile: Path) -> str:
    """Render a self-contained HTML graph explorer."""
    project_name = escape(view_model["project"]["name"])
    data_json = (
        json.dumps(view_model, separators=(",", ":"))
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    lockfile_label = escape(str(source_lockfile))
    title = f"Depsly Graph • {project_name}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: rgba(16, 24, 46, 0.9);
      --panel-strong: #121a33;
      --ink: #eaf0ff;
      --muted: #96a4ca;
      --line: rgba(255,255,255,0.08);
      --accent: #4fd1c5;
      --root: #f6ad55;
      --direct: #7dd3fc;
      --direct-dev: #a78bfa;
      --transitive: #34d399;
      --other: #94a3b8;
      --shadow: 0 24px 60px rgba(0,0,0,0.35);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(79,209,197,0.12), transparent 32%),
        radial-gradient(circle at top right, rgba(167,139,250,0.14), transparent 26%),
        linear-gradient(180deg, #0b1020 0%, #090d19 100%);
      color: var(--ink);
    }}
    .shell {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 16px;
      min-height: 100vh;
      padding: 18px;
    }}
    .main, .side {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }}
    .main {{
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .topbar {{
      padding: 18px 20px 14px;
      border-bottom: 1px solid var(--line);
      display: grid;
      gap: 14px;
    }}
    .title-row {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
    }}
    h1 {{
      margin: 0;
      font-size: 28px;
      line-height: 1;
      letter-spacing: -0.03em;
    }}
    .subtitle {{
      color: var(--muted);
      font-size: 14px;
      margin-top: 6px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
    }}
    .metric {{
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 14px;
    }}
    .metric-label {{
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .metric-value {{
      margin-top: 6px;
      font-size: 24px;
      font-weight: 700;
    }}
    .controls {{
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .search {{
      flex: 1 1 260px;
      min-width: 220px;
      display: flex;
      align-items: center;
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 0 12px;
    }}
    .search input {{
      width: 100%;
      padding: 12px 4px;
      background: transparent;
      border: 0;
      color: var(--ink);
      outline: none;
      font-size: 14px;
    }}
    .btn {{
      background: rgba(255,255,255,0.05);
      border: 1px solid var(--line);
      color: var(--ink);
      border-radius: 12px;
      padding: 10px 12px;
      cursor: pointer;
      font-size: 13px;
    }}
    .btn.active {{
      background: rgba(79,209,197,0.16);
      border-color: rgba(79,209,197,0.55);
      color: #dffcf8;
    }}
    .btn.hidden {{
      display: none;
    }}
    .legend {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      font-size: 13px;
      color: var(--muted);
    }}
    .legend span {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}
    .dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      display: inline-block;
    }}
    .viewport {{
      position: relative;
      flex: 1;
      overflow: hidden;
      background:
        linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
      background-size: 36px 36px;
    }}
    .explorer-pane {{
      position: absolute;
      inset: 0;
      overflow: auto;
      padding: 22px;
      display: none;
    }}
    .explorer-pane.active {{
      display: block;
    }}
    .explorer-shell {{
      display: grid;
      gap: 14px;
      min-height: 100%;
      align-content: start;
    }}
    .explorer-intro {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      color: var(--muted);
      font-size: 14px;
    }}
    .explorer-tree {{
      display: grid;
      gap: 10px;
    }}
    .tree-children {{
      margin-left: 22px;
      border-left: 1px solid rgba(255,255,255,0.08);
      padding-left: 14px;
      display: grid;
      gap: 8px;
    }}
    .tree-node {{
      display: grid;
      gap: 8px;
    }}
    .tree-entry {{
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 10px 12px;
      display: grid;
      gap: 8px;
    }}
    .tree-entry.active {{
      border-color: rgba(79,209,197,0.55);
      box-shadow: 0 12px 28px rgba(79,209,197,0.12);
    }}
    .tree-summary {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .tree-toggle {{
      width: 22px;
      height: 22px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
      color: var(--ink);
      cursor: pointer;
      flex: 0 0 auto;
    }}
    .tree-toggle.hidden {{
      visibility: hidden;
    }}
    .tree-select {{
      appearance: none;
      border: 0;
      background: transparent;
      color: var(--ink);
      padding: 0;
      margin: 0;
      cursor: pointer;
      font: inherit;
      text-align: left;
      min-width: 0;
    }}
    .tree-select strong {{
      display: block;
      font-size: 14px;
      line-height: 1.2;
      word-break: break-word;
    }}
    .tree-meta {{
      color: var(--muted);
      font-size: 12px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .tree-badges {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
      font-size: 11px;
      color: var(--ink);
    }}
    .badge.root {{
      border-color: rgba(246,173,85,0.4);
    }}
    .badge.direct {{
      border-color: rgba(125,211,252,0.4);
    }}
    .badge.direct-dev {{
      border-color: rgba(167,139,250,0.4);
    }}
    .badge.transitive {{
      border-color: rgba(52,211,153,0.4);
    }}
    .zoom-overlay {{
      position: absolute;
      border: 1px solid rgba(79,209,197,0.95);
      background: rgba(79,209,197,0.14);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08);
      pointer-events: none;
      display: none;
    }}
    .mode-chip {{
      position: absolute;
      top: 16px;
      right: 16px;
      padding: 8px 10px;
      border-radius: 999px;
      background: rgba(12,18,35,0.88);
      border: 1px solid rgba(79,209,197,0.35);
      color: #dffcf8;
      font-size: 12px;
      letter-spacing: 0.03em;
      display: none;
      pointer-events: none;
    }}
    svg {{
      width: 100%;
      height: 100%;
      display: block;
      cursor: grab;
    }}
    svg.dragging {{ cursor: grabbing; }}
    .edge {{
      fill: none;
      stroke: rgba(255,255,255,0.12);
      stroke-width: 1.3;
    }}
    .edge.active {{
      stroke: rgba(79,209,197,0.65);
      stroke-width: 2.4;
    }}
    .node-card {{
      cursor: pointer;
    }}
    .node-rect {{
      stroke: rgba(255,255,255,0.08);
      stroke-width: 1;
      rx: 16;
      ry: 16;
    }}
    .node-card.dimmed {{ opacity: 0.18; }}
    .node-card.active .node-rect {{
      stroke: rgba(255,255,255,0.7);
      stroke-width: 2;
      filter: drop-shadow(0 8px 24px rgba(79,209,197,0.32));
    }}
    .node-label {{
      font-size: 13px;
      fill: #f8fbff;
      font-weight: 700;
    }}
    .node-sub {{
      font-size: 11px;
      fill: #c6d2f3;
    }}
    .depth-label {{
      font-size: 12px;
      fill: #9db0dd;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .side {{
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .side h2 {{
      margin: 0;
      font-size: 18px;
    }}
    .card {{
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
    }}
    .muted {{ color: var(--muted); }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 6px 10px;
      background: rgba(255,255,255,0.05);
      border: 1px solid var(--line);
      font-size: 12px;
      color: var(--ink);
    }}
    .list {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      display: grid;
      gap: 6px;
      font-size: 14px;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      font-size: 13px;
    }}
    .meta-grid strong {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 4px;
    }}
    .path-strip {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 8px;
    }}
    .path-chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 7px 10px;
      background: rgba(255,255,255,0.05);
      border: 1px solid var(--line);
      font-size: 12px;
      color: var(--ink);
      max-width: 100%;
    }}
    .path-arrow {{
      color: var(--muted);
      font-size: 12px;
      align-self: center;
    }}
    @media (max-width: 1080px) {{
      .shell {{
        grid-template-columns: 1fr;
      }}
      .summary {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="main">
      <div class="topbar">
        <div class="title-row">
          <div>
            <h1>Dependency Graph</h1>
            <div class="subtitle">{project_name} • {lockfile_label}</div>
          </div>
          <div class="pill">HTML explorer</div>
        </div>
        <div class="summary" id="summary"></div>
        <div class="controls">
          <label class="search">
            <input id="searchInput" type="search" placeholder="Search package name or version">
          </label>
          <button class="btn active" id="surfaceModeBtn" type="button">Explorer</button>
          <button class="btn active" id="viewModeBtn" type="button">Neighborhood</button>
          <button class="btn" id="boxZoomBtn" type="button">Box zoom</button>
          <button class="btn" id="resetViewBtn" type="button">Reset view</button>
          <button class="btn" id="clearSelectionBtn" type="button">Clear selection</button>
        </div>
        <div class="legend">
          <span><i class="dot" style="background: var(--root)"></i>Root</span>
          <span><i class="dot" style="background: var(--direct)"></i>Direct</span>
          <span><i class="dot" style="background: var(--direct-dev)"></i>Direct dev</span>
          <span><i class="dot" style="background: var(--transitive)"></i>Transitive</span>
        </div>
      </div>
      <div class="viewport">
        <div class="mode-chip" id="modeChip">Box zoom mode</div>
        <div class="zoom-overlay" id="zoomOverlay"></div>
        <div class="explorer-pane" id="explorerPane"></div>
        <svg id="graphSvg" viewBox="0 0 1600 900" aria-label="Dependency graph">
          <g id="graphViewport"></g>
        </svg>
      </div>
    </section>
    <aside class="side">
      <div>
        <h2>Inspect a package</h2>
        <div class="muted">Click a node to inspect its role, depth, parents, and neighbors.</div>
      </div>
      <div class="card" id="selectionCard">
        <div class="muted">No package selected.</div>
      </div>
      <div class="card">
        <h2>How to use this</h2>
        <ul class="list">
          <li>Search to isolate a package or version.</li>
          <li>Use Explorer view for a readable tree of direct and transitive dependencies.</li>
          <li>Neighborhood mode shows only the selected package and its immediate relationships.</li>
          <li>Click a package to focus its immediate neighborhood, or switch to full graph for the complete map.</li>
          <li>Use the Path view in the sidebar to see one route from the root to the selected package.</li>
          <li>Drag to pan, use the mouse wheel to zoom at the cursor, or toggle box zoom to frame an area.</li>
          <li>Use arrow keys to pan, <code>Option</code>/<code>Ctrl</code> + arrow keys for larger jumps, and <code>+</code>/<code>-</code> to zoom.</li>
          <li>Use depth columns to understand how direct and transitive packages are layered.</li>
        </ul>
      </div>
    </aside>
  </div>
  <script>
    const GRAPH_DATA = {data_json};

    const svg = document.getElementById("graphSvg");
    const viewport = document.getElementById("graphViewport");
    const viewportFrame = document.querySelector(".viewport");
    const explorerPane = document.getElementById("explorerPane");
    const searchInput = document.getElementById("searchInput");
    const selectionCard = document.getElementById("selectionCard");
    const summary = document.getElementById("summary");
    const surfaceModeBtn = document.getElementById("surfaceModeBtn");
    const viewModeBtn = document.getElementById("viewModeBtn");
    const boxZoomBtn = document.getElementById("boxZoomBtn");
    const resetViewBtn = document.getElementById("resetViewBtn");
    const clearSelectionBtn = document.getElementById("clearSelectionBtn");
    const zoomOverlay = document.getElementById("zoomOverlay");
    const modeChip = document.getElementById("modeChip");

    const nodeWidth = 164;
    const nodeHeight = 56;
    const neighborhoodNodeWidth = 220;
    const neighborhoodNodeHeight = 72;
    const depthGap = 96;
    const laneGap = 194;
    const maxRowsPerLane = 18;
    const topPadding = 90;
    const leftPadding = 110;
    const layerGap = 86;

    const toneColor = {{
      "root": "var(--root)",
      "direct": "var(--direct)",
      "direct-dev": "var(--direct-dev)",
      "transitive": "var(--transitive)",
      "other": "var(--other)"
    }};

    const nodesByKey = new Map(GRAPH_DATA.nodes.map(node => [node.key, node]));
    const outgoing = new Map();
    const incoming = new Map();
    for (const node of GRAPH_DATA.nodes) {{
      outgoing.set(node.key, []);
      incoming.set(node.key, []);
    }}
    for (const edge of GRAPH_DATA.edges) {{
      outgoing.get(edge.source)?.push(edge.target);
      incoming.get(edge.target)?.push(edge.source);
    }}

    const layers = new Map();
    for (const node of GRAPH_DATA.nodes) {{
      const depth = node.depth ?? 999;
      if (!layers.has(depth)) layers.set(depth, []);
      layers.get(depth).push(node);
    }}

    const orderedDepths = Array.from(layers.keys()).sort((a, b) => a - b);
    const laneLayouts = new Map();
    const layerHeights = orderedDepths.map(depth => Math.min(layers.get(depth).length, maxRowsPerLane));
    const canvasHeight = Math.max(900, topPadding + Math.max(...layerHeights, 1) * layerGap + 120);

    let runningX = leftPadding;
    orderedDepths.forEach((depth) => {{
      const layerNodes = layers.get(depth);
      const laneCount = Math.max(1, Math.ceil(layerNodes.length / maxRowsPerLane));
      const width = nodeWidth + (laneCount - 1) * laneGap;
      laneLayouts.set(depth, {{
        x: runningX,
        width,
        laneCount,
      }});
      runningX += width + depthGap;
    }});
    const canvasWidth = Math.max(1600, runningX + 220);
    svg.setAttribute("viewBox", `0 0 ${{canvasWidth}} ${{canvasHeight}}`);

    const positions = new Map();
    orderedDepths.forEach((depth, depthIndex) => {{
      const layerNodes = layers.get(depth).slice().sort((a, b) => {{
        if (b.dependent_count !== a.dependent_count) return b.dependent_count - a.dependent_count;
        return a.key.localeCompare(b.key);
      }});
      const layout = laneLayouts.get(depth);
      const rowCount = Math.min(layerNodes.length, maxRowsPerLane);
      const layerHeight = (rowCount - 1) * layerGap;
      const startY = Math.max(topPadding, (canvasHeight - layerHeight) / 2);
      layerNodes.forEach((node, index) => {{
        const lane = Math.floor(index / maxRowsPerLane);
        const row = index % maxRowsPerLane;
        positions.set(node.key, {{
          x: layout.x + lane * laneGap,
          y: startY + row * layerGap
        }});
      }});
    }});

    function metricCard(label, value) {{
      const el = document.createElement("div");
      el.className = "metric";
      el.innerHTML = `<div class="metric-label">${{label}}</div><div class="metric-value">${{value}}</div>`;
      return el;
    }}

    function escapeHtml(value) {{
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }}

    summary.append(
      metricCard("Nodes", GRAPH_DATA.summary.nodes),
      metricCard("Reachable", GRAPH_DATA.summary.reachable),
      metricCard("Direct", GRAPH_DATA.summary.direct),
      metricCard("Transitive", GRAPH_DATA.summary.transitive),
      metricCard("Max depth", GRAPH_DATA.summary.max_depth)
    );

    let selectedKey = null;
    let searchTerm = "";
    let transform = {{ x: 0, y: 0, scale: 1 }};
    let surfaceMode = "explorer";
    let viewMode = "neighborhood";
    let boxZoomMode = false;
    let dragState = null;
    let boxZoomStart = null;
    const collapsedKeys = new Set();
    const expandedKeys = new Set();
    let treeMatchCache = new Map();

    function applyTransform() {{
      viewport.setAttribute("transform", `translate(${{transform.x}}, ${{transform.y}}) scale(${{transform.scale}})`);
    }}

    function clampScale(scale) {{
      return Math.max(0.45, Math.min(12, scale));
    }}

    function currentNodeWidth() {{
      return viewMode === "neighborhood" ? neighborhoodNodeWidth : nodeWidth;
    }}

    function currentNodeHeight() {{
      return viewMode === "neighborhood" ? neighborhoodNodeHeight : nodeHeight;
    }}

    function currentLabelFontSize() {{
      return viewMode === "neighborhood" ? "15" : "13";
    }}

    function currentSubFontSize() {{
      return viewMode === "neighborhood" ? "12" : "11";
    }}

    function currentLabelMaxChars() {{
      return viewMode === "neighborhood" ? 28 : 22;
    }}

    function fitWorldRect(x, y, width, height, padding = 40) {{
      const frame = viewportFrame.getBoundingClientRect();
      const safeWidth = Math.max(width, 1);
      const safeHeight = Math.max(height, 1);
      const nextScale = clampScale(Math.min(
        (frame.width - padding * 2) / safeWidth,
        (frame.height - padding * 2) / safeHeight
      ));
      transform = {{
        scale: nextScale,
        x: (frame.width - safeWidth * nextScale) / 2 - x * nextScale,
        y: (frame.height - safeHeight * nextScale) / 2 - y * nextScale
      }};
      applyTransform();
    }}

    function setBoxZoomMode(enabled) {{
      boxZoomMode = enabled;
      boxZoomBtn.classList.toggle("active", enabled);
      modeChip.style.display = enabled ? "block" : "none";
      svg.style.cursor = enabled ? "crosshair" : "";
    }}

    function setViewMode(mode) {{
      viewMode = mode;
      viewModeBtn.textContent = mode === "full" ? "Full graph" : "Neighborhood";
      viewModeBtn.classList.toggle("active", mode === "neighborhood");
    }}

    function setSurfaceMode(mode) {{
      surfaceMode = mode;
      const explorerActive = mode === "explorer";
      surfaceModeBtn.textContent = explorerActive ? "Explorer" : "Graph";
      surfaceModeBtn.classList.toggle("active", explorerActive);
      explorerPane.classList.toggle("active", explorerActive);
      svg.style.display = explorerActive ? "none" : "block";
      viewModeBtn.classList.toggle("hidden", explorerActive);
      boxZoomBtn.classList.toggle("hidden", explorerActive);
      resetViewBtn.textContent = explorerActive ? "Reset tree" : "Reset view";
      if (explorerActive) {{
        setBoxZoomMode(false);
      }}
    }}

    function zoomAtScreenPoint(nextScale, screenX, screenY) {{
      const clamped = clampScale(nextScale);
      const worldX = (screenX - transform.x) / transform.scale;
      const worldY = (screenY - transform.y) / transform.scale;
      transform.scale = clamped;
      transform.x = screenX - worldX * clamped;
      transform.y = screenY - worldY * clamped;
      applyTransform();
    }}

    function pathToNode(key) {{
      const rootKey = GRAPH_DATA.project.root_key;
      if (!key || !rootKey || !nodesByKey.has(key) || !nodesByKey.has(rootKey)) return [];
      if (key === rootKey) return [rootKey];

      const queue = [rootKey];
      const seen = new Set([rootKey]);
      const prev = new Map();

      while (queue.length) {{
        const current = queue.shift();
        for (const next of outgoing.get(current) || []) {{
          if (seen.has(next)) continue;
          seen.add(next);
          prev.set(next, current);
          if (next === key) {{
            const path = [key];
            let cursor = key;
            while (prev.has(cursor)) {{
              cursor = prev.get(cursor);
              path.push(cursor);
            }}
            return path.reverse();
          }}
          queue.push(next);
        }}
      }}

      return [key];
    }}

    function renderPath(path) {{
      if (!path.length) {{
        return `<div class="muted">No root path available for this package.</div>`;
      }}
      return `
        <div class="path-strip">
          ${{path.map((item, index) => `
            ${{index ? '<span class="path-arrow">→</span>' : ""}}
            <span class="path-chip">${{escapeHtml(item)}}</span>
          `).join("")}}
        </div>
      `;
    }}

    function scopeBadge(node) {{
      const scopeText = node.scope === "direct" && node.is_dev_dependency ? "direct dev" : node.scope;
      return `<span class="badge ${{node.tone}}">${{escapeHtml(scopeText)}}</span>`;
    }}

    function renderSidebar(node) {{
      if (!node) {{
        selectionCard.innerHTML = `<div class="muted">No package selected.</div>`;
        return;
      }}
      const parentList = (incoming.get(node.key) || []).sort();
      const depList = (outgoing.get(node.key) || []).sort();
      const path = pathToNode(node.key);
      selectionCard.innerHTML = `
        <div class="pill" style="margin-bottom: 10px;">${{escapeHtml(node.scope)}} • ${{escapeHtml(node.tone)}}</div>
        <h2 style="margin: 0 0 4px;">${{escapeHtml(node.name)}}</h2>
        <div class="muted" style="margin-bottom: 12px;">${{escapeHtml(node.key)}}</div>
        <div class="meta-grid">
          <div><strong>Version</strong>${{escapeHtml(node.version)}}</div>
          <div><strong>Depth</strong>${{escapeHtml(node.depth ?? "unknown")}}</div>
          <div><strong>Parents</strong>${{escapeHtml(node.parent_count)}}</div>
          <div><strong>Dependencies</strong>${{escapeHtml(node.dependency_count)}}</div>
          <div><strong>Dependents</strong>${{escapeHtml(node.dependent_count)}}</div>
          <div><strong>Root dev dependency</strong>${{escapeHtml(node.scope === "root" ? "n/a" : node.is_dev_dependency === true ? "yes" : node.is_dev_dependency === false ? "no" : "unknown")}}</div>
        </div>
        <div style="height: 12px;"></div>
        <strong class="muted">Path from root</strong>
        ${{renderPath(path)}}
        <div style="height: 12px;"></div>
        <strong class="muted">Depends on</strong>
        <ul class="list">${{depList.length ? depList.map(item => `<li>${{escapeHtml(item)}}</li>`).join("") : "<li>None</li>"}}</ul>
        <strong class="muted">Introduced by</strong>
        <ul class="list">${{parentList.length ? parentList.map(item => `<li>${{escapeHtml(item)}}</li>`).join("") : "<li>Root only</li>"}}</ul>
      `;
    }}

    function matchesSearch(node) {{
      if (!searchTerm) return true;
      const haystack = `${{node.key}} ${{node.name}} ${{node.version}}`.toLowerCase();
      return haystack.includes(searchTerm);
    }}

    function nodeActive(node) {{
      if (!selectedKey) return true;
      if (node.key === selectedKey) return true;
      return (incoming.get(selectedKey) || []).includes(node.key) || (outgoing.get(selectedKey) || []).includes(node.key);
    }}

    function edgeActive(edge) {{
      if (!selectedKey) return false;
      return edge.source === selectedKey || edge.target === selectedKey;
    }}

    function buildVisibleNodeKeys() {{
      const matchingKeys = new Set(
        GRAPH_DATA.nodes.filter(node => matchesSearch(node)).map(node => node.key)
      );

      if (viewMode === "full") {{
        return matchingKeys;
      }}

      const visible = new Set();
      const rootKey = GRAPH_DATA.project.root_key;

      function includeNeighborhood(key) {{
        if (!key || !nodesByKey.has(key)) return;
        visible.add(key);
        for (const parent of incoming.get(key) || []) visible.add(parent);
        for (const child of outgoing.get(key) || []) visible.add(child);
      }}

      if (selectedKey) {{
        includeNeighborhood(selectedKey);
      }} else if (searchTerm && matchingKeys.size > 0) {{
        for (const key of matchingKeys) includeNeighborhood(key);
      }} else {{
        includeNeighborhood(rootKey);
      }}

      if (searchTerm) {{
        for (const key of Array.from(visible)) {{
          const node = nodesByKey.get(key);
          if (!node || matchesSearch(node)) continue;
          const linkedToMatch =
            (incoming.get(key) || []).some(parent => matchingKeys.has(parent))
            || (outgoing.get(key) || []).some(child => matchingKeys.has(child));
          if (!linkedToMatch && key !== selectedKey && key !== rootKey) {{
            visible.delete(key);
          }}
        }}
      }}

      return visible;
    }}

    function explorerChildren(key) {{
      const children = (outgoing.get(key) || []).map(childKey => nodesByKey.get(childKey)).filter(Boolean);
      children.sort((a, b) => {{
        if ((a.depth ?? 999) !== (b.depth ?? 999)) return (a.depth ?? 999) - (b.depth ?? 999);
        if (b.dependent_count !== a.dependent_count) return b.dependent_count - a.dependent_count;
        return a.key.localeCompare(b.key);
      }});
      return children;
    }}

    function treeNodeMatches(key, seen = new Set()) {{
      if (treeMatchCache.has(key) && seen.size === 0) {{
        return treeMatchCache.get(key);
      }}
      if (seen.has(key)) return false;
      seen.add(key);
      const node = nodesByKey.get(key);
      if (!node) return false;
      const result = matchesSearch(node) || explorerChildren(key).some(child => treeNodeMatches(child.key, new Set(seen)));
      if (seen.size === 1) {{
        treeMatchCache.set(key, result);
      }}
      return result;
    }}

    function renderExplorerNode(key, depth = 0, stack = new Set(), renderedKeys = new Set()) {{
      const node = nodesByKey.get(key);
      if (!node) return "";
      if (stack.has(key)) return "";
      if (searchTerm && !treeNodeMatches(key)) return "";

      const children = explorerChildren(key).filter(child => child && child.key !== key);
      const alreadyRendered = renderedKeys.has(key);
      const expanded = !collapsedKeys.has(key) && (searchTerm || expandedKeys.has(key) || depth === 0);
      const nextStack = new Set(stack);
      nextStack.add(key);
      const nextRenderedKeys = new Set(renderedKeys);
      nextRenderedKeys.add(key);
      const childMarkup = expanded
        ? children.map(child => renderExplorerNode(child.key, depth + 1, nextStack, nextRenderedKeys)).join("")
        : "";
      const activeClass = selectedKey === key ? " active" : "";
      const duplicateBadge = alreadyRendered ? '<span class="badge">shared</span>' : "";

      return `
        <div class="tree-node">
          <div class="tree-entry${{activeClass}}">
            <div class="tree-summary">
              <button class="tree-toggle${{children.length ? "" : " hidden"}}" type="button" data-toggle-key="${{key}}" data-expanded="${{expanded ? "true" : "false"}}">${{expanded ? "−" : "+"}}</button>
              <button class="tree-select" type="button" data-select-key="${{key}}">
                <strong>${{escapeHtml(node.name)}}</strong>
                <div class="tree-meta">
                  <span>${{escapeHtml(node.version)}}</span>
                  <span>depth ${{escapeHtml(node.depth ?? "?")}}</span>
                  <span>deps ${{escapeHtml(node.dependency_count)}}</span>
                  <span>parents ${{escapeHtml(node.parent_count)}}</span>
                </div>
              </button>
            </div>
            <div class="tree-badges">
              ${{scopeBadge(node)}}
              ${{duplicateBadge}}
            </div>
          </div>
          ${{expanded && childMarkup ? `<div class="tree-children">${{childMarkup}}</div>` : ""}}
        </div>
      `;
    }}

    function renderExplorer() {{
      treeMatchCache = new Map();
      const rootKey = GRAPH_DATA.project.root_key;
      const rootNode = nodesByKey.get(rootKey);
      const intro = searchTerm
        ? `Filtering tree for "${{escapeHtml(searchTerm)}}"` 
        : "Collapsible dependency tree from the project root.";
      explorerPane.innerHTML = `
        <div class="explorer-shell">
          <div class="explorer-intro">
            <span>${{intro}}</span>
            <span>${{rootNode ? escapeHtml(rootNode.name) : "unknown root"}}</span>
          </div>
          <div class="explorer-tree">
            ${{rootKey ? renderExplorerNode(rootKey) : '<div class="muted">No root package available.</div>'}}
          </div>
        </div>
      `;

      explorerPane.querySelectorAll("[data-toggle-key]").forEach((button) => {{
        button.addEventListener("click", () => {{
          const key = button.dataset.toggleKey;
          const expanded = button.dataset.expanded === "true";
          if (expanded) {{
            expandedKeys.delete(key);
            collapsedKeys.add(key);
          }} else {{
            collapsedKeys.delete(key);
            expandedKeys.add(key);
          }}
          renderExplorer();
        }});
      }});

      explorerPane.querySelectorAll("[data-select-key]").forEach((button) => {{
        button.addEventListener("click", () => {{
          const key = button.dataset.selectKey;
          selectedKey = key === selectedKey ? null : key;
          renderSidebar(selectedKey ? nodesByKey.get(selectedKey) : null);
          renderExplorer();
        }});
      }});
    }}

    function visibleBounds(visibleKeys) {{
      const visibleNodes = Array.from(visibleKeys)
        .map(key => positions.get(key))
        .filter(Boolean);
      if (!visibleNodes.length) {{
        return {{ x: 0, y: 0, width: canvasWidth, height: canvasHeight }};
      }}

      const minX = Math.min(...visibleNodes.map(point => point.x));
      const minY = Math.min(...visibleNodes.map(point => point.y));
      const maxX = Math.max(...visibleNodes.map(point => point.x + currentNodeWidth()));
      const maxY = Math.max(...visibleNodes.map(point => point.y + currentNodeHeight()));
      return {{
        x: Math.max(0, minX - 80),
        y: Math.max(0, minY - 80),
        width: Math.min(canvasWidth, maxX - minX + Math.max(160, currentNodeWidth() - nodeWidth + 160)),
        height: Math.min(canvasHeight, maxY - minY + 160)
      }};
    }}

    function draw() {{
      viewport.innerHTML = "";
      const displayNodeWidth = currentNodeWidth();
      const displayNodeHeight = currentNodeHeight();
      const visibleKeys = buildVisibleNodeKeys();
      const visibleDepths = orderedDepths.filter(depth =>
        layers.get(depth).some(node => visibleKeys.has(node.key))
      );

      for (const depth of visibleDepths) {{
        const layout = laneLayouts.get(depth);
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", String(layout.x + layout.width / 2));
        label.setAttribute("y", "38");
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("class", "depth-label");
        label.textContent = depth === 0 ? "ROOT" : `DEPTH ${{depth}}`;
        viewport.appendChild(label);
      }}

      for (const edge of GRAPH_DATA.edges) {{
        const source = positions.get(edge.source);
        const target = positions.get(edge.target);
        const sourceNode = nodesByKey.get(edge.source);
        const targetNode = nodesByKey.get(edge.target);
        if (!source || !target || !sourceNode || !targetNode) continue;
        if (!visibleKeys.has(edge.source) || !visibleKeys.has(edge.target)) continue;
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const startX = source.x + displayNodeWidth;
        const startY = source.y + displayNodeHeight / 2;
        const endX = target.x;
        const endY = target.y + displayNodeHeight / 2;
        const curve = Math.max(40, (endX - startX) * 0.45);
        path.setAttribute("d", `M ${{startX}} ${{startY}} C ${{startX + curve}} ${{startY}}, ${{endX - curve}} ${{endY}}, ${{endX}} ${{endY}}`);
        path.setAttribute("class", edgeActive(edge) ? "edge active" : "edge");
        if (selectedKey && !edgeActive(edge)) {{
          path.setAttribute("opacity", "0.08");
        }}
        viewport.appendChild(path);
      }}

      for (const node of GRAPH_DATA.nodes) {{
        if (!visibleKeys.has(node.key)) continue;
        const position = positions.get(node.key);
        const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
        group.setAttribute("transform", `translate(${{position.x}}, ${{position.y}})`);
        group.setAttribute("class", `node-card${{nodeActive(node) ? "" : " dimmed"}}${{selectedKey === node.key ? " active" : ""}}`);
        group.dataset.key = node.key;

        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("width", String(displayNodeWidth));
        rect.setAttribute("height", String(displayNodeHeight));
        rect.setAttribute("class", "node-rect");
        rect.setAttribute("fill", toneColor[node.tone] || toneColor.other);
        rect.setAttribute("fill-opacity", node.key === selectedKey ? "0.34" : "0.18");
        group.appendChild(rect);

        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", "14");
        label.setAttribute("y", viewMode === "neighborhood" ? "29" : "24");
        label.setAttribute("class", "node-label");
        label.setAttribute("font-size", currentLabelFontSize());
        label.textContent = node.name.length > currentLabelMaxChars()
          ? `${{node.name.slice(0, currentLabelMaxChars() - 3)}}...`
          : node.name;
        group.appendChild(label);

        const sub = document.createElementNS("http://www.w3.org/2000/svg", "text");
        sub.setAttribute("x", "14");
        sub.setAttribute("y", viewMode === "neighborhood" ? "50" : "42");
        sub.setAttribute("class", "node-sub");
        sub.setAttribute("font-size", currentSubFontSize());
        const scopeText = node.scope === "direct" && node.is_dev_dependency ? "direct dev" : node.scope;
        sub.textContent = `${{node.version}} • ${{scopeText}} • ↑${{node.dependent_count}} ↓${{node.dependency_count}}`;
        group.appendChild(sub);

        group.addEventListener("click", () => {{
          if (boxZoomMode) return;
          selectedKey = node.key === selectedKey ? null : node.key;
          renderSidebar(selectedKey ? nodesByKey.get(selectedKey) : null);
          resetView();
        }});
        viewport.appendChild(group);
      }}

      return visibleBounds(visibleKeys);
    }}

    function resetView() {{
      if (surfaceMode === "explorer") {{
        collapsedKeys.clear();
        expandedKeys.clear();
        renderExplorer();
        return;
      }}
      const bounds = draw();
      fitWorldRect(bounds.x, bounds.y, bounds.width, bounds.height, 32);
    }}

    surfaceModeBtn.addEventListener("click", () => {{
      setSurfaceMode(surfaceMode === "explorer" ? "graph" : "explorer");
      if (surfaceMode === "explorer") {{
        renderExplorer();
      }} else {{
        resetView();
      }}
    }});
    viewModeBtn.addEventListener("click", () => {{
      setViewMode(viewMode === "full" ? "neighborhood" : "full");
      resetView();
    }});
    boxZoomBtn.addEventListener("click", () => {{
      setBoxZoomMode(!boxZoomMode);
    }});
    resetViewBtn.addEventListener("click", resetView);
    clearSelectionBtn.addEventListener("click", () => {{
      selectedKey = null;
      renderSidebar(null);
      if (surfaceMode === "explorer") {{
        renderExplorer();
      }} else {{
        resetView();
      }}
    }});

    searchInput.addEventListener("input", (event) => {{
      searchTerm = event.target.value.trim().toLowerCase();
      if (surfaceMode === "explorer") {{
        renderExplorer();
      }} else {{
        resetView();
      }}
    }});

    svg.addEventListener("mousedown", (event) => {{
      if (event.button !== 0) return;
      if (boxZoomMode) {{
        const frame = viewportFrame.getBoundingClientRect();
        boxZoomStart = {{
          x: event.clientX - frame.left,
          y: event.clientY - frame.top
        }};
        zoomOverlay.style.display = "block";
        zoomOverlay.style.left = `${{boxZoomStart.x}}px`;
        zoomOverlay.style.top = `${{boxZoomStart.y}}px`;
        zoomOverlay.style.width = "0px";
        zoomOverlay.style.height = "0px";
        return;
      }}
      if (event.target.closest(".node-card")) return;
      dragState = {{
        x: event.clientX - transform.x,
        y: event.clientY - transform.y
      }};
      svg.classList.add("dragging");
    }});
    window.addEventListener("mouseup", () => {{
      if (boxZoomStart) {{
        const left = parseFloat(zoomOverlay.style.left || "0");
        const top = parseFloat(zoomOverlay.style.top || "0");
        const width = parseFloat(zoomOverlay.style.width || "0");
        const height = parseFloat(zoomOverlay.style.height || "0");
        zoomOverlay.style.display = "none";
        if (width > 12 && height > 12) {{
          fitWorldRect(
            (left - transform.x) / transform.scale,
            (top - transform.y) / transform.scale,
            width / transform.scale,
            height / transform.scale,
            24
          );
        }}
        boxZoomStart = null;
      }}
      dragState = null;
      svg.classList.remove("dragging");
    }});
    window.addEventListener("mousemove", (event) => {{
      if (boxZoomStart) {{
        const frame = viewportFrame.getBoundingClientRect();
        const currentX = event.clientX - frame.left;
        const currentY = event.clientY - frame.top;
        const left = Math.min(boxZoomStart.x, currentX);
        const top = Math.min(boxZoomStart.y, currentY);
        zoomOverlay.style.left = `${{left}}px`;
        zoomOverlay.style.top = `${{top}}px`;
        zoomOverlay.style.width = `${{Math.abs(currentX - boxZoomStart.x)}}px`;
        zoomOverlay.style.height = `${{Math.abs(currentY - boxZoomStart.y)}}px`;
        return;
      }}
      if (!dragState) return;
      transform.x = event.clientX - dragState.x;
      transform.y = event.clientY - dragState.y;
      applyTransform();
    }});
    svg.addEventListener("wheel", (event) => {{
      event.preventDefault();
      const factor = event.deltaY < 0 ? 1.08 : 0.92;
      const frame = viewportFrame.getBoundingClientRect();
      const pointerX = event.clientX - frame.left;
      const pointerY = event.clientY - frame.top;
      zoomAtScreenPoint(transform.scale * factor, pointerX, pointerY);
    }}, {{ passive: false }});

    window.addEventListener("keydown", (event) => {{
      const tagName = event.target?.tagName;
      if (tagName === "INPUT" || tagName === "TEXTAREA" || event.target?.isContentEditable) return;

      const panStep = (event.altKey || event.ctrlKey) ? 360 : event.shiftKey ? 180 : 90;
      const frame = viewportFrame.getBoundingClientRect();
      const centerX = frame.width / 2;
      const centerY = frame.height / 2;

      if (event.key === "ArrowLeft") {{
        event.preventDefault();
        transform.x += panStep;
        applyTransform();
        return;
      }}
      if (event.key === "ArrowRight") {{
        event.preventDefault();
        transform.x -= panStep;
        applyTransform();
        return;
      }}
      if (event.key === "ArrowUp") {{
        event.preventDefault();
        transform.y += panStep;
        applyTransform();
        return;
      }}
      if (event.key === "ArrowDown") {{
        event.preventDefault();
        transform.y -= panStep;
        applyTransform();
        return;
      }}
      if (event.key === "+" || event.key === "=") {{
        event.preventDefault();
        zoomAtScreenPoint(transform.scale * 1.12, centerX, centerY);
        return;
      }}
      if (event.key === "-"
          || event.key === "_") {{
        event.preventDefault();
        zoomAtScreenPoint(transform.scale * 0.88, centerX, centerY);
      }}
    }});

    setSurfaceMode(surfaceMode);
    setViewMode(viewMode);
    renderSidebar(null);
    renderExplorer();
  </script>
</body>
</html>"""


def write_graph_html(
    graph: DependencyGraph,
    *,
    lockfile: Path,
    normalized_data: dict | None = None,
    output_path: Path,
) -> Path:
    """Write a self-contained graph explorer HTML file."""
    view_model = build_graph_view_model(graph, normalized_data=normalized_data)
    html = render_graph_html(view_model, source_lockfile=lockfile)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
