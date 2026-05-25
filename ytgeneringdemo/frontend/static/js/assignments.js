import { state, agencyColor, showToast } from "./state.js";
import { applyViewMode } from "./viewmode.js";
import { applySelectionVisual, clearSelectionVisual, selectLocation, syncOverviewSelection } from "./selection.js";
import { getOverviewMode, filterOverview, loadMissingAgencies } from "./panels.js";
import { applyTransform, saveTransform } from "./transform.js";
import { loadOverview } from "./prebook.js";
import { clearEmptyLocs } from "./empty.js";

const NS = "http://www.w3.org/2000/svg";
const svg = document.getElementById("map-svg");
const overviewPanel = document.getElementById("overview-panel");

export function setDefaultText(textEl, name, cx, cy) {
  textEl.innerHTML = "";
  textEl.setAttribute("x", cx);
  textEl.setAttribute("y", cy);
  const span = document.createElementNS(NS, "tspan");
  span.setAttribute("x", cx);
  span.setAttribute("dy", "0");
  span.setAttribute("class", "loc-label");
  span.textContent = name;
  textEl.appendChild(span);
}

export function setAssignedText(textEl, name, alias, customer, cx, cy) {
  textEl.innerHTML = "";
  textEl.setAttribute("x", cx);
  textEl.setAttribute("y", cy - 17);

  const lines = [
    { text: name,     cls: "loc-label-sub" },
    { text: customer, cls: "loc-label-agency" },
    { text: alias,    cls: "loc-label-sub" },
  ];

  lines.forEach((line, i) => {
    const span = document.createElementNS(NS, "tspan");
    span.setAttribute("x", cx);
    span.setAttribute("dy", i === 0 ? "0" : "17");
    span.setAttribute("class", line.cls);
    span.textContent = line.text;
    textEl.appendChild(span);
  });
}

export async function loadAssignments(day) {
  let rows;
  try {
    const res = await fetch(`/api/assignments/all?day=${day}`);
    if (!res.ok) throw new Error(res.status);
    rows = await res.json();
  } catch (e) {
    showToast("Failed to load assignments.");
    return;
  }

  clearEmptyLocs();
  state.locData.forEach(({ rectEl, textEl, cx, cy }, name) => {
    rectEl.style.fill = "";
    setDefaultText(textEl, name, cx, cy);
  });

  const assignments = [];
  rows.forEach(({ location, agency_alias, agency_num, custom_num, custom_desc }) => {
    if (!agency_alias) return;
    const data = state.locData.get(location);
    if (!data) return;
    setAssignedText(data.textEl, location, agency_alias, custom_desc, data.cx, data.cy);
    assignments.push({ location, agency_num, custom_num, agency_alias, custom_desc });
  });

  state.lastAssignments = assignments;
  applyViewMode();
  renderOverviewPanel(rows);
}

export function renderOverviewPanel(rows) {
  const list = document.getElementById("overview-list");
  if (!list) return;

  list.innerHTML = "";
  const table = document.createElement("table");
  table.className = "overview-table";
  table.innerHTML = `<thead><tr>
      <th>Location</th><th>Agency</th><th class="ov-th-id">ID</th>
      <th>Customer</th><th class="ov-th-weight">Weight</th><th>Pallets</th>
    </tr></thead>`;
  const tbody = document.createElement("tbody");

  rows.forEach(({ location, agency_alias, custom_num, custom_desc, assign_weight, assign_pall }) => {
    const tr = document.createElement("tr");
    tr.dataset.location = location;
    const assigned = !!agency_alias;
    if (assigned) {
      const color = agencyColor(agency_alias);
      tr.innerHTML = `
        <td class="ov-loc">${location}</td>
        <td class="ov-agency"><span class="ov-swatch" style="background:${color}"></span>${agency_alias}</td>
        <td class="ov-id">${custom_num ?? ""}</td>
        <td class="ov-customer">${custom_desc ?? ""}</td>
        <td class="ov-weight">${assign_weight != null ? assign_weight + " kg" : ""}</td>
        <td class="ov-pall">${assign_pall != null ? assign_pall : ""}</td>
      `;
    } else {
      tr.className = "ov-empty";
      tr.innerHTML = `
        <td class="ov-loc">${location}</td>
        <td class="ov-agency"></td>
        <td class="ov-id"></td>
        <td class="ov-customer"></td>
        <td class="ov-weight"></td>
        <td class="ov-pall"></td>
      `;
    }
    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  list.appendChild(table);

  table.addEventListener("click", e => {
    if (getOverviewMode() === "copy") {
      const td = e.target.closest(".ov-loc, .ov-id, .ov-customer");
      if (!td || !td.textContent.trim()) return;
      navigator.clipboard.writeText(td.textContent.trim());
      td.classList.add("ov-copied");
      setTimeout(() => td.classList.remove("ov-copied"), 600);
    } else {
      const tr = e.target.closest("tr[data-location]");
      if (!tr) return;
      if (e.shiftKey && state.overviewAnchorLoc) {
        const allRows = [...document.querySelectorAll("#overview-list tr[data-location]")]
          .filter(r => r.style.display !== "none");
        const anchorIdx = allRows.findIndex(r => r.dataset.location === state.overviewAnchorLoc);
        const targetIdx = allRows.indexOf(tr);
        if (anchorIdx !== -1 && targetIdx !== -1) {
          const [from, to] = anchorIdx < targetIdx ? [anchorIdx, targetIdx] : [targetIdx, anchorIdx];
          state.selectedLocs.forEach(n => clearSelectionVisual(n));
          state.selectedLocs.clear();
          for (let i = from; i <= to; i++) {
            const loc = allRows[i].dataset.location;
            applySelectionVisual(loc);
            state.selectedLocs.add(loc);
          }
          syncOverviewSelection();
        }
      } else {
        state.overviewAnchorLoc = tr.dataset.location;
        selectLocation(tr.dataset.location, e.ctrlKey);
      }
    }
  });

  table.addEventListener("dblclick", e => {
    if (getOverviewMode() !== "normal") return;
    const tr = e.target.closest("tr[data-location]");
    if (!tr) return;
    const name = tr.dataset.location;
    const d = state.locData.get(name);
    if (!d) return;
    if (!state.selectedLocs.has(name)) selectLocation(name);
    const svgRect = svg.getBoundingClientRect();
    state.transform.x = svgRect.width  / 2 - d.cx * state.transform.scale;
    state.transform.y = svgRect.height / 2 - d.cy * state.transform.scale;
    applyTransform();
    saveTransform();
  });

  filterOverview();
  requestAnimationFrame(() => {
    document.documentElement.style.setProperty("--ov-w", overviewPanel.offsetWidth + "px");
  });
}

export function clearDay() {
  document.querySelectorAll("#day-toggle .toggle-opt").forEach(opt => opt.classList.remove("active"));
  sessionStorage.removeItem("activeDay");
  clearEmptyLocs();
  state.locData.forEach(({ rectEl, textEl, cx, cy }, name) => {
    rectEl.style.fill = "";
    setDefaultText(textEl, name, cx, cy);
  });
  document.getElementById("legend-list").innerHTML = "<li class=\"legend-empty\">Select a day to see agencies.</li>";
  document.getElementById("overview-list").innerHTML = "<p class=\"legend-empty\">Select a day to see assignments.</p>";
  state.lastAssignments = [];
  state.selectedCustomer = null;
}

export function selectDay(day) {
  document.querySelectorAll("#day-toggle .toggle-opt").forEach(opt => {
    opt.classList.toggle("active", parseInt(opt.dataset.day) === day);
  });
  sessionStorage.setItem("activeDay", day);
  loadAssignments(day);
  loadOverview(day);
  loadMissingAgencies(day);
}

window.__reloadDay = (day) => {
  loadAssignments(day);
  loadOverview(day);
  loadMissingAgencies(day);
};

document.querySelectorAll("#day-toggle .toggle-opt").forEach((opt) => {
  opt.addEventListener("click", () => {
    const day = parseInt(opt.dataset.day);
    if (opt.classList.contains("active")) {
      clearDay();
    } else {
      selectDay(day);
    }
  });
});

document.getElementById("assign-locations").addEventListener("click", async () => {
  const day = parseInt(sessionStorage.getItem("activeDay"));
  if (!day) return;
  const orderstop = document.querySelector("#cfg-orderstop .toggle-opt.active")?.dataset.value;
  if (!orderstop) return;
  const lock = document.getElementById("cfg-lock-locations").classList.contains("active");
  try {
    const res = await fetch(`/api/assignments/run?day=${day}&orderstop=${orderstop}&lock=${lock}`, { method: "POST" });
    if (!res.ok) throw new Error(res.status);
    loadAssignments(day);
    loadOverview(day);
    loadMissingAgencies(day);
  } catch (e) {
    showToast("Assignment failed.");
  }
});

document.getElementById("clear-locations").addEventListener("click", async () => {
  const dayNames = { 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday" };
  const day = sessionStorage.getItem("activeDay");
  if (!day) { showToast("Select a day first."); return; }
  const label = dayNames[day] || `Day ${day}`;
  try {
    const r = await fetch(`/api/assignments/clear?day=${day}`, { method: "POST" });
    if (!r.ok) throw new Error(r.status);
    const dayInt = parseInt(day);
    loadAssignments(dayInt);
    loadOverview(dayInt);
    loadMissingAgencies(dayInt);
    showToast(`Locations cleared for ${label}.`);
  } catch {
    showToast("Failed to clear locations.");
  }
});

document.querySelectorAll("#cfg-orderstop .toggle-opt").forEach((opt) => {
  opt.addEventListener("click", () => {
    document.querySelectorAll("#cfg-orderstop .toggle-opt").forEach(o => o.classList.remove("active"));
    opt.classList.add("active");
  });
});

document.getElementById("cfg-lock-locations").addEventListener("click", function () {
  this.classList.toggle("active");
});

const ctxMenu = document.getElementById("map-ctx-menu");
let ctxTargetLocs = new Set();

let copiedAssignment = null;

svg.addEventListener("contextmenu", (e) => {
  e.preventDefault();
  const rectEl = e.target.closest(".loc-rect");
  if (rectEl) {
    const name = rectEl.dataset.location;
    if (!state.selectedLocs.has(name)) selectLocation(name);
  }
  ctxTargetLocs = new Set(state.selectedLocs);

  const noTargets = ctxTargetLocs.size === 0;
  const noDay = !sessionStorage.getItem("activeDay");
  ctxMenu.querySelectorAll(".ctx-item").forEach(b => b.disabled = noTargets || noDay);

  ctxMenu.style.left = e.clientX + "px";
  ctxMenu.style.top  = e.clientY + "px";
  document.getElementById("ctx-assign-sub").classList.remove("open");
  ctxMenu.classList.add("open");

  requestAnimationFrame(() => {
    const r = ctxMenu.getBoundingClientRect();
    if (r.right  > window.innerWidth)  ctxMenu.style.left = (e.clientX - r.width)  + "px";
    if (r.bottom > window.innerHeight) ctxMenu.style.top  = (e.clientY - r.height) + "px";
  });
});

function closeCtxMenu() {
  ctxMenu.classList.remove("open");
  document.getElementById("ctx-assign-sub").classList.remove("open");
  ctxTargetLocs = new Set();
}

document.addEventListener("mousedown", (e) => {
  if (ctxMenu.classList.contains("open") && !ctxMenu.contains(e.target)) closeCtxMenu();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && ctxMenu.classList.contains("open")) closeCtxMenu();

  const tag = document.activeElement?.tagName;

  if (e.key === "z" && e.ctrlKey && !e.shiftKey) {
    if (tag === "INPUT" || tag === "TEXTAREA") return;
    e.preventDefault();
    const day = parseInt(sessionStorage.getItem("activeDay"));
    if (isNaN(day)) return;
    fetch(`/api/assignments/undo?day=${day}`, { method: "POST" })
      .then(r => { if (!r.ok) throw new Error(`undo ${r.status}`); return r.json(); })
      .then(data => {
        console.log("undo:", data);
        loadAssignments(day);
        loadOverview(day);
        loadMissingAgencies(day);
      })
      .catch(err => console.error("undo failed:", err));
  }

  if (e.key === "c" && e.ctrlKey && !e.shiftKey) {
    if (tag === "INPUT" || tag === "TEXTAREA") return;
    if (window.getSelection()?.toString()) return;
    if (state.selectedLocs.size !== 1) return;
    const name = [...state.selectedLocs][0];
    const assignment = state.lastAssignments.find(a => a.location === name);
    if (!assignment) return;
    e.preventDefault();
    copiedAssignment = { custom_num: assignment.custom_num, custom_desc: assignment.custom_desc, agency_alias: assignment.agency_alias };
    showToast(`Copied: ${assignment.custom_desc}`, "success");
  }

  if (e.key === "v" && e.ctrlKey && !e.shiftKey) {
    if (tag === "INPUT" || tag === "TEXTAREA") return;
    if (!copiedAssignment || !state.selectedLocs.size) return;
    e.preventDefault();
    const day = parseInt(sessionStorage.getItem("activeDay"));
    if (isNaN(day)) { showToast("Select a day first."); return; }
    const locs = [...state.selectedLocs];
    fetch("/api/assignments/manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locations: locs, day, custom_num: copiedAssignment.custom_num }),
    }).then(r => {
      if (!r.ok) throw new Error(r.status);
      loadAssignments(day);
      loadOverview(day);
      loadMissingAgencies(day);
    }).catch(() => showToast("Paste failed."));
  }
});

function triggerExportDownload(url) {
  const a = document.createElement("a");
  a.href = url;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

document.getElementById("export-to-ask").addEventListener("click", () => {
  const day = parseInt(sessionStorage.getItem("activeDay"));
  if (!day) { showToast("Select a day first."); return; }
  triggerExportDownload(`/api/assignments/export-ask?day=${day}&placeholder=0`);
});

document.getElementById("export-placeholder").addEventListener("click", () => {
  const day = parseInt(sessionStorage.getItem("activeDay"));
  if (!day) { showToast("Select a day first."); return; }
  triggerExportDownload(`/api/assignments/export-ask?day=${day}&placeholder=1`);
});

document.getElementById("export-kontrollpanel").addEventListener("click", () => {
  const day = parseInt(sessionStorage.getItem("activeDay"));
  if (!day) { showToast("Select a day first."); return; }
  triggerExportDownload(`/api/assignments/export-kontrollpanel?day=${day}`);
});

document.getElementById("export-tider-for-kund").addEventListener("click", () => {
  triggerExportDownload(`/api/assignments/export-tider-for-kund`);
});

document.getElementById("copy-kontrollpanel").addEventListener("click", async () => {
  const day = parseInt(sessionStorage.getItem("activeDay"));
  if (!day) { showToast("Select a day first."); return; }
  try {
    const resp = await fetch(`/api/assignments/export-kontrollpanel?day=${day}`);
    const text = await resp.text();
    const rows = text.trim().split("\n").map(r => r.split("\t"));
    const htmlRows = rows.map(cols =>
      "<tr>" + cols.map(c => `<td>${c}</td>`).join("") + "</tr>"
    ).join("");
    const html = `<table>${htmlRows}</table>`;
    await navigator.clipboard.write([
      new ClipboardItem({
        "text/plain": new Blob([text], { type: "text/plain" }),
        "text/html": new Blob([html], { type: "text/html" }),
      })
    ]);
    showToast("Copied to clipboard.");
  } catch (err) {
    showToast("Copy failed: " + err.message);
  }
});

ctxMenu.addEventListener("click", (e) => {
  const item = e.target.closest(".ctx-item");
  if (!item) return;
  const action = item.dataset.action;
  const targetLocs = [...ctxTargetLocs];

  if (action === "assign") {
    const sub = document.getElementById("ctx-assign-sub");
    if (sub.classList.contains("open")) {
      sub.classList.remove("open");
      return;
    }
    const btn = item.getBoundingClientRect();
    sub.style.left = btn.right + 4 + "px";
    sub.style.top  = btn.top + "px";
    sub.classList.add("open");
    requestAnimationFrame(() => {
      const r = sub.getBoundingClientRect();
      if (r.right  > window.innerWidth)  sub.style.left = (btn.left - r.width - 4) + "px";
      if (r.bottom > window.innerHeight) sub.style.top  = (btn.bottom - r.height)  + "px";
    });
    return;
  }

  if (action === "assign-prebook") {
    const anchorRect = ctxMenu.getBoundingClientRect();
    closeCtxMenu();
    const day = parseInt(sessionStorage.getItem("activeDay"));
    if (!day) { showToast("Select a day first."); return; }
    openPrebookPicker(targetLocs, day, anchorRect);
    return;
  }

  closeCtxMenu();

  if (action === "assign-search") {
    const anchorRect = ctxMenu.getBoundingClientRect();
    openCustomerPicker(targetLocs, anchorRect);
    return;
  }
  if (action === "release") {
    const day = parseInt(sessionStorage.getItem("activeDay"));
    fetch("/api/assignments/release", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locations: targetLocs, day }),
    }).then(r => {
      if (!r.ok) throw new Error(r.status);
      loadAssignments(day);
      loadOverview(day);
      loadMissingAgencies(day);
    }).catch(() => showToast("Release failed."));
  }
});

const prebookPicker     = document.getElementById("prebook-picker");
const prebookPickerBody = document.getElementById("prebook-picker-body");
let _pickerLocs = [];
let _pickerDay  = null;

function closePrebookPicker() {
  prebookPicker.classList.remove("open");
}

function filterPrebookPicker(q) {
  prebookPickerBody.querySelectorAll(".agency-item").forEach(agencyItem => {
    let anyVisible = false;
    agencyItem.querySelectorAll(".picker-customer-row").forEach(row => {
      const name = row.querySelector(".customer-name")?.textContent.toLowerCase() ?? "";
      const visible = !q || name.includes(q);
      row.style.display = visible ? "" : "none";
      if (visible) anyVisible = true;
    });
    agencyItem.style.display = anyVisible ? "" : "none";
  });
}

const pickerSearch      = document.getElementById("prebook-picker-search");
const pickerSearchClear = document.getElementById("prebook-picker-search-clear");

pickerSearch.addEventListener("input", () => {
  pickerSearchClear.hidden = !pickerSearch.value;
  filterPrebookPicker(pickerSearch.value.trim().toLowerCase());
});

pickerSearchClear.addEventListener("click", () => {
  pickerSearch.value = "";
  pickerSearchClear.hidden = true;
  pickerSearch.focus();
  filterPrebookPicker("");
});

document.getElementById("prebook-picker-close").addEventListener("click", closePrebookPicker);

document.addEventListener("mousedown", (e) => {
  if (prebookPicker.classList.contains("open") && !prebookPicker.contains(e.target)) {
    closePrebookPicker();
  }
});

prebookPickerBody.addEventListener("click", async (e) => {
  const row = e.target.closest(".picker-customer-row");
  if (!row) return;
  const customNum = parseInt(row.dataset.customNum);
  const locs = _pickerLocs;
  const day  = _pickerDay;
  closePrebookPicker();
  try {
    const res = await fetch("/api/assignments/manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locations: locs, day, custom_num: customNum }),
    });
    if (!res.ok) throw new Error(res.status);
    loadAssignments(day);
    loadOverview(day);
    loadMissingAgencies(day);
  } catch {
    showToast("Assignment failed.");
  }
});

async function openPrebookPicker(targetLocs, day, anchorRect) {
  _pickerLocs = targetLocs;
  _pickerDay  = day;

  pickerSearch.value = "";
  pickerSearchClear.hidden = true;
  prebookPickerBody.innerHTML = '<li class="legend-empty">Loading…</li>';
  prebookPicker.style.left = anchorRect.right + 4 + "px";
  prebookPicker.style.top  = anchorRect.top + "px";
  prebookPicker.classList.add("open");

  requestAnimationFrame(() => {
    const r = prebookPicker.getBoundingClientRect();
    if (r.right > window.innerWidth) prebookPicker.style.left = (anchorRect.left - r.width - 4) + "px";
    prebookPicker.style.top = Math.max(8, (window.innerHeight - r.height) * 0.3) + "px";
    pickerSearch.focus();
  });

  let rows;
  try {
    const res = await fetch(`/api/prebook?day=${day}`);
    if (!res.ok) throw new Error(res.status);
    rows = await res.json();
  } catch {
    prebookPickerBody.innerHTML = '<li class="legend-empty">Failed to load prebook.</li>';
    return;
  }

  if (!rows.length) {
    prebookPickerBody.innerHTML = '<li class="legend-empty">No prebook for this day.</li>';
    return;
  }

  const grouped = new Map();
  rows.forEach(({ agency_alias, custom_num, custom_desc, assign_pall }) => {
    if (!grouped.has(agency_alias)) grouped.set(agency_alias, []);
    grouped.get(agency_alias).push({ custom_num, custom_desc, assign_pall });
  });

  const sorted = [...grouped.entries()].sort(
    (a, b) => state.agencyOrder.indexOf(a[0]) - state.agencyOrder.indexOf(b[0])
  );

  prebookPickerBody.innerHTML = "";
  sorted.forEach(([alias, customers]) => {
    const color = agencyColor(alias);
    const li = document.createElement("li");
    li.className = "agency-item open";

    const header = document.createElement("div");
    header.className = "agency-header";
    header.innerHTML = `
      <div class="agency-header-left">
        <span class="legend-swatch" style="background:${color}"></span>
        <span class="legend-label">${alias}</span>
      </div>
      <span class="agency-chevron" style="transform:rotate(90deg)">›</span>
    `;
    header.addEventListener("click", () => {
      const open = li.classList.toggle("open");
      header.querySelector(".agency-chevron").style.transform = open ? "rotate(90deg)" : "";
    });

    const ul = document.createElement("ul");
    ul.className = "agency-customers";
    ul.style.borderLeftColor = color;

    customers.forEach(({ custom_num, custom_desc, assign_pall }) => {
      const row = document.createElement("li");
      row.className = "customer-row picker-customer-row";
      row.dataset.customNum = custom_num;
      row.innerHTML = `
        <span class="customer-name">${custom_desc}</span>
        <span class="customer-meta">${assign_pall} pall</span>
      `;
      ul.appendChild(row);
    });

    li.appendChild(header);
    li.appendChild(ul);
    prebookPickerBody.appendChild(li);
  });
}

const customerPicker     = document.getElementById("customer-picker");
const customerPickerBody = document.getElementById("customer-picker-body");
let _customerPickerLocs = [];

function closeCustomerPicker() {
  customerPicker.classList.remove("open");
}

function filterCustomerPicker(q) {
  customerPickerBody.querySelectorAll(".agency-item").forEach(agencyItem => {
    let anyVisible = false;
    agencyItem.querySelectorAll(".picker-customer-row").forEach(row => {
      const name = row.querySelector(".customer-name")?.textContent.toLowerCase() ?? "";
      const visible = !q || name.includes(q);
      row.style.display = visible ? "" : "none";
      if (visible) anyVisible = true;
    });
    agencyItem.style.display = anyVisible ? "" : "none";
  });
}

const custSearch      = document.getElementById("customer-picker-search");
const custSearchClear = document.getElementById("customer-picker-search-clear");

custSearch.addEventListener("input", () => {
  custSearchClear.hidden = !custSearch.value;
  filterCustomerPicker(custSearch.value.trim().toLowerCase());
});

custSearchClear.addEventListener("click", () => {
  custSearch.value = "";
  custSearchClear.hidden = true;
  custSearch.focus();
  filterCustomerPicker("");
});

document.getElementById("customer-picker-close").addEventListener("click", closeCustomerPicker);

document.addEventListener("mousedown", (e) => {
  if (customerPicker.classList.contains("open") && !customerPicker.contains(e.target)) {
    closeCustomerPicker();
  }
});

customerPickerBody.addEventListener("click", async (e) => {
  const row = e.target.closest(".picker-customer-row");
  if (!row) return;
  const customNum = parseInt(row.dataset.customNum);
  const locs = _customerPickerLocs;
  const day  = parseInt(sessionStorage.getItem("activeDay"));
  closeCustomerPicker();
  if (!day) { showToast("Select a day first."); return; }
  try {
    const res = await fetch("/api/assignments/manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locations: locs, day, custom_num: customNum }),
    });
    if (!res.ok) throw new Error(res.status);
    loadAssignments(day);
    loadOverview(day);
    loadMissingAgencies(day);
  } catch {
    showToast("Assignment failed.");
  }
});

async function openCustomerPicker(targetLocs, anchorRect) {
  _customerPickerLocs = targetLocs;

  custSearch.value = "";
  custSearchClear.hidden = true;
  customerPickerBody.innerHTML = '<li class="legend-empty">Loading…</li>';
  customerPicker.style.left = anchorRect.right + 4 + "px";
  customerPicker.style.top  = anchorRect.top + "px";
  customerPicker.classList.add("open");

  requestAnimationFrame(() => {
    const r = customerPicker.getBoundingClientRect();
    if (r.right > window.innerWidth) customerPicker.style.left = (anchorRect.left - r.width - 4) + "px";
    customerPicker.style.top = Math.max(8, (window.innerHeight - r.height) * 0.3) + "px";
    custSearch.focus();
  });

  let rows;
  try {
    const res = await fetch("/api/customers");
    if (!res.ok) throw new Error(res.status);
    rows = await res.json();
  } catch {
    customerPickerBody.innerHTML = '<li class="legend-empty">Failed to load customers.</li>';
    return;
  }

  if (!rows.length) {
    customerPickerBody.innerHTML = '<li class="legend-empty">No customers found.</li>';
    return;
  }

  const grouped = new Map();
  rows.forEach(({ agency_alias, custom_num, custom_desc }) => {
    const key = agency_alias ?? "(No agency)";
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push({ custom_num, custom_desc });
  });

  const sorted = [...grouped.entries()].sort(
    (a, b) => state.agencyOrder.indexOf(a[0]) - state.agencyOrder.indexOf(b[0])
  );

  customerPickerBody.innerHTML = "";
  sorted.forEach(([alias, customers]) => {
    const color = agencyColor(alias);
    const li = document.createElement("li");
    li.className = "agency-item open";

    const header = document.createElement("div");
    header.className = "agency-header";
    header.innerHTML = `
      <div class="agency-header-left">
        <span class="legend-swatch" style="background:${color}"></span>
        <span class="legend-label">${alias}</span>
      </div>
      <span class="agency-chevron" style="transform:rotate(90deg)">›</span>
    `;
    header.addEventListener("click", () => {
      const open = li.classList.toggle("open");
      header.querySelector(".agency-chevron").style.transform = open ? "rotate(90deg)" : "";
    });

    const ul = document.createElement("ul");
    ul.className = "agency-customers";
    ul.style.borderLeftColor = color;

    customers.forEach(({ custom_num, custom_desc }) => {
      const row = document.createElement("li");
      row.className = "customer-row picker-customer-row";
      row.dataset.customNum = custom_num;
      row.innerHTML = `<span class="customer-name">${custom_desc}</span>`;
      ul.appendChild(row);
    });

    li.appendChild(header);
    li.appendChild(ul);
    customerPickerBody.appendChild(li);
  });
}
