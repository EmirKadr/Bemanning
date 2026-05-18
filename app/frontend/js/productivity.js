let productivityReport = null;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]
  );
}

function formatNumber(value, decimals = 0) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("sv-SE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatMetric(value) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const decimals = Math.abs(Number(value)) < 10 && !Number.isInteger(Number(value)) ? 1 : 0;
  return formatNumber(value, decimals);
}

function formatPercent(value) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  return (Number(value) * 100).toLocaleString("sv-SE", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }) + " %";
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
  });
}

function metricClass(value) {
  if (value == null) return "";
  if (value >= 1) return " good";
  if (value >= 0.85) return " warn";
  return " low";
}

function activeGroupFilter() {
  return document.getElementById("productivityGroupFilter").value;
}

function activeSearch() {
  return document.getElementById("productivitySearch").value.trim().toLowerCase();
}

function sectionMatches(section, search) {
  if (!search) return true;
  if (section.title.toLowerCase().includes(search)) return true;
  return section.rows.some((row) => row.user.toLowerCase().includes(search));
}

function filteredRows(section, search) {
  if (!search || section.title.toLowerCase().includes(search)) return section.rows;
  return section.rows.filter((row) => row.user.toLowerCase().includes(search));
}

function renderSummary(report) {
  const summary = report.summary || {};
  const items = [
    ["Rader", formatNumber(summary.total_rows)],
    ["Timmar", formatNumber(summary.worked_hours)],
    ["Rader/tim", formatMetric(summary.rows_per_hour)],
    ["Snitt mot mål", formatPercent(summary.average_productivity_pct)],
  ];

  document.getElementById("productivitySummary").innerHTML = items.map(([label, value]) => `
    <div class="productivity-kpi">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `).join("");
}

function renderSources(report) {
  const sources = Object.values(report.sources || {});
  document.getElementById("productivitySources").innerHTML = sources.map((source) => `
    <div class="productivity-source">
      <span>${escapeHtml(source.label)}</span>
      <strong>${escapeHtml(source.name)}</strong>
      <small>${formatNumber(source.rows)} rader</small>
    </div>
  `).join("");
}

function renderGroupFilter(report) {
  const select = document.getElementById("productivityGroupFilter");
  const current = select.value || "all";
  select.innerHTML = '<option value="all">Alla</option>' + (report.groups || [])
    .map((group) => `<option value="${escapeHtml(group.id)}">${escapeHtml(group.title)}</option>`)
    .join("");
  select.value = Array.from(select.options).some((option) => option.value === current) ? current : "all";
}

function renderSection(section, hours, search) {
  const rows = filteredRows(section, search);
  const hourHeaders = hours.map((hour) => `<th>${String(hour).padStart(2, "0")}</th>`).join("");
  const emptyRow = `
    <tr>
      <td colspan="${hours.length + 9}" class="muted-cell">Inga rader</td>
    </tr>`;

  const body = rows.length ? rows.map((row) => {
    const hourCells = hours.map((hour) => {
      const value = row.hourly[String(hour)] || "";
      return `<td class="${value ? "has-work" : ""}">${value ? escapeHtml(value) : ""}</td>`;
    }).join("");
    return `
      <tr>
        <td class="name">${escapeHtml(row.user)}</td>
        ${hourCells}
        <td>${formatNumber(row.total_rows)}</td>
        <td>${row.total_kolli == null ? "-" : formatNumber(row.total_kolli)}</td>
        <td>${row.total_weight == null ? "-" : formatNumber(row.total_weight, 1)}</td>
        <td>${formatMetric(row.rows_per_hour)}</td>
        <td>${formatMetric(row.worked_hours)}</td>
        <td>${formatMetric(row.target_per_hour)}</td>
        <td class="productivity-pct${metricClass(row.productivity_pct)}">${formatPercent(row.productivity_pct)}</td>
      </tr>`;
  }).join("") : emptyRow;

  return `
    <section class="productivity-panel">
      <div class="productivity-panel-header">
        <div>
          <h3>${escapeHtml(section.title)}</h3>
          <span>${escapeHtml(section.target_company)} · ${escapeHtml(section.process)}</span>
        </div>
        <div class="productivity-panel-score${metricClass(section.productivity_pct)}">
          ${formatPercent(section.productivity_pct)}
        </div>
      </div>
      <div class="table-wrap productivity-table-wrap">
        <table class="productivity-table">
          <thead>
            <tr>
              <th class="name">Användare</th>
              ${hourHeaders}
              <th>Rader</th>
              <th>Kolli</th>
              <th>Vikt</th>
              <th>Rad/tim</th>
              <th>Timmar</th>
              <th>Mål</th>
              <th>%</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </section>`;
}

function renderContent() {
  if (!productivityReport) return;
  const content = document.getElementById("productivityContent");
  const groupFilter = activeGroupFilter();
  const search = activeSearch();
  const hours = productivityReport.hours || [];

  const groups = (productivityReport.groups || [])
    .filter((group) => groupFilter === "all" || group.id === groupFilter)
    .map((group) => ({
      ...group,
      sections: group.sections.filter((section) => sectionMatches(section, search)),
    }))
    .filter((group) => group.sections.length);

  if (!groups.length) {
    content.innerHTML = '<div class="empty-state">Ingen produktivitet matchade filtret.</div>';
    return;
  }

  content.innerHTML = groups.map((group) => `
    <section class="productivity-group">
      <h2>${escapeHtml(group.title)}</h2>
      <div class="productivity-section-list">
        ${group.sections.map((section) => renderSection(section, hours, search)).join("")}
      </div>
    </section>
  `).join("");
}

async function loadProductivity() {
  const status = document.getElementById("productivityStatus");
  const dateInput = document.getElementById("productivityDate");
  status.textContent = "Läser produktivitet...";
  try {
    const params = new URLSearchParams();
    if (dateInput.value) params.set("date", dateInput.value);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    productivityReport = await api.get(`/api/productivity${suffix}`);
    if (productivityReport.date) dateInput.value = productivityReport.date;
    const dates = productivityReport.available_dates || [];
    if (dates.length) {
      dateInput.min = dates[0];
      dateInput.max = dates[dates.length - 1];
    }
    renderGroupFilter(productivityReport);
    renderSummary(productivityReport);
    renderSources(productivityReport);
    renderContent();
    status.textContent = `${productivityReport.date} · uppdaterad ${formatTimestamp(productivityReport.generated_at)}`;
  } catch (error) {
    productivityReport = null;
    document.getElementById("productivitySummary").innerHTML = "";
    document.getElementById("productivitySources").innerHTML = "";
    document.getElementById("productivityContent").innerHTML = "";
    status.textContent = error.message || "Kunde inte läsa produktivitet.";
    showToast(status.textContent, "error", 7000);
  }
}

(async () => {
  const user = await initPage("productivity", { requireSuperUser: true });
  if (!user) return;

  document.getElementById("refreshProductivityBtn").addEventListener("click", loadProductivity);
  document.getElementById("productivityDate").addEventListener("change", loadProductivity);
  document.getElementById("productivityGroupFilter").addEventListener("change", renderContent);
  document.getElementById("productivitySearch").addEventListener("input", renderContent);
  await loadProductivity();
})();
