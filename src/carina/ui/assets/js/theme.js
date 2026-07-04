/* Theme tokens + ECharts base options implementing the dataviz specs:
   2px lines, hairline solid grid, surface-ringed markers, crosshair tooltip
   with line keys and value-first rows, legend for >= 2 series, text tokens
   (never series color) on all text. */

export const PALETTES = {
  light: {
    surface: "#fcfcfb", page: "#f9f9f7",
    ink: "#0b0b0b", ink2: "#52514e", ink3: "#898781",
    grid: "#e1e0d9", baseline: "#c3c2b7",
    series: ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"],
    deEmph: "#86b6ef", muted: "#b5b3ab",
  },
  dark: {
    surface: "#1a1a19", page: "#0d0d0d",
    ink: "#ffffff", ink2: "#c3c2b7", ink3: "#898781",
    grid: "#2c2c2a", baseline: "#383835",
    series: ["#3987e5", "#199e70", "#c98500", "#008300", "#9085e9", "#e66767", "#d55181", "#d95926"],
    deEmph: "#1c5cab", muted: "#5a5952",
  },
};

export function currentTheme() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function pal() {
  return PALETTES[currentTheme()];
}

const themeListeners = new Set();
export function onThemeChange(fn) { themeListeners.add(fn); }

export function initThemeToggle() {
  const btn = document.getElementById("theme-toggle");
  btn.addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("carina-theme", next);
    themeListeners.forEach((fn) => fn(next));
  });
}

export function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

export const fmt = {
  /** values stored in thousands -> people counts */
  thousands(v) {
    if (v == null) return "—";
    const n = v * 1000;
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2).replace(/\.?0+$/, "") + "M";
    if (Math.abs(n) >= 1e3) return Math.round(n / 1e3) + "K";
    return String(Math.round(n));
  },
  pct(v, d = 1) { return v == null ? "—" : v.toFixed(d) + "%"; },
  ratio(v) { return v == null ? "—" : v.toFixed(2); },
  plain(v) {
    if (v == null) return "—";
    return Number.isInteger(v) ? v.toLocaleString("en-US") : v.toLocaleString("en-US", { maximumFractionDigits: 1 });
  },
  monthYear(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
  },
  quarter(iso) {
    const d = new Date(iso);
    return `Q${Math.floor(d.getMonth() / 3) + 1} ${d.getFullYear()}`;
  },
  byGrain(iso, grain) {
    if (grain === "quarter") return fmt.quarter(iso);
    if (grain === "year") return String(new Date(iso).getFullYear());
    return fmt.monthYear(iso);
  },
};

export function valueFormatter(unit) {
  if (unit === "%") return (v) => fmt.pct(v);
  if (unit === "ratio") return (v) => fmt.ratio(v);
  if (unit === "×1,000") return (v) => fmt.thousands(v);
  if (unit === "index") return (v) => fmt.plain(v);
  return (v) => fmt.plain(v);
}

/** Axis label variant (more compact than tooltip values). */
export function axisFormatter(unit) {
  if (unit === "%") return (v) => v + "%";
  if (unit === "ratio") return (v) => v.toFixed(2).replace(/\.?0+$/, "") || "0";
  if (unit === "×1,000") return (v) => fmt.thousands(v);
  return (v) => v.toLocaleString("en-US");
}

/** Shared ECharts scaffolding per the mark/anatomy/interaction specs. */
export function baseOption({ unit, grain }) {
  const p = pal();
  return {
    animationDuration: 350,
    grid: { left: 10, right: 74, top: 18, bottom: 6, containLabel: true },
    textStyle: { fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif' },
    xAxis: {
      type: "time",
      axisLine: { lineStyle: { color: p.baseline, width: 1 } },
      axisTick: { show: false },
      axisLabel: { color: p.ink3, fontSize: 11.5, hideOverlap: true },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: p.ink3, fontSize: 11.5, formatter: axisFormatter(unit) },
      splitLine: { lineStyle: { color: p.grid, width: 1, type: "solid" } },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: p.baseline, width: 1 } },
      backgroundColor: p.surface,
      borderColor: p.grid,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: p.ink, fontSize: 12.5 },
      extraCssText: "box-shadow: 0 6px 24px rgba(0,0,0,.12); border-radius: 8px;",
      formatter: (params) => {
        const list = Array.isArray(params) ? params : [params];
        if (!list.length) return "";
        const vf = valueFormatter(unit);
        const when = fmt.byGrain(list[0].value[0], grain);
        const rows = list
          .filter((it) => it.value[1] != null)
          .map((it) =>
            `<div style="display:flex;align-items:center;gap:8px;margin-top:3px;">
               <span style="display:inline-block;width:12px;height:0;border-top:3px solid ${it.color};border-radius:2px;"></span>
               <strong style="font-weight:650;">${esc(vf(it.value[1]))}</strong>
               <span style="color:${pal().ink2};">${esc(it.seriesName)}</span>
             </div>`)
          .join("");
        return `<div style="color:${p.ink3};font-size:11.5px;">${esc(when)}</div>${rows}`;
      },
    },
  };
}

/** Line series per spec: 2px, round joins, hover markers with surface ring. */
export function lineSeries({ name, data, color, areaWash = false, endLabel = false, width = 2, unit }) {
  const p = pal();
  return {
    name,
    type: "line",
    data,
    color,
    showSymbol: false,
    symbol: "circle",
    symbolSize: 8,
    itemStyle: { color, borderColor: p.surface, borderWidth: 2 },
    lineStyle: { width, join: "round", cap: "round", color },
    emphasis: { focus: "none", lineStyle: { width } },
    areaStyle: areaWash ? { color, opacity: 0.1 } : undefined,
    endLabel: endLabel
      ? {
          show: true,
          formatter: (s) => (s.value[1] == null ? "" : valueFormatter(unit)(s.value[1])),
          color: p.ink2,
          fontSize: 11.5,
          fontWeight: 600,
          distance: 8,
        }
      : undefined,
    labelLayout: endLabel ? { moveOverlap: "shiftY" } : undefined,
  };
}

const LEGEND_MAX_CHARS = 26;

/** Estimated legend rows for a typical card width — drives grid bottom padding. */
export function legendPad(seriesNames, plotWidth = 540) {
  if (seriesNames.length < 2) return 8;
  const itemW = (n) => 14 + 6 + Math.min(n.length, LEGEND_MAX_CHARS) * 6.4 + 16;
  let rows = 1, x = 0;
  for (const n of seriesNames) {
    const w = itemW(n);
    if (x + w > plotWidth) { rows++; x = w; } else { x += w; }
  }
  return 18 + rows * 21;
}

export function legendFor(seriesNames, selected) {
  const p = pal();
  if (seriesNames.length < 2) return { show: false };
  return {
    show: true,
    bottom: 0,
    left: 8,
    icon: "rect",
    itemWidth: 14,
    itemHeight: 3,
    itemGap: 16,
    formatter: (name) => (name.length > LEGEND_MAX_CHARS ? name.slice(0, LEGEND_MAX_CHARS - 1) + "…" : name),
    textStyle: { color: p.ink2, fontSize: 12 },
    selected,
  };
}
