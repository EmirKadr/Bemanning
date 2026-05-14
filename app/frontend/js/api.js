// Tunn fetch-wrapper. Skickar med session-cookie. 401 -> /login.html.

async function request(path, options = {}) {
  const { headers = {}, ...rest } = options;
  const resp = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...headers },
    ...rest,
  });

  if (resp.status === 401 && !path.startsWith("/api/auth/login") && !path.startsWith("/api/auth/me")) {
    if (!window.location.pathname.endsWith("/login.html")) {
      window.location.href = "/login.html";
    }
    throw new Error("Unauthorized");
  }

  if (resp.status === 204) return null;

  const ct = resp.headers.get("content-type") || "";
  const body = ct.includes("application/json") ? await resp.json() : await resp.text();

  if (!resp.ok) {
    const err = new Error(body?.detail || body?.error || `HTTP ${resp.status}`);
    err.status = resp.status;
    err.body = body;
    throw err;
  }
  return body;
}

const api = {
  get: (path, options = {}) => request(path, options),
  post: (path, data, options = {}) =>
    request(path, { ...options, method: "POST", body: JSON.stringify(data) }),
  put: (path, data, options = {}) =>
    request(path, { ...options, method: "PUT", body: JSON.stringify(data) }),
  del: (path, options = {}) => request(path, { ...options, method: "DELETE" }),
};

window.api = api;
