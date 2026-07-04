/* The "why you can trust this" drawer — every AI/analytics answer in CARINA
   renders its provenance: contracts, freshness, quality, policy lane, the
   compiled SQL, and the evidence-chain head at query time. */

import { esc } from "./theme.js";

let drawer, body;

export function initTrust() {
  drawer = document.getElementById("trust-drawer");
  body = document.getElementById("trust-body");
  document.getElementById("trust-close").addEventListener("click", closeTrust);
  document.getElementById("trust-scrim").addEventListener("click", closeTrust);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeTrust(); });
}

export function closeTrust() { drawer.setAttribute("aria-hidden", "true"); }

export function openTrust({ card, result, product }) {
  const prov = result?.provenance || {};
  const metric = result?.metric || {};
  const contracts = (product?.contracts || []).filter((c) => (prov.contracts || []).includes(c.id));

  const contractBlocks = contracts.map((c) => {
    const checks = c.checks_latest || [];
    const passed = checks.filter((x) => x.passed).length;
    const rows = checks.map((x) => `
      <div class="check-row">
        <span class="check-dot ${x.passed ? "pass" : "fail"}"></span>
        <span class="check-name">${esc(x.name)}</span>
      </div>`).join("");
    return `
      <div class="trust-contract">
        <div class="tc-name">${esc(c.name)}</div>
        <div class="tc-meta">
          <code class="inline">${esc(c.id)}</code> · ${esc(c.classification)} ·
          ${esc(c.source.license || "")} ·
          <a class="source-chip" target="_blank" rel="noopener"
             href="${esc(c.source.landing_page || c.source.url || "#")}">${esc(c.source.attribution || c.source.table)}</a>
        </div>
        <div class="tc-meta">source modified ${esc((c.freshness?.source_modified || "—").slice(0, 10))}
          · ingested ${esc((c.freshness?.ingested_at || "—").slice(0, 16))}
          · ${esc(String(c.freshness?.silver_rows ?? "—"))} rows</div>
        <div class="checks" style="margin-top:8px;">${rows}</div>
        <div class="tc-meta" style="margin-top:4px;">${passed}/${checks.length} checks passing</div>
      </div>`;
  }).join("");

  body.innerHTML = `
    <section class="trust-section">
      <h3>Answer</h3>
      <dl class="kv">
        <dt>Metric</dt><dd>${esc(metric.title || card.metricId)} <code class="inline">${esc(card.metricId)}</code></dd>
        <dt>Definition</dt><dd>${esc(metric.description || "—")}</dd>
        <dt>Grain</dt><dd>${esc(result?.grain || "—")}</dd>
        <dt>Compute lane</dt><dd><code class="inline">${esc(prov.lane || "—")}</code> — routed, not chosen</dd>
      </dl>
    </section>
    <section class="trust-section">
      <h3>Contracts behind this answer</h3>
      ${contractBlocks || '<p class="muted">No contract metadata available.</p>'}
    </section>
    <section class="trust-section">
      <h3>Semantic compilation</h3>
      <div class="trust-sql">${esc(prov.sql || "—")}</div>
      <p class="muted" style="font-size:12px;margin:8px 0 0;">
        Compiled by the semantic layer from <code class="inline">${esc(prov.model || "—")}</code>.
        Raw SQL from consumers is not accepted (ADR-0008).</p>
    </section>
    <section class="trust-section">
      <h3>Evidence</h3>
      <dl class="kv">
        <dt>Chain head</dt><dd class="hash">${esc(prov.evidence_head || "—")}</dd>
        <dt>Logged</dt><dd>this query, the ingests and quality runs behind it — <a href="#/evidence">open the evidence log</a></dd>
      </dl>
    </section>`;
  drawer.setAttribute("aria-hidden", "false");
}
