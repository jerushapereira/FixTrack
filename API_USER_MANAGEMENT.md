# FixTrack roles and API guide

## Authentication and one-time Admin setup

FixTrack reuses its server-side Flask sessions, CSRF protection, password hashes, and PostgreSQL role checks. Call GET /api/auth/csrf first; keep the session cookie and send the returned value in X-CSRFToken for all POST, PATCH, and DELETE requests. Admin authorization is rechecked from PostgreSQL on each protected request.

Set FIXTRACK_ADMIN_EMAIL in the ignored .env file to the actual address you designate. The address is read from configuration and is not hardcoded. The explicit setup command is not called by Flask startup:

~~~powershell
.\.venv\Scripts\Activate.ps1
python setup_admin.py
~~~

The command asks for the configured address as confirmation, requests a name if it must create the account, prompts twice with hidden input for the temporary value specified in the project request, hashes it with Werkzeug, and records a non-secret password-change marker. The password is not kept in source, .env, logs, or a plaintext database field. It refuses to proceed when another Admin exists; it never changes other users’ roles or prints a password or hash. The temporary demo password must be changed before production with POST /api/auth/change-password. A login for the account marked as requiring a password change is restricted to the password-change endpoint. FIXTRACK_ENV=production makes app startup fail unless the designated account is the only Admin and its marker confirms the change. The marker contains only a user ID and state and must be preserved under instance/ when deploying.

## API access

| Endpoint | Who can use it | Purpose |
| --- | --- | --- |
| GET /api/auth/csrf, POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me | Sign-in or authenticated | Session and identity |
| POST /api/auth/change-password | Authenticated | Change own password |
| GET /api/locations | Authenticated | Location choices for a request form |
| POST /api/requests | Authenticated | Create request; reporter is taken from session |
| GET /api/requests and GET /api/requests/{id} | Authenticated | Only the signed-in reporter’s own requests |
| DELETE /api/requests/{id} | Request owner | Delete only if no assignment or status history exists |
| GET /api/admin/data/{table} | Admin | Read one of six tables; related complaint, reporter, worker, assignment, and status details are joined |
| GET /api/admin/reports/{report} | Admin | Existing reports and views |
| /api/admin/users... | Admin | User create/list/edit/password/delete |
| /api/admin/locations... | Admin | Create, update, delete campus locations; use table data route to list |
| /api/admin/workers... | Admin | Create, update, delete workers; use table data route to list |
| POST /api/admin/requests | Admin | Create for an existing reporter |
| PATCH /api/admin/requests/{id} | Admin | Edit request details and update status |
| DELETE /api/admin/requests/{id} | Admin | Delete only when no related history exists |
| POST /api/admin/assignments | Admin | Assign or reassign using assign_worker procedure |

The six table names accepted by /api/admin/data are campus_users, campus_locations, workers, maintenance_requests, assignments, and status_history. campus_users results never include password_hash. Reports include location totals, unresolved-by-category counts, active assignment workload, high-priority unresolved requests, overdue requests, and both existing views plus repair/status history.

The regular request JSON is location_id, title, description, category, and priority. The API sets reporter_id from the session. A successful insert returns 201 and the database-generated request details. Admin request creation accepts the same fields plus reporter_id. Admin account creation cannot assign the Admin role; the one-time setup command is the only way to designate it.

## Exact user-management API contract

Before each state-changing call, request GET /api/auth/csrf, keep its session cookie, and send the returned token in the X-CSRFToken header. The examples below show JSON shapes; example values are illustrative and are not database records.

All user routes require an authenticated Admin. Unauthenticated requests return 401; a signed-in non-Admin gets 403. Invalid or missing fields return 400. Database failures return a generic 503. Errors have this shape: {"error":"Short explanation"}. No response contains a password or password_hash.

### POST /api/admin/users

Required JSON fields: full_name (1–100 characters), email (valid address, maximum 150, normalized to lowercase), user_role, password, and confirm_password. New account roles can be Student, Faculty, or Staff; use the explicit Admin setup command for the single Admin. Passwords must match and contain 12–128 characters.

Example request:

~~~json
{"full_name":"Example User","email":"user@example.edu","user_role":"Student","password":"a-long-example-passphrase","confirm_password":"a-long-example-passphrase"}
~~~

Success is 201:

~~~json
{"message":"User created.","user":{"user_id":23,"full_name":"Example User","email":"user@example.edu","user_role":"Student"}}
~~~

A duplicate email returns 409, for example {"error":"An account with this email already exists."}. Invalid role, email, or password returns 400.

### GET /api/admin/users

No request body. Optional q query parameter searches name or email. Success is 200:

~~~json
{"users":[{"user_id":23,"full_name":"Example User","email":"user@example.edu","user_role":"Student"}]}
~~~

### GET /api/admin/users/{user_id}

No request body. Success is 200 with {"user":{"user_id":23,"full_name":"Example User","email":"user@example.edu","user_role":"Student"}}. A missing account returns 404 with an error object.

### PATCH /api/admin/users/{user_id}

Send one or more of full_name, email, and user_role. Unknown fields are rejected. For example:

~~~json
{"full_name":"Updated Example User","user_role":"Faculty"}
~~~

Success is 200, for example: {"message":"User updated.","user":{"user_id":23,"full_name":"Updated Example User","email":"user@example.edu","user_role":"Faculty"}}. Duplicate email or an attempt to remove/demote the last Admin returns 409. The endpoint cannot designate a second Admin.

### POST /api/admin/users/{user_id}/password

Required JSON fields are password and confirm_password, both 12–128 characters and equal:

~~~json
{"password":"a-new-example-passphrase","confirm_password":"a-new-example-passphrase"}
~~~

Success is 200 with {"message":"Password changed. That user's existing sessions will be rejected on their next request."}. A missing user returns 404; invalid fields return 400. Existing sessions fail their next protected request because the password hash marker no longer matches.

### DELETE /api/admin/users/{user_id}

No request body. Success is 200 with {"message":"User deleted."}. A missing user returns 404. A user with reported requests or the last Admin returns 409; related complaints and history are never deleted to make this operation succeed.

## Record preservation

The request-insert trigger creates a status-history row, so normal requests cannot be deleted without removing audit history. The API returns 409 when assignment or status history exists. Assignment and status-history records are read-only history; worker reassignment uses the existing procedure and keeps ended assignments. Foreign keys prevent deleting users with reported requests, locations used by requests, and workers with assignment history. These operations return 409 rather than cascading or deleting related records. Admins may edit worker/location records, but existing history remains linked by ID.

All database operations use db.py, parameterized SQL, and transactions. Regular users cannot see all users or data and cannot choose their reporter ID. Unauthenticated requests return 401, non-Admin requests to Admin routes return 403, invalid input returns 400, duplicate/conflicting records return 409, and database failures return a generic 503.

## Local run and safe tests

Keep local .env values private. Use FIXTRACK_ENV=development for the local demonstration. Start the server:

~~~powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
~~~

For an isolated integration test, create a separate empty fixtrack_test database in pgAdmin. Execute 02_create_tables.sql, 09_authentication_migration.sql, 07_functions_procedure_trigger.sql, then 08_reports_and_views.sql. Do not execute 01_create_database.sql or insert sample data for tests. The test module refuses to run unless both DB_NAME and FIXTRACK_ALLOW_TEST_DB select the dedicated test database.

~~~powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DB_NAME = "fixtrack_test"
$env:FIXTRACK_ALLOW_TEST_DB = "YES"
python -m pytest -q
~~~

Keep the other database environment variables and Flask secret configured in .env. Close this test shell or restore DB_NAME=fixtrack before running the normal app. For deployment set FIXTRACK_ENV=production, use HTTPS, and set COOKIE_SECURE=true.
