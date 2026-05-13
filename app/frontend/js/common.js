// Delade hjälpare: navbar, toast, auth-check.

async function loadCurrentUser() {
  try {
    return await api.get("/api/auth/me");
  } catch (e) {
    return null;
  }
}

function showToast(message, kind = "info", durationMs = 4000) {
  const el = document.createElement("div");
  el.className = "toast" + (kind ? " " + kind : "");
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), durationMs);
}

function renderTopbar(user, activePage) {
  const bar = document.querySelector(".topbar");
  if (!bar) return;
  const nav = `
    <nav>
      <a href="/index.html"     class="${activePage === 'schedule' ? 'active' : ''}">Bemanning</a>
      <a href="/overblick.html" class="${activePage === 'overview' ? 'active' : ''}">Översikt</a>
      <a href="/personer.html"  class="${activePage === 'persons'  ? 'active' : ''}">Personer</a>
      <a href="/stallen.html"   class="${activePage === 'stallen'  ? 'active' : ''}">Ställen</a>
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
}

async function initPage(activePage) {
  const user = await loadCurrentUser();
  if (!user) {
    window.location.href = "/login.html";
    return null;
  }
  renderTopbar(user, activePage);
  return user;
}

window.showToast = showToast;
window.initPage = initPage;
