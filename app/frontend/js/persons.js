// Personregister – CRUD-vy.

let areas = [];

async function loadAreas() {
  areas = await api.get("/api/areas");
}

function areaName(id) {
  const a = areas.find((x) => x.id === id);
  return a ? a.name : "";
}

async function loadPersons() {
  const includeInactive = document.getElementById("show-inactive").checked;
  const persons = await api.get(`/api/persons?include_inactive=${includeInactive}`);
  const tbody = document.getElementById("persons-body");
  tbody.innerHTML = "";
  persons.forEach((p) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(p.name)}</td>
      <td>${escapeHtml(areaName(p.home_area_id))}</td>
      <td>${escapeHtml(p.comment || "")}</td>
      <td>${p.is_active ? "Ja" : "Nej"}</td>
      <td>${p.sort_order}</td>
      <td>
        <button data-edit="${p.id}">Redigera</button>
        ${p.is_active ? `<button data-delete="${p.id}" class="danger">Inaktivera</button>` : ""}
      </td>`;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll("button[data-edit]").forEach((b) =>
    b.addEventListener("click", () => openModal(persons.find((p) => p.id === Number(b.dataset.edit))))
  );
  tbody.querySelectorAll("button[data-delete]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm("Inaktivera person?")) return;
      await api.del(`/api/persons/${b.dataset.delete}`);
      loadPersons();
    })
  );
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );
}

function openModal(person) {
  const isEdit = !!person;
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal">
      <h2>${isEdit ? "Redigera person" : "Ny person"}</h2>
      <label>Namn</label>
      <input id="m-name" value="${escapeHtml(person?.name || "")}" />
      <label>Hemområde</label>
      <select id="m-area">
        <option value="">(inget)</option>
        ${areas.map((a) => `<option value="${a.id}" ${person?.home_area_id === a.id ? "selected" : ""}>${escapeHtml(a.name)}</option>`).join("")}
      </select>
      <label>Kommentar</label>
      <textarea id="m-comment" rows="2">${escapeHtml(person?.comment || "")}</textarea>
      <label>Sortering</label>
      <input id="m-sort" type="number" value="${person?.sort_order ?? 0}" />
      <label><input id="m-active" type="checkbox" ${person?.is_active !== false ? "checked" : ""} /> Aktiv</label>
      <div class="actions">
        <button id="m-cancel">Avbryt</button>
        <button class="primary" id="m-save">Spara</button>
      </div>
    </div>`;
  document.body.appendChild(backdrop);

  document.getElementById("m-cancel").addEventListener("click", () => backdrop.remove());
  document.getElementById("m-save").addEventListener("click", async () => {
    const payload = {
      name: document.getElementById("m-name").value.trim(),
      home_area_id: document.getElementById("m-area").value ? Number(document.getElementById("m-area").value) : null,
      comment: document.getElementById("m-comment").value || null,
      sort_order: Number(document.getElementById("m-sort").value) || 0,
      is_active: document.getElementById("m-active").checked,
    };
    if (!payload.name) { showToast("Namn krävs", "error"); return; }
    try {
      if (isEdit) await api.put(`/api/persons/${person.id}`, payload);
      else await api.post("/api/persons", payload);
      backdrop.remove();
      loadPersons();
    } catch (e) {
      showToast(e.message, "error");
    }
  });
}

(async () => {
  await initPage("persons");
  await loadAreas();
  await loadPersons();
  document.getElementById("new-person").addEventListener("click", () => openModal(null));
  document.getElementById("show-inactive").addEventListener("change", loadPersons);
})();
