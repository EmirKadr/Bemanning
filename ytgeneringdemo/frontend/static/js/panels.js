export function setConfigPanel(open) {
  panel.classList.toggle("open", open);
  viewport.classList.toggle("panel-open", open);
  sessionStorage.setItem("panelConfig", open);
}

export function setOverviewPanel(open) {
  overviewPanel.classList.toggle("open", open);
  viewport.classList.toggle("overview-open", open);
  sessionStorage.setItem("panelOverview", open);
  if (!open) {
    document.documentElement.style.setProperty("--ov-w", "0px");
  } else {
    requestAnimationFrame(() => {
      document.documentElement.style.setProperty("--ov-w", overviewPanel.offsetWidth + "px");
    });
  }
}

export function setSubPanel(open) {
  if (open) {
    const day = parseInt(sessionStorage.getItem("activeDay")) || null;
    loadMissingAgencies(day);
  }
  subPanel.classList.toggle("open", open);
  missingAgenciesBtn.classList.toggle("active", open);
  sessionStorage.setItem("panelMissing", open);
}

let missingRows = [];
let activeAgencies = new Set();

export async function loadMissingAgencies(day) {
  const body = document.getElementById("missing-agencies-body");
  const filterBar = document.getElementById("miss-filter-bar");
  if (!body) return;
  if (!day) {
    missingAgenciesBtn.classList.remove("has-missing");
    missingRows = [];
    activeAgencies.clear();
    filterBar.hidden = true;
    filterBar.innerHTML = "";
    body.innerHTML = '<p class="legend-empty">Select a day to see missing customers.</p>';
    return;
  }
  try {
    const res = await fetch(`/api/prebook/missing?day=${day}`);
    if (!res.ok) throw new Error(res.status);
    missingRows = await res.json();
    missingAgenciesBtn.classList.toggle("has-missing", missingRows.length > 0);
    activeAgencies = new Set();
    renderMissingCustomers();
  } catch {
    filterBar.hidden = true;
    body.innerHTML = '<p class="legend-empty">Failed to load.</p>';
  }
}

function renderMissingCustomers() {
  const body = document.getElementById("missing-agencies-body");
  const filterBar = document.getElementById("miss-filter-bar");

  if (missingRows.length === 0) {
    filterBar.hidden = true;
    filterBar.innerHTML = "";
    body.innerHTML = '<p class="legend-empty">All customers have sufficient locations.</p>';
    return;
  }

  const seen = new Set();
  const chips = [];
  for (const r of missingRows) {
    if (seen.has(r.agency_alias)) continue;
    seen.add(r.agency_alias);
    chips.push({ alias: r.agency_alias, color: r.color ?? "#d1d5db" });
  }
  filterBar.hidden = false;
  filterBar.innerHTML = chips.map(c => {
    const active = activeAgencies.has(c.alias);
    return `<button class="miss-chip${active ? " active" : ""}" data-alias="${c.alias}" style="--chip-color:${c.color}">
      <span class="miss-chip-dot"></span>${c.alias}
    </button>`;
  }).join("");

  const visible = missingRows
    .filter(r => activeAgencies.size === 0 || activeAgencies.has(r.agency_alias))
    .sort((a, b) => b.pall_missing - a.pall_missing);

  if (visible.length === 0) {
    body.innerHTML = '<p class="legend-empty">No customers match the filter.</p>';
    return;
  }

  body.innerHTML = visible.map(r => {
    const locsLine = r.assigned_locs && r.assigned_locs.length > 0
      ? `<span class="miss-locs">${r.assigned_locs.join(", ")}</span>`
      : `<span class="miss-not-assigned">Not assigned</span>`;
    return `
    <div class="miss-item">
      <div class="miss-header">
        <span class="miss-dot" style="background:${r.color ?? "#d1d5db"}"></span>
        <span class="miss-alias">${r.agency_alias}</span>
        <span class="miss-name">${r.custom_desc || r.custom_num}</span>
      </div>
      <div class="miss-stats">
        <span class="miss-weight">${r.assign_weight} kg</span>
        <span class="miss-pall">${r.assign_pall} pall</span>
        <span class="miss-short">−${_fmtPall(r.pall_missing)} short</span>
        <span class="miss-orderstop">${r.orderstop ?? ""}</span>
      </div>
      <div class="miss-locs-row">${locsLine}</div>
    </div>`;
  }).join("");
}

function _fmtPall(val) {
  return Number.isInteger(val) ? String(val) : val.toFixed(1).replace(".", ",");
}

export function getOverviewMode() {
  return document.querySelector("#overview-mode-toggle .toggle-opt.active")?.dataset.mode ?? "normal";
}

export function filterOverview() {
  const q = overviewSearch.value.trim().toLowerCase();
  const table = document.querySelector("#overview-list .overview-table");
  if (!table) return;
  table.querySelectorAll("tbody tr").forEach(tr => {
    const searchText = [".ov-loc", ".ov-agency", ".ov-id", ".ov-customer"]
      .map(sel => tr.querySelector(sel)?.textContent ?? "").join(" ").toLowerCase();
    tr.style.display = q === "" || searchText.includes(q) ? "" : "none";
  });
}

const panel          = document.getElementById("config-panel");
const toggleBtn      = document.getElementById("config-toggle");
const closeBtn       = document.getElementById("config-close");
const viewport       = document.querySelector(".map-viewport");
const overviewPanel  = document.getElementById("overview-panel");
const overviewToggle = document.getElementById("overview-toggle");
const overviewClose  = document.getElementById("overview-close");
const overviewSearch = document.getElementById("overview-search");
const overviewSearchClear = document.getElementById("overview-search-clear");
const subPanel            = document.getElementById("missing-agencies-panel");
const missingAgenciesBtn  = document.getElementById("missing-agencies-toggle");
const subPanelClose       = document.getElementById("missing-agencies-close");

{
  const root = document.documentElement;

  const savedCfg = localStorage.getItem("panelWidthConfig");
  const savedOv  = localStorage.getItem("panelWidthOverview");
  const savedSub = localStorage.getItem("panelWidthSub");
  if (savedCfg) root.style.setProperty("--cfg-w", savedCfg + "px");
  if (savedOv)  { overviewPanel.style.width = savedOv + "px"; overviewPanel.style.minWidth = "unset"; }
  if (savedSub) root.style.setProperty("--sub-w", savedSub + "px");

  let activeHandle = null;
  let activePanel  = null;
  let startX       = 0;
  let startWidth   = 0;
  let panelType    = "";
  let minW         = 200;
  let maxW         = 700;

  document.querySelectorAll(".panel-resize-handle").forEach(handle => {
    handle.addEventListener("mousedown", e => {
      e.preventDefault();
      activeHandle = handle;
      activePanel  = handle.closest("aside");
      panelType    = handle.dataset.panel;
      startX       = e.clientX;
      startWidth   = activePanel.offsetWidth;

      if (panelType === "config")   { minW = 260; maxW = 640; }
      else if (panelType === "overview") { minW = 300; maxW = 740; }
      else                          { minW = 180; maxW = 460; }

      activeHandle.classList.add("is-resizing");
      viewport.classList.add("is-resizing-active");
      document.body.style.cursor     = "ew-resize";
      document.body.style.userSelect = "none";

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup",   onUp);
    });
  });

  function onMove(e) {
    const dx       = panelType === "sub" ? e.clientX - startX : startX - e.clientX;
    const newWidth = Math.min(Math.max(startWidth + dx, minW), maxW);

    if (panelType === "config") {
      root.style.setProperty("--cfg-w", newWidth + "px");
      localStorage.setItem("panelWidthConfig", newWidth);
    } else if (panelType === "overview") {
      activePanel.style.width    = newWidth + "px";
      activePanel.style.minWidth = "unset";
      if (overviewPanel.classList.contains("open")) {
        root.style.setProperty("--ov-w", newWidth + "px");
      }
      localStorage.setItem("panelWidthOverview", newWidth);
    } else {
      root.style.setProperty("--sub-w", newWidth + "px");
      localStorage.setItem("panelWidthSub", newWidth);
    }
  }

  function onUp() {
    if (activeHandle) activeHandle.classList.remove("is-resizing");
    viewport.classList.remove("is-resizing-active");
    document.body.style.cursor     = "";
    document.body.style.userSelect = "";
    activeHandle = null;
    activePanel  = null;
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup",   onUp);
  }
}

{
  const COMPACT1 = 420;
  const COMPACT2 = 360;

  new ResizeObserver(([entry]) => {
    const w = entry.contentRect.width;
    overviewPanel.classList.toggle("ov-compact-1", w < COMPACT1);
    overviewPanel.classList.toggle("ov-compact-2", w < COMPACT2);
  }).observe(overviewPanel);
}

toggleBtn.addEventListener("click", () => setConfigPanel(true));
closeBtn.addEventListener("click",  () => setConfigPanel(false));

overviewToggle.addEventListener("click", () => setOverviewPanel(true));
overviewClose.addEventListener("click",  () => setOverviewPanel(false));

missingAgenciesBtn.addEventListener("click", () => setSubPanel(!subPanel.classList.contains("open")));
subPanelClose.addEventListener("click",      () => setSubPanel(false));

document.getElementById("miss-filter-bar").addEventListener("click", e => {
  const chip = e.target.closest(".miss-chip");
  if (!chip) return;
  const alias = chip.dataset.alias;
  if (activeAgencies.has(alias)) activeAgencies.delete(alias);
  else activeAgencies.add(alias);
  renderMissingCustomers();
});

document.querySelectorAll("#overview-mode-toggle .toggle-opt").forEach(opt => {
  opt.addEventListener("click", () => {
    document.querySelectorAll("#overview-mode-toggle .toggle-opt").forEach(o => o.classList.remove("active"));
    opt.classList.add("active");
    overviewPanel.classList.toggle("overview-copy-mode", opt.dataset.mode === "copy");
  });
});

overviewSearch.addEventListener("input", () => {
  overviewSearchClear.hidden = !overviewSearch.value;
  filterOverview();
});
overviewSearchClear.addEventListener("click", () => {
  overviewSearch.value = "";
  overviewSearchClear.hidden = true;
  overviewSearch.focus();
  filterOverview();
});

document.getElementById("overview-print").addEventListener("click", () => {
  const table = document.querySelector("#overview-list .overview-table");
  if (!table) { return; }

  const day = parseInt(sessionStorage.getItem("activeDay"));
  const dayNames = ["", "Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"];
  const dayName = dayNames[day] || "";
  const printDate = new Date().toLocaleDateString("sv-SE");

  const rows = [...table.querySelectorAll("tbody tr")].map(tr => {
    const loc      = tr.querySelector(".ov-loc")?.textContent.trim() ?? "";
    const agCell   = tr.querySelector(".ov-agency");
    const color    = agCell?.querySelector(".ov-swatch")?.style.background ?? "";
    const agency   = agCell?.textContent.trim() ?? "";
    const customer = tr.querySelector(".ov-customer")?.textContent.trim() ?? "";
    const empty    = tr.classList.contains("ov-empty");
    return { loc, agency, color, customer, empty };
  });

  const half = Math.ceil(rows.length / 2);
  const left  = rows.slice(0, half);
  const right = rows.slice(half);

  function buildRows(arr) {
    return arr.map(r => {
      if (r.empty) return `<tr class="row-empty"><td>${r.loc}</td><td></td><td></td></tr>`;
      const dot = r.color ? `<span class="dot" style="background:${r.color}"></span>` : "";
      return `<tr><td>${r.loc}</td><td>${dot}${r.agency}</td><td>${r.customer}</td></tr>`;
    }).join("");
  }

  const colgroup = `<colgroup><col class="col-loc"><col class="col-agency"><col class="col-cust"></colgroup>`;
  const thead    = `<thead><tr><th>Yta</th><th>Transportör</th><th>Kundnamn</th></tr></thead>`;

  const allRects = [...document.querySelectorAll(".loc-rect")];
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  allRects.forEach(r => {
    const x = parseFloat(r.getAttribute("x")), y = parseFloat(r.getAttribute("y"));
    const w = parseFloat(r.getAttribute("width")), h = parseFloat(r.getAttribute("height"));
    if (x < minX) minX = x; if (y < minY) minY = y;
    if (x + w > maxX) maxX = x + w; if (y + h > maxY) maxY = y + h;
  });
  const pad = 10;
  const mapViewBox = `${minX - pad} ${minY - pad} ${maxX - minX + pad * 2} ${maxY - minY + pad * 2}`;
  const mapRects = allRects.map(r => {
    const fill = r.style.fill || "#adb3b8";
    const stroke = fill === "#adb3b8" ? "#959ba0" : "none";
    return `<rect x="${r.getAttribute("x")}" y="${r.getAttribute("y")}" width="${r.getAttribute("width")}" height="${r.getAttribute("height")}" fill="${fill}" stroke="${stroke}" stroke-width="1" rx="1"/>`;
  }).join("");
  const mapSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${mapViewBox}" style="width:100%;height:auto;display:block;">${mapRects}</svg>`;

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Tilldelade ytor – ${dayName}</title>
  <style>
    @page { size: A4 portrait; margin: 1.2cm 1cm; }
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    body { font-family: Arial, sans-serif; font-size: 7pt; color: #111; }
    .title-row { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.4cm; }
    h1 { font-size: 9pt; font-weight: 700; }
    .print-date { font-size: 8pt; color: #555; }
    .columns { display: flex; gap: 0.5cm; align-items: flex-start; }
    .col { flex: 1; min-width: 0; }
    table { width: 100%; border-collapse: collapse; }
    thead th {
      font-size: 6pt; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.04em; color: #555;
      padding: 2px 3px; border-bottom: 1.5px solid #222; text-align: left;
    }
    tbody td { padding: 1.5px 3px; border-bottom: 1px solid #e8e8e8; vertical-align: middle; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    tbody tr:nth-child(even) td { background: #f0f2f4; }
    .row-empty td { color: #ccc; }
    .dot { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 4px; vertical-align: middle; flex-shrink: 0; }
    col.col-loc    { width: 18%; }
    col.col-agency { width: 22%; }
    col.col-cust   { width: 60%; }
  </style>
</head>
<body>
  <div class="title-row">
    <h1>Tilldelade ytor – ${dayName}</h1>
    <span class="print-date">${printDate}</span>
  </div>
  <div class="columns">
    <div class="col">
      <table>${colgroup}${thead}<tbody>${buildRows(left)}</tbody></table>
    </div>
    <div class="col">
      <table>${colgroup}${thead}<tbody>${buildRows(right)}</tbody></table>
    </div>
  </div>
  <div style="margin-top:1.6cm;">${mapSvg}</div>
  <script>window.onload = () => window.print();<\/script>
</body>
</html>`;

  const win = window.open("", "_blank");
  win.document.write(html);
  win.document.close();
});

const isReload = performance.getEntriesByType("navigation")[0]?.type === "reload";
if (!isReload) {
  if (sessionStorage.getItem("panelConfig") === "true")   setConfigPanel(true);
  if (sessionStorage.getItem("panelOverview") === "true") setOverviewPanel(true);
  if (sessionStorage.getItem("panelMissing") === "true")  setSubPanel(true);
}
