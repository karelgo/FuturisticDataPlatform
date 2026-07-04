#!/usr/bin/env python3
"""Export the CARINA laptop-profile app as a single self-contained HTML file.

The live app is FastAPI + DuckDB. This bakes every API response the UI needs
into an embedded ``CARINA_DATA`` object, swaps the network API client for one
that reads it (applying time-range filtering client-side), bundles the *real*
app JS with esbuild, and inlines CSS + ECharts — producing one static page
that works with no backend. The evidence chain keeps its integrity: raw hash
fields are baked so the page re-hashes the chain in the browser (SubtleCrypto).

Usage:  python scripts/build_static.py [output.html]
Requires: a built lakehouse (run `carina run` first) and Node/esbuild.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from carina import api as capi  # noqa: E402
from carina import config  # noqa: E402

UI = config.UI_DIR
ESBUILD = ROOT.parent  # not used; esbuild resolved below

# The exact (metric, dimension) pairs the UI requests. Dimensioned metrics are
# only ever queried WITH their dimension, so we bake precisely these.
PAIRS = [
    ("unemployment_rate", None),
    ("vacancies_unfilled", None),
    ("tension_ratio", None),
    ("net_participation", None),
    ("permanent_share", None),
    ("flexible_share", None),
    ("self_employed_share", None),
    ("participation_by_age", "age_group"),
    ("vacancies_by_sector", "sector"),
    ("employment_by_sector", "sector"),
]

PRODUCT_ID = "labour-market-nl"


def find_esbuild() -> str:
    for cand in [
        ROOT.parent / "scratchpad" / "echarts-vendor" / "node_modules" / ".bin" / "esbuild",
        Path("/tmp/claude-0/-home-user-FuturisticDataPlatform/5b6dbab7-bbdc-584d-8fa2-58fbead25a6f/scratchpad/echarts-vendor/node_modules/.bin/esbuild"),
    ]:
        if cand.exists():
            return str(cand)
    if shutil.which("esbuild"):
        return "esbuild"
    return "npx esbuild"


def capture_data() -> dict:
    """Capture every response the UI needs. Reads through the API's own
    connection so the evidence chain includes these very queries."""
    con = capi.con()

    overview = capi.overview()
    product = capi.product_detail(PRODUCT_ID)
    lineage = capi.lineage(PRODUCT_ID)
    metrics = capi.metric_catalog()

    queries = {}
    for mid, dim in PAIRS:
        res = capi.metric_query(mid, dim, None)
        queries[f"{mid}|{dim or ''}"] = res

    insights = capi.prepared_insights()

    # Raw evidence straight from DuckDB (exact stored fields) so the browser
    # can re-hash the chain. Captured last, so it reflects all baked queries.
    rows = con.execute(
        "SELECT seq, ts, actor, action, subject, payload, payload_hash, prev_hash, chain_hash "
        "FROM evidence ORDER BY seq"
    ).fetchall()
    evidence = []
    for seq, ts, actor, action, subject, payload, payload_hash, prev_hash, chain_hash in rows:
        ts_iso = ts.replace(tzinfo=timezone.utc).isoformat() if ts.tzinfo is None else ts.isoformat()
        evidence.append({
            "seq": seq, "ts": str(ts), "ts_iso": ts_iso, "actor": actor,
            "action": action, "subject": subject, "payload_str": payload,
            "payload_hash": payload_hash, "prev_hash": prev_hash, "chain_hash": chain_hash,
        })

    return {
        "overview": overview,
        "products": {PRODUCT_ID: product},
        "lineage": {PRODUCT_ID: lineage},
        "metrics": metrics,
        "queries": queries,
        "insights": insights,
        "evidence": evidence,
    }


STATIC_API_JS = r"""
/* Static API client: reads the baked window.CARINA_DATA instead of the network.
   Same interface as the live client; time-range 'since' is applied here. */
const D = window.CARINA_DATA;
const clone = (x) => (typeof structuredClone === "function" ? structuredClone(x) : JSON.parse(JSON.stringify(x)));

function applySince(result, since) {
  const r = clone(result);
  if (!since) return r;
  if (r.data.kind === "single") {
    r.data.points = r.data.points.filter((p) => p[0] >= since);
  } else {
    for (const k of Object.keys(r.data.series)) {
      r.data.series[k] = r.data.series[k].filter((p) => p[0] >= since);
    }
  }
  return r;
}

async function sha256Hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

const GENESIS = "0".repeat(64);

export const api = {
  async overview() { return clone(D.overview); },
  async product(id) { return clone(D.products[id]); },
  async lineage(id) { return clone(D.lineage[id]); },
  async metrics() { return clone(D.metrics); },
  async insights() { return clone(D.insights); },

  async evidence(params = {}) {
    let recs = D.evidence.slice();
    if (params.action) recs = recs.filter((r) => r.action.startsWith(params.action));
    recs.sort((a, b) => b.seq - a.seq);
    const total = recs.length;
    const offset = params.offset || 0;
    const limit = params.limit || 50;
    const page = recs.slice(offset, offset + limit).map((r) => ({
      seq: r.seq, ts: r.ts, actor: r.actor, action: r.action, subject: r.subject,
      payload: JSON.parse(r.payload_str), payload_hash: r.payload_hash,
      prev_hash: r.prev_hash, chain_hash: r.chain_hash,
    }));
    return { total, records: page };
  },

  /* Genuinely re-hash the chain in the browser — compliance as a query. */
  async evidenceVerify() {
    const recs = D.evidence.slice().sort((a, b) => a.seq - b.seq);
    let prev = GENESIS;
    for (const r of recs) {
      if (r.prev_hash !== prev)
        return { ok: false, broken_at: r.seq, reason: "prev_hash mismatch", records: recs.length };
      if ((await sha256Hex(r.payload_str)) !== r.payload_hash)
        return { ok: false, broken_at: r.seq, reason: "payload tampered", records: recs.length };
      const expect = await sha256Hex(
        `${r.seq}|${r.ts_iso}|${r.actor}|${r.action}|${r.subject}|${r.payload_hash}|${r.prev_hash}`
      );
      if (expect !== r.chain_hash)
        return { ok: false, broken_at: r.seq, reason: "chain_hash mismatch", records: recs.length };
      prev = r.chain_hash;
    }
    return { ok: true, records: recs.length, head: recs.length ? prev : null };
  },

  async query(metricId, { dimension, since } = {}) {
    const key = `${metricId}|${dimension || ""}`;
    const base = D.queries[key];
    if (!base) throw new Error(`No baked data for ${key}`);
    return applySince(base, since);
  },

  async productCached(id) { return clone(D.products[id]); },
};
"""


def bundle_js(build_dir: Path) -> str:
    esbuild = find_esbuild()
    entry = build_dir / "app.js"
    out = build_dir / "bundle.js"
    cmd = esbuild.split() + [str(entry), "--bundle", "--format=iife", f"--outfile={out}", "--log-level=warning"]
    subprocess.run(cmd, check=True)
    return out.read_text()


def body_markup() -> str:
    html = (UI / "index.html").read_text()
    start = html.index("<body>") + len("<body>")
    end = html.index('<script src="/assets/vendor/echarts.min.js">')
    return html[start:end].strip()


THEME_INIT = """
(function () {
  try {
    var saved = localStorage.getItem('carina-theme');
    var preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    document.documentElement.dataset.theme = saved || preferred;
  } catch (e) { document.documentElement.dataset.theme = 'light'; }
})();
"""


def build(out_path: Path) -> None:
    print("→ capturing API data …")
    data = capture_data()
    print(f"   overview + product + lineage + {len(data['queries'])} queries + "
          f"{len(data['insights']['insights'])} insights + {len(data['evidence'])} evidence records")

    print("→ bundling app JS with esbuild …")
    with tempfile.TemporaryDirectory() as tmp:
        bd = Path(tmp)
        shutil.copytree(UI / "assets" / "js", bd, dirs_exist_ok=True)
        (bd / "api.js").write_text(STATIC_API_JS)
        bundle = bundle_js(bd)

    css = (UI / "assets" / "css" / "app.css").read_text()
    echarts = (UI / "assets" / "vendor" / "echarts.min.js").read_text()
    markup = body_markup()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    parts = [
        f"<style>\n{css}\n</style>",
        f"<script>{THEME_INIT}</script>",
        markup,
        f'<script id="carina-data" type="application/json">{payload}</script>',
        "<script>window.CARINA_DATA = JSON.parse(document.getElementById('carina-data').textContent);</script>",
        f"<script>{echarts}</script>",
        f"<script>{bundle}</script>",
    ]
    out_path.write_text("\n".join(parts))
    size = out_path.stat().st_size
    print(f"→ wrote {out_path}  ({size / 1024:.0f} KB)")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    build(out)
