/* ================================================================
   Invoice Agent — JavaScript Application
   ================================================================ */

const API = "/api";

// ── Couleurs par catégorie ──────────────────────────────────────
const CAT_COLORS = {
  "Electricité": "#f59e0b", "Eau": "#3b82f6", "Internet": "#8b5cf6",
  "Téléphone": "#ec4899",   "Loyer": "#ef4444", "Assurance": "#14b8a6",
  "Abonnement": "#f97316",  "Courses": "#22c55e", "Santé": "#06b6d4",
  "Transport": "#a78bfa",   "Autre": "#94a3b8",
};

// ── État global ─────────────────────────────────────────────────
const state = {
  currentPage: "dashboard",
  currentMonth: todayMonth(),
  urgentCount: 0,
};

// ================================================================
// Utilitaires
// ================================================================

function todayMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function formatMonth(ym) {
  const [y, m] = ym.split("-");
  const names = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"];
  return `${names[parseInt(m) - 1]} ${y}`;
}

function prevMonth(ym) {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 2, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function nextMonth(ym) {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function fmtAmount(amount, currency = "EUR") {
  return `${parseFloat(amount || 0).toFixed(2)} ${currency}`;
}

function fmtDate(d) {
  if (!d) return "—";
  const [y, m, day] = d.split("-");
  return `${day}/${m}/${y}`;
}

function statusBadge(s) {
  const map = { pending: "En attente", paid: "Payée", overdue: "En retard", reminded: "Rappelée" };
  return `<span class="badge badge-${s}">${map[s] || s}</span>`;
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Erreur API");
  }
  return res.json();
}

function showAlert(container, type, msg) {
  const icons = { info: "ℹ️", success: "✅", warning: "⚠️", danger: "❌" };
  container.innerHTML = `<div class="alert alert-${type}">${icons[type]} ${msg}</div>`;
}

function loading(container, msg = "Chargement…") {
  container.innerHTML = `<div class="loading-overlay"><div class="spinner"></div> ${msg}</div>`;
}

// ================================================================
// Navigation
// ================================================================

function navigate(page) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));

  const pageEl = document.getElementById(`page-${page}`);
  const navEl  = document.querySelector(`.nav-item[data-page="${page}"]`);
  if (pageEl) pageEl.classList.add("active");
  if (navEl)  navEl.classList.add("active");

  state.currentPage = page;
  document.querySelector(".topbar-title").textContent = navEl?.querySelector(".nav-label")?.textContent || "";

  const loaders = {
    dashboard: loadDashboard,
    invoices:  loadInvoices,
    reminders: loadReminders,
    scan:      initScan,
  };
  loaders[page]?.();
}

// ================================================================
// STATS HEADER
// ================================================================

async function loadStats() {
  try {
    const s = await apiFetch("/stats");
    document.getElementById("stat-total").textContent   = s.total_invoices;
    document.getElementById("stat-pending").textContent = s.pending;
    document.getElementById("stat-overdue").textContent = s.overdue;
    document.getElementById("stat-unpaid").textContent  = fmtAmount(s.total_unpaid);

    state.urgentCount = s.urgent_count;
    const badge = document.getElementById("nav-badge-reminders");
    if (s.urgent_count > 0) {
      badge.textContent = s.urgent_count;
      badge.style.display = "inline-block";
    } else {
      badge.style.display = "none";
    }
  } catch (e) {
    console.warn("Stats error:", e);
  }
}

// ================================================================
// PAGE — DASHBOARD
// ================================================================

async function loadDashboard() {
  const container = document.getElementById("dashboard-content");
  loading(container, "Chargement du tableau de bord…");

  try {
    const data = await apiFetch(`/dashboard?month=${state.currentMonth}`);
    document.getElementById("month-label").textContent = formatMonth(state.currentMonth);

    const s = data.summary || {};
    document.getElementById("dash-total").textContent  = fmtAmount(s.total_amount);
    document.getElementById("dash-count").textContent  = s.invoice_count || 0;
    document.getElementById("dash-pending").textContent = s.pending || 0;
    document.getElementById("dash-paid").textContent   = s.paid || 0;

    // Graphique barres horizontales
    renderBarChart(data.by_category || [], s.total_amount || 0);

    // Top 3
    renderTop3(data.top_3_expenses || []);

    container.style.display = "";

  } catch (e) {
    container.innerHTML = `<div class="alert alert-danger">❌ ${e.message}</div>`;
  }
}

function renderBarChart(categories, total) {
  const el = document.getElementById("bar-chart");
  if (!categories.length) { el.innerHTML = `<p class="text-muted text-sm">Aucune donnée pour ce mois.</p>`; return; }

  el.innerHTML = categories.map(c => {
    const pct = total > 0 ? (c.total / total * 100) : 0;
    const color = CAT_COLORS[c.category] || "#94a3b8";
    return `
      <div class="chart-bar-row">
        <div class="chart-bar-label" title="${c.category}">${c.category}</div>
        <div class="chart-bar-track">
          <div class="chart-bar-fill" style="width:${pct}%;background:${color}"></div>
        </div>
        <div class="chart-bar-val">${fmtAmount(c.total)}</div>
      </div>`;
  }).join("");
}

function renderTop3(top3) {
  const el = document.getElementById("top3-list");
  if (!top3.length) { el.innerHTML = `<p class="text-muted text-sm">Aucune donnée.</p>`; return; }
  el.innerHTML = top3.map((t, i) => `
    <div class="result-row">
      <span class="result-key">${["🥇","🥈","🥉"][i]} ${t.supplier}</span>
      <span class="result-val">${fmtAmount(t.amount)}</span>
    </div>`).join("");
}

// Donut SVG pour répartition
function renderDonut(categories, total) {
  const el = document.getElementById("donut-chart");
  if (!el || !categories.length) return;

  const size = 140, cx = 70, cy = 70, r = 52, stroke = 18;
  const circ = 2 * Math.PI * r;
  let offset = 0;

  const slices = categories.slice(0, 8).map(c => {
    const pct = total > 0 ? c.total / total : 0;
    const len = pct * circ;
    const color = CAT_COLORS[c.category] || "#94a3b8";
    const slice = { ...c, pct, len, offset, color };
    offset += len;
    return slice;
  });

  const svgSlices = slices.map(s => `
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none"
      stroke="${s.color}" stroke-width="${stroke}"
      stroke-dasharray="${s.len} ${circ - s.len}"
      stroke-dashoffset="${-(s.offset - circ * 0.25)}"
      transform="rotate(-90 ${cx} ${cy})"/>
  `).join("");

  const legendHTML = slices.map(s => `
    <div class="legend-item">
      <div class="legend-dot" style="background:${s.color}"></div>
      <span>${s.category} — ${s.percentage}%</span>
    </div>`).join("");

  el.innerHTML = `
    <div class="donut-wrap">
      <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${getComputedStyle(document.documentElement).getPropertyValue('--border')}" stroke-width="${stroke}"/>
        ${svgSlices}
        <text x="${cx}" y="${cy+5}" text-anchor="middle" font-size="12" font-weight="700" fill="${getComputedStyle(document.documentElement).getPropertyValue('--text')}">${fmtAmount(total, '')}</text>
        <text x="${cx}" y="${cy+18}" text-anchor="middle" font-size="9" fill="${getComputedStyle(document.documentElement).getPropertyValue('--muted')}">EUR</text>
      </svg>
      <div class="donut-legend">${legendHTML}</div>
    </div>`;
}

// ================================================================
// PAGE — INVOICES
// ================================================================

let invoicesFilter = "all";

async function loadInvoices() {
  const container = document.getElementById("invoices-content");
  loading(container, "Chargement des factures…");

  try {
    const data = await apiFetch(`/invoices?status=${invoicesFilter}`);
    renderInvoicesTable(data.invoices || [], container);
  } catch (e) {
    container.innerHTML = `<div class="alert alert-danger">❌ ${e.message}</div>`;
  }
}

function renderInvoicesTable(invoices, container) {
  if (!invoices.length) {
    container.innerHTML = `<div class="alert alert-info">ℹ️ Aucune facture trouvée.</div>`;
    return;
  }

  container.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Fournisseur</th>
            <th>Montant</th>
            <th>Catégorie</th>
            <th>Échéance</th>
            <th>Statut</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${invoices.map(inv => `
            <tr>
              <td>
                <div style="font-weight:600">${inv.supplier}</div>
                ${inv.invoice_number ? `<div class="text-muted text-sm">Réf: ${inv.invoice_number}</div>` : ""}
              </td>
              <td style="font-weight:600">${fmtAmount(inv.amount, inv.currency)}</td>
              <td><span style="display:inline-flex;align-items:center;gap:5px">
                <span style="width:8px;height:8px;border-radius:50%;background:${CAT_COLORS[inv.category]||'#94a3b8'};display:inline-block"></span>
                ${inv.category}
              </span></td>
              <td>${fmtDate(inv.due_date)}</td>
              <td>${statusBadge(inv.status)}</td>
              <td>
                <div class="flex gap-3">
                  ${inv.status !== "paid" ? `<button class="btn btn-sm btn-success" onclick="markPaid('${inv.invoice_id}')">✓ Payée</button>` : ""}
                  <button class="btn btn-sm" onclick="sendReminderFromList('${inv.invoice_id}')">🔔</button>
                </div>
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
}

async function markPaid(id) {
  try {
    await apiFetch(`/invoices/${id}/status?status=paid`, { method: "PATCH" });
    loadInvoices();
    loadStats();
  } catch (e) {
    alert("Erreur : " + e.message);
  }
}

async function sendReminderFromList(id) {
  try {
    await apiFetch(`/reminders/${id}/send`, { method: "POST" });
    alert("✅ Rappel envoyé !");
    loadInvoices();
  } catch (e) {
    alert("Erreur : " + e.message);
  }
}

// ================================================================
// PAGE — REMINDERS
// ================================================================

async function loadReminders() {
  const container = document.getElementById("reminders-content");
  loading(container, "Vérification des échéances…");

  try {
    const data = await apiFetch("/reminders");
    const invoices = data.invoices || [];

    if (!invoices.length) {
      container.innerHTML = `<div class="alert alert-success">✅ Aucune facture urgente. Tout est en ordre !</div>`;
      return;
    }

    container.innerHTML = `
      <div class="alert alert-warning" style="margin-bottom:20px">
        ⚠️ <strong>${data.total_urgent}</strong> facture(s) nécessitent votre attention
        (${data.overdue_count} en retard, ${data.upcoming_count} à venir).
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Priorité</th>
              <th>Fournisseur</th>
              <th>Montant</th>
              <th>Échéance</th>
              <th>Jours restants</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${invoices.map(inv => `
              <tr>
                <td><span class="priority-${inv.priority}" style="font-size:13px">${inv.priority}</span></td>
                <td style="font-weight:600">${inv.supplier}</td>
                <td>${fmtAmount(inv.amount, inv.currency)}</td>
                <td>${fmtDate(inv.due_date)}</td>
                <td style="font-weight:700;color:${inv.days_left < 0 ? 'var(--danger)' : inv.days_left <= 1 ? 'var(--warning)' : 'var(--accent)'}">
                  ${inv.days_left < 0 ? `${Math.abs(inv.days_left)}j de retard` : inv.days_left === 0 ? "Aujourd'hui" : `${inv.days_left}j`}
                </td>
                <td>
                  <button class="btn btn-sm btn-primary" onclick="sendReminderNow('${inv.invoice_id}', this)">
                    ${inv.reminder_sent ? "🔁 Renvoyer" : "📬 Envoyer rappel"}
                  </button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  } catch (e) {
    container.innerHTML = `<div class="alert alert-danger">❌ ${e.message}</div>`;
  }
}

async function sendReminderNow(id, btn) {
  btn.disabled = true;
  btn.textContent = "Envoi…";
  try {
    await apiFetch(`/reminders/${id}/send`, { method: "POST" });
    btn.textContent = "✅ Envoyé";
    btn.className = "btn btn-sm btn-success";
    loadStats();
  } catch (e) {
    btn.textContent = "❌ Erreur";
    btn.disabled = false;
  }
}

// ================================================================
// PAGE — SCAN
// ================================================================

function initScan() {
  const zone = document.getElementById("upload-zone");
  const input = document.getElementById("file-input");

  if (zone._initialized) return;
  zone._initialized = true;

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("drag-over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", e => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });
  input.addEventListener("change", () => {
    if (input.files[0]) uploadFile(input.files[0]);
  });
}

async function uploadFile(file) {
  const result = document.getElementById("scan-result");
  const zone   = document.getElementById("upload-zone");

  zone.innerHTML = `<div class="loading-overlay"><div class="spinner"></div> Analyse de "${file.name}"…</div>`;

  const fd = new FormData();
  fd.append("file", file);

  try {
    const data = await apiFetch("/scan", { method: "POST", body: fd });
    const ext = data.extracted;
    const sto = data.stored;

    result.innerHTML = `
      <div class="alert alert-success">✅ Facture analysée et enregistrée — ID : <strong>${sto.invoice_id}</strong></div>
      <div class="result-panel">
        <div class="result-row"><span class="result-key">Fournisseur</span><span class="result-val">${ext.supplier || "—"}</span></div>
        <div class="result-row"><span class="result-key">Montant</span><span class="result-val">${fmtAmount(ext.amount, ext.currency)}</span></div>
        <div class="result-row"><span class="result-key">Date d'émission</span><span class="result-val">${fmtDate(ext.issue_date)}</span></div>
        <div class="result-row"><span class="result-key">Date d'échéance</span><span class="result-val">${fmtDate(ext.due_date)}</span></div>
        <div class="result-row"><span class="result-key">Catégorie</span><span class="result-val">${ext.category || "—"}</span></div>
        ${ext.invoice_number ? `<div class="result-row"><span class="result-key">N° Facture</span><span class="result-val">${ext.invoice_number}</span></div>` : ""}
        <div class="result-row"><span class="result-key">Confiance IA</span><span class="result-val">${Math.round((ext.confidence || 1) * 100)}%</span></div>
      </div>
      <div class="flex mt-4" style="gap:10px">
        <button class="btn btn-primary" onclick="navigate('invoices')">📋 Voir les factures</button>
        <button class="btn" onclick="resetScan()">📎 Scanner une autre facture</button>
      </div>`;

    loadStats();
  } catch (e) {
    result.innerHTML = `<div class="alert alert-danger">❌ ${e.message}</div>`;
    resetScan();
  }
}

function resetScan() {
  document.getElementById("upload-zone").innerHTML = `
    <div class="upload-icon">📎</div>
    <p><strong>Glissez votre facture ici</strong> ou cliquez pour choisir un fichier</p>
    <p style="margin-top:6px">Formats acceptés : PDF, PNG, JPG, TXT</p>`;
  document.getElementById("upload-zone")._initialized = false;
  document.getElementById("scan-result").innerHTML = "";
  document.getElementById("file-input").value = "";
  initScan();
}

// ================================================================
// Init
// ================================================================

document.addEventListener("DOMContentLoaded", () => {
  // Navigation
  document.querySelectorAll(".nav-item[data-page]").forEach(btn => {
    btn.addEventListener("click", () => navigate(btn.dataset.page));
  });

  // Month navigation
  document.getElementById("btn-prev-month")?.addEventListener("click", () => {
    state.currentMonth = prevMonth(state.currentMonth);
    loadDashboard();
  });
  document.getElementById("btn-next-month")?.addEventListener("click", () => {
    state.currentMonth = nextMonth(state.currentMonth);
    loadDashboard();
  });

  // Filtre statut factures
  document.getElementById("invoice-filter")?.addEventListener("change", e => {
    invoicesFilter = e.target.value;
    loadInvoices();
  });

  // Rafraîchir les stats toutes les 60s
  loadStats();
  setInterval(loadStats, 60000);

  // Page par défaut
  navigate("dashboard");
});
