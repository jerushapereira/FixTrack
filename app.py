"""FixTrack authentication and Admin user-management API."""

import hashlib
import hmac
import os
import re
from datetime import timedelta
from functools import wraps
from pathlib import Path

import psycopg2
from cachelib.file import FileSystemCache
from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request, session
from flask_session import Session
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash

from db import DatabaseUnavailable, database_connection
from auth_security import read_admin_password_state, write_admin_password_state

load_dotenv()
secret_key = os.getenv("FLASK_SECRET_KEY")
if not secret_key:
    raise RuntimeError("Set FLASK_SECRET_KEY in the project .env file before starting Flask.")

app = Flask(__name__)
session_directory = Path(app.instance_path) / "server_sessions"
session_directory.mkdir(parents=True, exist_ok=True)
app.config.update(
    SECRET_KEY=secret_key,
    SESSION_TYPE="cachelib",
    SESSION_CACHELIB=FileSystemCache(cache_dir=str(session_directory), threshold=500, default_timeout=1800),
    SESSION_SERIALIZATION_FORMAT="json",
    SESSION_PERMANENT=False,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").strip().lower() == "true",
    ADMIN_PASSWORD_STATE_FILE=str(Path(app.instance_path) / "admin_password_state.json"),
    MAX_CONTENT_LENGTH=16 * 1024,
)
Session(app)
csrf = CSRFProtect(app)
ALLOWED_ROLES = {"Student", "Faculty", "Non-Teaching Staff", "Admin"}
REGULAR_USER_ROLES = {"Student", "Faculty", "Non-Teaching Staff"}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_MIN = 12
PASSWORD_MAX = 128


@app.get("/")
def frontend_home():
    """Serve the same-origin FixTrack prototype frontend."""
    return render_template("index.html")


def _password_tag(password_hash):
    """Make a keyed session marker so changing a password invalidates old sessions."""
    key = app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(key, password_hash.encode("utf-8"), hashlib.sha256).hexdigest()


def _json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _validate_password(data):
    password = data.get("password")
    confirm = data.get("confirm_password")
    if not isinstance(password, str) or not isinstance(confirm, str):
        return None, "Password and confirm_password are required."
    if password != confirm:
        return None, "Password and confirmation do not match."
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        return None, f"Password must be between {PASSWORD_MIN} and {PASSWORD_MAX} characters."
    return password, None


def _validate_profile(data, partial=False):
    allowed = {"full_name", "email", "user_role"}
    if not isinstance(data, dict) or (set(data) - allowed):
        return None, "Send only full_name, email, and user_role."
    values = {}
    for field, maximum in (("full_name", 100), ("email", 150)):
        if field not in data:
            if not partial:
                return None, f"{field} is required."
            continue
        value = data[field]
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
            return None, f"{field} must contain 1 to {maximum} characters."
        value = value.strip()
        if field == "email":
            value = value.lower()
            if not EMAIL_PATTERN.match(value):
                return None, "Enter a valid email address."
        values[field] = value
    if "user_role" in data:
        role = data["user_role"]
        if not isinstance(role, str) or role not in ALLOWED_ROLES:
            return None, "user_role must be Student, Faculty, Non-Teaching Staff, or Admin."
        values["user_role"] = role
    elif not partial:
        return None, "user_role is required."
    return values, None


def read_current_user():
    """Load current identity and role from PostgreSQL and validate password marker."""
    user_id = session.get("user_id")
    tag = session.get("password_tag")
    if not isinstance(user_id, int) or isinstance(user_id, bool) or not isinstance(tag, str):
        return None
    with database_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT user_id, full_name, user_role, password_hash FROM campus_users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
    if not user or not user["password_hash"]:
        return None
    if not hmac.compare_digest(tag, _password_tag(user["password_hash"])):
        return None
    return dict(user)


def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(error="Please log in to use this endpoint."), 401
        user = read_current_user()
        if user is None:
            session.clear()
            return jsonify(error="Your session is no longer valid. Please log in again."), 401
        g.current_user = user
        if session.get("must_change_password") and request.endpoint != "change_own_password":
            return jsonify(error="Change the temporary Admin password before using the application."), 403
        return view_function(*args, **kwargs)
    return wrapped_view


def admin_required(view_function):
    @wraps(view_function)
    @login_required
    def wrapped_view(*args, **kwargs):
        if g.current_user["user_role"] != "Admin":
            return jsonify(error="Admin permission is required."), 403
        return view_function(*args, **kwargs)
    return wrapped_view


def _public_user(user):
    return {"user_id": user["user_id"], "full_name": user["full_name"], "email": user["email"], "user_role": user["user_role"]}


def _lock_admins(cursor):
    cursor.execute("SELECT user_id FROM campus_users WHERE user_role = %s ORDER BY user_id FOR UPDATE", ("Admin",))
    return [row["user_id"] for row in cursor.fetchall()]


@app.errorhandler(DatabaseUnavailable)
def database_error(_error):
    return jsonify(error="The database is unavailable. Check the server and .env settings."), 503


@app.errorhandler(psycopg2.Error)
def database_operation_error(_error):
    # Database diagnostics stay in server logs; responses do not expose SQL details.
    app.logger.error("A PostgreSQL operation failed.")
    return jsonify(error="The database could not complete the request."), 503


@app.errorhandler(OSError)
def authentication_state_error(_error):
    app.logger.error("A local authentication-state file operation failed.")
    return jsonify(error="The server could not update authentication state."), 503


@app.errorhandler(CSRFError)
def csrf_error(_error):
    return jsonify(error="The CSRF token is missing or invalid. Get a new token and try again."), 400


@app.get("/api/auth/csrf")
def get_csrf_token():
    return jsonify(csrf_token=generate_csrf())


@app.post("/api/auth/login")
def login():
    data = _json_object()
    if data is None:
        return jsonify(error="Send a JSON object with email and password."), 400
    email, password = data.get("email"), data.get("password")
    if not isinstance(email, str) or not email.strip():
        return jsonify(error="Email is required."), 400
    if not isinstance(password, str) or not password:
        return jsonify(error="Password is required."), 400
    with database_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT user_id, full_name, user_role, password_hash FROM campus_users WHERE lower(email) = %s", (email.strip().lower(),))
            user = cursor.fetchone()
    if not user or not user["password_hash"]:
        return jsonify(error="Invalid email or password."), 401
    try:
        valid = check_password_hash(user["password_hash"], password)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        return jsonify(error="Invalid email or password."), 401
    app.session_interface.regenerate(session)
    session.clear()
    session["user_id"] = user["user_id"]
    session["password_tag"] = _password_tag(user["password_hash"])
    password_state = read_admin_password_state(app.config["ADMIN_PASSWORD_STATE_FILE"])
    if user["user_role"] == "Admin" and password_state and password_state["user_id"] == user["user_id"] and password_state["state"] == "change_required":
        session["must_change_password"] = True
    return jsonify(message="Login successful.", password_change_required=bool(session.get("must_change_password")), user={"user_id": user["user_id"], "name": user["full_name"], "role": user["user_role"]})


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify(message="You have been logged out.")


@app.post("/api/auth/change-password")
@login_required
def change_own_password():
    """Let a signed-in user replace their current password."""
    data = _json_object()
    if not isinstance(data, dict) or set(data) != {"current_password", "password", "confirm_password"}:
        return jsonify(error="Provide current_password, password, and confirm_password."), 400
    current_password = data.get("current_password")
    if not isinstance(current_password, str) or not check_password_hash(g.current_user["password_hash"], current_password):
        return jsonify(error="Current password is incorrect."), 401
    password, error = _validate_password(data)
    if error:
        return jsonify(error=error), 400
    new_hash = generate_password_hash(password)
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE campus_users SET password_hash = %s WHERE user_id = %s", (new_hash, g.current_user["user_id"]))
    state = read_admin_password_state(app.config["ADMIN_PASSWORD_STATE_FILE"])
    if state and state["user_id"] == g.current_user["user_id"]:
        write_admin_password_state(app.config["ADMIN_PASSWORD_STATE_FILE"], g.current_user["user_id"], "changed")
    session.clear()
    return jsonify(message="Password changed. Please sign in again.")


@app.get("/api/auth/me")
@login_required
def current_user():
    return jsonify(user={"user_id": g.current_user["user_id"], "name": g.current_user["full_name"], "role": g.current_user["user_role"]})


@app.get("/api/dashboard/summary")
@login_required
def dashboard_summary():
    """Return live request counts for all requests or only this reporter's requests."""
    query = """SELECT COUNT(*) AS total_requests,
        COUNT(CASE WHEN current_status = 'Pending' THEN 1 END) AS pending_requests,
        COUNT(CASE WHEN current_status = 'In Progress' THEN 1 END) AS in_progress_requests,
        COUNT(CASE WHEN current_status = 'Resolved' THEN 1 END) AS resolved_requests
        FROM maintenance_requests"""
    params = ()
    if g.current_user["user_role"] != "Admin":
        query += " WHERE reporter_id = %s"
        params = (g.current_user["user_id"],)
    rows = _rows(query, params)
    return jsonify(summary=rows[0])


@app.get("/api/admin/check")
@admin_required
def admin_check():
    return jsonify(message="Admin access granted.", user={"user_id": g.current_user["user_id"], "name": g.current_user["full_name"], "role": g.current_user["user_role"]})


@app.post("/api/admin/users")
@admin_required
def create_user():
    data = _json_object()
    if data is None:
        return jsonify(error="Send a JSON object."), 400
    if set(data) != {"full_name", "email", "user_role", "password", "confirm_password"}:
        return jsonify(error="Provide full_name, email, user_role, password, and confirm_password only."), 400
    values, error = _validate_profile({key: data.get(key) for key in ("full_name", "email", "user_role")})
    if error:
        return jsonify(error=error), 400
    if values["user_role"] not in REGULAR_USER_ROLES:
        return jsonify(error="Choose Student, Faculty, or Non-Teaching Staff."), 400
    password, error = _validate_password(data)
    if error:
        return jsonify(error=error), 400
    password_hash = generate_password_hash(password)
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT 1 FROM campus_users WHERE lower(email) = %s", (values["email"],))
                if cursor.fetchone():
                    return jsonify(error="An account with this email already exists."), 409
                cursor.execute("INSERT INTO campus_users (full_name, email, user_role, password_hash) VALUES (%s, %s, %s, %s) RETURNING user_id, full_name, email, user_role", (values["full_name"], values["email"], values["user_role"], password_hash))
                user = cursor.fetchone()
    except psycopg2.errors.UniqueViolation:
        return jsonify(error="An account with this email already exists."), 409
    return jsonify(message="User created.", user=_public_user(user)), 201


@app.get("/api/admin/users")
@admin_required
def list_users():
    query = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    if role and role not in REGULAR_USER_ROLES:
        return jsonify(error="role must be Student, Faculty, or Non-Teaching Staff."), 400
    with database_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            conditions = ["user_role <> %s"]
            params = ["Admin"]
            if role:
                conditions.append("user_role = %s")
                params.append(role)
            if query:
                pattern = "%" + query + "%"
                conditions.append("(full_name ILIKE %s OR email ILIKE %s)")
                params.extend([pattern, pattern])
            sql = "SELECT user_id, full_name, email, user_role FROM campus_users"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY user_role, full_name, user_id"
            cursor.execute(sql, tuple(params))
            users = cursor.fetchall()
    return jsonify(users=[_public_user(user) for user in users])


@app.get("/api/admin/users/<int:user_id>")
@admin_required
def get_user(user_id):
    with database_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT user_id, full_name, email, user_role FROM campus_users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
    if not user:
        return jsonify(error="User not found."), 404
    return jsonify(user=_public_user(user))


@app.patch("/api/admin/users/<int:user_id>")
@admin_required
def update_user(user_id):
    data = _json_object()
    if data is None or not data:
        return jsonify(error="Send at least one editable field as JSON."), 400
    values, error = _validate_profile(data, partial=True)
    if error:
        return jsonify(error=error), 400
    fields = list(values)
    assignments = ", ".join(f"{field} = %s" for field in fields)
    params = [values[field] for field in fields]
    params.append(user_id)
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                admins = _lock_admins(cursor)
                cursor.execute("SELECT user_id, user_role FROM campus_users WHERE user_id = %s FOR UPDATE", (user_id,))
                existing = cursor.fetchone()
                if not existing:
                    return jsonify(error="User not found."), 404
                if "email" in values:
                    cursor.execute("SELECT 1 FROM campus_users WHERE lower(email) = %s AND user_id <> %s", (values["email"], user_id))
                    if cursor.fetchone():
                        return jsonify(error="An account with this email already exists."), 409
                if values.get("user_role") == "Admin" and existing["user_role"] != "Admin":
                    return jsonify(error="Only the explicit setup_admin.py command may designate the project Admin."), 409
                if existing["user_role"] == "Admin" and values.get("user_role") not in (None, "Admin"):
                    if len(admins) <= 1:
                        return jsonify(error="The last Admin account cannot be demoted."), 409
                cursor.execute(f"UPDATE campus_users SET {assignments} WHERE user_id = %s RETURNING user_id, full_name, email, user_role", params)
                user = cursor.fetchone()
    except psycopg2.errors.UniqueViolation:
        return jsonify(error="An account with this email already exists."), 409
    return jsonify(message="User updated.", user=_public_user(user))


@app.post("/api/admin/users/<int:user_id>/password")
@admin_required
def reset_user_password(user_id):
    data = _json_object()
    if data is None:
        return jsonify(error="Send a JSON object."), 400
    if set(data) != {"password", "confirm_password"}:
        return jsonify(error="Provide password and confirm_password only."), 400
    password, error = _validate_password(data)
    if error:
        return jsonify(error=error), 400
    password_hash = generate_password_hash(password)
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE campus_users SET password_hash = %s WHERE user_id = %s", (password_hash, user_id))
            if cursor.rowcount == 0:
                return jsonify(error="User not found."), 404
    state = read_admin_password_state(app.config["ADMIN_PASSWORD_STATE_FILE"])
    if state and state["user_id"] == user_id:
        write_admin_password_state(app.config["ADMIN_PASSWORD_STATE_FILE"], user_id, "changed")
    return jsonify(message="Password changed. That user's existing sessions will be rejected on their next request.")


@app.delete("/api/admin/users/<int:user_id>")
@admin_required
def delete_user(user_id):
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                admins = _lock_admins(cursor)
                cursor.execute("SELECT user_id, user_role FROM campus_users WHERE user_id = %s FOR UPDATE", (user_id,))
                user = cursor.fetchone()
                if not user:
                    return jsonify(error="User not found."), 404
                if user_id == g.current_user["user_id"]:
                    return jsonify(error="You cannot delete your own account. Another Admin must manage this account."), 403
                cursor.execute("SELECT 1 FROM maintenance_requests WHERE reporter_id = %s LIMIT 1", (user_id,))
                if cursor.fetchone():
                    return jsonify(error="This user reported maintenance requests and cannot be deleted while those records are retained."), 409
                if user["user_role"] == "Admin":
                    if len(admins) <= 1:
                        return jsonify(error="The last Admin account cannot be deleted."), 409
                cursor.execute("DELETE FROM campus_users WHERE user_id = %s", (user_id,))
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify(error="This user is referenced by existing records and cannot be deleted."), 409
    return jsonify(message="User deleted.")


# Read-only Admin access to each existing table. Password hashes are excluded.
ADMIN_TABLE_QUERIES = {
    "campus_users": "SELECT user_id, full_name, email, user_role FROM campus_users ORDER BY user_id",
    "campus_locations": "SELECT location_id, building_name, area_name FROM campus_locations ORDER BY location_id",
    "workers": "SELECT worker_id, full_name, phone, specialization FROM workers ORDER BY worker_id",
    "maintenance_requests": """SELECT r.request_id, r.title, r.description, r.category, r.priority,
        r.current_status, r.reported_at, u.user_id AS reporter_id,
        u.full_name AS reporter_name, u.email AS reporter_email,
        l.location_id, l.building_name, l.area_name
        FROM maintenance_requests AS r
        JOIN campus_users AS u ON u.user_id = r.reporter_id
        JOIN campus_locations AS l ON l.location_id = r.location_id
        ORDER BY r.reported_at DESC""",
    "assignments": """SELECT a.assignment_id, a.request_id, r.title,
        a.worker_id, w.full_name AS worker_name, a.assigned_at, a.ended_at
        FROM assignments AS a
        JOIN maintenance_requests AS r ON r.request_id = a.request_id
        JOIN workers AS w ON w.worker_id = a.worker_id
        ORDER BY a.request_id, a.assigned_at""",
    "status_history": """SELECT h.history_id, h.request_id, r.title, h.status,
        h.changed_at, h.note
        FROM status_history AS h
        JOIN maintenance_requests AS r ON r.request_id = h.request_id
        ORDER BY h.request_id, h.changed_at""",
}


def _rows(query, params=()):
    with database_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


def _find_unresolved_duplicate(cursor, location_id, category):
    """Find an open request for this location/category before inserting another."""
    # Locking the location serializes concurrent submissions to the same location.
    cursor.execute("SELECT location_id FROM campus_locations WHERE location_id = %s FOR UPDATE", (location_id,))
    if cursor.fetchone() is None:
        return None
    cursor.execute(
        "SELECT request_id FROM maintenance_requests "
        "WHERE location_id = %s AND lower(category) = lower(%s) "
        "AND current_status IN ('Pending', 'In Progress') "
        "ORDER BY request_id LIMIT 1",
        (location_id, category),
    )
    duplicate = cursor.fetchone()
    return duplicate["request_id"] if duplicate else None


def _id_value(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _text_value(data, key, maximum, required=True):
    value = data.get(key)
    if value is None and not required:
        return None, None
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        return None, f"{key} must contain 1 to {maximum} characters."
    return value.strip(), None


def _location_values(data, partial=False):
    allowed = {"building_name", "area_name"}
    if not isinstance(data, dict) or set(data) - allowed or (not partial and not {"full_name", "specialization"}.issubset(data)) or (partial and not data):
        return None, "Provide building_name and area_name only; include both when creating a location."
    result = {}
    for key in allowed:
        if key in data:
            value, error = _text_value(data, key, 100)
            if error:
                return None, error
            result[key] = value
    return result, None


def _worker_values(data, partial=False):
    allowed = {"full_name", "phone", "specialization"}
    if not isinstance(data, dict) or set(data) - allowed or (not partial and not {"full_name", "specialization"}.issubset(data)) or (partial and not data):
        return None, "Provide full_name, phone, and specialization only; include name and specialization when creating a worker."
    result = {}
    for key, limit in (("full_name", 100), ("specialization", 60)):
        if key in data:
            value, error = _text_value(data, key, limit)
            if error:
                return None, error
            result[key] = value
    if "phone" in data:
        phone = data["phone"]
        if phone is not None and (not isinstance(phone, str) or len(phone.strip()) > 20):
            return None, "phone must be no more than 20 characters or null."
        result["phone"] = phone.strip() if isinstance(phone, str) and phone.strip() else None
    elif not partial:
        result["phone"] = None
    return result, None


@app.get("/api/admin/data/<table_name>")
@admin_required
def admin_table_data(table_name):
    query = ADMIN_TABLE_QUERIES.get(table_name)
    if query is None:
        return jsonify(error="Unknown table. Choose one of the six FixTrack tables."), 404
    return jsonify(table=table_name, rows=_rows(query))


@app.get("/api/admin/reports/<report_name>")
@admin_required
def admin_report(report_name):
    queries = {
        "location_requests": """SELECT l.location_id, l.building_name, l.area_name,
            COUNT(r.request_id) AS request_count FROM campus_locations AS l
            LEFT JOIN maintenance_requests AS r ON r.location_id = l.location_id
            GROUP BY l.location_id, l.building_name, l.area_name
            ORDER BY l.building_name, l.area_name""",
        "unresolved_by_category": """SELECT category, COUNT(*) AS request_count
            FROM maintenance_requests WHERE current_status IN ('Pending', 'In Progress')
            GROUP BY category ORDER BY category""",
        "request_status_counts": """SELECT status, COUNT(r.request_id) AS request_count
            FROM (VALUES ('Pending'), ('In Progress'), ('Resolved')) AS statuses(status)
            LEFT JOIN maintenance_requests AS r ON r.current_status = statuses.status
            GROUP BY status
            ORDER BY CASE status WHEN 'Pending' THEN 1 WHEN 'In Progress' THEN 2 ELSE 3 END""",
        "active_worker_workload": """SELECT w.worker_id, w.full_name,
            COUNT(a.assignment_id) AS active_assignment_count FROM workers AS w
            LEFT JOIN assignments AS a ON a.worker_id = w.worker_id AND a.ended_at IS NULL
            GROUP BY w.worker_id, w.full_name ORDER BY w.full_name""",
        "high_priority_unresolved": """SELECT r.request_id, r.title, r.priority, r.current_status,
            r.reported_at, l.building_name, l.area_name FROM maintenance_requests AS r
            JOIN campus_locations AS l ON l.location_id = r.location_id
            WHERE r.priority = 'High' AND r.current_status IN ('Pending', 'In Progress')
            ORDER BY r.reported_at""",
        "overdue": """SELECT r.request_id, r.title, r.priority, r.current_status,
            r.reported_at, l.building_name, l.area_name FROM maintenance_requests AS r
            JOIN campus_locations AS l ON l.location_id = r.location_id
            WHERE r.current_status IN ('Pending', 'In Progress')
              AND r.reported_at < CURRENT_TIMESTAMP - INTERVAL '7 days'
            ORDER BY r.reported_at""",
        "pending_complaints_view": "SELECT * FROM pending_complaints_view ORDER BY reported_at",
        "active_assignments_view": "SELECT * FROM active_assignments_view ORDER BY assigned_at",
        "repair_assignment_history": """SELECT r.request_id, r.title, r.current_status,
            w.full_name AS worker_name, a.assigned_at,
            CASE WHEN r.current_status = 'Resolved' THEN
                (SELECT MAX(h.changed_at)::date FROM status_history AS h
                 WHERE h.request_id = r.request_id AND h.status = 'Resolved')
                ELSE NULL END AS ended_at,
            CASE WHEN r.current_status = 'Resolved' THEN 'Yes' ELSE 'No' END AS assignment_ended
            FROM maintenance_requests AS r LEFT JOIN assignments AS a ON a.request_id = r.request_id
            LEFT JOIN workers AS w ON w.worker_id = a.worker_id
            ORDER BY r.request_id, a.assigned_at""",
        "status_history": """SELECT r.request_id, r.title, r.current_status,
            h.status AS history_status, h.changed_at, h.note
            FROM maintenance_requests AS r LEFT JOIN status_history AS h ON h.request_id = r.request_id
            ORDER BY r.request_id, h.changed_at""",
    }
    query = queries.get(report_name)
    if query is None:
        return jsonify(error="Unknown report."), 404
    return jsonify(report=report_name, rows=_rows(query))


@app.post("/api/requests")
@login_required
def create_own_request():
    data = _json_object()
    allowed = {"location_id", "title", "description", "category", "priority"}
    if data is None or set(data) != allowed:
        return jsonify(error="Provide location_id, title, description, category, and priority."), 400
    location_id = data.get("location_id")
    if not _id_value(location_id):
        return jsonify(error="location_id must be a positive integer."), 400
    title, error = _text_value(data, "title", 120)
    if error:
        return jsonify(error=error), 400
    description, error = _text_value(data, "description", 8000)
    if error:
        return jsonify(error=error), 400
    category, error = _text_value(data, "category", 40)
    if error:
        return jsonify(error=error), 400
    priority = data.get("priority")
    if not isinstance(priority, str) or priority not in {"Low", "Medium", "High"}:
        return jsonify(error="priority must be Low, Medium, or High."), 400
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                duplicate_id = _find_unresolved_duplicate(cursor, location_id, category)
                if duplicate_id is not None:
                    return jsonify(error=f"An unresolved {category} request already exists for this location (request #{duplicate_id})."), 409
                cursor.execute("INSERT INTO maintenance_requests (reporter_id, location_id, title, description, category, priority) VALUES (%s, %s, %s, %s, %s, %s) RETURNING request_id, reporter_id, location_id, title, description, category, priority, current_status, reported_at", (g.current_user["user_id"], location_id, title, description, category, priority))
                created = dict(cursor.fetchone())
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify(error="The selected campus location does not exist."), 400
    return jsonify(message="Maintenance request created.", request=created), 201


@app.get("/api/locations")
@login_required
def list_request_locations():
    """Locations are needed to file a request and are not private user data."""
    return jsonify(locations=_rows("SELECT location_id, building_name, area_name FROM campus_locations ORDER BY building_name, area_name"))


@app.get("/api/requests")
@login_required
def list_own_requests():
    rows = _rows("""SELECT r.request_id, r.title, r.description, r.category, r.priority,
        r.current_status, r.reported_at, l.location_id, l.building_name, l.area_name
        FROM maintenance_requests AS r JOIN campus_locations AS l ON l.location_id = r.location_id
        WHERE r.reporter_id = %s ORDER BY r.reported_at DESC""", (g.current_user["user_id"],))
    return jsonify(requests=rows)


@app.get("/api/requests/search")
@login_required
def search_requests():
    """Search authorized requests with every user value passed as a SQL parameter."""
    request_id = request.args.get("request_id", "").strip()
    title = request.args.get("title", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    priority = request.args.get("priority", "").strip()
    location = request.args.get("location", "").strip()
    reporter_name = request.args.get("reporter_name", "").strip()
    reporter_role = request.args.get("reporter_role", "").strip()
    if request_id and (not request_id.isdigit() or int(request_id) < 1):
        return jsonify(error="Request ID must be a positive whole number."), 400
    if len(title) > 120 or len(category) > 40 or len(location) > 100 or len(reporter_name) > 100:
        return jsonify(error="Search text is longer than the supported field length."), 400
    if status and status not in {"Pending", "In Progress", "Resolved"}:
        return jsonify(error="Status must be Pending, In Progress, or Resolved."), 400
    if priority and priority not in {"Low", "Medium", "High"}:
        return jsonify(error="Priority must be Low, Medium, or High."), 400
    if reporter_role and reporter_role not in ALLOWED_ROLES:
        return jsonify(error="Reporter role must be Student, Faculty, Non-Teaching Staff, or Admin."), 400

    conditions = []
    params = []
    if g.current_user["user_role"] != "Admin":
        conditions.append("r.reporter_id = %s")
        params.append(g.current_user["user_id"])
    if request_id:
        conditions.append("r.request_id = %s")
        params.append(int(request_id))
    if title:
        conditions.append("r.title ILIKE %s")
        params.append("%" + title + "%")
    if category:
        conditions.append("r.category ILIKE %s")
        params.append("%" + category + "%")
    if status:
        conditions.append("r.current_status = %s")
        params.append(status)
    if priority:
        conditions.append("r.priority = %s")
        params.append(priority)
    if location:
        conditions.append("(l.building_name ILIKE %s OR l.area_name ILIKE %s)")
        params.extend(["%" + location + "%", "%" + location + "%"])
    if reporter_name:
        conditions.append("u.full_name ILIKE %s")
        params.append("%" + reporter_name + "%")
    if reporter_role:
        conditions.append("u.user_role = %s")
        params.append(reporter_role)

    if g.current_user["user_role"] == "Admin":
        query = """SELECT r.request_id, r.reporter_id, r.location_id, r.title,
            r.description, r.category, r.priority, r.current_status, r.reported_at,
            l.building_name, l.area_name,
            u.full_name AS reporter_name, u.email AS reporter_email,
            u.user_role AS reporter_role,
            current_worker.worker_name AS assigned_worker_name
            FROM maintenance_requests AS r
            JOIN campus_locations AS l ON l.location_id = r.location_id
            JOIN campus_users AS u ON u.user_id = r.reporter_id
            LEFT JOIN LATERAL (
                SELECT w.full_name AS worker_name
                FROM assignments AS a
                JOIN workers AS w ON w.worker_id = a.worker_id
                WHERE a.request_id = r.request_id AND a.ended_at IS NULL
                ORDER BY a.assigned_at DESC
                LIMIT 1
            ) AS current_worker ON TRUE"""
    else:
        query = """SELECT r.request_id, r.reporter_id, r.location_id, r.title,
            r.description, r.category, r.priority, r.current_status, r.reported_at,
            l.building_name, l.area_name,
            u.full_name AS reporter_name, u.user_role AS reporter_role
            FROM maintenance_requests AS r
            JOIN campus_locations AS l ON l.location_id = r.location_id
            JOIN campus_users AS u ON u.user_id = r.reporter_id"""
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY r.reported_at DESC"
    return jsonify(requests=_rows(query, tuple(params)))


@app.patch("/api/requests/<int:request_id>")
@login_required
def update_own_request(request_id):
    """Let a reporter edit their own request fields, but not its status or reporter."""
    data = _json_object()
    allowed = {"title", "description", "category", "priority", "location_id"}
    if not isinstance(data, dict) or not data or set(data) - allowed:
        return jsonify(error="Send one or more permitted request fields only."), 400
    values = {}
    for field, limit in (("title", 120), ("description", 8000), ("category", 40)):
        if field in data:
            value, error = _text_value(data, field, limit)
            if error:
                return jsonify(error=error), 400
            values[field] = value
    if "priority" in data:
        if not isinstance(data["priority"], str) or data["priority"] not in {"Low", "Medium", "High"}:
            return jsonify(error="priority must be Low, Medium, or High."), 400
        values["priority"] = data["priority"]
    if "location_id" in data:
        if not _id_value(data["location_id"]):
            return jsonify(error="location_id must be a positive integer."), 400
        values["location_id"] = data["location_id"]

    fields = list(values)
    set_clause = ", ".join(field + " = %s" for field in fields)
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "UPDATE maintenance_requests SET " + set_clause +
                    " WHERE request_id = %s AND reporter_id = %s "
                    "RETURNING request_id, reporter_id, location_id, title, description, category, priority, current_status, reported_at",
                    [values[field] for field in fields] + [request_id, g.current_user["user_id"]],
                )
                updated = cursor.fetchone()
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify(error="The selected campus location does not exist."), 400
    if not updated:
        return jsonify(error="Maintenance request not found or it does not belong to your account."), 404
    return jsonify(message="Maintenance request updated.", request=dict(updated))


@app.get("/api/requests/<int:request_id>")
@login_required
def get_own_request(request_id):
    rows = _rows("""SELECT r.request_id, r.title, r.description, r.category, r.priority,
        r.current_status, r.reported_at, l.location_id, l.building_name, l.area_name
        FROM maintenance_requests AS r JOIN campus_locations AS l ON l.location_id = r.location_id
        WHERE r.request_id = %s AND r.reporter_id = %s""", (request_id, g.current_user["user_id"]))
    if not rows:
        return jsonify(error="Maintenance request not found."), 404
    return jsonify(request=rows[0])


def _delete_request_if_unreferenced(cursor, request_id):
    cursor.execute("SELECT 1 FROM assignments WHERE request_id = %s LIMIT 1", (request_id,))
    has_assignments = cursor.fetchone() is not None
    cursor.execute("SELECT 1 FROM status_history WHERE request_id = %s LIMIT 1", (request_id,))
    has_history = cursor.fetchone() is not None
    if has_assignments or has_history:
        return False
    cursor.execute("DELETE FROM maintenance_requests WHERE request_id = %s", (request_id,))
    return cursor.rowcount == 1


@app.delete("/api/requests/<int:request_id>")
@login_required
def delete_own_request(request_id):
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT request_id FROM maintenance_requests WHERE request_id = %s AND reporter_id = %s FOR UPDATE", (request_id, g.current_user["user_id"]))
                if cursor.fetchone() is None:
                    return jsonify(error="Maintenance request not found."), 404
                if not _delete_request_if_unreferenced(cursor, request_id):
                    return jsonify(error="This request has assignment or status history and cannot be deleted while preserving its records."), 409
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify(error="This request is referenced by history and cannot be deleted."), 409
    return jsonify(message="Maintenance request deleted.")


@app.post("/api/admin/locations")
@admin_required
def create_location():
    data = _json_object()
    values, error = _location_values(data)
    if error:
        return jsonify(error=error), 400
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("INSERT INTO campus_locations (building_name, area_name) VALUES (%s, %s) RETURNING location_id, building_name, area_name", (values["building_name"], values["area_name"]))
                location = dict(cursor.fetchone())
    except psycopg2.errors.UniqueViolation:
        return jsonify(error="That building and area already exist."), 409
    return jsonify(location=location), 201


@app.patch("/api/admin/locations/<int:location_id>")
@admin_required
def update_location(location_id):
    values, error = _location_values(_json_object(), partial=True)
    if error:
        return jsonify(error=error), 400
    fields = list(values)
    sets = ", ".join(f"{field} = %s" for field in fields)
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(f"UPDATE campus_locations SET {sets} WHERE location_id = %s RETURNING location_id, building_name, area_name", [values[f] for f in fields] + [location_id])
                row = cursor.fetchone()
    except psycopg2.errors.UniqueViolation:
        return jsonify(error="That building and area already exist."), 409
    if not row:
        return jsonify(error="Campus location not found."), 404
    return jsonify(location=dict(row))


@app.delete("/api/admin/locations/<int:location_id>")
@admin_required
def delete_location(location_id):
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM campus_locations WHERE location_id = %s", (location_id,))
                if cursor.rowcount == 0:
                    return jsonify(error="Campus location not found."), 404
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify(error="This location is used by maintenance requests and cannot be deleted."), 409
    return jsonify(message="Campus location deleted.")


@app.post("/api/admin/workers")
@admin_required
def create_worker():
    values, error = _worker_values(_json_object())
    if error:
        return jsonify(error=error), 400
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("INSERT INTO workers (full_name, phone, specialization) VALUES (%s, %s, %s) RETURNING worker_id, full_name, phone, specialization", (values["full_name"], values.get("phone"), values["specialization"]))
                worker = dict(cursor.fetchone())
    except psycopg2.errors.UniqueViolation:
        return jsonify(error="That phone number is already assigned to a worker."), 409
    return jsonify(worker=worker), 201


@app.patch("/api/admin/workers/<int:worker_id>")
@admin_required
def update_worker(worker_id):
    values, error = _worker_values(_json_object(), partial=True)
    if error:
        return jsonify(error=error), 400
    fields = list(values)
    sets = ", ".join(f"{field} = %s" for field in fields)
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(f"UPDATE workers SET {sets} WHERE worker_id = %s RETURNING worker_id, full_name, phone, specialization", [values[f] for f in fields] + [worker_id])
                row = cursor.fetchone()
    except psycopg2.errors.UniqueViolation:
        return jsonify(error="That phone number is already assigned to a worker."), 409
    if not row:
        return jsonify(error="Worker not found."), 404
    return jsonify(worker=dict(row))


@app.delete("/api/admin/workers/<int:worker_id>")
@admin_required
def delete_worker(worker_id):
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM workers WHERE worker_id = %s", (worker_id,))
                if cursor.rowcount == 0:
                    return jsonify(error="Worker not found."), 404
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify(error="This worker has assignment history and cannot be deleted."), 409
    return jsonify(message="Worker deleted.")


@app.post("/api/admin/requests")
@admin_required
def create_request_for_user():
    """Create a request for an existing reporter; the trigger records its initial status."""
    data = _json_object()
    allowed = {"reporter_id", "location_id", "title", "description", "category", "priority"}
    if not isinstance(data, dict) or set(data) != allowed:
        return jsonify(error="Provide reporter_id, location_id, title, description, category, and priority."), 400
    if not _id_value(data["reporter_id"]) or not _id_value(data["location_id"]):
        return jsonify(error="reporter_id and location_id must be positive integers."), 400
    limits = {"title": 120, "description": 8000, "category": 40}
    for field, limit in limits.items():
        value, error = _text_value(data, field, limit)
        if error:
            return jsonify(error=error), 400
        data[field] = value
    if not isinstance(data["priority"], str) or data["priority"] not in {"Low", "Medium", "High"}:
        return jsonify(error="priority must be Low, Medium, or High."), 400
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                duplicate_id = _find_unresolved_duplicate(cursor, data["location_id"], data["category"])
                if duplicate_id is not None:
                    return jsonify(error=f"An unresolved {data['category']} request already exists for this location (request #{duplicate_id})."), 409
                cursor.execute("INSERT INTO maintenance_requests (reporter_id, location_id, title, description, category, priority) VALUES (%s, %s, %s, %s, %s, %s) RETURNING request_id, reporter_id, location_id, title, description, category, priority, current_status, reported_at", (data["reporter_id"], data["location_id"], data["title"], data["description"], data["category"], data["priority"]))
                created = dict(cursor.fetchone())
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify(error="The selected reporter or campus location does not exist."), 400
    return jsonify(message="Maintenance request created.", request=created), 201


@app.patch("/api/admin/requests/<int:request_id>")
@admin_required
def update_request(request_id):
    data = _json_object()
    allowed = {"title", "description", "category", "priority", "current_status", "location_id"}
    if not isinstance(data, dict) or not data or set(data) - allowed:
        return jsonify(error="Send one or more allowed request fields only."), 400
    values = {}
    limits = {"title": 120, "description": 8000, "category": 40}
    for key, limit in limits.items():
        if key in data:
            value, error = _text_value(data, key, limit)
            if error:
                return jsonify(error=error), 400
            values[key] = value
    if "priority" in data:
        if not isinstance(data["priority"], str) or data["priority"] not in {"Low", "Medium", "High"}:
            return jsonify(error="priority must be Low, Medium, or High."), 400
        values["priority"] = data["priority"]
    if "current_status" in data:
        if not isinstance(data["current_status"], str) or data["current_status"] not in {"Pending", "In Progress", "Resolved"}:
            return jsonify(error="current_status must be Pending, In Progress, or Resolved."), 400
        values["current_status"] = data["current_status"]
    if "location_id" in data:
        if not _id_value(data["location_id"]):
            return jsonify(error="location_id must be a positive integer."), 400
        values["location_id"] = data["location_id"]
    fields = list(values)
    sets = ", ".join(f"{field} = %s" for field in fields)
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(f"UPDATE maintenance_requests SET {sets} WHERE request_id = %s RETURNING request_id, reporter_id, location_id, title, description, category, priority, current_status, reported_at", [values[f] for f in fields] + [request_id])
                row = cursor.fetchone()
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify(error="The selected campus location does not exist."), 400
    if not row:
        return jsonify(error="Maintenance request not found."), 404
    return jsonify(request=dict(row))


@app.delete("/api/admin/requests/<int:request_id>")
@admin_required
def delete_admin_request(request_id):
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT request_id FROM maintenance_requests WHERE request_id = %s FOR UPDATE", (request_id,))
                if cursor.fetchone() is None:
                    return jsonify(error="Maintenance request not found."), 404
                if not _delete_request_if_unreferenced(cursor, request_id):
                    return jsonify(error="This request has assignment or status history and cannot be deleted while preserving its records."), 409
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify(error="This request is referenced by history and cannot be deleted."), 409
    return jsonify(message="Maintenance request deleted.")


@app.post("/api/admin/assignments")
@admin_required
def assign_request_worker():
    data = _json_object()
    if not isinstance(data, dict) or set(data) != {"request_id", "worker_id"}:
        return jsonify(error="Provide request_id and worker_id."), 400
    if not _id_value(data["request_id"]) or not _id_value(data["worker_id"]):
        return jsonify(error="request_id and worker_id must be positive integers."), 400
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("CALL assign_worker(%s, %s)", (data["request_id"], data["worker_id"]))
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify(error="The selected request or worker does not exist."), 400
    return jsonify(message="Worker assigned. Any previous active assignment was ended and kept in history."), 201


def _check_production_admin_setup():
    """Refuse production mode until the one designated Admin is marked as having changed the temporary password."""
    if os.getenv("FIXTRACK_ENV", "development").strip().lower() != "production":
        return
    designated_email = os.getenv("FIXTRACK_ADMIN_EMAIL", "").strip().lower()
    if not designated_email:
        raise RuntimeError("Production startup requires FIXTRACK_ADMIN_EMAIL.")
    with database_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT user_id, user_role, password_hash FROM campus_users WHERE lower(email) = %s", (designated_email,))
            designated = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) AS admin_count FROM campus_users WHERE user_role = 'Admin'")
            admin_count = cursor.fetchone()["admin_count"]
    if not designated or designated["user_role"] != "Admin" or not designated["password_hash"]:
        raise RuntimeError("Production startup requires the designated Admin account to exist.")
    password_state = read_admin_password_state(app.config["ADMIN_PASSWORD_STATE_FILE"])
    if admin_count != 1 or not password_state or password_state["user_id"] != designated["user_id"] or password_state["state"] != "changed":
        raise RuntimeError("Production startup blocked: keep one Admin and complete the temporary-password change first.")


_check_production_admin_setup()


if __name__ == "__main__":
    app.run(debug=False)
