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
    data_json = json.dumps(view_model, separators=(",", ":"))
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
          <li>Click a package to highlight its immediate neighborhood.</li>
          <li>Drag to pan, and use the mouse wheel to zoom.</li>
          <li>Use depth columns to understand how direct and transitive packages are layered.</li>
        </ul>
      </div>
    </aside>
  </div>
  <script>
    const GRAPH_DATA = {data_json};

    const svg = document.getElementById("graphSvg");
    const viewport = document.getElementById("graphViewport");
    const searchInput = document.getElementById("searchInput");
    const selectionCard = document.getElementById("selectionCard");
    const summary = document.getElementById("summary");
    const resetViewBtn = document.getElementById("resetViewBtn");
    const clearSelectionBtn = document.getElementById("clearSelectionBtn");

    const nodeWidth = 164;
    const nodeHeight = 56;
    const depthGap = 260;
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
    const layerHeights = orderedDepths.map(depth => layers.get(depth).length);
    const canvasHeight = Math.max(900, topPadding + Math.max(...layerHeights, 1) * layerGap + 120);
    const canvasWidth = Math.max(1600, leftPadding + orderedDepths.length * depthGap + 320);
    svg.setAttribute("viewBox", `0 0 ${{canvasWidth}} ${{canvasHeight}}`);

    const positions = new Map();
    orderedDepths.forEach((depth, depthIndex) => {{
      const layerNodes = layers.get(depth).slice().sort((a, b) => {{
        if (b.dependent_count !== a.dependent_count) return b.dependent_count - a.dependent_count;
        return a.key.localeCompare(b.key);
      }});
      const layerHeight = (layerNodes.length - 1) * layerGap;
      const startY = Math.max(topPadding, (canvasHeight - layerHeight) / 2);
      layerNodes.forEach((node, index) => {{
        positions.set(node.key, {{
          x: leftPadding + depthIndex * depthGap,
          y: startY + index * layerGap
        }});
      }});
    }});

    function metricCard(label, value) {{
      const el = document.createElement("div");
      el.className = "metric";
      el.innerHTML = `<div class="metric-label">${{label}}</div><div class="metric-value">${{value}}</div>`;
      return el;
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

    function applyTransform() {{
      viewport.setAttribute("transform", `translate(${{transform.x}}, ${{transform.y}}) scale(${{transform.scale}})`);
    }}

    function renderSidebar(node) {{
      if (!node) {{
        selectionCard.innerHTML = `<div class="muted">No package selected.</div>`;
        return;
      }}
      const parentList = (incoming.get(node.key) || []).sort();
      const depList = (outgoing.get(node.key) || []).sort();
      selectionCard.innerHTML = `
        <div class="pill" style="margin-bottom: 10px;">${{node.scope}} • ${{node.tone}}</div>
        <h2 style="margin: 0 0 4px;">${{node.name}}</h2>
        <div class="muted" style="margin-bottom: 12px;">${{node.key}}</div>
        <div class="meta-grid">
          <div><strong>Version</strong>${{node.version}}</div>
          <div><strong>Depth</strong>${{node.depth ?? "unknown"}}</div>
          <div><strong>Parents</strong>${{node.parent_count}}</div>
          <div><strong>Dependencies</strong>${{node.dependency_count}}</div>
          <div><strong>Dependents</strong>${{node.dependent_count}}</div>
          <div><strong>Root dev dependency</strong>${{node.scope === "root" ? "n/a" : node.is_dev_dependency === true ? "yes" : node.is_dev_dependency === false ? "no" : "unknown"}}</div>
        </div>
        <div style="height: 12px;"></div>
        <strong class="muted">Depends on</strong>
        <ul class="list">${{depList.length ? depList.map(item => `<li>${{item}}</li>`).join("") : "<li>None</li>"}}</ul>
        <strong class="muted">Introduced by</strong>
        <ul class="list">${{parentList.length ? parentList.map(item => `<li>${{item}}</li>`).join("") : "<li>Root only</li>"}}</ul>
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

    function draw() {{
      viewport.innerHTML = "";

      for (const depth of orderedDepths) {{
        const x = positions.get(layers.get(depth)[0].key).x;
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", String(x + nodeWidth / 2));
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
        if (!source || !target || !matchesSearch(sourceNode) || !matchesSearch(targetNode)) continue;
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const startX = source.x + nodeWidth;
        const startY = source.y + nodeHeight / 2;
        const endX = target.x;
        const endY = target.y + nodeHeight / 2;
        const curve = Math.max(40, (endX - startX) * 0.45);
        path.setAttribute("d", `M ${{startX}} ${{startY}} C ${{startX + curve}} ${{startY}}, ${{endX - curve}} ${{endY}}, ${{endX}} ${{endY}}`);
        path.setAttribute("class", edgeActive(edge) ? "edge active" : "edge");
        if (selectedKey && !edgeActive(edge)) {{
          path.setAttribute("opacity", "0.08");
        }}
        viewport.appendChild(path);
      }}

      for (const node of GRAPH_DATA.nodes) {{
        if (!matchesSearch(node)) continue;
        const position = positions.get(node.key);
        const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
        group.setAttribute("transform", `translate(${{position.x}}, ${{position.y}})`);
        group.setAttribute("class", `node-card${{nodeActive(node) ? "" : " dimmed"}}${{selectedKey === node.key ? " active" : ""}}`);
        group.dataset.key = node.key;

        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("width", String(nodeWidth));
        rect.setAttribute("height", String(nodeHeight));
        rect.setAttribute("class", "node-rect");
        rect.setAttribute("fill", toneColor[node.tone] || toneColor.other);
        rect.setAttribute("fill-opacity", node.key === selectedKey ? "0.34" : "0.18");
        group.appendChild(rect);

        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", "12");
        label.setAttribute("y", "24");
        label.setAttribute("class", "node-label");
        label.textContent = node.name.length > 22 ? `${{node.name.slice(0, 19)}}...` : node.name;
        group.appendChild(label);

        const sub = document.createElementNS("http://www.w3.org/2000/svg", "text");
        sub.setAttribute("x", "12");
        sub.setAttribute("y", "42");
        sub.setAttribute("class", "node-sub");
        const scopeText = node.scope === "direct" && node.is_dev_dependency ? "direct dev" : node.scope;
        sub.textContent = `${{node.version}} • ${{scopeText}} • ↑${{node.dependent_count}} ↓${{node.dependency_count}}`;
        group.appendChild(sub);

        group.addEventListener("click", () => {{
          selectedKey = node.key === selectedKey ? null : node.key;
          renderSidebar(selectedKey ? nodesByKey.get(selectedKey) : null);
          draw();
        }});
        viewport.appendChild(group);
      }}
    }}

    function resetView() {{
      transform = {{ x: 0, y: 0, scale: 1 }};
      applyTransform();
    }}

    resetViewBtn.addEventListener("click", resetView);
    clearSelectionBtn.addEventListener("click", () => {{
      selectedKey = null;
      renderSidebar(null);
      draw();
    }});

    searchInput.addEventListener("input", (event) => {{
      searchTerm = event.target.value.trim().toLowerCase();
      draw();
    }});

    let dragging = false;
    let dragStart = null;

    svg.addEventListener("mousedown", (event) => {{
      dragging = true;
      dragStart = {{
        x: event.clientX - transform.x,
        y: event.clientY - transform.y
      }};
      svg.classList.add("dragging");
    }});
    window.addEventListener("mouseup", () => {{
      dragging = false;
      dragStart = null;
      svg.classList.remove("dragging");
    }});
    window.addEventListener("mousemove", (event) => {{
      if (!dragging || !dragStart) return;
      transform.x = event.clientX - dragStart.x;
      transform.y = event.clientY - dragStart.y;
      applyTransform();
    }});
    svg.addEventListener("wheel", (event) => {{
      event.preventDefault();
      const factor = event.deltaY < 0 ? 1.08 : 0.92;
      const next = Math.max(0.45, Math.min(2.4, transform.scale * factor));
      transform.scale = next;
      applyTransform();
    }}, {{ passive: false }});

    renderSidebar(null);
    draw();
    applyTransform();
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
