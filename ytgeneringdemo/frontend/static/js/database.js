const PAGE_SIZE = 200;
let currentTable = null;
let schema = [];
let totalRows = 0;
let pageOffset = 0;
let selectedRowids = new Set();
let activeFilters = {};

const tableList  = document.getElementById("db-table-list");
const mainArea   = document.getElementById("db-main");
const toolbar    = document.getElementById("db-toolbar");
const tableWrap  = document.getElementById("db-table-wrap");
const pagination = document.getElementById("db-pagination");
const emptyState = document.getElementById("db-empty");
const colMenu    = document.getElementById("db-col-menu");
const filterDrop = document.getElementById("db-filter-dropdown");

function toast(msg, type = "error") {
  const el = document.createElement("div");
  el.className = `toast toast--${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => {
    el.classList.add("toast--fade");
    el.addEventListener("transitionend", () => el.remove(), { once: true });
  }, 3000);
}

async function api(path, opts = {}) {
  const res = await fetch(`/api/db${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail ?? res.statusText;
    throw new Error(detail);
  }
  return res.json();
}

function filtersParam() {
  if (Object.keys(activeFilters).length === 0) return "";
  return `&filters=${encodeURIComponent(JSON.stringify(activeFilters))}`;
}

function removeFilter(col) {
  delete activeFilters[col];
  pageOffset = 0;
  loadRows();
}

function renderFilterChips() {
  const wrap = document.getElementById("db-filter-chips");
  if (!wrap) return;
  const entries = Object.entries(activeFilters);
  if (entries.length === 0) {
    wrap.style.display = "none";
    return;
  }
  wrap.style.display = "flex";
  wrap.innerHTML = entries.map(([col, val]) => {
    const display = val === null ? "NULL"
      : typeof val === "string" && val.startsWith("~") ? `contains "${val.slice(1)}"`
      : `"${val}"`;
    const escaped = String(display).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `<span class="db-chip">${col} = ${escaped}<button class="db-chip-x" data-col="${col}">&times;</button></span>`;
  }).join("");
  for (const btn of wrap.querySelectorAll(".db-chip-x")) {
    btn.addEventListener("click", () => removeFilter(btn.dataset.col));
  }
}

let filterCol = null;

async function openFilterDropdown(colName, anchorEl) {
  filterCol = colName;
  filterDrop.innerHTML = `<div class="db-fd-loading">Loading...</div>`;
  filterDrop.classList.add("open");

  const rect = anchorEl.getBoundingClientRect();
  filterDrop.style.left = rect.left + "px";
  filterDrop.style.top = rect.bottom + 2 + "px";

  const values = await api(`/tables/${currentTable}/distinct/${colName}?${filtersParam().replace(/^&/, "")}`);

  let html = `<div class="db-fd-search-wrap">
    <input class="db-fd-search" placeholder="Search or type value..." />
  </div>`;
  html += `<ul class="db-fd-list">`;
  for (const v of values) {
    const label = v === null ? "NULL" : String(v);
    const escaped = label.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    html += `<li class="db-fd-item" data-value="${escaped}">${escaped}</li>`;
  }
  if (values.length === 0) {
    html += `<li class="db-fd-empty">No values</li>`;
  }
  html += `</ul>`;

  filterDrop.innerHTML = html;

  const searchInput = filterDrop.querySelector(".db-fd-search");
  const listItems = filterDrop.querySelectorAll(".db-fd-item");

  searchInput.focus();
  searchInput.addEventListener("input", () => {
    const q = searchInput.value.toLowerCase();
    for (const li of listItems) {
      li.style.display = li.textContent.toLowerCase().includes(q) ? "" : "none";
    }
  });
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && searchInput.value.trim()) {
      activeFilters[filterCol] = "~" + searchInput.value.trim();
      pageOffset = 0;
      closeFilterDropdown();
      loadRows();
    }
    if (e.key === "Escape") closeFilterDropdown();
  });

  for (const li of listItems) {
    li.addEventListener("click", () => {
      const raw = li.dataset.value;
      activeFilters[filterCol] = raw === "NULL" ? null : raw;
      pageOffset = 0;
      closeFilterDropdown();
      loadRows();
    });
  }
}

function closeFilterDropdown() {
  filterDrop.classList.remove("open");
  filterCol = null;
}

document.addEventListener("click", (e) => {
  if (!filterDrop.contains(e.target) && !e.target.closest(".db-col-header")) {
    closeFilterDropdown();
  }
});

async function loadTables() {
  const tables = await api("/tables");
  tableList.innerHTML = "";
  for (const name of tables) {
    const li = document.createElement("li");
    li.className = "db-table-item";
    li.textContent = name;
    li.addEventListener("click", () => selectTable(name));
    tableList.appendChild(li);
  }
}

async function selectTable(name) {
  currentTable = name;
  pageOffset = 0;
  selectedRowids.clear();
  activeFilters = {};

  for (const li of tableList.children) {
    li.classList.toggle("active", li.textContent === name);
  }

  schema = await api(`/tables/${name}/schema`);
  emptyState.style.display = "none";
  toolbar.style.display = "flex";
  tableWrap.style.display = "block";
  pagination.style.display = "flex";

  await loadRows();
}

async function loadRows() {
  const data = await api(`/tables/${currentTable}/rows?limit=${PAGE_SIZE}&offset=${pageOffset}${filtersParam()}`);
  totalRows = data.total;
  selectedRowids.clear();
  renderToolbar();
  renderTable(data.rows);
  renderPagination();
}

function renderToolbar() {
  toolbar.innerHTML = `
    <span class="db-toolbar-title">
      ${currentTable}
      <span class="db-toolbar-count">${totalRows} rows</span>
    </span>
    <div id="db-filter-chips" class="db-filter-chips" style="display:none;"></div>
    <button class="db-btn db-btn--ghost" id="btn-add-row">+ Row</button>
    <button class="db-btn db-btn--ghost" id="btn-add-col">+ Column</button>
    <button class="db-btn db-btn--danger" id="btn-delete-rows" disabled>Delete selected</button>
    <button class="db-btn db-btn--danger" id="btn-clear-table">Clear table</button>
  `;
  document.getElementById("btn-add-row").addEventListener("click", addRow);
  document.getElementById("btn-add-col").addEventListener("click", addColumn);
  document.getElementById("btn-delete-rows").addEventListener("click", deleteSelected);
  document.getElementById("btn-clear-table").addEventListener("click", clearTable);
  renderFilterChips();
}

function updateDeleteBtn() {
  const btn = document.getElementById("btn-delete-rows");
  if (btn) {
    btn.disabled = selectedRowids.size === 0;
    btn.textContent = selectedRowids.size
      ? `Delete selected (${selectedRowids.size})`
      : "Delete selected";
  }
}

function renderTable(rows) {
  let html = `<table class="db-table"><thead><tr>`;
  html += `<th class="db-th-checkbox"><input type="checkbox" class="db-row-check" id="db-check-all"></th>`;
  html += `<th class="db-th-rowid">rowid</th>`;
  for (const col of schema) {
    const isFiltered = col.name in activeFilters;
    html += `<th class="db-col-header${isFiltered ? " db-col-filtered" : ""}" data-col="${col.name}">
      <span class="db-th-inner">
        ${col.name}
        <span class="db-col-type">${col.type || "—"}</span>
        ${col.pk ? '<span class="db-col-type">pk</span>' : ""}
      </span>
    </th>`;
  }
  html += `</tr></thead><tbody>`;

  for (const row of rows) {
    const rid = row.rowid;
    html += `<tr data-rowid="${rid}">`;
    html += `<td class="db-cell-checkbox"><input type="checkbox" class="db-row-check" data-rowid="${rid}"></td>`;
    html += `<td class="db-cell-rowid">${rid}</td>`;
    for (const col of schema) {
      const val = row[col.name];
      if (val === null || val === undefined) {
        html += `<td class="db-cell-editable db-cell-null" data-col="${col.name}" data-rowid="${rid}">NULL</td>`;
      } else {
        const escaped = String(val).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        html += `<td class="db-cell-editable" data-col="${col.name}" data-rowid="${rid}">${escaped}</td>`;
      }
    }
    html += `</tr>`;
  }

  if (rows.length === 0) {
    html += `<tr><td colspan="${schema.length + 2}" style="text-align:center;color:var(--c-faint);padding:2rem;">No rows</td></tr>`;
  }

  html += `</tbody></table>`;
  tableWrap.innerHTML = html;

  wireTableEvents();
}

function wireTableEvents() {
  const checkAll = document.getElementById("db-check-all");
  checkAll?.addEventListener("change", (e) => {
    const checked = e.target.checked;
    for (const cb of tableWrap.querySelectorAll("tbody .db-row-check")) {
      cb.checked = checked;
      const rid = Number(cb.dataset.rowid);
      checked ? selectedRowids.add(rid) : selectedRowids.delete(rid);
      cb.closest("tr").classList.toggle("db-row-selected", checked);
    }
    updateDeleteBtn();
  });

  for (const cb of tableWrap.querySelectorAll("tbody .db-row-check")) {
    cb.addEventListener("change", (e) => {
      const rid = Number(e.target.dataset.rowid);
      if (e.target.checked) {
        selectedRowids.add(rid);
      } else {
        selectedRowids.delete(rid);
      }
      e.target.closest("tr").classList.toggle("db-row-selected", e.target.checked);
      updateDeleteBtn();
    });
  }

  for (const td of tableWrap.querySelectorAll(".db-cell-editable")) {
    td.addEventListener("dblclick", startCellEdit);
  }

  for (const th of tableWrap.querySelectorAll(".db-col-header")) {
    th.addEventListener("click", (e) => {
      e.stopPropagation();
      openFilterDropdown(th.dataset.col, th);
    });
  }

  for (const th of tableWrap.querySelectorAll(".db-col-header")) {
    th.addEventListener("contextmenu", openColMenu);
  }
}

function startCellEdit(e) {
  const td = e.currentTarget;
  if (td.querySelector(".db-cell-input")) return;

  const col = td.dataset.col;
  const rowid = Number(td.dataset.rowid);
  const isNull = td.classList.contains("db-cell-null");
  const oldVal = isNull ? "" : td.textContent;

  const input = document.createElement("input");
  input.className = "db-cell-input";
  input.value = oldVal;
  td.textContent = "";
  td.appendChild(input);
  input.focus();
  input.select();

  async function commit() {
    const newVal = input.value;
    try {
      let typed = newVal;
      if (newVal === "" || newVal.toLowerCase() === "null") {
        typed = null;
      } else if (!isNaN(newVal) && newVal.trim() !== "") {
        typed = Number(newVal);
      }

      await api(`/tables/${currentTable}/rows`, {
        method: "PATCH",
        body: JSON.stringify({ rowid, column: col, value: typed }),
      });

      td.textContent = typed === null ? "NULL" : String(typed);
      td.classList.toggle("db-cell-null", typed === null);
    } catch (err) {
      toast(err.message);
      td.textContent = oldVal;
      td.classList.toggle("db-cell-null", isNull);
    }
  }

  input.addEventListener("blur", commit);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") input.blur();
    if (e.key === "Escape") {
      input.removeEventListener("blur", commit);
      td.textContent = oldVal;
      td.classList.toggle("db-cell-null", isNull);
    }
  });
}

let menuCol = null;

function openColMenu(e) {
  e.preventDefault();
  menuCol = e.currentTarget.dataset.col;
  colMenu.style.left = e.clientX + "px";
  colMenu.style.top = e.clientY + "px";
  colMenu.classList.add("open");
}

function closeColMenu() {
  colMenu.classList.remove("open");
  menuCol = null;
}

document.addEventListener("click", closeColMenu);

document.getElementById("col-menu-rename")?.addEventListener("click", async () => {
  if (!menuCol) return;
  const newName = prompt(`Rename column "${menuCol}" to:`, menuCol);
  if (!newName || newName === menuCol) return;
  try {
    await api(`/tables/${currentTable}/columns`, {
      method: "PATCH",
      body: JSON.stringify({ old_name: menuCol, new_name: newName }),
    });
    toast("Column renamed", "success");
    await selectTable(currentTable);
  } catch (err) {
    toast(err.message);
  }
});

document.getElementById("col-menu-drop")?.addEventListener("click", async () => {
  if (!menuCol) return;
  if (!confirm(`Drop column "${menuCol}"? This cannot be undone.`)) return;
  try {
    await api(`/tables/${currentTable}/columns/${menuCol}`, { method: "DELETE" });
    toast("Column dropped", "success");
    await selectTable(currentTable);
  } catch (err) {
    toast(err.message);
  }
});

async function addRow() {
  const values = {};
  for (const col of schema) {
    if (!col.pk) values[col.name] = null;
  }
  try {
    await api(`/tables/${currentTable}/rows`, {
      method: "POST",
      body: JSON.stringify({ values }),
    });
    toast("Row added", "success");
    pageOffset = Math.max(0, Math.floor(totalRows / PAGE_SIZE) * PAGE_SIZE);
    await loadRows();
  } catch (err) {
    toast(err.message);
  }
}

async function addColumn() {
  const name = prompt("Column name:");
  if (!name) return;
  const type = prompt("Column type (TEXT, INTEGER, REAL):", "TEXT");
  if (!type) return;
  try {
    await api(`/tables/${currentTable}/columns`, {
      method: "POST",
      body: JSON.stringify({ name, type }),
    });
    toast("Column added", "success");
    await selectTable(currentTable);
  } catch (err) {
    toast(err.message);
  }
}

async function deleteSelected() {
  if (selectedRowids.size === 0) return;
  if (!confirm(`Delete ${selectedRowids.size} row(s)?`)) return;
  try {
    await api(`/tables/${currentTable}/rows`, {
      method: "DELETE",
      body: JSON.stringify({ rowids: [...selectedRowids] }),
    });
    toast(`${selectedRowids.size} row(s) deleted`, "success");
    selectedRowids.clear();
    await loadRows();
  } catch (err) {
    toast(err.message);
  }
}

async function clearTable() {
  if (!confirm(`Delete ALL rows in "${currentTable}"? This cannot be undone.`)) return;
  try {
    await api(`/tables/${currentTable}/rows/all`, { method: "DELETE" });
    toast(`All rows in "${currentTable}" deleted`, "success");
    pageOffset = 0;
    await loadRows();
  } catch (err) {
    toast(err.message);
  }
}

function renderPagination() {
  const page = Math.floor(pageOffset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(totalRows / PAGE_SIZE));

  pagination.innerHTML = `
    <span>Page ${page} of ${totalPages}</span>
    <div class="db-page-btns">
      <button class="db-page-btn" id="pg-first" ${page <= 1 ? "disabled" : ""}>First</button>
      <button class="db-page-btn" id="pg-prev" ${page <= 1 ? "disabled" : ""}>Prev</button>
      <button class="db-page-btn" id="pg-next" ${page >= totalPages ? "disabled" : ""}>Next</button>
      <button class="db-page-btn" id="pg-last" ${page >= totalPages ? "disabled" : ""}>Last</button>
    </div>
  `;

  document.getElementById("pg-first").addEventListener("click", () => goPage(0));
  document.getElementById("pg-prev").addEventListener("click", () => goPage(pageOffset - PAGE_SIZE));
  document.getElementById("pg-next").addEventListener("click", () => goPage(pageOffset + PAGE_SIZE));
  document.getElementById("pg-last").addEventListener("click", () => goPage((totalPages - 1) * PAGE_SIZE));
}

async function goPage(offset) {
  pageOffset = Math.max(0, offset);
  await loadRows();
  tableWrap.scrollTop = 0;
}

let pendingKey = null;
document.addEventListener("keydown", (e) => {
  if (e.target.matches("input, textarea, select")) return;
  const key = e.key.toLowerCase();
  if (pendingKey === "v" && key === "f") {
    pendingKey = null;
    if (Object.keys(activeFilters).length > 0) {
      activeFilters = {};
      pageOffset = 0;
      loadRows();
    }
    return;
  }
  pendingKey = key === "v" ? "v" : null;
});

loadTables();
