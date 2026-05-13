/* ============================================================
   Demo mock data + delade UI-funktioner
   ============================================================ */

const HOURS = Array.from({ length: 18 }, (_, i) => 6 + i);
const DAYS = { 1: "Måndag", 2: "Tisdag", 3: "Onsdag", 4: "Torsdag", 5: "Fredag", 6: "Lördag", 7: "Söndag" };

const AREAS = [
  { id: 1, code: "GG", name: "Granngården" },
  { id: 2, code: "MG", name: "Mestergruppen" },
  { id: 3, code: "AS", name: "Autostore" },
];

const ACTIVITIES = [
  { id: 11, code: "GG_PLOCK",   label: "GG Plock",      area_id: 1, color: "#dbeafe" },
  { id: 12, code: "GG_VM",      label: "GG VM",         area_id: 1, color: "#d1fae5" },
  { id: 13, code: "GG_HELPALL", label: "GG Helpall",    area_id: 1, color: "#ffedd5" },
  { id: 14, code: "GG_PAFY",    label: "GG Påfyllning", area_id: 1, color: "#ede9fe" },
  { id: 15, code: "GG_SKRYMME", label: "GG Skrymme",    area_id: 1, color: "#fef3c7" },
  { id: 16, code: "GG_LKON",    label: "GG Lkon",       area_id: 1, color: "#cffafe" },
  { id: 17, code: "GG_ARTPL",   label: "GG Art. Pl",    area_id: 1, color: "#fce7f3" },
  { id: 18, code: "GG_LOTS",    label: "GG Lotsvård",   area_id: 1, color: "#fed7aa" },
  { id: 21, code: "MG_PLOCK",   label: "MG Plock",      area_id: 2, color: "#fee2e2" },
  { id: 22, code: "MG_VM",      label: "MG VM",         area_id: 2, color: "#fef9c3" },
  { id: 23, code: "MG_SKJUT",   label: "MG Skjutare",   area_id: 2, color: "#fde2e4" },
  { id: 24, code: "MG_LOTS",    label: "MG Lots",       area_id: 2, color: "#ffe4e6" },
  { id: 31, code: "AS_PLOCK",   label: "AS Plock",      area_id: 3, color: "#e0e7ff" },
  { id: 32, code: "AS_DEK",     label: "AS Dek",        area_id: 3, color: "#ddd6fe" },
  { id: 33, code: "AS_STOD",    label: "AS Stöd",       area_id: 3, color: "#c7d2fe" },
  { id: 91, code: "LEDIG",      label: "Ledig",         area_id: null, color: "#e2e8f0" },
  { id: 92, code: "SJUK",       label: "Sjuk",          area_id: null, color: "#fecaca" },
  { id: 93, code: "VAB",        label: "VAB",           area_id: null, color: "#fde68a" },
];

const PERSONS = [
  { id: 1,  name: "Filip Malmqvist",  home_area_id: 1, home_activity_id: 11, is_active: true, sort_order: 1 },
  { id: 2,  name: "Oscar Pihl",       home_area_id: 1, home_activity_id: 11, is_active: true, sort_order: 2 },
  { id: 3,  name: "Henric",           home_area_id: 1, home_activity_id: 12, is_active: true, sort_order: 3 },
  { id: 4,  name: "Sebastian Färg",   home_area_id: 1, home_activity_id: 13, is_active: true, sort_order: 4 },
  { id: 5,  name: "Malin Kling",      home_area_id: 1, home_activity_id: 12, is_active: true, sort_order: 5 },
  { id: 6,  name: "Emanuel",          home_area_id: 1, home_activity_id: 11, is_active: true, sort_order: 6 },
  { id: 7,  name: "Fation",           home_area_id: 1, home_activity_id: 14, is_active: true, sort_order: 7 },
  { id: 8,  name: "Alex Vico",        home_area_id: 1, home_activity_id: 11, is_active: true, sort_order: 8 },
  { id: 9,  name: "Ludwig Ek",        home_area_id: 1, home_activity_id: 18, is_active: true, sort_order: 9 },
  { id: 10, name: "Marcus Svensson",  home_area_id: 1, home_activity_id: 15, is_active: true, sort_order: 10 },
  { id: 11, name: "Anton Holmqvist",  home_area_id: 2, home_activity_id: 21, is_active: true, sort_order: 11 },
  { id: 12, name: "Hugo Fredriksson", home_area_id: 2, home_activity_id: 22, is_active: true, sort_order: 12 },
  { id: 13, name: "Dan Källgren",     home_area_id: 2, home_activity_id: 21, is_active: true, sort_order: 13 },
  { id: 14, name: "Erik Gezelius",    home_area_id: 2, home_activity_id: 24, is_active: true, sort_order: 14 },
  { id: 15, name: "Sanna Ferm",       home_area_id: 2, home_activity_id: 23, is_active: true, sort_order: 15 },
  { id: 16, name: "Kim Lindqvist",    home_area_id: 3, home_activity_id: 31, is_active: true, sort_order: 16 },
  { id: 17, name: "Tova Berg",        home_area_id: 3, home_activity_id: 32, is_active: true, sort_order: 17 },
];

// Mockad bemanning för måndag i Granngården – några celler ifyllda
const CELLS = [
  // Filip: GG VM 6-11, GG Plock 13-15
  { p: 1, h: 6,  a: 12 }, { p: 1, h: 7,  a: 12 }, { p: 1, h: 8,  a: 12 }, { p: 1, h: 9,  a: 12 },
  { p: 1, h: 10, a: 12 }, { p: 1, h: 11, a: 12 }, { p: 1, h: 13, a: 11 }, { p: 1, h: 14, a: 11 }, { p: 1, h: 15, a: 11 },
  // Oscar: GG Plock hela dagen
  ...HOURS.filter(h => h >= 7 && h <= 15 && h !== 12).map(h => ({ p: 2, h, a: 11 })),
  // Malin: GG VM 7-11, GG Helpall 13-15
  { p: 5, h: 7, a: 12 }, { p: 5, h: 8, a: 12 }, { p: 5, h: 9, a: 12 }, { p: 5, h: 10, a: 12 }, { p: 5, h: 11, a: 12 },
  { p: 5, h: 13, a: 13 }, { p: 5, h: 14, a: 13 }, { p: 5, h: 15, a: 13 },
  // Alex Vico: GG Plock 8-15
  ...[8,9,10,11,13,14,15].map(h => ({ p: 8, h, a: 11 })),
  // Ludwig: GG Lotsvård
  ...[7,8,9,10,11,13,14,15].map(h => ({ p: 9, h, a: 18 })),
  // Sebastian: blandad - GG Helpall morgon, Sjuk eftermiddag
  { p: 4, h: 7, a: 13 }, { p: 4, h: 8, a: 13 }, { p: 4, h: 9, a: 13 },
  { p: 4, h: 13, a: 92 }, { p: 4, h: 14, a: 92 }, { p: 4, h: 15, a: 92 },
];


/* ============================================================
   Helpers
   ============================================================ */

function activityById(id) { return ACTIVITIES.find(a => a.id === id); }
function areaById(id) { return AREAS.find(a => a.id === id); }
function personById(id) { return PERSONS.find(p => p.id === id); }
function colorFor(activityId) {
  const a = activityById(activityId);
  return a ? a.color : "transparent";
}
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );
}


/* ============================================================
   Sidebar / topbar rendering
   ============================================================ */

function renderSidebar(activePage) {
  const sidebar = document.querySelector(".sidebar");
  if (!sidebar) return;

  const link = (href, page, icon, label) =>
    `<a href="${href}" class="${activePage === page ? "active" : ""}">
       <span class="icon">${icon}</span><span>${label}</span>
     </a>`;

  sidebar.innerHTML = `
    <div class="brand">
      <div class="brand-dot">B</div>
      <div>
        <div class="brand-name">Bemanning</div>
        <div class="brand-sub">Stigamo · demo</div>
      </div>
    </div>
    <nav class="nav">
      ${link("index.html",     "schedule", "📋", "Bemanning")}
      ${link("overblick.html", "overview", "📅", "Översikt")}
      ${link("personer.html",  "persons",  "👥", "Personer")}
      ${link("stallen.html",   "places",   "📍", "Ställen")}
    </nav>
    <div class="sidebar-bottom">
      <div class="avatar">EK</div>
      <div>
        <div class="who">Emika</div>
        <div>Administratör</div>
      </div>
    </div>
  `;
}


/* ============================================================
   Toasts
   ============================================================ */

function toast(msg, kind = "") {
  let host = document.querySelector(".toasts");
  if (!host) { host = document.createElement("div"); host.className = "toasts"; document.body.appendChild(host); }
  const el = document.createElement("div");
  el.className = "toast" + (kind ? " " + kind : "");
  el.textContent = msg;
  host.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}
