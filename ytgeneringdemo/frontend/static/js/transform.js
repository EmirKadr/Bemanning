import { state } from "./state.js";

const svg    = document.getElementById("map-svg");
const canvas = document.getElementById("map-canvas");
const grid   = document.getElementById("grid");

export function applyTransform() {
  const t = `translate(${state.transform.x}, ${state.transform.y}) scale(${state.transform.scale})`;
  canvas.setAttribute("transform", t);
  grid.setAttribute("patternTransform", t);
}

export function saveTransform() {
  sessionStorage.setItem("mapTransform", JSON.stringify(state.transform));
}

export function centerLocations(locations) {
  const rect = svg.getBoundingClientRect();
  const minX = Math.min(...locations.map(l => l.x));
  const minY = Math.min(...locations.map(l => l.y));
  const maxX = Math.max(...locations.map(l => l.x + l.w));
  const maxY = Math.max(...locations.map(l => l.y + l.h));
  const contentW = maxX - minX;
  const contentH = maxY - minY;
  const padding = 60;
  const scale = Math.min(
    (rect.width  - padding * 2) / contentW,
    (rect.height - padding * 2) / contentH
  );
  state.transform.scale = scale;
  state.transform.x = (rect.width  - contentW * scale) / 2 - minX * scale;
  state.transform.y = (rect.height - contentH * scale) / 2 - minY * scale;
  applyTransform();
}

let mapRotation = 0;
const rotateGroup = document.getElementById("map-rotate-group");
const rotateBtn   = document.getElementById("rotate-toggle");

export function getMapRotation() { return mapRotation; }

function applyRotation() {
  const { width, height } = svg.getBoundingClientRect();
  rotateGroup.style.transformOrigin = `${width / 2}px ${height / 2}px`;
  rotateGroup.style.transform = mapRotation === 0 ? "" : `rotate(${mapRotation}deg)`;
}

rotateBtn.addEventListener("click", () => {
  mapRotation = mapRotation === 0 ? 90 : 0;
  rotateBtn.classList.toggle("active", mapRotation !== 0);
  applyRotation();
});

svg.addEventListener("mousedown", (e) => {
  if (e.shiftKey) return;
  if (e.ctrlKey && e.target.closest(".loc-rect")) return;
  state.hasDragged = false;
  state.drag = {
    initX: state.transform.x,
    initY: state.transform.y,
    initClientX: e.clientX,
    initClientY: e.clientY,
  };
  svg.classList.add("is-dragging");
});

window.addEventListener("mousemove", (e) => {
  if (!state.drag) return;
  const dx = e.clientX - state.drag.initClientX;
  const dy = e.clientY - state.drag.initClientY;
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) state.hasDragged = true;
  if (mapRotation === 90) {
    state.transform.x = state.drag.initX + dy;
    state.transform.y = state.drag.initY - dx;
  } else {
    state.transform.x = state.drag.initX + dx;
    state.transform.y = state.drag.initY + dy;
  }
  applyTransform();
  saveTransform();
});

window.addEventListener("mouseup", () => {
  if (!state.drag) return;
  state.drag = null;
  svg.classList.remove("is-dragging");
});

svg.addEventListener("wheel", (e) => {
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
  const rect = svg.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  state.transform.x = mx - (mx - state.transform.x) * factor;
  state.transform.y = my - (my - state.transform.y) * factor;
  state.transform.scale *= factor;
  applyTransform();
  saveTransform();
}, { passive: false });
