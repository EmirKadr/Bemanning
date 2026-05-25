export const state = {
  transform: { x: 0, y: 0, scale: 1 },
  drag: null,
  hasDragged: false,
  marquee: null,
  overviewAnchorLoc: null,
  selectedLocs: new Set(),

  locData: new Map(),

  agencyColorMap: {},
  clusterMap: {},
  agencyOrder: [],
  agencyData: {},

  lastAssignments: [],

  emptyLocs: new Set(),

  viewMode: "agency",
  selectedCustomer: null,
};

export function agencyColor(alias) {
  return state.agencyColorMap[alias] ?? "#d1d5db";
}

export function showToast(msg, type = "error") {
  const el = document.createElement("div");
  el.className = `toast toast--${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => {
    el.classList.add("toast--fade");
    el.addEventListener("transitionend", () => el.remove(), { once: true });
  }, 3000);
}
