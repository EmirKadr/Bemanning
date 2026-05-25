import { state, showToast } from "./state.js";
import { loadAssignments } from "./assignments.js";
import { loadOverview } from "./prebook.js";

const advancedOverlay = document.getElementById("advanced-overlay");

function openAdvanced() {
  const tbody = document.querySelector("#advanced-table tbody");
  tbody.innerHTML = "";
  state.agencyOrder.forEach((alias, i) => {
    const a = state.agencyData[alias] ?? {};
    const tr = document.createElement("tr");
    tr.draggable = true;
    tr.dataset.alias = alias;
    tr.innerHTML = `
      <td class="adv-handle">⠿</td>
      <td class="adv-index">${i + 1}</td>
      <td class="adv-agency">${alias}</td>
      <td class="adv-time" data-field="agency_asn">${a.agency_asn ?? ""}</td>
      <td class="adv-time" data-field="agency_arrive">${a.agency_arrive ?? ""}</td>
      <td class="adv-time" data-field="agency_depart">${a.agency_depart ?? ""}</td>
      <td class="adv-time" data-field="cluster_group">${a.cluster_group ?? ""}</td>
      <td class="adv-time adv-seq" data-field="start_seq">${a.start_seq ?? ""}</td>
      <td class="adv-time adv-seq" data-field="end_seq">${a.end_seq ?? ""}</td>
      <td data-field="color"><span class="adv-color-swatch" style="background:${a.color ?? "#d1d5db"}"></span></td>
    `;
    tbody.appendChild(tr);
  });

  initAdvancedDrag(tbody);
  initAdvancedEdit(tbody);
  advancedOverlay.classList.add("open");
}

function initAdvancedEdit(tbody) {
  tbody.addEventListener("dblclick", (e) => {
    const td = e.target.closest("td");
    if (!td || td.classList.contains("adv-handle") || td.classList.contains("adv-index") || td.classList.contains("adv-agency")) return;
    if (td.querySelector("input")) return;

    const isColor = td.querySelector(".adv-color-swatch");
    const alias = td.closest("tr").dataset.alias;
    const field = td.dataset.field;

    if (isColor) {
      const input = document.createElement("input");
      input.type = "color";
      input.value = rgbToHex(td.querySelector(".adv-color-swatch").style.background);
      td.innerHTML = "";
      td.appendChild(input);
      input.focus();
      input.click();
      const commit = () => {
        const val = input.value;
        td.innerHTML = `<span class="adv-color-swatch" style="background:${val}"></span>`;
        saveAgencyField(alias, field, val);
      };
      input.addEventListener("change", commit);
      input.addEventListener("blur", commit);
      return;
    }

    const original = td.textContent.trim();
    const input = document.createElement("input");
    input.type = td.classList.contains("adv-seq") ? "number" : "text";
    input.value = original;
    input.className = "adv-edit-input";
    td.textContent = "";
    td.appendChild(input);
    input.focus();
    input.select();

    const commit = () => {
      const val = input.value.trim() || original;
      td.textContent = val;
      if (val !== original) saveAgencyField(alias, field, val);
    };
    input.addEventListener("blur", commit);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") input.blur();
      if (e.key === "Escape") { td.textContent = original; }
    });
  });
}

async function saveAgencyField(alias, field, value) {
  try {
    const res = await fetch("/api/agencies", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alias, field, value }),
    });
    if (!res.ok) throw new Error(res.status);
  } catch (e) {
    showToast("Failed to save agency field.");
    return;
  }
  if (field === "color") {
    state.agencyColorMap[alias] = value;
    const activeDay = sessionStorage.getItem("activeDay");
    if (activeDay) {
      loadAssignments(parseInt(activeDay));
      loadOverview(parseInt(activeDay));
    }
  }
}

async function saveAgencyOrder(tbody) {
  const aliases = [...tbody.querySelectorAll("tr")].map(tr => tr.dataset.alias);
  try {
    const res = await fetch("/api/agencies/reorder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aliases }),
    });
    if (!res.ok) throw new Error(res.status);
  } catch (e) {
    showToast("Failed to save agency order.");
    return;
  }
  state.agencyOrder = aliases;
  const activeDay = sessionStorage.getItem("activeDay");
  if (activeDay) loadOverview(parseInt(activeDay));
}

function rgbToHex(rgb) {
  const match = rgb.match(/\d+/g);
  if (!match) return "#000000";
  return "#" + match.slice(0, 3).map(n => parseInt(n).toString(16).padStart(2, "0")).join("");
}

function initAdvancedDrag(tbody) {
  let dragSrc = null;

  tbody.addEventListener("dragstart", (e) => {
    dragSrc = e.target.closest("tr");
    dragSrc.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
  });

  tbody.addEventListener("dragover", (e) => {
    e.preventDefault();
    const target = e.target.closest("tr");
    if (!target || target === dragSrc) return;
    const rect = target.getBoundingClientRect();
    const after = e.clientY > rect.top + rect.height / 2;
    tbody.insertBefore(dragSrc, after ? target.nextSibling : target);
  });

  tbody.addEventListener("dragend", () => {
    dragSrc.classList.remove("dragging");
    dragSrc = null;
    [...tbody.querySelectorAll("tr")].forEach((tr, i) => {
      tr.querySelector(".adv-index").textContent = i + 1;
    });
    saveAgencyOrder(tbody);
  });
}

document.getElementById("advanced-open").addEventListener("click", openAdvanced);
document.getElementById("advanced-close").addEventListener("click", () => advancedOverlay.classList.remove("open"));
advancedOverlay.addEventListener("click", (e) => {
  if (e.target === advancedOverlay) advancedOverlay.classList.remove("open");
});

document.querySelectorAll(".modal-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".modal-tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".modal-tab-panel").forEach(p => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById("tab-" + tab.dataset.tab).classList.add("active");
  });
});
