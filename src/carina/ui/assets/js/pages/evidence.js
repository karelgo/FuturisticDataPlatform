/* Evidence explorer — the hash-chained audit log, verifiable in one click. */

import { api } from "../api.js";
import { esc } from "../theme.js";

const FILTERS = [
  { key: "", label: "All" },
  { key: "ingest", label: "Ingest" },
  { key: "transform", label: "Transform" },
  { key: "quality", label: "Quality" },
  { key: "semantic", label: "Queries" },
];

export async function renderEvidence(root) {
  root.innerHTML = `
    <div class="page-head">
      <p class="eyebrow">Trust plane</p>
      <h1>Evidence chain</h1>
      <p class="lede">Every ingest, transform, quality run, and semantic query is appended to a
        hash-chained log: each record commits to the full history before it. Tamper with any past
        record and verification breaks — compliance here is a query, not a promise.</p>
    </div>
    <div id="verify"></div>
    <div class="filter-row" role="group" aria-label="Filter by action">
      <span class="filter-label">Action</span>
      <div class="seg" id="ev-seg">
        ${FILTERS.map((f, i) => `<button type="button" data-f="${f.key}" aria-pressed="${i === 0}">${esc(f.label)}</button>`).join("")}
      </div>
    </div>
    <div class="card evidence-table-wrap" id="ev-table"></div>`;

  const verifyEl = root.querySelector("#verify");
  const tableEl = root.querySelector("#ev-table");

  const v = await api.evidenceVerify();
  verifyEl.innerHTML = `
    <div class="verify-banner ${v.ok ? "" : "broken"}">
      <span class="big-dot"></span>
      <div>
        <strong>${v.ok ? "Chain verified" : `Chain BROKEN at record ${v.broken_at}: ${esc(v.reason || "")}`}</strong>
        — ${v.records} records re-hashed and checked just now.
        ${v.head ? `<div class="hash">head ${esc(v.head)}</div>` : ""}
      </div>
    </div>`;

  async function loadTable(action) {
    tableEl.innerHTML = '<div class="spin" role="status" aria-label="Loading"></div>';
    const { records, total } = await api.evidence({ limit: 100, ...(action ? { action } : {}) });
    const rows = records.map((r) => `
      <tr>
        <td class="mono">${r.seq}</td>
        <td class="mono" style="white-space:nowrap;">${esc(r.ts.slice(0, 19))}</td>
        <td><span class="action-chip ${esc(r.action.split(".")[0])}">${esc(r.action)}</span></td>
        <td>${esc(r.subject)}</td>
        <td>
          <details class="payload"><summary>payload</summary>
            <pre>${esc(JSON.stringify(r.payload, null, 2))}</pre>
          </details>
        </td>
        <td class="mono" title="${esc(r.chain_hash)}">${esc(r.chain_hash.slice(0, 12))}…</td>
      </tr>`).join("");
    tableEl.innerHTML = `
      <table class="evidence-table">
        <thead><tr><th>#</th><th>timestamp (UTC)</th><th>action</th><th>subject</th><th>payload</th><th>chain hash</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <p class="muted" style="padding:10px 14px;font-size:12px;">showing ${records.length} of ${total} records (newest first)</p>`;
  }

  await loadTable("");
  root.querySelector("#ev-seg").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-f]");
    if (!btn) return;
    root.querySelectorAll("#ev-seg button").forEach((b) => b.setAttribute("aria-pressed", b === btn ? "true" : "false"));
    loadTable(btn.dataset.f);
  });
}
