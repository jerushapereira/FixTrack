-- Report 1: Count requests for every location, including locations with none.
SELECT l.location_id, l.building_name, l.area_name,
       COUNT(r.request_id) AS request_count
FROM campus_locations AS l
LEFT JOIN maintenance_requests AS r ON r.location_id = l.location_id
GROUP BY l.location_id, l.building_name, l.area_name
ORDER BY l.building_name, l.area_name;

-- Report 2: Count unresolved requests by category.
SELECT category, COUNT(*) AS unresolved_request_count
FROM maintenance_requests
WHERE current_status IN ('Pending', 'In Progress')
GROUP BY category
ORDER BY category;

-- Report 3: Count active assignments for every worker, including workers with none.
SELECT w.worker_id, w.full_name, w.specialization,
       COUNT(a.assignment_id) AS active_assignment_count
FROM workers AS w
LEFT JOIN assignments AS a
    ON a.worker_id = w.worker_id
   AND a.ended_at IS NULL
GROUP BY w.worker_id, w.full_name, w.specialization
ORDER BY active_assignment_count DESC, w.full_name;

-- Report 4A: Assignment and repair history, one row per assignment record.
-- A LEFT JOIN keeps requests that do not have an assignment yet.
SELECT r.request_id, r.title, r.current_status,
       w.full_name AS worker_assigned, a.assigned_at, a.ended_at
FROM maintenance_requests AS r
LEFT JOIN assignments AS a ON a.request_id = r.request_id
LEFT JOIN workers AS w ON w.worker_id = a.worker_id
ORDER BY r.request_id, a.assigned_at;

-- Report 4B: Status history, one row per status-history record.
-- Kept separate from assignment history to avoid multiplying rows
-- when a request has multiple assignments and multiple status changes.
SELECT r.request_id, r.title, r.current_status,
       h.status AS history_status, h.changed_at, h.note
FROM maintenance_requests AS r
LEFT JOIN status_history AS h ON h.request_id = r.request_id
ORDER BY r.request_id, h.changed_at;

-- Report 5: High-priority unresolved requests, oldest report first.
SELECT r.request_id, r.title, r.category, r.current_status,
       l.building_name, l.area_name, r.reported_at
FROM maintenance_requests AS r
JOIN campus_locations AS l ON l.location_id = r.location_id
WHERE r.priority = 'High'
  AND r.current_status IN ('Pending', 'In Progress')
ORDER BY r.reported_at;

-- Report 6: Unresolved requests reported more than seven days ago.
SELECT r.request_id, r.title, r.priority, r.current_status,
       l.building_name, l.area_name, r.reported_at
FROM maintenance_requests AS r
JOIN campus_locations AS l ON l.location_id = r.location_id
WHERE r.current_status IN ('Pending', 'In Progress')
  AND r.reported_at < CURRENT_TIMESTAMP - INTERVAL '7 days'
ORDER BY r.reported_at;

-- View of unresolved complaints with reporter and location details.
CREATE OR REPLACE VIEW pending_complaints_view AS
SELECT r.request_id, r.title, r.description, r.category, r.priority,
       r.current_status, r.reported_at,
       u.user_id AS reporter_id, u.full_name AS reporter_name,
       l.location_id, l.building_name, l.area_name
FROM maintenance_requests AS r
JOIN campus_users AS u ON u.user_id = r.reporter_id
JOIN campus_locations AS l ON l.location_id = r.location_id
WHERE r.current_status IN ('Pending', 'In Progress');

-- View of current assignments with worker and request details.
CREATE OR REPLACE VIEW active_assignments_view AS
SELECT a.assignment_id, a.assigned_at,
       w.worker_id, w.full_name AS worker_name, w.specialization,
       r.request_id, r.title, r.category, r.priority, r.current_status,
       l.building_name, l.area_name
FROM assignments AS a
JOIN workers AS w ON w.worker_id = a.worker_id
JOIN maintenance_requests AS r ON r.request_id = a.request_id
JOIN campus_locations AS l ON l.location_id = r.location_id
WHERE a.ended_at IS NULL;
