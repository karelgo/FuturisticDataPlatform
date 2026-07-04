/* ChartCard — a governed chart with its table-view twin and trust panel.
   Tooltips enhance but never gate: every chart offers a Table toggle.
   The Trust button opens the drawer with contracts, checks, SQL, evidence. */

import { api } from "./api.js";
import { baseOption, esc, fmt, onThemeChange, pal, valueFormatter } from "./theme.js";
import { openTrust } from "./trust.js";

const registry = new Set();
onThemeChange(() => registry.forEach((c) => c.render()));
window.addEventListener("resize", () => registry.forEach((c) => c.resize()));

export class ChartCard {
  /**
   * @param {object} cfg
   *  title, subtitle, metricId, dimension?, productId,
   *  build(card, queryResult, palette) -> echarts option,
   *  tall?, transform?(queryResult) -> queryResult (client-side derivation)
   */
  constructor(cfg) {
    this.cfg = cfg;
    this.el = document.createElement("div");
    this.el.className = `card chart-card ${cfg.className || ""}`;
    this.mode = "chart";
    this.result = null;
    this.chart = null;
    registry.add(this);
  }

  async mount(container, since) {
    container.appendChild(this.el);
    this.el.innerHTML = `
      <div class="chart-head">
        <div class="chart-titles">
          <h3 class="chart-title">${esc(this.cfg.title)}</h3>
          <p class="chart-sub">${esc(this.cfg.subtitle || "")}</p>
        </div>
        <div class="chart-actions">
          <button class="chip-btn" data-act="table" aria-pressed="false" title="Toggle table view">Table</button>
          <button class="chip-btn" data-act="trust" title="Provenance, contracts, quality, evidence">Why trust this?</button>
        </div>
      </div>
      <div class="chart-body">
        <div class="chart-plot ${this.cfg.tall ? "tall" : ""}" role="img" aria-label="${esc(this.cfg.title)}"></div>
        <div class="chart-table-wrap" hidden></div>
      </div>
      <div class="chart-foot"></div>`;
    this.body = this.el.querySelector(".chart-body");
    this.plotEl = this.el.querySelector(".chart-plot");
    this.tableEl = this.el.querySelector(".chart-table-wrap");
    this.footEl = this.el.querySelector(".chart-foot");
    this.el.querySelector('[data-act="table"]').addEventListener("click", (e) => this.toggleTable(e.currentTarget));
    this.el.querySelector('[data-act="trust"]').addEventListener("click", () => this.showTrust());
    await this.load(since);
  }

  async load(since) {
    this.body.classList.add("loading"); // hold previous render at reduced opacity
    try {
      let result = await api.query(this.cfg.metricId, { dimension: this.cfg.dimension, since });
      if (this.cfg.transform) result = await this.cfg.transform(result, this);
      this.result = result;
      this.render();
      await this.renderFoot();
    } catch (err) {
      this.plotEl.innerHTML = `<div class="error-box">Failed to load: ${esc(err.message)}</div>`;
    } finally {
      this.body.classList.remove("loading");
    }
  }

  render() {
    if (!this.result) return;
    if (!this.chart) this.chart = echarts.init(this.plotEl, null, { renderer: "canvas" });
    const option = this.cfg.build(this, this.result, pal());
    this.chart.setOption(option, { notMerge: true });
    if (this.mode === "table") this.renderTable();
  }

  resize() { this.chart && this.chart.resize(); }

  toggleTable(btn) {
    this.mode = this.mode === "chart" ? "table" : "chart";
    btn.setAttribute("aria-pressed", this.mode === "table" ? "true" : "false");
    this.plotEl.hidden = this.mode === "table";
    this.tableEl.hidden = this.mode === "chart";
    if (this.mode === "table") this.renderTable();
    else this.resize();
  }

  renderTable() {
    const r = this.result;
    const vf = valueFormatter(r.metric.unit);
    const grain = r.grain;
    const table = document.createElement("table");
    table.className = "data-table";
    const thead = document.createElement("thead");
    const tbody = document.createElement("tbody");

    if (r.data.kind === "single") {
      thead.innerHTML = "";
      const hr = document.createElement("tr");
      for (const name of ["Period", r.metric.title]) {
        const th = document.createElement("th");
        th.textContent = name; // untrusted-safe
        hr.appendChild(th);
      }
      thead.appendChild(hr);
      for (const [t, v] of [...r.data.points].reverse()) {
        const tr = document.createElement("tr");
        const td1 = document.createElement("td");
        td1.textContent = fmt.byGrain(t, grain);
        const td2 = document.createElement("td");
        td2.textContent = vf(v);
        tr.append(td1, td2);
        tbody.appendChild(tr);
      }
    } else {
      const names = Object.keys(r.data.series);
      const dates = [...new Set(names.flatMap((n) => r.data.series[n].map((p) => p[0])))].sort();
      const byDate = {};
      for (const n of names) for (const [t, v] of r.data.series[n]) (byDate[t] ||= {})[n] = v;
      const hr = document.createElement("tr");
      for (const name of ["Period", ...names]) {
        const th = document.createElement("th");
        th.textContent = name;
        hr.appendChild(th);
      }
      thead.appendChild(hr);
      for (const t of dates.reverse()) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.textContent = fmt.byGrain(t, grain);
        tr.appendChild(td);
        for (const n of names) {
          const td2 = document.createElement("td");
          td2.textContent = vf(byDate[t]?.[n]);
          tr.appendChild(td2);
        }
        tbody.appendChild(tr);
      }
    }
    table.append(thead, tbody);
    this.tableEl.replaceChildren(table);
  }

  async renderFoot() {
    const prov = this.result?.provenance;
    if (!prov) return;
    const product = await api.productCached(this.cfg.productId);
    const contracts = product.contracts.filter((c) => prov.contracts.includes(c.id));
    const checks = contracts.flatMap((c) => c.checks_latest);
    const failed = checks.filter((c) => !c.passed).length;
    const chips = contracts
      .map((c) => `<a class="source-chip" href="${esc(c.source.url ? c.source.landing_page || c.source.url : "#")}"
                     target="_blank" rel="noopener">CBS ${esc(c.source.table)}</a>`)
      .join('<span class="sep">·</span>');
    const freshest = contracts.map((c) => c.freshness?.source_modified).filter(Boolean).sort().reverse()[0];
    this.footEl.innerHTML = `
      <span class="badge ${failed ? "fail" : "pass"}"><span class="badge-ico">${failed ? "✕" : "✓"}</span>
        ${failed ? `${failed} checks failing` : `${checks.length}/${checks.length} checks`}</span>
      <span class="sep">·</span>
      <span>Source ${chips}</span>
      ${freshest ? `<span class="sep">·</span><span>updated ${esc(freshest.slice(0, 10))}</span>` : ""}
      <span class="sep">·</span><span>lane: ${esc(prov.lane)}</span>`;
  }

  async showTrust() {
    const product = await api.productCached(this.cfg.productId);
    openTrust({ card: this.cfg, result: this.result, product });
  }
}

/** Stat tile with optional delta and 12-point sparkline. */
export function statTile({ label, value, delta, deltaLabel, good, period, spark }) {
  const el = document.createElement("div");
  el.className = "card tile";
  const deltaCls = delta == null ? "" : good == null ? "flat" : good ? "good" : "bad";
  const arrow = delta == null ? "" : delta > 0 ? "↑" : delta < 0 ? "↓" : "→";
  el.innerHTML = `
    <span class="tile-label">${esc(label)}</span>
    <div class="tile-row">
      <span class="tile-value">${esc(value)}</span>
      ${delta != null ? `<span class="tile-delta ${deltaCls}">${arrow} ${esc(deltaLabel)}</span>` : ""}
    </div>
    <span class="tile-period">${esc(period || "")}</span>
    <div class="tile-spark"></div>`;
  if (spark && spark.length > 1) el.querySelector(".tile-spark").appendChild(sparkline(spark));
  return el;
}

function sparkline(points) {
  const p = pal();
  const w = 132, h = 30, pad = 3;
  const vals = points.map((d) => d[1]).filter((v) => v != null);
  const min = Math.min(...vals), max = Math.max(...vals);
  const span = max - min || 1;
  const step = (w - pad * 2) / (points.length - 1);
  const xy = points.map((d, i) => [pad + i * step, h - pad - ((d[1] - min) / span) * (h - pad * 2)]);
  const path = xy.map((c, i) => (i ? "L" : "M") + c[0].toFixed(1) + " " + c[1].toFixed(1)).join(" ");
  const last = xy[xy.length - 1];
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("width", w);
  svg.setAttribute("height", h);
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = `
    <path d="${path}" fill="none" stroke="${p.deEmph}" stroke-width="1.6" stroke-linecap="round"/>
    <circle cx="${last[0]}" cy="${last[1]}" r="3.2" fill="${p.series[0]}" stroke="${p.surface}" stroke-width="1.6"/>`;
  return svg;
}
