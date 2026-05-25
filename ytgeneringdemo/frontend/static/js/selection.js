import { state } from "./state.js";
import { applyViewMode } from "./viewmode.js";
import { setOverviewPanel } from "./panels.js";

const NS  = "http://www.w3.org/2000/svg";
const svg = document.getElementById("map-svg");
const overviewPanel = document.getElementById("overview-panel");

export function applySelectionVisual(name) {
  const d = state.locData.get(name);
  if (!d) return;
  d.rectEl.classList.add("loc-rect--selected");
  const overlay = document.createElementNS(NS, "rect");
  overlay.setAttribute("x", d.rectEl.getAttribute("x"));
  overlay.setAttribute("y", d.rectEl.getAttribute("y"));
  overlay.setAttribute("width", d.rectEl.getAttribute("width"));
  overlay.setAttribute("height", d.rectEl.getAttribute("height"));
  overlay.setAttribute("class", "loc-overlay");
  d.rectEl.parentElement.insertBefore(overlay, d.textEl);
  d.overlayEl = overlay;
}

export function clearSelectionVisual(name) {
  const d = state.locData.get(name);
  if (!d) return;
  d.rectEl.classList.remove("loc-rect--selected");
  d.overlayEl?.remove();
  d.overlayEl = null;
}

export function syncOverviewSelection() {
  document.querySelectorAll("#overview-list tr[data-location]").forEach(tr => {
    tr.classList.toggle("ov-row--selected", state.selectedLocs.has(tr.dataset.location));
  });
}

export function selectLocation(name, additive = false) {
  if (name === null) {
    state.selectedLocs.forEach(n => clearSelectionVisual(n));
    state.selectedLocs.clear();
    syncOverviewSelection();
    return;
  }
  if (!additive) {
    const isSoleSelection = state.selectedLocs.size === 1 && state.selectedLocs.has(name);
    state.selectedLocs.forEach(n => clearSelectionVisual(n));
    state.selectedLocs.clear();
    if (!isSoleSelection) {
      applySelectionVisual(name);
      state.selectedLocs.add(name);
    }
  } else {
    if (state.selectedLocs.has(name)) {
      clearSelectionVisual(name);
      state.selectedLocs.delete(name);
    } else {
      applySelectionVisual(name);
      state.selectedLocs.add(name);
    }
  }
  syncOverviewSelection();
}

svg.addEventListener("mousedown", (e) => {
  if (!e.shiftKey) return;
  state.hasDragged = false;
  const svgRect = svg.getBoundingClientRect();
  const x = e.clientX - svgRect.left;
  const y = e.clientY - svgRect.top;
  const rectEl = document.createElementNS(NS, "rect");
  rectEl.setAttribute("class", "marquee-rect");
  rectEl.setAttribute("x", x);
  rectEl.setAttribute("y", y);
  rectEl.setAttribute("width", 0);
  rectEl.setAttribute("height", 0);
  svg.appendChild(rectEl);
  state.marquee = { startX: x, startY: y, rectEl };
});

window.addEventListener("mousemove", (e) => {
  if (!state.marquee) return;
  const svgRect = svg.getBoundingClientRect();
  const x = e.clientX - svgRect.left;
  const y = e.clientY - svgRect.top;
  const rx = Math.min(x, state.marquee.startX);
  const ry = Math.min(y, state.marquee.startY);
  const rw = Math.abs(x - state.marquee.startX);
  const rh = Math.abs(y - state.marquee.startY);
  state.marquee.rectEl.setAttribute("x", rx);
  state.marquee.rectEl.setAttribute("y", ry);
  state.marquee.rectEl.setAttribute("width", rw);
  state.marquee.rectEl.setAttribute("height", rh);
  if (rw > 4 || rh > 4) state.hasDragged = true;
});

window.addEventListener("mouseup", () => {
  if (!state.marquee) return;
  if (state.hasDragged) {
    const vx1 = parseFloat(state.marquee.rectEl.getAttribute("x"));
    const vy1 = parseFloat(state.marquee.rectEl.getAttribute("y"));
    const vx2 = vx1 + parseFloat(state.marquee.rectEl.getAttribute("width"));
    const vy2 = vy1 + parseFloat(state.marquee.rectEl.getAttribute("height"));
    const cx1 = (vx1 - state.transform.x) / state.transform.scale;
    const cy1 = (vy1 - state.transform.y) / state.transform.scale;
    const cx2 = (vx2 - state.transform.x) / state.transform.scale;
    const cy2 = (vy2 - state.transform.y) / state.transform.scale;

    const hit = [];
    state.locData.forEach((d, name) => {
      const lx = parseFloat(d.rectEl.getAttribute("x"));
      const ly = parseFloat(d.rectEl.getAttribute("y"));
      const lw = parseFloat(d.rectEl.getAttribute("width"));
      const lh = parseFloat(d.rectEl.getAttribute("height"));
      if (lx < cx2 && lx + lw > cx1 && ly < cy2 && ly + lh > cy1) hit.push(name);
    });
    const allAlreadySelected = hit.length > 0 && hit.every(n => state.selectedLocs.has(n));
    if (allAlreadySelected) {
      hit.forEach(n => { clearSelectionVisual(n); state.selectedLocs.delete(n); });
    } else {
      hit.forEach(n => { if (!state.selectedLocs.has(n)) { applySelectionVisual(n); state.selectedLocs.add(n); } });
    }
    syncOverviewSelection();
  }
  state.marquee.rectEl.remove();
  state.marquee = null;
});

svg.addEventListener("click", (e) => {
  if (state.hasDragged) return;
  if (state.viewMode === "empty") return;
  const rect = e.target.closest(".loc-rect");
  if (rect) {
    selectLocation(rect.dataset.location, e.ctrlKey);
    if (state.viewMode === "customer") {
      const assignment = state.lastAssignments.find(a => a.location === rect.dataset.location);
      if (assignment) {
        state.selectedCustomer = { agency_alias: assignment.agency_alias, custom_num: assignment.custom_num };
        applyViewMode();
      }
    }
  } else {
    selectLocation(null);
  }
});

svg.addEventListener("dblclick", (e) => {
  if (state.viewMode === "empty") return;
  const rectEl = e.target.closest(".loc-rect");
  if (!rectEl) return;
  const name = rectEl.dataset.location;
  if (!state.selectedLocs.has(name)) selectLocation(name);
  const wasOpen = overviewPanel.classList.contains("open");
  setOverviewPanel(true);
  setTimeout(() => {
    document.querySelector(`#overview-list tr[data-location="${CSS.escape(name)}"]`)
      ?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, wasOpen ? 0 : 240);
});
