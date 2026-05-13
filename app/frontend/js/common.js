// Delade hjälpare: navbar, toast, auth-check.

async function loadCurrentUser() {
  try {
    return await api.get("/api/auth/me");
  } catch (e) {
    return null;
  }
}

function queueToast(message, kind = "info", durationMs = 4000) {
  sessionStorage.setItem("queued-toast", JSON.stringify({ message, kind, durationMs }));
}

function showToast(message, kind = "info", durationMs = 4000) {
  const el = document.createElement("div");
  el.className = "toast" + (kind ? " " + kind : "");
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), durationMs);
}

function flushQueuedToast() {
  const raw = sessionStorage.getItem("queued-toast");
  if (!raw) return;
  sessionStorage.removeItem("queued-toast");
  try {
    const toast = JSON.parse(raw);
    showToast(toast.message, toast.kind, toast.durationMs);
  } catch (e) {
    // Ignorera trasig sessionStorage-data.
  }
}

function renderTopbar(user, activePage) {
  const bar = document.querySelector(".topbar");
  if (!bar) return;
  const tips = activePage === "schedule" ? document.querySelector(".tips-fab") : null;
  const adminLink = user?.role === "admin"
    ? `<a href="/anvandare.html" class="${activePage === 'users' ? 'active' : ''}">Användare</a>`
    : "";
  const nav = `
    <nav>
      <a href="/index.html"     class="${activePage === 'schedule' ? 'active' : ''}">Bemanning</a>
      <a href="/overblick.html" class="${activePage === 'overview' ? 'active' : ''}">Översikt</a>
      <a href="/personer.html"  class="${activePage === 'persons'  ? 'active' : ''}">Personer</a>
      <a href="/stallen.html"   class="${activePage === 'stallen'  ? 'active' : ''}">Ställen</a>
      ${adminLink}
    </nav>`;
  const userInfo = user
    ? `<span class="user-info">${user.display_name || user.username} <a href="#" id="logout-link">Logga ut</a></span>`
    : "";
  bar.innerHTML = `<h1 id="page-title">Bemanning</h1>${nav}${userInfo}`;

  const logout = document.getElementById("logout-link");
  if (logout) {
    logout.addEventListener("click", async (e) => {
      e.preventDefault();
      await api.post("/api/auth/logout");
      window.location.href = "/login.html";
    });
  }

  if (tips) {
    const userInfoEl = bar.querySelector(".user-info");
    if (userInfoEl) bar.insertBefore(tips, userInfoEl);
    else bar.appendChild(tips);
  }
}

async function initPage(activePage, options = {}) {
  const user = await loadCurrentUser();
  if (!user) {
    window.location.href = "/login.html";
    return null;
  }
  if (options.requireAdmin && user.role !== "admin") {
    queueToast("Sidan kräver administratörsbehörighet", "error");
    window.location.href = "/index.html";
    return null;
  }
  renderTopbar(user, activePage);
  flushQueuedToast();
  return user;
}

window.showToast = showToast;
window.initPage = initPage;
window.queueToast = queueToast;
