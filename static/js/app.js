/* FixTrack's small same-origin frontend. All displayed records come from Flask. */
const appRoot = document.getElementById("app");
const state = { user: null, csrf: "", page: "dashboard", notice: null, requests: [], locations: [] };
const pages = [
  ["dashboard", "Home / Dashboard"], ["add", "Add Record"], ["update", "Update Record"],
  ["delete", "Delete Record"], ["search", "Search Record"], ["reports", "Reports"], ["users", "Campus Users"], ["workers", "Workers"]
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
  const shownPages = state.user.role === "Admin" ? pages : pages.filter(([id]) => !["update", "delete", "search", "reports", "users", "workers"].includes(id));
  appRoot.innerHTML = `
    <header class="topbar">
      <div class="topbar-inner">
        <h1 class="brand">FixTrack<span>College Campus Maintenance</span></h1>
        <div class="identity"><span class="identity-copy"><strong>${state.user.role === "Admin" ? "Admin" : esc(state.user.name)}</strong>${state.user.role === "Admin" ? "" : `<span class="identity-role">${esc(state.user.role)}</span>`}</span><div class="identity-actions"><button class="button secondary" data-action="logout">Log out</button></div></div>
      </div>
      <nav class="nav" aria-label="Main navigation">${shownPages.map(([id, label]) => `<button data-page="${id}" ${state.page === id ? 'aria-current="page"' : ""}>${label}</button>`).join("")}</nav>
    </header>
    <main class="main">${noticeMarkup()}${content}</main>
    <footer class="footer"><p class="footer-college">FR. CONCEICAO RODRIGUES COLLEGE OF ENGINEERING, BANDRA</p><p class="footer-address">Fr. Agnel Ashram, Bandstand Promenade, W, Bandra West, Mumbai, Maharashtra 400050</p></footer>`;
}

function loginScreen(message = "", kind = "error") {
  state.user = null;
  appRoot.innerHTML = `<main class="login-wrap"><section class="login-card">
    <h1 class="brand">FixTrack<span>College Campus Maintenance</span></h1>
    <p>Sign in with your campus account.</p>
    ${message ? `<div class="notice ${kind === "success" ? "success" : ""}" role="status">${esc(message)}</div>` : ""}
    <form id="login-form"><div class="field"><label for="login-email">Email</label><input id="login-email" name="email" type="email" maxlength="150" autocomplete="username" required></div>
    <div class="field" style="margin-top:.8rem"><label for="login-password">Password</label><input id="login-password" name="password" type="password" autocomplete="current-password" required></div>
    <div class="form-actions"><button class="button" type="submit">Log in</button></div>
    </form>
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
  return `<div class="table-wrap"><table><thead><tr>${headers.map(([, label]) => `<th scope="col">${esc(label)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${headers.map(([key]) => `<td>${key === "reported_at" || key === "assigned_at" || key === "ended_at" || key === "changed_at" ? date(row[key]) : esc(row[key] ?? "—")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function locationName(row) { return [row.building_name, row.area_name].filter(Boolean).join(" / "); }
function requestRows(rows, mode) {
  if (!rows.length) return empty("No maintenance requests match these criteria.");
  const canAdmin = state.user.role === "Admin";
  return `<div class="table-wrap"><table><thead><tr><th>ID</th>${canAdmin ? "<th>Reporter name</th><th>Reporter role</th><th>Reporter email</th><th>Assigned worker</th>" : ""}<th>Request</th><th>Category</th><th>Priority</th><th>Status</th><th>Location</th><th>Reported</th>${mode ? "<th>Action</th>" : ""}</tr></thead><tbody>${rows.map((r) => `<tr>
    <td class="request-id-cell">${esc(r.request_id)}</td>${canAdmin ? `<td>${esc(r.reporter_name || "—")}</td><td>${esc(r.reporter_role || "—")}</td><td>${esc(r.reporter_email || "—")}</td><td>${esc(r.assigned_worker_name || "—")}</td>` : ""}<td class="request-details-cell"><strong>${esc(r.title)}</strong><br>${esc(r.description || "")}</td><td>${esc(r.category)}</td><td class="request-priority-cell">${esc(r.priority)}</td><td class="request-status-cell">${esc(r.current_status)}</td><td>${esc(locationName(r))}</td><td class="request-reported-cell">${date(r.reported_at)}</td>
    ${mode ? `<td><div class="actions">${mode === "update" ? `<button class="button small" data-edit="${esc(r.request_id)}">Edit</button>${canAdmin ? `<button class="button secondary small" data-edit-status="${esc(r.request_id)}">Update status</button>` : ""}` : ""}<button class="button danger small" data-delete="${esc(r.request_id)}" data-admin-delete="${canAdmin}">Delete</button></div></td>` : ""}
    </tr>`).join("")}</tbody></table></div>`;
}

function searchForm(prefix = "search") {
  return `<form id="${prefix}-form" class="filter-grid">
    <div class="field"><label for="${prefix}-id">Request ID</label><input id="${prefix}-id" name="request_id" type="number" min="1" step="1"></div>
    <div class="field"><label for="${prefix}-title">Title contains</label><input id="${prefix}-title" name="title" maxlength="120"></div>
    <div class="field"><label for="${prefix}-category">Category</label><input id="${prefix}-category" name="category" maxlength="40"></div>
    <div class="field"><label for="${prefix}-status">Status</label><select id="${prefix}-status" name="status"><option value="">Any status</option>${statuses.map((s) => `<option>${s}</option>`).join("")}</select></div>
    <div class="field"><label for="${prefix}-priority">Priority</label><select id="${prefix}-priority" name="priority"><option value="">Any priority</option>${priorities.map((p) => `<option>${p}</option>`).join("")}</select></div>
    <div class="field"><label for="${prefix}-location">Building or area</label><input id="${prefix}-location" name="location" maxlength="100"></div>
    <div class="field"><label for="${prefix}-reporter-name">Reporter name</label><input id="${prefix}-reporter-name" name="reporter_name" maxlength="100"></div>
    <div class="field"><label for="${prefix}-reporter-role">Reporter role</label><select id="${prefix}-reporter-role" name="reporter_role"><option value="">Any role</option><option>Student</option><option>Faculty</option><option>Non-Teaching Staff</option><option>Admin</option></select></div>
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
  if (page === "users" && state.user.role !== "Admin") page = "dashboard";
  if (page === "workers" && state.user.role !== "Admin") page = "dashboard";
  if (["update", "delete"].includes(page) && state.user.role !== "Admin") page = "dashboard";
  if (page === "search" && state.user.role !== "Admin") page = "dashboard";
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
      content = `<h1>Add a maintenance request</h1><section class="panel"><form id="add-form"><div class="form-grid">
        <div class="field full"><label for="add-title">Title</label><input id="add-title" name="title" maxlength="120" required></div>
        <div class="field full"><label for="add-description">Description</label><textarea id="add-description" name="description" maxlength="8000" required></textarea></div>
        <div class="field"><label for="add-category">Category</label><input id="add-category" name="category" maxlength="40" required></div>
        <div class="field"><label for="add-priority">Priority</label><select id="add-priority" name="priority">${priorities.map((p) => `<option ${p === "Medium" ? "selected" : ""}>${p}</option>`).join("")}</select></div>
        <div class="field full"><label for="add-location">Campus location</label><select id="add-location" name="location_id" required><option value="">Choose a location</option>${locationOptions()}</select></div>
        </div><div class="form-actions"><button class="button" type="submit">Submit request</button></div></form></section>`;
    } else if (page === "search" || page === "update" || page === "delete") {
      const heading = page === "search" ? "Search maintenance requests" : page === "update" ? "Update a maintenance request" : "Delete a maintenance request";
      const description = page === "search" ? "Search by request details, location, reporter name, or reporter role." : "";
      content = `<h1>${heading}</h1>${description ? `<p class="intro">${description}</p>` : ""}<section class="panel"><h2>Search filters</h2>${searchForm(page)}<div id="request-results" class="panel-results">${empty("Enter filters and choose Search to load records.")}</div></section>${page === "update" ? '<section id="edit-section"></section>' : ""}`;
    } else if (page === "reports") {
      const [statusReport, locationReport] = await Promise.all([
        api("/api/admin/reports/request_status_counts"), api("/api/admin/reports/location_requests")
      ]);
      state.reportRows = { status: statusReport.rows || [], locations: locationReport.rows || [] };
      content = `<div class="panel-head"><h1>Maintenance reports</h1><button class="button secondary" type="button" data-action="download-reports">Download reports</button></div>
        <section class="panel"><h2>Maintenance requests by status</h2>${table([["status", "Status"], ["request_count", "Request count"]], statusReport.rows || [])}</section>
        <section class="panel"><h2>Maintenance requests by location</h2>${table([["building_name", "Building"], ["area_name", "Area"], ["request_count", "Request count"]], locationReport.rows || [])}</section>`;
    } else if (page === "users" && state.user.role === "Admin") {
      const result = await api("/api/admin/users");
      content = `<h1>Campus users</h1>
        <section class="panel"><h2>Create a user account</h2><form id="admin-create-user-form"><div class="form-grid">
          <div class="field"><label for="admin-user-name">Full name</label><input id="admin-user-name" name="full_name" maxlength="100" required></div>
          <div class="field"><label for="admin-user-email">Email address</label><input id="admin-user-email" name="email" type="email" maxlength="150" required></div>
          <div class="field"><label for="admin-user-role">Role</label><select id="admin-user-role" name="user_role" required><option value="Student">Student</option><option value="Faculty">Faculty</option><option value="Non-Teaching Staff">Non-Teaching Staff</option></select></div>
          <div class="field"><label for="admin-user-password">Password (12–128 characters)</label><input id="admin-user-password" name="password" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></div>
          <div class="field"><label for="admin-user-confirm">Confirm password</label><input id="admin-user-confirm" name="confirm_password" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></div>
        </div><div class="form-actions"><button class="button" type="submit">Create user</button></div></form></section>
        <section class="panel"><div class="panel-head"><h2>User directory</h2><button class="button secondary" type="button" data-action="download-users">Download user list</button></div><form id="admin-user-filter" class="filter-grid">
          <div class="field"><label for="directory-role">User category</label><select id="directory-role" name="role"><option value="">All three categories</option><option>Student</option><option>Faculty</option><option>Non-Teaching Staff</option></select></div>
          <div class="field"><label for="directory-search">Name or email contains</label><input id="directory-search" name="q" maxlength="150"></div>
          <div class="form-actions"><button class="button" type="submit">Filter</button><button class="button secondary" type="reset">Clear</button></div>
        </form><div id="admin-user-results" class="user-directory-results">${userDirectoryTable(result.users || [])}</div></section>`;
    } else if (page === "workers" && state.user.role === "Admin") {
      const [workerData, requestData] = await Promise.all([
        api("/api/admin/data/workers"), api("/api/admin/data/maintenance_requests")
      ]);
      const workers = workerData.rows || [];
      const requests = requestData.rows || [];
      content = `<h1>Workers</h1>
        <section class="panel"><h2>Add a worker</h2><p>Workers are maintenance staff records and do not need FixTrack login accounts.</p><form id="admin-create-worker-form"><div class="form-grid">
          <div class="field"><label for="worker-name">Full name</label><input id="worker-name" name="full_name" maxlength="100" required></div>
          <div class="field"><label for="worker-specialization">Specialization</label><input id="worker-specialization" name="specialization" maxlength="60" required></div>
          <div class="field"><label for="worker-phone">Phone (optional)</label><input id="worker-phone" name="phone" maxlength="20"></div>
        </div><div class="form-actions"><button class="button" type="submit">Add worker</button></div></form></section>
        <section class="panel"><h2>Assign worker to a request</h2><form id="admin-assign-worker-form"><div class="form-grid">
          <div class="field"><label for="assignment-request">Maintenance request</label><select id="assignment-request" name="request_id" required><option value="">Choose a request</option>${requests.map((r) => `<option value="${esc(r.request_id)}">#${esc(r.request_id)} · ${esc(r.title)} · ${esc(r.current_status)}</option>`).join("")}</select></div>
          <div class="field"><label for="assignment-worker">Worker</label><select id="assignment-worker" name="worker_id" required><option value="">Choose a worker</option>${workers.map((w) => `<option value="${esc(w.worker_id)}">${esc(w.full_name)} · ${esc(w.specialization)}</option>`).join("")}</select></div>
        </div><div class="form-actions"><button class="button" type="submit" ${!requests.length || !workers.length ? "disabled" : ""}>Assign worker</button></div></form><div id="assignment-history">${table([["request_id", "Request ID"], ["title", "Request"], ["worker_name", "Worker"], ["assigned_at", "Assigned"], ["ended_at", "Assignment ended"]], (await api("/api/admin/reports/repair_assignment_history")).rows || [])}</div></section>
        <section class="panel"><h2>Worker directory</h2>${table([["worker_id", "Worker ID"], ["full_name", "Name"], ["specialization", "Specialization"], ["phone", "Phone"]], workers)}</section>`;
    }
    shell(content);
    if (["search", "update", "delete"].includes(page)) bindSearch(page);
    if (page === "users" && state.user.role === "Admin") bindAdminUsers();
  } catch (error) {
    shell(`<h1>Could not load this page</h1><p class="notice">${esc(error.message)}</p><button class="button" data-refresh="${esc(page)}">Try again</button>`);
  }
}

function userDirectoryTable(users) {
  const regularUsers = users.filter((user) => ["Student", "Faculty", "Non-Teaching Staff"].includes(user.user_role));
  if (!regularUsers.length) return empty("No users match this category.");
  return `<div class="table-wrap"><table><thead><tr><th scope="col">Role</th><th scope="col">Name</th><th scope="col">Email</th><th scope="col">Action</th></tr></thead><tbody>${regularUsers.map((user) => `<tr><td>${esc(user.user_role)}</td><td>${esc(user.full_name)}</td><td>${esc(user.email)}</td><td><button class="button danger small" type="button" data-delete-user="${esc(user.user_id)}" data-user-name="${esc(user.full_name)}">Delete account</button></td></tr>`).join("")}</tbody></table></div>`;
}

async function deleteCampusUser(userId, userName) {
  if (state.user?.role !== "Admin") { setNotice("Admin permission is required."); return; }
  if (!window.confirm(`Delete ${userName}'s account? This cannot be undone. Accounts referenced by maintenance requests or other records cannot be deleted.`)) return;
  try {
    const result = await api(`/api/admin/users/${encodeURIComponent(userId)}`, { method: "DELETE" });
    state.notice = { message: result.message || "User account deleted.", kind: "success" };
    await showPage("users");
  } catch (error) { setNotice(error.message); }
}

function downloadUserList(users) {
  const headers = ["Name", "Role", "Email"];
  const csvCell = (value) => {
    // Prevent spreadsheet formula execution if a field begins with a formula marker.
    const safeValue = /^[=+\-@\t\r]/.test(String(value ?? "")) ? `'${value}` : String(value ?? "");
    return `"${safeValue.replace(/"/g, '""')}"`;
  };
  const contents = [headers, ...users.map((user) => [user.full_name, user.user_role, user.email])]
    .map((row) => row.map(csvCell).join(","))
    .join("\r\n");
  const file = new Blob(["\uFEFF", contents], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(file);
  const link = document.createElement("a");
  link.href = url;
  link.download = "fixtrack_users.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function downloadReports(reports) {
  const csvCell = (value) => {
    const text = String(value ?? "");
    const safeValue = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
    return `"${safeValue.replace(/"/g, '""')}"`;
  };
  const rows = [["Report", "Status", "Building", "Area", "Request count"]];
  for (const row of reports.status || []) {
    rows.push(["Requests by status", row.status, "", "", row.request_count]);
  }
  for (const row of reports.locations || []) {
    rows.push(["Requests by location", "", row.building_name, row.area_name, row.request_count]);
  }
  const csv = rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
  const file = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(file);
  const link = document.createElement("a");
  link.href = url;
  link.download = "fixtrack_reports.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function bindAdminUsers() {
  const filter = document.getElementById("admin-user-filter");
  const loadFilteredUsers = async () => {
    const params = new URLSearchParams(new FormData(filter));
    const result = await api(`/api/admin/users?${params.toString()}`);
    document.getElementById("admin-user-results").innerHTML = userDirectoryTable(result.users || []);
  };
  filter?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const results = document.getElementById("admin-user-results");
    results.innerHTML = "<p>Loading users from PostgreSQL…</p>";
    try { await loadFilteredUsers(); }
    catch (error) { results.innerHTML = `<p class="notice">${esc(error.message)}</p>`; }
  });
  filter?.addEventListener("reset", () => setTimeout(async () => {
    try { await loadFilteredUsers(); }
    catch (error) { document.getElementById("admin-user-results").innerHTML = `<p class="notice">${esc(error.message)}</p>`; }
  }, 0));
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

async function editRequest(requestId, statusOnly = false) {
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
    section.innerHTML = `<section class="panel"><h2>${statusOnly ? "Update status for" : "Edit request"} #${esc(row.request_id)}</h2><form id="edit-form" data-id="${esc(row.request_id)}" data-status-only="${statusOnly}"><div class="form-grid">
      ${statusOnly ? `<div class="field"><label for="edit-status">Current status</label><select id="edit-status" name="current_status" required>${statuses.map((s) => `<option ${s === row.current_status ? "selected" : ""}>${s}</option>`).join("")}</select></div>` : `
      <div class="field full"><label for="edit-title">Title</label><input id="edit-title" name="title" maxlength="120" value="${esc(row.title)}" required></div>
      <div class="field full"><label for="edit-description">Description</label><textarea id="edit-description" name="description" maxlength="8000" required>${esc(row.description)}</textarea></div>
      <div class="field"><label for="edit-category">Category</label><input id="edit-category" name="category" maxlength="40" value="${esc(row.category)}" required></div>
      <div class="field"><label for="edit-priority">Priority</label><select id="edit-priority" name="priority">${priorities.map((p) => `<option ${p === row.priority ? "selected" : ""}>${p}</option>`).join("")}</select></div>
      <div class="field"><label for="edit-location">Location</label><select id="edit-location" name="location_id">${locationOptions(row.location_id)}</select></div>
      ${admin ? `<div class="field"><label for="edit-status">Status</label><select id="edit-status" name="current_status">${statuses.map((s) => `<option ${s === row.current_status ? "selected" : ""}>${s}</option>`).join("")}</select></div>` : ""}`}
      </div><div class="form-actions"><button class="button" type="submit">Save changes</button><button class="button secondary" type="button" data-close-edit>Close</button></div></form></section>`;
    document.getElementById("edit-form").addEventListener("submit", saveRequest);
    document.getElementById("edit-form").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) { setNotice(error.message); }
}

async function saveRequest(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form).entries());
  const statusOnly = form.dataset.statusOnly === "true";
  if (!statusOnly) values.location_id = Number(values.location_id);
  const requestId = form.dataset.id;
  try {
    const admin = state.user.role === "Admin";
    await api(admin ? `/api/admin/requests/${requestId}` : `/api/requests/${requestId}`, { method: "PATCH", body: JSON.stringify(values) });
    state.notice = { message: statusOnly ? "Request status updated; status history recorded." : "Request updated successfully.", kind: "success" };
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
  const edit = event.target.closest("[data-edit]");
  if (edit) { await editRequest(edit.dataset.edit); return; }
  const editStatus = event.target.closest("[data-edit-status]");
  if (editStatus) { await editRequest(editStatus.dataset.editStatus, true); return; }
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
  const deleteUserButton = event.target.closest("[data-delete-user]");
  if (deleteUserButton) {
    await deleteCampusUser(deleteUserButton.dataset.deleteUser, deleteUserButton.dataset.userName);
    return;
  }
  if (event.target.closest('[data-action="download-users"]')) {
    if (state.user?.role !== "Admin") { setNotice("Admin permission is required."); return; }
    try {
      const result = await api("/api/admin/users");
      downloadUserList(result.users || []);
      setNotice("The current campus user list was downloaded without passwords.", "success");
    } catch (error) { setNotice(error.message); }
  }
  if (event.target.closest('[data-action="download-reports"]')) {
    if (state.user?.role !== "Admin") { setNotice("Admin permission is required."); return; }
    try {
      const [statusReport, locationReport] = await Promise.all([
        api("/api/admin/reports/request_status_counts"), api("/api/admin/reports/location_requests")
      ]);
      downloadReports({ status: statusReport.rows || [], locations: locationReport.rows || [] });
      setNotice("The current reports were downloaded.", "success");
    } catch (error) { setNotice(error.message); }
  }
});

appRoot.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  if (form.id === "admin-create-user-form") {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    if (data.password !== data.confirm_password) { setNotice("The password entries do not match."); return; }
    try {
      const result = await api("/api/admin/users", { method: "POST", body: JSON.stringify(data) });
      state.notice = { message: `${result.user.full_name} was added as ${result.user.user_role}.`, kind: "success" };
      await showPage("users");
    } catch (error) { setNotice(error.message); }
  } else if (form.id === "admin-create-worker-form") {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(form).entries());
    if (!values.phone.trim()) values.phone = null;
    try {
      const result = await api("/api/admin/workers", { method: "POST", body: JSON.stringify(values) });
      state.notice = { message: `${result.worker.full_name} was added to the worker directory.`, kind: "success" };
      await showPage("workers");
    } catch (error) { setNotice(error.message); }
  } else if (form.id === "admin-assign-worker-form") {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(form).entries());
    values.request_id = Number(values.request_id);
    values.worker_id = Number(values.worker_id);
    try {
      const result = await api("/api/admin/assignments", { method: "POST", body: JSON.stringify(values) });
      state.notice = { message: result.message || "Worker assigned.", kind: "success" };
      await showPage("workers");
    } catch (error) { setNotice(error.message); }
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
