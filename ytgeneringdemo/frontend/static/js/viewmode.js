import { state, agencyColor } from "./state.js";

const BW_COLOR = "#d4d4d4";

function generatePalette(n) {
  if (n === 0) return [];
  return Array.from({ length: n }, (_, i) =>
    `hsl(${Math.round((i / n) * 360)}, 60%, 58%)`
  );
}

const EMPTY_PICKED_COLOR = "#4ade80";

export function applyViewMode() {
  const assignMap = new Map(state.lastAssignments.map(a => [a.location, a]));

  if (state.viewMode === "agency") {
    state.locData.forEach(({ rectEl }, name) => {
      const a = assignMap.get(name);
      rectEl.style.fill = a ? agencyColor(a.agency_alias) : "";
    });
    return;
  }

  if (state.viewMode === "empty") {
    state.locData.forEach(({ rectEl }, name) => {
      const a = assignMap.get(name);
      if (!a) { rectEl.style.fill = ""; return; }
      rectEl.style.fill = state.emptyLocs.has(name) ? EMPTY_PICKED_COLOR : agencyColor(a.agency_alias);
    });
    return;
  }

  state.locData.forEach(({ rectEl }, name) => {
    rectEl.style.fill = assignMap.has(name) ? BW_COLOR : "";
  });

  if (!state.selectedCustomer) return;

  const { agency_alias } = state.selectedCustomer;
  const agencyRows = state.lastAssignments.filter(a => a.agency_alias === agency_alias);
  const uniqueCustomers = [...new Set(agencyRows.map(a => a.custom_num))];
  const palette = generatePalette(uniqueCustomers.length);
  const colorMap = new Map(uniqueCustomers.map((num, i) => [num, palette[i]]));

  agencyRows.forEach(({ location, custom_num }) => {
    const d = state.locData.get(location);
    if (d) d.rectEl.style.fill = colorMap.get(custom_num);
  });
}

document.querySelectorAll("#view-toggle .toggle-opt").forEach(opt => {
  opt.addEventListener("click", () => {
    document.querySelectorAll("#view-toggle .toggle-opt").forEach(o => o.classList.remove("active"));
    opt.classList.add("active");
    state.viewMode = opt.dataset.view;
    state.selectedCustomer = null;
    applyViewMode();
  });
});
