import { state, agencyColor } from "./state.js";
import { applyViewMode } from "./viewmode.js";

const svg       = document.getElementById("map-svg");
const freeBtn   = document.getElementById("free-locations-btn");
const freeList  = document.getElementById("free-list");
const ovList    = document.getElementById("overview-list");
const ovSearch  = document.querySelector(".overview-search");

let freeListActive = false;

svg.addEventListener("click", (e) => {
  if (state.viewMode !== "empty") return;
  const rectEl = e.target.closest(".loc-rect");
  if (!rectEl) return;
  const name = rectEl.dataset.location;
  if (!state.lastAssignments.some(a => a.location === name)) return;
  if (state.emptyLocs.has(name)) {
    state.emptyLocs.delete(name);
  } else {
    state.emptyLocs.add(name);
  }
  applyViewMode();
  if (freeListActive) renderFreeList();
});

freeBtn.addEventListener("click", () => {
  freeListActive = !freeListActive;
  freeBtn.classList.toggle("active", freeListActive);
  if (freeListActive) {
    ovList.style.display  = "none";
    ovSearch.style.display = "none";
    freeList.hidden = false;
    renderFreeList();
  } else {
    ovList.style.display  = "";
    ovSearch.style.display = "";
    freeList.hidden = true;
    freeList.innerHTML = "";
  }
});

function renderFreeList() {
  const byCustomer = new Map();
  state.lastAssignments.forEach(({ location, custom_num, custom_desc, agency_alias }) => {
    if (!byCustomer.has(custom_num)) {
      byCustomer.set(custom_num, { custom_desc, agency_alias, locs: [] });
    }
    byCustomer.get(custom_num).locs.push(location);
  });

  const free = [];
  byCustomer.forEach((data, custom_num) => {
    if (data.locs.length > 0 && data.locs.every(l => state.emptyLocs.has(l))) {
      free.push({ custom_num, ...data });
    }
  });

  if (!free.length) {
    freeList.innerHTML = '<p class="legend-empty">No customers fully freed up yet.</p>';
    return;
  }

  const byAgency = new Map();
  free.forEach(c => {
    if (!byAgency.has(c.agency_alias)) byAgency.set(c.agency_alias, []);
    byAgency.get(c.agency_alias).push(c);
  });
  const sorted = [...byAgency.entries()].sort(
    (a, b) => state.agencyOrder.indexOf(a[0]) - state.agencyOrder.indexOf(b[0])
  );

  freeList.innerHTML = "";

  const copyBar = document.createElement("div");
  copyBar.className = "free-copy-bar";
  const copyBtn = document.createElement("button");
  copyBtn.className = "free-copy-btn";
  copyBtn.textContent = "Copy all names";
  copyBtn.addEventListener("click", () => {
    const names = sorted.flatMap(([, customers]) => customers.map(c => c.custom_desc));
    navigator.clipboard.writeText(names.join("\n")).then(() => {
      copyBtn.textContent = "Copied!";
      setTimeout(() => { copyBtn.textContent = "Copy all names"; }, 1500);
    });
  });
  copyBar.appendChild(copyBtn);
  freeList.appendChild(copyBar);

  sorted.forEach(([alias, customers]) => {
    const color = agencyColor(alias);
    const section = document.createElement("div");
    section.className = "free-agency-section";

    const header = document.createElement("div");
    header.className = "free-agency-header";
    header.innerHTML = `
      <span class="legend-swatch" style="background:${color}"></span>
      <span class="free-agency-name">${alias}</span>
      <span class="free-agency-count">${customers.length}</span>
    `;
    section.appendChild(header);

    customers.forEach(({ custom_desc, locs }) => {
      const item = document.createElement("div");
      item.className = "free-customer-item";
      item.innerHTML = `
        <span class="free-customer-name">${custom_desc}</span>
        <span class="free-customer-locs">${locs.join(", ")}</span>
      `;
      section.appendChild(item);
    });

    freeList.appendChild(section);
  });
}

export function clearEmptyLocs() {
  state.emptyLocs.clear();
  applyViewMode();
  if (freeListActive) renderFreeList();
}
