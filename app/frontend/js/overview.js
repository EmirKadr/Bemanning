// Översikt-vy – kalender per vecka, rader=personer, kolumner=dagar.

const DAYS = { 1: "Måndag", 2: "Tisdag", 3: "Onsdag", 4: "Torsdag", 5: "Fredag", 6: "Lördag", 7: "Söndag" };

const state = {
  year: 0,
  week: 0,
  areaId: null,
  areas: [],
  activities: [],
  activitiesActive: [],
  persons: [],
  matrix: [],  // [{person_id, weekday, activity_id, mixed, hours_total, template_hours}, ...]
};


// ---- ISO-vecka ----
function isoWeek(d = new Date()) {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((date - yearStart) / 86400000 + 1) / 7);
  return { year: date.getUTCFullYear(), week };
}

function isoWeekToMonday(year, week) {
  // Hämta måndag i ISO-veckan
  const jan4 = new Date(Date.UTC(year, 0, 4));
  const jan4Dow = jan4.getUTCDay() || 7;
  const week1Mon = new Date(jan4);
  week1Mon.setUTCDate(jan4.getUTCDate() - (jan4Dow - 1));
  const monday = new Date(week1Mon);
  monday.setUTCDate(week1Mon.getUTCDate() + (week - 1) * 7);
  return monday;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );
}

function activityById(id) {
  return state.activities.find((a) => a.id === id);
}
function colorFor(activityId) {
  const a = activityById(activityId);
  return a ? a.color : "#ffffff";
}


// ---- Rendering ----
function buildHeader() {
  const header = document.getElementById("headerRow");
  while (header.children.length > 1) header.removeChild(header.lastChild);
  const monday = isoWeekToMonday(state.year, state.week);
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday);
    d.setUTCDate(monday.getUTCDate() + i);
    const th = document.createElement("th");
    const wd = i + 1;
    th.textContent = `${DAYS[wd].slice(0, 3)} ${d.getUTCDate()}/${d.getUTCMonth() + 1}`;
    header.appendChild(th);
  }
}

function buildBody() {
  const body = document.getElementById("overviewBody");
  body.innerHTML = "";

  // Bygg lookup för matris
  const lookup = new Map();
  state.matrix.forEach((m) => lookup.set(`${m.person_id}:${m.weekday}`, m));

  state.persons.forEach((p) => {
    const tr = document.createElement("tr");
    tr.dataset.personId = p.id;
    const nameTd = document.createElement("td");
    nameTd.className = "name";
    nameTd.textContent = p.name;
    tr.appendChild(nameTd);

    for (let wd = 1; wd <= 7; wd++) {
      const cell = lookup.get(`${p.id}:${wd}`) || { activity_id: null, mixed: false, hours_total: 0, template_hours: 0 };
      const td = document.createElement("td");
      td.className = "day";
      td.dataset.personId = p.id;
      td.dataset.weekday = wd;
      renderDayCell(td, cell);
      tr.appendChild(td);
    }

    body.appendChild(tr);
  });
}

function renderDayCell(td, cell) {
  td.innerHTML = "";
  td.classList.remove("mixed", "is-off");
  td.style.background = "#fff";

  const isOff = cell.template_hours === 0;
  if (isOff) {
    td.classList.add("is-off");
    td.textContent = "Ledig";
    return;
  }

  if (cell.mixed) td.classList.add("mixed");
  else td.style.background = colorFor(cell.activity_id);

  const sel = document.createElement("select");
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "–";
  sel.appendChild(empty);
  state.activitiesActive.forEach((act) => {
    const opt = document.createElement("option");
    opt.value = String(act.id);
    opt.textContent = act.label;
    opt.style.background = act.color;
    sel.appendChild(opt);
  });
  sel.value = cell.activity_id ? String(cell.activity_id) : "";

  sel.addEventListener("change", () => onDayChange(td, sel, cell));
  td.appendChild(sel);

  const info = document.createElement("div");
  info.className = "hour-info";
  if (cell.mixed) info.textContent = `Blandat (${cell.hours_total}h)`;
  else if (cell.activity_id) info.textContent = `${cell.hours_total}/${cell.template_hours}h`;
  else info.textContent = `0/${cell.template_hours}h`;
  td.appendChild(info);
}

async function onDayChange(td, sel, cell) {
  const newActivityId = sel.value ? Number(sel.value) : null;
  if (cell.mixed && !confirm("Denna dag har flera olika aktiviteter. Skriv över med samma värde?")) {
    sel.value = cell.activity_id ? String(cell.activity_id) : "";
    return;
  }

  try {
    const resp = await api.post("/api/overview/day", {
      person_id: Number(td.dataset.personId),
      year: state.year, week: state.week,
      weekday: Number(td.dataset.weekday),
      activity_id: newActivityId,
    });
    showToast(`Bemannade ${resp.written} h, tog bort ${resp.deleted} h`);
    await load();
  } catch (e) {
    showToast("Kunde inte spara: " + e.message, "error");
    sel.value = cell.activity_id ? String(cell.activity_id) : "";
  }
}


// ---- Load ----
async function loadInitial() {
  const [areas, activities, activitiesAll] = await Promise.all([
    api.get("/api/areas"),
    api.get("/api/activities"),
    api.get("/api/activities?include_inactive=true"),
  ]);
  state.areas = areas;
  state.activitiesActive = activities;
  state.activities = activitiesAll;

  const sel = document.getElementById("areaSelect");
  sel.innerHTML = "";
  const allOpt = document.createElement("option");
  allOpt.value = "";
  allOpt.textContent = "Alla";
  sel.appendChild(allOpt);
  areas.forEach((a) => {
    const opt = document.createElement("option");
    opt.value = a.id; opt.textContent = a.name;
    sel.appendChild(opt);
  });
  if (areas.length > 0) state.areaId = areas[0].id;
  sel.value = state.areaId == null ? "" : String(state.areaId);
}

async function load() {
  const data = await api.get(
    `/api/overview?year=${state.year}&week=${state.week}` +
      (state.areaId ? `&area_id=${state.areaId}` : "")
  );
  state.persons = data.persons;
  state.matrix = data.matrix;

  const areaName = state.areaId == null ? "Alla" : (state.areas.find((a) => a.id === state.areaId)?.name || "");
  document.getElementById("sectionTitle").textContent = `Översikt – ${areaName} – V${state.week}/${state.year}`;

  buildHeader();
  buildBody();
}

function shiftWeek(delta) {
  state.week += delta;
  if (state.week < 1) { state.year -= 1; state.week = 52; }
  if (state.week > 53) { state.year += 1; state.week = 1; }
  document.getElementById("yearInput").value = state.year;
  document.getElementById("weekInput").value = state.week;
  load();
}


// ---- Init ----
(async () => {
  await initPage("overview");
  await loadInitial();

  const now = isoWeek();
  state.year = now.year;
  state.week = now.week;

  document.getElementById("yearInput").value = state.year;
  document.getElementById("weekInput").value = state.week;

  await load();

  const onControlChange = async () => {
    state.year = Number(document.getElementById("yearInput").value) || state.year;
    state.week = Number(document.getElementById("weekInput").value) || state.week;
    const areaVal = document.getElementById("areaSelect").value;
    state.areaId = areaVal === "" ? null : Number(areaVal);
    await load();
  };

  document.getElementById("yearInput").addEventListener("change", onControlChange);
  document.getElementById("weekInput").addEventListener("change", onControlChange);
  document.getElementById("areaSelect").addEventListener("change", onControlChange);
  document.getElementById("reloadBtn").addEventListener("click", onControlChange);
  document.getElementById("prevWeek").addEventListener("click", () => shiftWeek(-1));
  document.getElementById("nextWeek").addEventListener("click", () => shiftWeek(1));
})();
