/* App shell: hash router, nav state, theme toggle, evidence pill. */

import { api } from "./api.js";
import { initThemeToggle } from "./theme.js";
import { initTrust, closeTrust } from "./trust.js";
import { renderPortal } from "./pages/portal.js";
import { renderProduct } from "./pages/product.js";
import { renderDashboard } from "./pages/dashboard.js";
import { renderEvidence } from "./pages/evidence.js";

const main = document.getElementById("main");

const routes = [
  { pattern: /^#?\/?$/, nav: "portal", render: (root) => renderPortal(root) },
  { pattern: /^#\/product\/([\w-]+)$/, nav: "product", render: (root, m) => renderProduct(root, m[1]) },
  { pattern: /^#\/dashboard$/, nav: "dashboard", render: (root) => renderDashboard(root) },
  { pattern: /^#\/evidence$/, nav: "evidence", render: (root) => renderEvidence(root) },
];

async function route() {
  closeTrust();
  const hash = location.hash || "#/";
  const r = routes.find((x) => x.pattern.test(hash)) || routes[0];
  document.querySelectorAll(".topnav a").forEach((a) => a.classList.toggle("active", a.dataset.nav === r.nav));
  main.innerHTML = '<div class="spin" role="status" aria-label="Loading"></div>';
  try {
    await r.render(main, hash.match(r.pattern));
    window.scrollTo({ top: 0 });
  } catch (err) {
    main.innerHTML = `<div class="error-box"><strong>Something went wrong.</strong><br/>${err.message}
      <br/><span class="muted">Is the pipeline built? Run <code class="inline">carina run</code> then reload.</span></div>`;
  }
}

async function evidencePill() {
  try {
    const v = await api.evidenceVerify();
    const pill = document.getElementById("evidence-pill");
    document.getElementById("evidence-pill-text").textContent =
      v.ok ? `evidence ✓ ${v.records}` : "evidence BROKEN";
    pill.classList.toggle("broken", !v.ok);
    pill.title = v.head ? `chain head ${v.head}` : "no evidence yet";
  } catch { /* pill is decorative; the Evidence page is authoritative */ }
}

initThemeToggle();
initTrust();
window.addEventListener("hashchange", route);
route();
evidencePill();
