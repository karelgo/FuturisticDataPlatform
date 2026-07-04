/* Portal home — the marketplace view. */

import { api } from "../api.js";
import { esc } from "../theme.js";

export async function renderPortal(root) {
  root.innerHTML = '<div class="spin" role="status" aria-label="Loading"></div>';
  const ov = await api.overview();
  const p = ov.products[0];
  const checksTotal = p ? p.checks.passed + p.checks.failed : 0;

  root.innerHTML = `
    <section class="hero">
      <p class="eyebrow">CARINA · reference implementation · laptop profile</p>
      <h1>Declare the what. Prove the why.<br/>The platform handles the how.</h1>
      <p class="lede">A working, single-node embodiment of the CARINA design: data products declared
        as contracts, quality compiled — never handwritten — every action hash-chained into an
        evidence log, and all consumption through one governed semantic layer.</p>
      <div class="hero-ctas">
        <a class="btn btn-primary" href="#/dashboard">Open the flagship dashboard</a>
        <a class="btn btn-ghost" href="#/product/labour-market-nl">Inspect the data product</a>
        <a class="btn btn-ghost" href="#/evidence">Verify the evidence chain</a>
      </div>
    </section>

    <div class="grid" style="margin-bottom:26px;">
      ${miniStat("Data products", ov.products.length, "contract-governed")}
      ${miniStat("Governed metrics", ov.metrics_count, "semantic layer — the only consumption path")}
      ${miniStat("Quality checks", p ? `${p.checks.passed}/${checksTotal}` : "—", "compiled from contracts, passing")}
      ${miniStat("Evidence records", ov.evidence.records, ov.evidence.ok ? "chain verified ✓" : "CHAIN BROKEN")}
    </div>

    <div class="section-head"><h2>Data products</h2>
      <span class="section-sub">each product = contracts + transforms + semantic models, versioned together</span></div>
    <div class="grid">
      ${ov.products.map(productCard).join("")}
    </div>

    <div class="section-head"><h2>How this platform works</h2>
      <span class="section-sub">the CARINA loop, end to end on your laptop</span></div>
    <div class="grid">
      ${step("1 · Declare", "Each dataset is declared in an ODCS-style contract: source, schema, classifications, quality SLOs, refresh cadence. No contract, no deployment.")}
      ${step("2 · Compile & ingest", "The pipeline compiles the contract into ingest filters, silver DDL, and quality checks, then lands CBS open data into a DuckDB lakehouse (bronze → silver → gold).")}
      ${step("3 · Serve & prove", "The semantic layer serves governed metrics to the dashboard; every ingest, check, and query is appended to a hash-chained evidence log you can verify on the Evidence page.")}
    </div>`;
}

function miniStat(label, value, sub) {
  return `<div class="col-3"><div class="card tile" style="min-height:110px;">
    <span class="tile-label">${esc(label)}</span>
    <span class="tile-value" style="font-size:30px;">${esc(String(value))}</span>
    <span class="tile-period">${esc(sub)}</span>
  </div></div>`;
}

function productCard(p) {
  const fresh = (p.freshness || []).map((f) => f.source_modified).filter(Boolean).sort().reverse()[0];
  return `<div class="col-8"><div class="card product-card">
    <div class="tags">
      <span class="tag tier">${esc(p.tier || "product")}</span>
      <span class="tag">${esc(p.status || "")}</span>
      ${(p.tags || []).slice(0, 4).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}
    </div>
    <h3>${esc(p.name)}</h3>
    <p>${esc(p.description)}</p>
    <div class="product-meta">
      <span>owner ${esc(p.owner)}</span>
      <span>${p.contracts.length} contracts</span>
      <span>${p.checks.passed}/${p.checks.passed + p.checks.failed} checks passing</span>
      ${fresh ? `<span>source updated ${esc(fresh.slice(0, 10))}</span>` : ""}
    </div>
    <div class="hero-ctas" style="margin-top:6px;">
      <a class="btn btn-primary" href="#/dashboard">Open dashboard</a>
      <a class="btn btn-ghost" href="#/product/${esc(p.id)}">Contracts & lineage</a>
    </div>
  </div></div>`;
}

function step(title, text) {
  return `<div class="col-4"><div class="card card-pad">
    <h3 style="margin:0 0 6px;font-size:15px;">${esc(title)}</h3>
    <p style="margin:0;color:var(--ink-2);font-size:13.5px;">${esc(text)}</p>
  </div></div>`;
}
