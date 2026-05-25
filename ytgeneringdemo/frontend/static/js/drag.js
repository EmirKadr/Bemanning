import { state, showToast } from "./state.js";
import { loadAssignments } from "./assignments.js";
import { loadOverview } from "./prebook.js";
import { loadMissingAgencies } from "./panels.js";

const svg = document.getElementById("map-svg");

let locDrag = null;

function createGhost(label) {
  const el = document.createElement("div");
  el.className = "loc-drag-ghost";
  el.textContent = label;
  document.body.appendChild(el);
  return el;
}

function setDragTarget(name) {
  if (locDrag.currentTarget === name) return;
  if (locDrag.currentTarget) {
    state.locData.get(locDrag.currentTarget)?.rectEl.classList.remove("loc-rect--drag-target");
  }
  locDrag.currentTarget = name;
  if (name) {
    state.locData.get(name)?.rectEl.classList.add("loc-rect--drag-target");
  }
}

svg.addEventListener("mousedown", (e) => {
  if (!e.ctrlKey) return;
  const rectEl = e.target.closest(".loc-rect");
  if (!rectEl) return;

  const name = rectEl.dataset.location;
  const assignment = state.lastAssignments.find(a => a.location === name);
  if (!assignment) return;

  state.hasDragged = false;

  const label = assignment.custom_desc || assignment.agency_alias || name;
  const ghost = createGhost(label);
  ghost.style.left = (e.clientX + 14) + "px";
  ghost.style.top  = (e.clientY + 14) + "px";

  locDrag = {
    sourceName: name,
    ghostEl: ghost,
    currentTarget: null,
    startX: e.clientX,
    startY: e.clientY,
  };

  svg.classList.add("is-loc-dragging");
});

window.addEventListener("mousemove", (e) => {
  if (!locDrag) return;

  locDrag.ghostEl.style.left = (e.clientX + 14) + "px";
  locDrag.ghostEl.style.top  = (e.clientY + 14) + "px";

  const dx = e.clientX - locDrag.startX;
  const dy = e.clientY - locDrag.startY;
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) state.hasDragged = true;

  const el = document.elementFromPoint(e.clientX, e.clientY);
  const hovered = el?.closest(".loc-rect")?.dataset?.location;
  setDragTarget(hovered && hovered !== locDrag.sourceName ? hovered : null);
});

window.addEventListener("mouseup", async () => {
  if (!locDrag) return;

  const { sourceName, ghostEl, currentTarget } = locDrag;

  ghostEl.remove();
  svg.classList.remove("is-loc-dragging");
  if (currentTarget) {
    state.locData.get(currentTarget)?.rectEl.classList.remove("loc-rect--drag-target");
  }
  locDrag = null;

  if (!currentTarget || !state.hasDragged) return;

  const day = parseInt(sessionStorage.getItem("activeDay"));
  if (isNaN(day)) return;

  try {
    const res = await fetch("/api/assignments/swap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ loc_a: sourceName, loc_b: currentTarget, day }),
    });
    if (!res.ok) throw new Error(res.status);
    loadAssignments(day);
    loadOverview(day);
    loadMissingAgencies(day);
  } catch {
    showToast("Swap failed.");
  }
});
