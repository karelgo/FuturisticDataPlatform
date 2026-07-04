/* The flagship dashboard: "How the Dutch job market is changing". */

import { api } from "../api.js";
import { ChartCard, statTile } from "../charts.js";
import { baseOption, esc, fmt, legendFor, legendPad, lineSeries } from "../theme.js";

const PRODUCT = "labour-market-nl";

const RANGES = [
  { key: "all", label: "All (1997–)", since: null },
  { key: "20y", label: "20 years", years: 20 },
  { key: "10y", label: "10 years", years: 10 },
  { key: "5y", label: "5 years", years: 5 },
];

function sinceFor(range) {
  if (!range.years) return null;
  const d = new Date();
  d.setFullYear(d.getFullYear() - range.years);
  return d.toISOString().slice(0, 10);
}

/* Stable slot assignment: color follows the entity, never its rank. */
const sectorSlots = new Map();
function slotFor(name, palette) {
  if (!sectorSlots.has(name)) sectorSlots.set(name, sectorSlots.size % 8);
  return palette.series[sectorSlots.get(name)];
}

function singleLineChart({ areaWash = false, markParity = false } = {}) {
  return (card, r, p) => {
    const opt = baseOption({ unit: r.metric.unit, grain: r.grain });
    const s = lineSeries({
      name: r.metric.title,
      data: r.data.points,
      color: p.series[0],
      areaWash,
      endLabel: true,
      unit: r.metric.unit,
    });
    if (markParity) {
      s.markLine = {
        symbol: "none",
        silent: true,
        lineStyle: { color: p.ink3, width: 1, type: "solid" },
        label: {
          formatter: "1.00 — one vacancy per unemployed person",
          position: "insideStartTop", color: p.ink3, fontSize: 11,
        },
        data: [{ yAxis: 1 }],
      };
    }
    return { ...opt, legend: { show: false }, series: [s] };
  };
}

function multiLineChart({ highlight = null, endLabels = [], washFirst = false } = {}) {
  return (card, r, p) => {
    const opt = baseOption({ unit: r.metric.unit, grain: r.grain });
    const names = Object.keys(r.data.series);
    const series = names.map((name, i) => {
      const isHi = !highlight || highlight.includes(name);
      const color = highlight
        ? (highlight.includes(name) ? p.series[highlight.indexOf(name) === 0 ? 0 : 4] : p.muted)
        : slotFor(name, p);
      return lineSeries({
        name,
        data: r.data.series[name],
        color,
        width: isHi ? 2 : 1.5,
        endLabel: endLabels.includes(name) || (!highlight && endLabels === "all"),
        areaWash: washFirst && i === 0,
        unit: r.metric.unit,
      });
    });
    return { ...opt, legend: legendFor(names), grid: { ...opt.grid, bottom: legendPad(names) }, series };
  };
}

/* Keep only the top-N series by their latest value (fold the tail away). */
function topN(n) {
  return (result) => {
    const entries = Object.entries(result.data.series);
    const latest = (pts) => { for (let i = pts.length - 1; i >= 0; i--) if (pts[i][1] != null) return pts[i][1]; return -1; };
    entries.sort((a, b) => latest(b[1]) - latest(a[1]));
    result.data.series = Object.fromEntries(entries.slice(0, n));
    return result;
  };
}

/* Rebase each series to 100 at its first visible point. */
function indexed(selected) {
  return (result) => {
    const out = {};
    for (const [name, pts] of Object.entries(result.data.series)) {
      if (selected && !selected.includes(name)) continue;
      const base = pts.find((d) => d[1] != null)?.[1];
      if (!base) continue;
      out[name] = pts.map(([t, v]) => [t, v == null ? null : (v / base) * 100]);
    }
    result.data.series = out;
    result.metric = { ...result.metric, unit: "index", title: result.metric.title + " (indexed)" };
    return result;
  };
}

const CHARTS = [
  {
    className: "col-12",
    title: "From surplus to scarcity: labour-market tension",
    subtitle: "Unfilled vacancies per unemployed person, quarterly. Above 1.00 there are more vacancies than unemployed — the market inverted in 2021.",
    metricId: "tension_ratio",
    tall: true,
    build: singleLineChart({ areaWash: true, markParity: true }),
  },
  {
    className: "col-6",
    title: "Unemployment near two-decade lows",
    subtitle: "Unemployment rate, 15–74, seasonally adjusted, monthly.",
    metricId: "unemployment_rate",
    build: singleLineChart(),
  },
  {
    className: "col-6",
    title: "Open vacancies",
    subtitle: "Unfilled vacancies at end of quarter, all economic activities.",
    metricId: "vacancies_unfilled",
    build: singleLineChart(),
  },
  {
    className: "col-6",
    title: "The shape of work is shifting",
    subtitle: "Share of the employed labour force by employment position, quarterly.",
    metricId: "permanent_share",
    combine: ["permanent_share", "flexible_share", "self_employed_share"],
    build: multiLineChart({ endLabels: "all" }),
  },
  {
    className: "col-6",
    title: "Everyone works — and longer",
    subtitle: "Net labour participation by age band, yearly. Older workers highlighted; other bands in gray.",
    metricId: "participation_by_age",
    dimension: "age_group",
    build: multiLineChart({ highlight: ["55 to 64 years", "65 to 74 years"], endLabels: ["55 to 64 years", "65 to 74 years"] }),
  },
  {
    className: "col-6",
    title: "Where employers search hardest",
    subtitle: "Unfilled vacancies by sector — top 5 sectors by current demand, quarterly.",
    metricId: "vacancies_by_sector",
    dimension: "sector",
    transform: topN(5),
    build: multiLineChart({}),
  },
  {
    className: "col-6",
    title: "Where the jobs went",
    subtitle: "Employed persons by sector, indexed to 100 at the start of the selected range.",
    metricId: "employment_by_sector",
    dimension: "sector",
    transform: indexed([
      "Q Health and social work activities",
      "J Information and communication",
      "M-N Business services",
      "C Manufacturing",
      "A Agriculture, forestry and fishing",
    ]),
    build: multiLineChart({}),
  },
];

export async function renderDashboard(root) {
  root.innerHTML = `
    <div class="page-head">
      <p class="eyebrow">Flagship data product · labour-market-nl</p>
      <h1>How the Dutch job market is changing</h1>
      <p class="lede">Live analysis on four contracted CBS StatLine sources. Every number below is
        served by the semantic layer, quality-checked against its contract, and logged to the
        evidence chain — open <em>“Why trust this?”</em> on any chart.</p>
    </div>

    <section aria-label="Prepared analysis">
      <div class="section-head" style="margin-top:0;">
        <h2>Prepared analysis</h2>
        <span class="section-sub">the platform already prepared your briefing — computed from the data, traceable to it</span>
      </div>
      <div class="insights" id="insights"><div class="spin" role="status" aria-label="Loading"></div></div>
    </section>

    <div class="section-head"><h2>The numbers</h2><span class="section-sub" id="tiles-sub"></span></div>
    <div class="filter-row" role="group" aria-label="Time range">
      <span class="filter-label">Range</span>
      <div class="seg" id="range-seg">
        ${RANGES.map((r, i) => `<button type="button" data-range="${r.key}" aria-pressed="${i === 0}">${esc(r.label)}</button>`).join("")}
      </div>
    </div>
    <div class="grid" id="tiles"></div>
    <div class="grid" id="charts" style="margin-top:18px;"></div>`;

  // Insights
  api.insights().then(({ insights }) => {
    const box = root.querySelector("#insights");
    if (!insights.length) { box.innerHTML = '<p class="muted">Run <code class="inline">carina run</code> to build the marts.</p>'; return; }
    box.innerHTML = insights.map((i, n) => `
      <article class="insight">
        <div class="insight-ico" aria-hidden="true">${n + 1}</div>
        <div><h3>${esc(i.headline)}</h3><p>${esc(i.detail)}</p></div>
      </article>`).join("");
  });

  // Tiles (always full-range: headline state of the market)
  renderTiles(root.querySelector("#tiles"), root.querySelector("#tiles-sub"));

  // Charts + range filter scoping all of them
  const chartsEl = root.querySelector("#charts");
  const cards = CHARTS.map((cfg) => new ChartCard({ ...cfg, productId: PRODUCT, ...(cfg.combine ? { transform: combineMetrics(cfg.combine) } : {}) }));
  let current = RANGES[0];
  for (const c of cards) await c.mount(wrap(chartsEl, c), sinceFor(current));

  root.querySelector("#range-seg").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-range]");
    if (!btn) return;
    current = RANGES.find((r) => r.key === btn.dataset.range);
    root.querySelectorAll("#range-seg button").forEach((b) => b.setAttribute("aria-pressed", b === btn ? "true" : "false"));
    cards.forEach((c) => c.load(sinceFor(current)));
  });
}

function wrap(container, card) {
  const div = document.createElement("div");
  div.className = card.cfg.className || "col-6";
  container.appendChild(div);
  return div;
}

/* Fetch sibling metrics of the same model and merge into one multi-series result. */
function combineMetrics(ids) {
  return async function transform(result) {
    const others = await Promise.all(ids.slice(1).map((id) => api.query(id, {
      since: null, // siblings share the base query's range via points slicing below
    })));
    // Reuse the base result's window: slice siblings to the base's min date.
    const minT = result.data.points[0]?.[0];
    const series = { [result.metric.title]: result.data.points };
    for (const o of others) {
      series[o.metric.title] = minT ? o.data.points.filter((p) => p[0] >= minT) : o.data.points;
    }
    result.data = { kind: "multi", series };
    return result;
  };
}

async function renderTiles(container, subEl) {
  const [unemp, vac, tension, part] = await Promise.all([
    api.query("unemployment_rate"), api.query("vacancies_unfilled"),
    api.query("tension_ratio"), api.query("net_participation"),
  ]);
  const last = (r) => { const pts = r.data.points.filter((p) => p[1] != null); return pts[pts.length - 1]; };
  const at = (r, back) => { const pts = r.data.points.filter((p) => p[1] != null); return pts[Math.max(0, pts.length - 1 - back)]; };
  const spark = (r, n = 12) => r.data.points.filter((p) => p[1] != null).slice(-n);

  const [uT, uV] = last(unemp); const uPrev = at(unemp, 12)[1];
  const [vT, vV] = last(vac); const vPrev = at(vac, 4)[1];
  const [tT, tV] = last(tension); const tPrev = at(tension, 4)[1];
  const [pT, pV] = last(part); const pPrev = at(part, 12)[1];

  subEl.textContent = `latest: ${fmt.monthYear(uT)} (monthly) · ${fmt.quarter(vT)} (quarterly)`;

  const tiles = [
    statTile({
      label: "Unemployment rate", value: fmt.pct(uV),
      delta: uV - uPrev, deltaLabel: `${Math.abs(uV - uPrev).toFixed(1)}pp y/y`, good: uV - uPrev <= 0,
      period: `15–74, seasonally adjusted · ${fmt.monthYear(uT)}`, spark: spark(unemp, 24),
    }),
    statTile({
      label: "Unfilled vacancies", value: fmt.thousands(vV),
      delta: vV - vPrev, deltaLabel: `${fmt.thousands(Math.abs(vV - vPrev))} y/y`, good: null,
      period: `all activities · ${fmt.quarter(vT)}`, spark: spark(vac, 20),
    }),
    statTile({
      label: "Vacancies per unemployed", value: fmt.ratio(tV),
      delta: tV - tPrev, deltaLabel: `${Math.abs(tV - tPrev).toFixed(2)} y/y`, good: null,
      period: `tension ratio · ${fmt.quarter(tT)}`, spark: spark(tension, 20),
    }),
    statTile({
      label: "Net labour participation", value: fmt.pct(pV),
      delta: pV - pPrev, deltaLabel: `${Math.abs(pV - pPrev).toFixed(1)}pp y/y`, good: pV - pPrev >= 0,
      period: `15–74 in work · ${fmt.monthYear(pT)}`, spark: spark(part, 24),
    }),
  ];
  container.replaceChildren(...tiles.map((t) => { const d = document.createElement("div"); d.className = "col-3"; d.appendChild(t); return d; }));
}
