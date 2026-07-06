/* Ops console — every platform component in one place: live status, an
   evidence-logged read-only SQL workbench, structured logs, and request
   traces. The laptop stand-in for Backstage + OTel→ClickStack. */

import { api } from "../api.js";
import { esc } from "../theme.js";

const PLANE_ORDER = ["data", "compute", "trust", "product"];

export async function renderOps(root) {
  root.innerHTML = `
    <div class="page-head">
      <p class="eyebrow">Operations plane</p>
      <h1>Ops console</h1>
      <p class="lede">The control plane in one place: each component reports its own live state,
        the SQL workbench is a read-only operator lane (every query lands in the evidence chain),
        and the logs and traces panes show what the platform is doing right now.</p>
    </div>
    <div id="ops-components"><div class="spin" role="status" aria-label="Loading"></div></div>

    <h2 class="ops-h2">SQL workbench <span class="muted ops-note">read-only · row-capped · evidence-logged as <code class="inline">ops.query</code></span></h2>
    <div class="card card-pad">
      <textarea id="sql-in" class="sql-input" rows="3" spellcheck="false"
        placeholder="SELECT date, tension_ratio FROM gold_labour_tension ORDER BY date DESC LIMIT 10"></textarea>
      <div class="ops-row">
        <button class="btn btn-primary" id="sql-run" type="button">Run</button>
        <span class="muted" id="sql-meta"></span>
      </div>
      <div id="sql-out"></div>
    </div>

    <h2 class="ops-h2">Logs <span class="muted ops-note">in-process ring buffer — ClickStack/HyperDX in the cluster profile</span></h2>
    <div class="card">
      <div class="ops-row" style="padding:12px 14px 0;">
        <select id="log-comp"><option value="">all components</option></select>
        <button class="btn btn-ghost" id="log-refresh" type="button">Refresh</button>
      </div>
      <div id="log-out" class="ops-scroll"></div>
    </div>

    <h2 class="ops-h2">Traces <span class="muted ops-note">one trace per API request; spans for authz, semantic compile, lane execution</span></h2>
    <div class="card">
      <div class="ops-row" style="padding:12px 14px 0;">
        <button class="btn btn-ghost" id="trace-refresh" type="button">Refresh</button>
      </div>
      <div id="trace-out" class="ops-scroll"></div>
    </div>`;

  const compEl = root.querySelector("#ops-components");
  try {
    await loadComponents(compEl);
  } catch (err) {
    compEl.innerHTML = `<div class="error-box"><strong>Ops API unavailable.</strong><br/>${esc(err.message)}
      <br/><span class="muted">This console needs a live platform (and, under OIDC, an operator group).</span></div>`;
    return;
  }

  wireSql(root);
  await loadLogs(root);
  root.querySelector("#log-refresh").addEventListener("click", () => loadLogs(root));
  root.querySelector("#log-comp").addEventListener("change", () => loadLogs(root));
  await loadTraces(root);
  root.querySelector("#trace-refresh").addEventListener("click", () => loadTraces(root));
}

async function loadComponents(el) {
  const { components } = await api.opsComponents();
  const byPlane = new Map();
  for (const c of components) {
    if (!byPlane.has(c.plane)) byPlane.set(c.plane, []);
    byPlane.get(c.plane).push(c);
  }
  el.innerHTML = PLANE_ORDER.filter((p) => byPlane.has(p)).map((plane) => `
    <p class="eyebrow" style="margin:18px 0 8px;">${esc(plane)} plane</p>
    <div class="ops-grid">
      ${byPlane.get(plane).map((c) => `
        <div class="card card-pad ops-card">
          <div class="ops-card-head">
            <span class="ops-dot ${esc(c.status)}"></span>
            <strong>${esc(c.name)}</strong>
          </div>
          <dl class="ops-kv">
            ${Object.entries(c.detail || {})
              .filter(([, v]) => v !== null && v !== undefined && v !== "")
              .map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(String(v))}</dd></div>`).join("")}
          </dl>
        </div>`).join("")}
    </div>`).join("");
}

function wireSql(root) {
  const input = root.querySelector("#sql-in");
  const out = root.querySelector("#sql-out");
  const meta = root.querySelector("#sql-meta");
  root.querySelector("#sql-run").addEventListener("click", async () => {
    const sql = input.value.trim();
    if (!sql) return;
    out.innerHTML = '<div class="spin" role="status" aria-label="Running"></div>';
    meta.textContent = "";
    try {
      const t0 = performance.now();
      const r = await api.opsQuery(sql);
      const ms = Math.round(performance.now() - t0);
      meta.textContent = `${r.row_count} row(s)${r.truncated ? ` (capped at ${r.row_cap})` : ""} · lane ${r.lane} · ${ms} ms`;
      out.innerHTML = r.rows.length ? `
        <div class="ops-scroll"><table class="evidence-table">
          <thead><tr>${r.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
          <tbody>${r.rows.map((row) => `<tr>${row.map((v) =>
            `<td class="mono">${v === null ? '<span class="muted">∅</span>' : esc(v)}</td>`).join("")}</tr>`).join("")}
          </tbody></table></div>`
        : '<p class="muted" style="padding:10px 0 0;">no rows</p>';
    } catch (err) {
      out.innerHTML = `<div class="error-box">${esc(err.message)}</div>`;
    }
  });
}

async function loadLogs(root) {
  const sel = root.querySelector("#log-comp");
  const { logs, components } = await api.opsLogs(sel.value);
  if (sel.options.length <= 1) {
    for (const c of components) sel.insertAdjacentHTML("beforeend",
      `<option value="${esc(c)}">${esc(c)}</option>`);
  }
  root.querySelector("#log-out").innerHTML = logs.length ? `
    <table class="evidence-table">
      <tbody>${logs.map((l) => `
        <tr>
          <td class="mono" style="white-space:nowrap;">${esc(l.ts.slice(11, 23))}</td>
          <td><span class="ops-level ${esc(l.level)}">${esc(l.level)}</span></td>
          <td class="mono">${esc(l.component)}</td>
          <td>${esc(l.message)}</td>
        </tr>`).join("")}
      </tbody></table>`
    : '<p class="muted" style="padding:12px 14px;">no log records yet — interact with the platform and refresh</p>';
}

async function loadTraces(root) {
  const { traces } = await api.opsTraces();
  root.querySelector("#trace-out").innerHTML = traces.length ? traces.map((t) => {
    const total = Math.max(t.duration_ms || 1, ...t.spans.map((s) => (s.offset_ms || 0) + (s.duration_ms || 0)));
    return `
      <details class="ops-trace">
        <summary>
          <span class="mono">${esc(t.start.slice(11, 23))}</span>
          <strong>${esc(t.name)}</strong>
          <span class="muted">${t.spans.length} span(s) · ${t.duration_ms} ms</span>
        </summary>
        <div class="ops-waterfall">
          ${t.spans.map((s) => `
            <div class="ops-span ${esc(s.status)}">
              <span class="ops-span-name mono">${s.parent_id ? "└ " : ""}${esc(s.name)}</span>
              <span class="ops-span-track">
                <span class="ops-span-bar" style="margin-left:${(100 * (s.offset_ms || 0) / total).toFixed(1)}%;width:${Math.max(1, 100 * (s.duration_ms || 0) / total).toFixed(1)}%;"></span>
              </span>
              <span class="mono muted">${s.duration_ms} ms</span>
            </div>`).join("")}
        </div>
      </details>`;
  }).join("") : '<p class="muted" style="padding:12px 14px;">no traces yet — hit any API endpoint and refresh</p>';
}
