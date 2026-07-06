/* API client — all data access goes through the semantic layer endpoints. */

const cache = new Map();

async function getJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText} — ${url}`);
  return resp.json();
}

export const api = {
  overview: () => getJSON("/api/overview"),
  product: (id) => getJSON(`/api/product/${encodeURIComponent(id)}`),
  lineage: (id) => getJSON(`/api/lineage/${encodeURIComponent(id)}`),
  metrics: () => getJSON("/api/metrics"),
  insights: () => getJSON("/api/insights"),
  evidence: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return getJSON(`/api/evidence${q ? "?" + q : ""}`);
  },
  evidenceVerify: () => getJSON("/api/evidence/verify"),
  query: (metricId, { dimension, since } = {}) => {
    const q = new URLSearchParams();
    if (dimension) q.set("dimension", dimension);
    if (since) q.set("since", since);
    const url = `/api/metrics/${encodeURIComponent(metricId)}/query${q.toString() ? "?" + q : ""}`;
    return getJSON(url);
  },
  opsComponents: () => getJSON("/api/ops/components"),
  opsLogs: (component) =>
    getJSON(`/api/ops/logs${component ? "?component=" + encodeURIComponent(component) : ""}`),
  opsTraces: () => getJSON("/api/ops/traces"),
  opsQuery: async (sql) => {
    const resp = await fetch("/api/ops/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql }),
    });
    const body = await resp.json();
    if (!resp.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail));
    return body;
  },
  /** cached product detail (used by trust drawer + chart footers) */
  async productCached(id) {
    if (!cache.has(id)) cache.set(id, await api.product(id));
    return cache.get(id);
  },
};
