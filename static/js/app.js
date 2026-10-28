/* FixTrack's small same-origin frontend. All displayed records come from Flask. */
const appRoot = document.getElementById("app");
const state = { user: null, csrf: "", page: "dashboard", notice: null, requests: [], locations: [] };
const pages = [
  ["dashboard", "Home / Dashboard"], ["add", "Add Record"], ["update", "Update Record"],
  ["delete", "Delete Record"], ["search", "Search Record"], ["reports", "Reports"]
];
const statuses = ["Pending", "In Progress", "Resolved"];
const priorities = ["Low", "Medium", "High"];

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

async function getCsrf() {
  const response = await fetch("/api/auth/csrf", { credentials: "same-origin" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not prepare a secure request.");
  state.csrf = data.csrf_token;
}

async function api(url, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { ...(options.headers || {}) };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    if (!state.csrf) await getCsrf();
    headers["X-CSRFToken"] = state.csrf;
  }
  let response;
  try {
    response = await fetch(url, { ...options, method, headers, credentials: "same-origin" });
  } catch (_error) {
    throw new Error("The FixTrack server could not be reached. Check that Flask is running.");
  }
  let data = {};
  try { data = await response.json(); } catch (_error) { data = {}; }
  if (!response.ok) throw new Error(data.error || data.message || `Request failed (${response.status}).`);
  return data;
}

function setNotice(message, kind = "error") {
  state.notice = message ? { message, kind } : null;
  const notice = document.getElementById("notice");
  if (!notice) return;
  notice.textContent = message || "";
  notice.hidden = !message;
  notice.className = `notice ${kind}`;
}

function noticeMarkup() {
  if (!state.notice) return '<div id="notice" class="notice" hidden></div>';
  return `<div id="notice" class="notice ${esc(state.notice.kind)}">${esc(state.notice.message)}</div>`;
}

function shell(content) {
  const shownPages = state.user.role === "Admin" ? pages : pages.filter(([id]) => id !== "reports");
  appRoot.innerHTML = `
    <header class="topbar">
      <div class="topbar-inner">
        <h1 class="brand">FixTrack<span>College Campus Maintenance</span></h1>
        <div class="identity"><span><strong>${esc(state.user.name)}</strong><span class="identity-role">${esc(state.user.role)}</span></span><button class="button secondary" data-action="logout">Log out</button></div>
      </div>
      <nav class="nav" aria-label="Main navigation">${shownPages.map(([id, label]) => `<button data-page="${id}" ${state.page === id ? 'aria-current="page"' : ""}>${label}</button>`).join("")}</nav>
    </header>
    <main class="main">${noticeMarkup()}${content}</main>
    <footer class="footer"><p>FixTrack records campus maintenance requests and their current status.</p><p>Displayed counts and records are read from the connected PostgreSQL database.</p></footer>`;
}

function loginScreen(message = "", mode = "login", kind = "error") {
  state.user = null;
  appRoot.innerHTML = `<main class="login-wrap"><section class="login-card">
    <h1 class="brand">FixTrack<span>College Campus Maintenance</span></h1>
    <p>Sign in or create a campus account to use FixTrack.</p>
    ${message ? `<div class="notice ${kind === "success" ? "success" : ""}" role="status">${esc(message)}</div>` : ""}
    ${mode === "login" ? `<form id="login-form"><div class="field"><label for="login-email">Email</label><input id="login-email" name="email" type="email" maxlength="150" autocomplete="username" required></div>
    <div class="field" style="margin-top:.8rem"><label for="login-password">Password</label><input id="login-password" name="password" type="password" autocomplete="current-password" required></div>
    <div class="form-actions"><button class="button" type="submit">Log in</button></div></form>` : `<form id="signup-form"><div class="field"><label for="signup-name">Full name</label><input id="signup-name" name="full_name" maxlength="100" autocomplete="name" required></div>
    <div class="field" style="margin-top:.8rem"><label for="signup-email">Email</label><input id="signup-email" name="email" type="email" maxlength="150" autocomplete="email" required></div>
    <div class="field" style="margin-top:.8rem"><label for="signup-password">Password (12–128 characters)</label><input id="signup-password" name="password" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></div>
    <div class="field" style="margin-top:.8rem"><label for="signup-confirm">Confirm password</label><input id="signup-confirm" name="confirm_password" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></div>
    <div class="form-actions"><button class="button" type="submit">Create account</button></div></form>`}
    <div class="form-actions auth-switch" role="tablist" aria-label="Account access"><button class="button ${mode === "login" ? "" : "secondary"}" type="button" role="tab" aria-selected="${mode === "login"}" data-auth-mode="login">Log in</button><button class="button ${mode === "signup" ? "" : "secondary"}" type="button" role="tab" aria-selected="${mode === "signup"}" data-auth-mode="signup">Sign up</button></div>
  </section></main>`;
}

function passwordChangeScreen() {
  appRoot.innerHTML = `<main class="login-wrap"><section class="login-card"><h1>Change password</h1><p>Your account must use a new password before you can continue.</p>${noticeMarkup()}
    <form id="forced-password-form"><div class="field"><label for="current-password">Current password</label><input id="current-password" name="current_password" type="password" autocomplete="current-password" required></div>
    <div class="field" style="margin-top:.8rem"><label for="new-password">New password (12–128 characters)</label><input id="new-password" name="password" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></div>
    <div class="field" style="margin-top:.8rem"><label for="confirm-password">Confirm new password</label><input id="confirm-password" name="confirm_password" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></div>
    <div class="form-actions"><button class="button" type="submit">Change password</button></div></form></section></main>`;
}

function empty(message) { return `<p class="empty">${esc(message)}</p>`; }
function date(value) { if (!value) return "—"; const d = new Date(value); return Number.isNaN(d.getTime()) ? esc(value) : esc(d.toLocaleString()); }
function table(headers, rows) {
  if (!rows.length) return empty("No matching records were found.");
  return `<div class="table-wrap"><table><thead><tr>${headers.map(([, label]) => `<th scope="col">${esc(label)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${headers.map(([key]) => `<td>${key === "reported_at" || key === "assigned_at" || key === "changed_at" ? date(row[key]) : esc(row[key] ?? "—")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function locationName(row) { return [row.building_name, row.area_name].filter(Boolean).join(" / "); }
function requestRows(rows, mode) {
  if (!rows.length) return empty("No maintenance requests match these criteria.");
  const canAdmin = state.user.role === "Admin";
  return `<div class="table-wrap"><table><thead><tr><th>ID</th><th>Request</th><th>Category</th><th>Priority</th><th>Status</th><th>Location</th><th>Reported</th>${mode ? "<th>Action</th>" : ""}</tr></thead><tbody>${rows.map((r) => `<tr>
    <td>${esc(r.request_id)}</td><td><strong>${esc(r.title)}</strong><br>${esc(r.description || "")}</td><td>${esc(r.category)}</td><td>${esc(r.priority)}</td><td>${esc(r.current_status)}</td><td>${esc(locationName(r))}</td><td>${date(r.reported_at)}</td>
    ${mode ? `<td><div class="actions">${mode === "update" ? `<button class="button small" data-edit="${esc(r.request_id)}">Edit</button>` : ""}<button class="button small" data-delete="${esc(r.request_id)}" data-admin-delete="${canAdmin}">Delete</button></div></td>` : ""}
    </tr>`).join("")}</tbody></table></div>`;
}

function searchForm(prefix = "search") {
  return `<form id="${prefix}-form" class="filter-grid">
    <div class="field"><label for="${prefix}-id">Request ID</label><input id="${prefix}-id" name="request_id" type="number" min="1" step="1"></div>
    <div class="field"><label for="${prefix}-title">Title contains</label><input id="${prefix}-title" name="title" maxlength="120"></div>
    <div class="field"><label for="${prefix}-category">Category</label><input id="${prefix}-category" name="category" maxlength="40"></div>
    <div class="field"><label for="${prefix}-status">Status</label><select id="${prefix}-status" name="status"><option value="">Any status</option>${statuses.map((s) => `<option>${s}</option>`).join("")}</select></div>
    <div class="field"><label for="${prefix}-location">Building or area</label><input id="${prefix}-location" name="location" maxlength="100"></div>
    <div class="form-actions"><button class="button" type="submit">Search</button><button class="button secondary" type="reset">Clear</button></div>
  </form>`;
}

async function loadLocations() {
  const data = await api("/api/locations");
  state.locations = data.locations || [];
  return state.locations;
}
function locationOptions(selected) {
  return state.locations.map((l) => `<option value="${esc(l.location_id)}" ${Number(selected) === Number(l.location_id) ? "selected" : ""}>${esc(l.building_name)} / ${esc(l.area_name)}</option>`).join("");
}
async function loadRequests(filters = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (String(value).trim()) query.set(key, String(value).trim());
  const data = await api(`/api/requests/search${query.size ? "?" + query.toString() : ""}`);
  state.requests = data.requests || [];
  return state.requests;
}

async function showPage(page = "dashboard") {
  if (!state.user) return loginScreen();
  if (page === "reports" && state.user.role !== "Admin") page = "dashboard";
  state.page = page;
  shell('<p>Loading current database records…</p>');
  try {
    let content = "";
    if (page === "dashboard") {
      const data = await api("/api/dashboard/summary");
      const s = data.summary;
      const own = state.user.role !== "Admin";
      const requests = await loadRequests();
      content = `<h1>${own ? "My maintenance requests" : "Maintenance dashboard"}</h1><p class="intro">${own ? "View the current status of requests you have reported." : "Current request totals from the FixTrack database."}</p>
        <section class="cards" aria-label="Request totals">${[["Total requests", s.total_requests], ["Pending", s.pending_requests], ["In progress", s.in_progress_requests], ["Resolved", s.resolved_requests]].map(([label, value]) => `<article class="metric"><span class="metric-label">${label}</span><span class="metric-value">${esc(value)}</span></article>`).join("")}</section>
        <section class="panel"><div class="panel-head"><h2>${own ? "Your recent requests" : "Recent maintenance requests"}</h2><button class="button secondary small" data-refresh="dashboard">Refresh</button></div>${requestRows(requests.slice(0, 10), "")}</section>`;
    } else if (page === "add") {
      await loadLocations();
      content = `<h1>Add a maintenance request</h1><p class="intro">The reporter is taken from your signed-in account.</p><section class="panel"><form id="add-form"><div class="form-grid">
        <div class="field full"><label for="add-title">Title</label><input id="add-title" name="title" maxlength="120" required></div>
        <div class="field full"><label for="add-description">Description</label><textarea id="add-description" name="description" maxlength="8000" required></textarea></div>
        <div class="field"><label for="add-category">Category</label><input id="add-category" name="category" maxlength="40" required></div>
        <div class="field"><label for="add-priority">Priority</label><select id="add-priority" name="priority">${priorities.map((p) => `<option ${p === "Medium" ? "selected" : ""}>${p}</option>`).join("")}</select></div>
        <div class="field full"><label for="add-location">Campus location</label><select id="add-location" name="location_id" required><option value="">Choose a location</option>${locationOptions()}</select></div>
        </div><div class="form-actions"><button class="button" type="submit">Submit request</button></div></form></section>`;
    } else if (page === "search" || page === "update" || page === "delete") {
      const heading = page === "search" ? "Search maintenance requests" : page === "update" ? "Update a maintenance request" : "Delete a maintenance request";
      const description = page === "delete" ? "Deletion is allowed only when related assignments and status history can be preserved." : page === "update" ? "Regular users can edit their own request details. Admins can also change status." : "Search by ID, title, category, status, building, or area.";
      content = `<h1>${heading}</h1><p class="intro">${description}</p><section class="panel"><h2>Search filters</h2>${searchForm(page)}<div id="request-results" class="panel-results">${empty("Enter filters and choose Search to load records.")}</div></section>${page === "update" ? '<section id="edit-section"></section>' : ""}`;
    } else if (page === "reports") {
      const [statusReport, locationReport] = await Promise.all([
        api("/api/admin/reports/request_status_counts"), api("/api/admin/reports/location_requests")
      ]);
      content = `<h1>Maintenance reports</h1><p class="intro">Both reports are calculated from current PostgreSQL records.</p>
        <section class="panel"><h2>Maintenance requests by status</h2>${table([["status", "Status"], ["request_count", "Request count"]], statusReport.rows || [])}</section>
        <section class="panel"><h2>Maintenance requests by location</h2>${table([["building_name", "Building"], ["area_name", "Area"], ["request_count", "Request count"]], locationReport.rows || [])}</section>`;
    }
    shell(content);
    if (["search", "update", "delete"].includes(page)) bindSearch(page);
  } catch (error) {
    shell(`<h1>Could not load this page</h1><p class="notice">${esc(error.message)}</p><button class="button" data-refresh="${esc(page)}">Try again</button>`);
  }
}

function bindSearch(page) {
  const form = document.getElementById(`${page}-form`);
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const filters = Object.fromEntries(new FormData(form).entries());
    const results = document.getElementById("request-results");
    results.innerHTML = "<p>Searching PostgreSQL…</p>";
    try {
      const rows = await loadRequests(filters);
      results.innerHTML = requestRows(rows, page === "search" ? "" : page);
    } catch (error) { results.innerHTML = `<p class="notice">${esc(error.message)}</p>`; }
  });
  form?.addEventListener("reset", () => setTimeout(() => {
    const target = document.getElementById("request-results");
    if (target) target.innerHTML = empty("Enter filters and choose Search to load records.");
  }, 0));
}

async function editRequest(requestId) {
  try {
    let row;
    if (state.user.role === "Admin") {
      const result = await api("/api/admin/data/maintenance_requests");
      row = (result.rows || []).find((r) => Number(r.request_id) === Number(requestId));
    } else {
      const result = await api(`/api/requests/${requestId}`);
      row = result.request;
    }
    if (!row) throw new Error("Maintenance request not found.");
    await loadLocations();
    const admin = state.user.role === "Admin";
    const section = document.getElementById("edit-section");
    section.innerHTML = `<section class="panel"><h2>Edit request #${esc(row.request_id)}</h2><form id="edit-form" data-id="${esc(row.request_id)}"><div class="form-grid">
      <div class="field full"><label for="edit-title">Title</label><input id="edit-title" name="title" maxlength="120" value="${esc(row.title)}" required></div>
      <div class="field full"><label for="edit-description">Description</label><textarea id="edit-description" name="description" maxlength="8000" required>${esc(row.description)}</textarea></div>
      <div class="field"><label for="edit-category">Category</label><input id="edit-category" name="category" maxlength="40" value="${esc(row.category)}" required></div>
      <div class="field"><label for="edit-priority">Priority</label><select id="edit-priority" name="priority">${priorities.map((p) => `<option ${p === row.priority ? "selected" : ""}>${p}</option>`).join("")}</select></div>
      <div class="field"><label for="edit-location">Location</label><select id="edit-location" name="location_id">${locationOptions(row.location_id)}</select></div>
      ${admin ? `<div class="field"><label for="edit-status">Status</label><select id="edit-status" name="current_status">${statuses.map((s) => `<option ${s === row.current_status ? "selected" : ""}>${s}</option>`).join("")}</select></div>` : ""}
      </div><div class="form-actions"><button class="button" type="submit">Save changes</button><button class="button secondary" type="button" data-close-edit>Close</button></div></form></section>`;
    document.getElementById("edit-form").addEventListener("submit", saveRequest);
    document.getElementById("edit-form").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) { setNotice(error.message); }
}

async function saveRequest(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form).entries());
  values.location_id = Number(values.location_id);
  const requestId = form.dataset.id;
  try {
    const admin = state.user.role === "Admin";
    await api(admin ? `/api/admin/requests/${requestId}` : `/api/requests/${requestId}`, { method: "PATCH", body: JSON.stringify(values) });
    state.notice = { message: "Request updated successfully.", kind: "success" };
    await showPage("update");
  } catch (error) { setNotice(error.message); }
}

async function deleteRequest(requestId, isAdmin) {
  if (!window.confirm(`Delete maintenance request #${requestId}? The backend will preserve related history and may refuse this deletion.`)) return;
  try {
    const path = isAdmin ? `/api/admin/requests/${requestId}` : `/api/requests/${requestId}`;
    await api(path, { method: "DELETE" });
    state.notice = { message: "Request deleted.", kind: "success" };
    await showPage("delete");
  } catch (error) { setNotice(error.message); }
}

async function startApp() {
  try { await getCsrf(); } catch (_error) { loginScreen("The server could not prepare a secure session."); return; }
  try {
    const data = await api("/api/auth/me");
    state.user = data.user;
    await showPage("dashboard");
  } catch (error) {
    if (error.message.toLowerCase().includes("change the temporary admin password")) passwordChangeScreen();
    else loginScreen();
  }
}

appRoot.addEventListener("click", async (event) => {
  const nav = event.target.closest("[data-page]");
  if (nav) { state.notice = null; await showPage(nav.dataset.page); return; }
  const authMode = event.target.closest("[data-auth-mode]");
  if (authMode) { loginScreen("", authMode.dataset.authMode); return; }
  const edit = event.target.closest("[data-edit]");
  if (edit) { await editRequest(edit.dataset.edit); return; }
  const remove = event.target.closest("[data-delete]");
  if (remove) { await deleteRequest(remove.dataset.delete, remove.dataset.adminDelete === "true"); return; }
  if (event.target.closest("[data-close-edit]")) { document.getElementById("edit-section").innerHTML = ""; return; }
  const refresh = event.target.closest("[data-refresh]");
  if (refresh) await showPage(refresh.dataset.refresh);
  if (event.target.closest('[data-action="logout"]')) {
    try { await api("/api/auth/logout", { method: "POST", body: "{}" }); } catch (_error) { /* Clear the local screen even when the server session expired. */ }
    state.user = null; state.csrf = "";
    try { await getCsrf(); } catch (_error) { }
    loginScreen("You have been logged out.");
  }
});

appRoot.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  if (form.id === "signup-form") {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    if (data.password !== data.confirm_password) { loginScreen("The password entries do not match.", "signup"); return; }
    try {
      const result = await api("/api/auth/register", { method: "POST", body: JSON.stringify(data) });
      loginScreen(result.message || "Account created. Sign in to continue.", "login", "success");
    } catch (error) { loginScreen(error.message, "signup"); }
  } else if (form.id === "login-form") {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    try {
      const result = await api("/api/auth/login", { method: "POST", body: JSON.stringify(data) });
      state.user = result.user;
      state.csrf = "";
      await getCsrf();
      if (result.password_change_required) passwordChangeScreen();
      else await showPage("dashboard");
    } catch (error) { loginScreen(error.message); }
  } else if (form.id === "forced-password-form") {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    if (data.password !== data.confirm_password) { setNotice("The new password entries do not match."); return; }
    try {
      await api("/api/auth/change-password", { method: "POST", body: JSON.stringify(data) });
      state.csrf = "";
      await getCsrf();
      loginScreen("Password changed. Sign in with your new password.");
    } catch (error) { setNotice(error.message); }
  } else if (form.id === "add-form") {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(form).entries());
    values.location_id = Number(values.location_id);
    try {
      const result = await api("/api/requests", { method: "POST", body: JSON.stringify(values) });
      state.notice = { message: `Request #${result.request.request_id} was submitted.`, kind: "success" };
      await showPage("dashboard");
    } catch (error) { setNotice(error.message); }
  }
});

startApp();
