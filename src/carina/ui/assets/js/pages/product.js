/* Data product page: contracts, quality, semantic models, lineage. */

import { api } from "../api.js";
import { esc } from "../theme.js";

export async function renderProduct(root, productId) {
  root.innerHTML = '<div class="spin" role="status" aria-label="Loading"></div>';
  const [p, lin] = await Promise.all([api.product(productId), api.lineage(productId)]);

  root.innerHTML = `
    <div class="page-head">
      <p class="eyebrow">Data product · ${esc(p.tier)} tier · ${esc(p.status)}</p>
      <h1>${esc(p.name)}</h1>
      <p class="lede">${esc(p.narrative || p.description)}</p>
    </div>

    <div class="grid">
      <div class="col-8">
        <div class="section-head" style="margin-top:0;"><h2>Contracts</h2>
          <span class="section-sub">the hub artifacts — everything below compiles from these</span></div>
        <div id="contracts"></div>
      </div>
      <div class="col-4">
        <div class="section-head" style="margin-top:0;"><h2>Product</h2></div>
        <div class="card card-pad">
          <dl class="kv">
            <dt>Owner</dt><dd>${esc(p.owner)}</dd>
            <dt>Contracts</dt><dd>${p.contracts.length}</dd>
            <dt>Semantic models</dt><dd>${p.semantic_models.length}</dd>
            <dt>Metrics</dt><dd>${p.metrics.length}</dd>
            <dt>Tags</dt><dd>${(p.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join(" ")}</dd>
          </dl>
          <div class="hero-ctas" style="margin-top:14px;">
            <a class="btn btn-primary" href="#/dashboard">Open dashboard</a>
          </div>
        </div>
        <div class="section-head"><h2>Metrics</h2><span class="section-sub">served by the semantic layer</span></div>
        <div class="card card-pad" style="display:grid;gap:8px;">
          ${p.metrics.map((m) => `
            <div style="display:flex;justify-content:space-between;gap:10px;font-size:13px;">
              <span><code class="inline">${esc(m.id)}</code></span>
              <span class="muted">${esc(m.unit)}</span>
            </div>`).join("")}
        </div>
      </div>
    </div>

    <div class="section-head"><h2>Lineage</h2>
      <span class="section-sub">source → silver (contracted) → gold (transforms) → semantic models</span></div>
    <div class="card lineage-wrap"><div id="lineage"></div></div>`;

  root.querySelector("#contracts").innerHTML = p.contracts.map(contractBlock).join("");
  root.querySelector("#lineage").appendChild(lineageSVG(lin));
}

function contractBlock(c) {
  const latest = c.checks_latest || [];
  const failed = latest.filter((x) => !x.passed).length;
  return `
  <details class="contract" ${failed ? "open" : ""}>
    <summary>
      <span class="badge ${failed ? "fail" : "pass"}"><span class="badge-ico">${failed ? "✕" : "✓"}</span>
        ${latest.length - failed}/${latest.length}</span>
      <span class="contract-name">${esc(c.name)}</span>
      <span class="contract-id">${esc(c.id)}</span>
      <span class="muted" style="margin-left:auto;font-size:12px;">
        ${esc((c.freshness?.source_modified || "").slice(0, 10))} · ${esc(String(c.freshness?.silver_rows ?? "—"))} rows</span>
    </summary>
    <div class="contract-body">
      <div class="contract-section">
        <h4>Source</h4>
        <dl class="kv">
          <dt>Dataset</dt><dd><a class="source-chip" target="_blank" rel="noopener"
            href="${esc(c.source.landing_page || c.source.url || "#")}">${esc(c.source.attribution || "")} (${esc(c.source.table || "")})</a></dd>
          <dt>License</dt><dd>${esc(c.source.license || "—")}</dd>
          <dt>Classification</dt><dd>${esc(c.classification)}</dd>
          <dt>Server-side filter</dt><dd><code class="inline">${esc(c.source.filter || "none — full table")}</code></dd>
          <dt>Refresh</dt><dd>${esc(c.refresh?.cadence || "—")} · ${esc(c.refresh?.sla || "")}</dd>
          <dt>Ingested</dt><dd>${esc((c.freshness?.ingested_at || "—").slice(0, 16))} → <code class="inline">${esc(c.silver_table)}</code></dd>
        </dl>
      </div>
      <div class="contract-section">
        <h4>Declared schema (compiled to silver DDL)</h4>
        <div class="chart-table-wrap" style="max-height:220px;padding:0;">
          <table class="data-table">
            <thead><tr><th>column</th><th style="text-align:left;">type</th><th style="text-align:left;">unit</th><th style="text-align:left;">description</th></tr></thead>
            <tbody>${c.columns.map((col) => `
              <tr><td style="text-align:left;"><code class="inline">${esc(col.name)}</code></td>
                  <td style="text-align:left;">${esc(col.type || "")}</td>
                  <td style="text-align:left;">${esc(col.unit || "")}</td>
                  <td style="text-align:left;">${esc(col.description || "")}</td></tr>`).join("")}
            </tbody>
          </table>
        </div>
      </div>
      <div class="contract-section">
        <h4>Quality — compiled from this contract, latest run</h4>
        <div class="checks">
          ${latest.map((x) => `
            <div class="check-row">
              <span class="check-dot ${x.passed ? "pass" : "fail"}"></span>
              <span class="check-name">${esc(x.name)}</span>
              <span class="muted" style="font-size:11.5px;">${esc(x.run_ts.slice(0, 16))}</span>
            </div>`).join("") || '<span class="muted">not yet run — <code class="inline">carina check</code></span>'}
        </div>
      </div>
    </div>
  </details>`;
}

/* Simple layered DAG: columns by kind, curved edges. */
function lineageSVG(lin) {
  const kinds = ["source", "silver", "gold", "semantic"];
  const cols = kinds.map((k) => lin.nodes.filter((n) => n.kind === k));
  const colX = [20, 260, 520, 800];
  const nodeW = 200, nodeH = 40, gapY = 14;
  const maxRows = Math.max(...cols.map((c) => c.length));
  const height = maxRows * (nodeH + gapY) + 30;

  const pos = new Map();
  cols.forEach((col, ci) => {
    const totalH = col.length * (nodeH + gapY) - gapY;
    const y0 = (height - totalH) / 2;
    col.forEach((n, ri) => pos.set(n.id, { x: colX[ci], y: y0 + ri * (nodeH + gapY) }));
  });

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 1040 ${height}`);
  svg.setAttribute("class", "lineage-svg");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Lineage graph from sources through silver and gold tables to semantic models");

  let edges = "", nodes = "";
  for (const e of lin.edges) {
    const a = pos.get(e.from), b = pos.get(e.to);
    if (!a || !b) continue;
    const x1 = a.x + nodeW, y1 = a.y + nodeH / 2, x2 = b.x, y2 = b.y + nodeH / 2;
    const mx = (x1 + x2) / 2;
    edges += `<path class="lineage-edge" d="M${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}"/>`;
  }
  for (const n of lin.nodes) {
    const p = pos.get(n.id);
    if (!p) continue;
    nodes += `
      <g transform="translate(${p.x},${p.y})">
        <rect class="lineage-node" width="${nodeW}" height="${nodeH}" rx="8"/>
        <text class="lineage-kind" x="12" y="15">${esc(n.kind)}</text>
        <text class="lineage-label" x="12" y="30">${esc(n.label.length > 28 ? n.label.slice(0, 27) + "…" : n.label)}</text>
      </g>`;
  }
  svg.innerHTML = edges + nodes;
  return svg;
}
