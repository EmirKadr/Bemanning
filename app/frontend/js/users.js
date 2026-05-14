let currentUser = null;
let users = [];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]
  );
}

function roleLabel(user) {
  if (user?.is_super_admin) return "Super admin";
  const role = user?.role;
  return role === "admin" ? "Administratör" : "Arbetsledare";
}

function formatDate(value) {
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

async function loadUsers() {
  const includeInactive = document.getElementById("show-inactive").checked;
  users = await api.get(`/api/users?include_inactive=${includeInactive}`);
  renderUsers();
}

function renderUsers() {
  const tbody = document.getElementById("users-body");
  tbody.innerHTML = "";

  users.forEach((user) => {
    const tr = document.createElement("tr");
    const selfLabel = user.id === currentUser.id ? " (du)" : "";
    tr.innerHTML = `
      <td>${escapeHtml(user.username)}${escapeHtml(selfLabel)}</td>
      <td>${escapeHtml(user.display_name || "–")}</td>
      <td>${escapeHtml(roleLabel(user))}</td>
      <td>${user.is_active ? "Ja" : "Nej"}</td>
      <td>${escapeHtml(formatDate(user.created_at))}</td>
      <td>
        <button data-edit="${user.id}">Redigera</button>
        ${user.is_active ? `<button data-toggle="${user.id}" class="danger">Inaktivera</button>` : `<button data-toggle="${user.id}">Aktivera</button>`}
      </td>`;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll("button[data-edit]").forEach((button) =>
    button.addEventListener("click", () => openModal(users.find((user) => user.id === Number(button.dataset.edit))))
  );
  tbody.querySelectorAll("button[data-toggle]").forEach((button) =>
    button.addEventListener("click", async () => {
      const user = users.find((item) => item.id === Number(button.dataset.toggle));
      if (!user) return;
      const nextActive = !user.is_active;
      const confirmText = nextActive ? "Aktivera användaren?" : "Inaktivera användaren?";
      if (!confirm(confirmText)) return;
      try {
        await api.put(`/api/users/${user.id}`, { is_active: nextActive });
        await loadUsers();
      } catch (error) {
        showToast(error.message, "error");
      }
    })
  );
}

function openModal(user) {
  const isEdit = !!user;
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal">
      <h2>${isEdit ? "Redigera användare" : "Ny användare"}</h2>
      <label>Användarnamn</label>
      <input id="m-username" autocomplete="username" value="${escapeHtml(user?.username || "")}" />
      <label>Visningsnamn</label>
      <input id="m-display-name" value="${escapeHtml(user?.display_name || "")}" />
      <label>Roll</label>
      <select id="m-role">
        <option value="leader" ${user?.role !== "admin" ? "selected" : ""}>Arbetsledare</option>
        <option value="admin" ${user?.role === "admin" ? "selected" : ""}>Administratör</option>
      </select>
      <label>${isEdit ? "Nytt lösenord" : "Lösenord"}</label>
      <input id="m-password" type="password" autocomplete="new-password" />
      <p class="note">${isEdit ? "Lämna lösenord tomt om det inte ska ändras." : "Minst 8 tecken."}</p>
      <label><input id="m-active" type="checkbox" ${user?.is_active !== false ? "checked" : ""} /> Aktiv</label>
      <div class="actions">
        <button id="m-cancel">Avbryt</button>
        <button class="primary" id="m-save">Spara</button>
      </div>
    </div>`;
  document.body.appendChild(backdrop);

  document.getElementById("m-cancel").addEventListener("click", () => backdrop.remove());
  document.getElementById("m-save").addEventListener("click", async () => {
    const password = document.getElementById("m-password").value;
    const payload = {
      username: document.getElementById("m-username").value.trim(),
      display_name: document.getElementById("m-display-name").value.trim() || null,
      role: document.getElementById("m-role").value,
      is_active: document.getElementById("m-active").checked,
    };

    if (!payload.username) {
      showToast("Användarnamn krävs", "error");
      return;
    }
    if (!isEdit && password.length < 8) {
      showToast("Lösenord måste vara minst 8 tecken", "error");
      return;
    }
    if (password) payload.password = password;

    try {
      if (isEdit) {
        await api.put(`/api/users/${user.id}`, payload);
      } else {
        if (!payload.password) {
          showToast("Lösenord krävs", "error");
          return;
        }
        await api.post("/api/users", payload);
      }
      backdrop.remove();
      await loadUsers();
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}

(async () => {
  currentUser = await initPage("users", { requireAdmin: true });
  if (!currentUser) return;

  await loadUsers();
  document.getElementById("new-user").addEventListener("click", () => openModal(null));
  document.getElementById("show-inactive").addEventListener("change", loadUsers);
})();
