import { state, showToast } from "./state.js";
import { applyTransform, centerLocations } from "./transform.js";
import { setDefaultText, setAssignedText, selectDay } from "./assignments.js";

import "./selection.js";
import "./viewmode.js";
import "./panels.js";
import "./prebook.js";
import "./advanced.js";
import "./drag.js";
import "./import_export.js";
import "./empty.js";

const NS     = "http://www.w3.org/2000/svg";
const canvas = document.getElementById("map-canvas");

async function loadPalette() {
  try {
    const res = await fetch("/api/agencies");
    if (!res.ok) throw new Error(res.status);
    const agencies = await res.json();
    state.agencyColorMap = Object.fromEntries(agencies.map(a => [a.agency_alias, a.color ?? "#d1d5db"]));
    state.clusterMap     = Object.fromEntries(agencies.map(a => [a.agency_alias, { start_seq: a.start_seq, end_seq: a.end_seq, cluster_group: a.cluster_group }]));
    state.agencyOrder    = agencies.map(a => a.agency_alias);
    state.agencyData     = Object.fromEntries(agencies.map(a => [a.agency_alias, a]));
  } catch (e) {
    showToast("Failed to load agency data.");
    throw e;
  }
}

async function loadLocations() {
  let locations;
  try {
    const res = await fetch("/api/locations");
    if (!res.ok) throw new Error(res.status);
    locations = await res.json();
  } catch (e) {
    showToast("Failed to load warehouse locations.");
    return;
  }

  for (const loc of locations) {
    const cx = loc.x + loc.w / 2;
    const cy = loc.y + loc.h / 2;
    const g = document.createElementNS(NS, "g");

    const rect = document.createElementNS(NS, "rect");
    rect.setAttribute("x", loc.x);
    rect.setAttribute("y", loc.y);
    rect.setAttribute("width", loc.w);
    rect.setAttribute("height", loc.h);
    rect.setAttribute("class", "loc-rect");
    rect.dataset.location = loc.location;

    const text = document.createElementNS(NS, "text");
    setDefaultText(text, loc.location, cx, cy);

    if (loc.h > loc.w) {
      text.setAttribute("transform", `rotate(-90, ${cx}, ${cy})`);
    }

    g.appendChild(rect);
    g.appendChild(text);
    canvas.appendChild(g);
    state.locData.set(loc.location, { rectEl: rect, textEl: text, cx, cy });
  }

  const isReload = performance.getEntriesByType("navigation")[0]?.type === "reload";

  const savedTransform = sessionStorage.getItem("mapTransform");
  if (!isReload && savedTransform) {
    Object.assign(state.transform, JSON.parse(savedTransform));
    applyTransform();
  } else {
    centerLocations(locations);
  }

  const savedDay = sessionStorage.getItem("activeDay");
  if (!isReload && savedDay) selectDay(parseInt(savedDay));
}

loadPalette().then(loadLocations);
