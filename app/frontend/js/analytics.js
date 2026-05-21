let currentUser = null;
let users = [];
let persons = [];
let activities = [];
let areas = [];

const ENTITY_LABELS = {
  schedule_cell: "Schema",
  person: "Person",
  person_schedule_template: "Standardschema",
  activity: "Aktivitet",
  area: "Område",
  user: "Användare",
  data_fetch: "Hämta data",
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]
  );
}

function formatTimestamp(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("sv-SE", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function userLabel(entry) {
  if (entry.display_name) return `${entry.display_name} (${entry.username || "okänd"})`;
  if (entry.username) return entry.username;
  return "System";
}

function entityLabel(entityType) {
  return ENTITY_LABELS[entityType] || entityType || "";
}

function personName(personId) {
  const person = persons.find((item) => item.id === Number(personId));
  return person ? person.name : `Person #${personId}`;
}

function activityLabel(activityId) {
  if (activityId == null) return "-";
  const activity = activities.find((item) => item.id === Number(activityId));
  return activity ? activity.label : `Aktivitet #${activityId}`;
}

function areaName(areaId) {
  if (areaId == null) return "-";
  const area = areas.find((item) => item.id === Number(areaId));
  return area ? area.name : `Område #${areaId}`;
}

function formatFieldValue(key, value) {
  if (value == null) return "-";
  if (key === "home_area_id" || key === "area_id") return areaName(value);
  if (key === "home_activity_id" || key === "activity_id" || key === "summary_activity_id") return activityLabel(value);
  if (key === "is_active" || key === "is_off" || key === "empty_override") return value ? "Ja" : "Nej";
  if (Array.isArray(value)) return value.join(", ") || "-";
  return String(value);
}

function summarizeChanges(oldValue, newValue) {
  const before = oldValue || {};
  const after = newValue || {};
  const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)]));
  const changed = keys
    .filter((key) => JSON.stringify(before[key]) !== JSON.stringify(after[key]))
    .slice(0, 6);
  if (!changed.length) return "Ingen detalj";
  return changed
    .map((key) => `${key}: ${formatFieldValue(key, before[key])} -> ${formatFieldValue(key, after[key])}`)
    .join(" | ");
}

function objectSummary(entry) {
  const snapshot = entry.new_value || entry.old_value || {};
  if (entry.entity_type === "person") return snapshot.name || `Person #${entry.entity_id}`;
  if (entry.entity_type === "activity") return snapshot.label || snapshot.code || `Aktivitet #${entry.entity_id}`;
  if (entry.entity_type === "area") return snapshot.name || snapshot.code || `Område #${entry.entity_id}`;
  if (entry.entity_type === "user") return snapshot.username || `Användare #${entry.entity_id}`;
  if (entry.entity_type === "schedule_cell") {
    const person = snapshot.person_id ? personName(snapshot.person_id) : `Cell #${entry.entity_id}`;
    const hour = snapshot.hour != null ? ` ${String(snapshot.hour).padStart(2, "0")}:00` : "";
    return person + hour;
  }
  if (entry.entity_type === "person_schedule_template") {
    const weekday = snapshot.weekday != null ? `Dag ${snapshot.weekday}` : `Mall #${entry.entity_id}`;
    return weekday;
  }
  if (entry.entity_type === "data_fetch") {
    return snapshot.view_label || snapshot.view || "Hämta data";
  }
  return `${entityLabel(entry.entity_type)} #${entry.entity_id}`;
}

function detailSummary(entry) {
  const snapshot = entry.new_value || entry.old_value || {};
  if (entry.entity_type === "schedule_cell") {
    const minuteStart = snapshot.minute_start ?? 0;
    const minuteEnd = snapshot.minute_end ?? 60;
    const activity = snapshot.activity_id == null ? "-" : activityLabel(snapshot.activity_id);
    const emptyFlag = snapshot.empty_override ? " (tom override)" : "";
    return `${String(snapshot.hour ?? "?").padStart(2, "0")}:00 ${minuteStart}-${minuteEnd}, aktivitet: ${activity}${emptyFlag}`;
  }
  if (entry.entity_type === "person_schedule_template") {
    if (snapshot.is_off) return `Dag ${snapshot.weekday}: ledig`;
    return `Dag ${snapshot.weekday}: ${snapshot.start_hour ?? "-"}-${snapshot.end_hour ?? "-"}`;
  }
  if (entry.entity_type === "data_fetch") {
    const parts = [];
    if (snapshot.message) parts.push(String(snapshot.message));
    if (snapshot.status_code) parts.push(`HTTP ${snapshot.status_code}`);
    if (snapshot.error_id) parts.push(`Fel-id ${snapshot.error_id}`);
    if (snapshot.total_rows != null) parts.push(`${snapshot.total_rows} rader`);
    return parts.join(" | ") || "Hämta data";
  }
  return summarizeChanges(entry.old_value, entry.new_value);
}

function periodStartIso(period) {
  const now = new Date();
  if (period === "24h") return new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString();
  if (period === "7d") return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
  if (period === "30d") return new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();
  return null;
}

function currentParams(limit = 200) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));

  const period = document.getElementById("periodSelect").value;
  const fromAt = periodStartIso(period);
  if (fromAt) params.set("from_at", fromAt);

  const userId = document.getElementById("userFilter").value;
  if (userId) params.set("user_id", userId);

  const entityType = document.getElementById("entityFilter").value.trim();
  if (entityType) params.set("entity_type", entityType);

  const action = document.getElementById("actionFilter").value.trim();
  if (action) params.set("action", action);

  const entityId = document.getElementById("entityIdFilter").value.trim();
  if (entityId) params.set("entity_id", entityId);

  return params;
}

function renderBuckets(bodyId, buckets) {
  const body = document.getElementById(bodyId);
  body.innerHTML = "";
  if (!buckets.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="2" class="muted-cell">Inga poster</td>`;
    body.appendChild(tr);
    return;
  }

  buckets.forEach((bucket) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(bucket.label)}</td>
      <td>${escapeHtml(bucket.count)}</td>`;
    body.appendChild(tr);
  });
}

function renderSummary(summary) {
  document.getElementById("totalEvents").textContent = String(summary.total_events || 0);
  document.getElementById("recentEvents").textContent = String(summary.events_last_24h || 0);
  document.getElementById("uniqueUsers").textContent = String(summary.unique_users || 0);
  renderBuckets("topUsersBody", summary.top_users || []);
  renderBuckets("topActionsBody", summary.top_actions || []);
  renderBuckets("topEntitiesBody", summary.top_entities || []);
}

function renderAuditRows(entries) {
  const body = document.getElementById("auditBody");
  body.innerHTML = "";

  if (!entries.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="6" class="muted-cell">Ingen historik matchade filtret.</td>`;
    body.appendChild(tr);
    return;
  }

  entries.forEach((entry) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(formatTimestamp(entry.created_at))}</td>
      <td>${escapeHtml(userLabel(entry))}</td>
      <td>${escapeHtml(entityLabel(entry.entity_type))}</td>
      <td>${escapeHtml(entry.action)}</td>
      <td>${escapeHtml(objectSummary(entry))}</td>
      <td class="log-detail">${escapeHtml(detailSummary(entry))}</td>`;
    body.appendChild(tr);
  });
}

function fillUserFilter() {
  const select = document.getElementById("userFilter");
  select.innerHTML = '<option value="">Alla</option>';
  users.forEach((user) => {
    const option = document.createElement("option");
    option.value = String(user.id);
    option.textContent = user.display_name || user.username;
    select.appendChild(option);
  });
}

async function loadLookups() {
  const [usersResp, personsResp, activitiesResp, areasResp] = await Promise.all([
    api.get("/api/users?include_inactive=true"),
    api.get("/api/persons?include_inactive=true"),
    api.get("/api/activities?include_inactive=true"),
    api.get("/api/areas?include_inactive=true"),
  ]);
  users = usersResp;
  persons = personsResp;
  activities = activitiesResp;
  areas = areasResp;
  fillUserFilter();
}

async function refreshAnalytics() {
  const params = currentParams();
  const [summary, entries] = await Promise.all([
    api.get(`/api/audit/summary?${params.toString()}`),
    api.get(`/api/audit?${params.toString()}`),
  ]);
  renderSummary(summary);
  renderAuditRows(entries);
}

(async () => {
  currentUser = await initPage("analytics", { requireSuperUser: true });
  if (!currentUser) return;

  await loadLookups();
  await refreshAnalytics();

  document.getElementById("refreshAuditBtn").addEventListener("click", refreshAnalytics);
  ["periodSelect", "userFilter", "entityFilter"].forEach((id) => {
    document.getElementById(id).addEventListener("change", refreshAnalytics);
  });
  ["actionFilter", "entityIdFilter"].forEach((id) => {
    document.getElementById(id).addEventListener("keydown", (event) => {
      if (event.key === "Enter") void refreshAnalytics();
    });
  });
})();
