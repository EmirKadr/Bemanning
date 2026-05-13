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
        <button data-schedule="${p.id}">Schema</button>
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
  tbody.querySelectorAll("button[data-schedule]").forEach((b) =>
    b.addEventListener("click", () => openScheduleModal(persons.find((p) => p.id === Number(b.dataset.schedule))))
  );
}

const DAY_LABELS = { 1: "Måndag", 2: "Tisdag", 3: "Onsdag", 4: "Torsdag", 5: "Fredag", 6: "Lördag", 7: "Söndag" };

async function openScheduleModal(person) {
  let template;
  try {
    template = await api.get(`/api/persons/${person.id}/schedule`);
  } catch (e) {
    showToast("Kunde inte ladda schema: " + e.message, "error");
    return;
  }

  const hoursFromOpts = Array.from({ length: 18 }, (_, i) => 6 + i)
    .map((h) => `<option value="${h}">${String(h).padStart(2, "0")}:00</option>`).join("");
  const hoursToOpts = Array.from({ length: 18 }, (_, i) => 7 + i)
    .map((h) => `<option value="${h}">${String(h).padStart(2, "0")}:00</option>`).join("");

  const rowFor = (d) => `
    <tr data-weekday="${d.weekday}">
      <td style="padding: 6px 10px; font-weight: bold;">${DAY_LABELS[d.weekday]}</td>
      <td><label><input type="checkbox" class="m-off" ${d.is_off ? "checked" : ""}/> Ledig</label></td>
      <td>Från <select class="m-from">${hoursFromOpts}</select></td>
      <td>Till <select class="m-to">${hoursToOpts}</select></td>
    </tr>`;

  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal" style="min-width: 480px;">
      <h2>Veckomall för ${escapeHtml(person.name)}</h2>
      <p class="note">Mallen används av Översikt för att veta vilka timmar att bemanna. Saknar du rader för en dag betyder det "ledig" om någon annan dag är sparad, annars 07-16 default.</p>
      <table style="margin-top: 12px;">
        <tbody id="sch-body">
          ${template.days.map(rowFor).join("")}
        </tbody>
      </table>
      <div class="actions">
        <button id="sch-default">Återställ alla till 07-16</button>
        <button id="sch-cancel">Avbryt</button>
        <button id="sch-save" class="primary">Spara</button>
      </div>
    </div>`;
  document.body.appendChild(backdrop);

  // Fyll initial värden
  template.days.forEach((d) => {
    const row = backdrop.querySelector(`tr[data-weekday="${d.weekday}"]`);
    row.querySelector(".m-from").value = String(d.start_hour ?? 7);
    row.querySelector(".m-to").value = String(d.end_hour ?? 16);
    updateRowDisabled(row);
  });

  backdrop.querySelectorAll(".m-off").forEach((cb) =>
    cb.addEventListener("change", (e) => updateRowDisabled(e.target.closest("tr")))
  );

  document.getElementById("sch-default").addEventListener("click", () => {
    backdrop.querySelectorAll("tr[data-weekday]").forEach((row) => {
      row.querySelector(".m-off").checked = false;
      row.querySelector(".m-from").value = "7";
      row.querySelector(".m-to").value = "16";
      updateRowDisabled(row);
    });
  });

  document.getElementById("sch-cancel").addEventListener("click", () => backdrop.remove());
  document.getElementById("sch-save").addEventListener("click", async () => {
    const days = [];
    for (const row of backdrop.querySelectorAll("tr[data-weekday]")) {
      const wd = Number(row.dataset.weekday);
      const isOff = row.querySelector(".m-off").checked;
      if (isOff) {
        days.push({ weekday: wd, is_off: true, start_hour: null, end_hour: null });
        continue;
      }
      const sh = Number(row.querySelector(".m-from").value);
      const eh = Number(row.querySelector(".m-to").value);
      if (sh >= eh) {
        showToast(`${DAY_LABELS[wd]}: Från måste vara mindre än Till`, "error");
        return;
      }
      days.push({ weekday: wd, is_off: false, start_hour: sh, end_hour: eh });
    }
    try {
      await api.put(`/api/persons/${person.id}/schedule`, { days });
      backdrop.remove();
      showToast("Schema sparat");
    } catch (e) {
      showToast(e.message, "error");
    }
  });
}

function updateRowDisabled(row) {
  const off = row.querySelector(".m-off").checked;
  row.querySelector(".m-from").disabled = off;
  row.querySelector(".m-to").disabled = off;
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
