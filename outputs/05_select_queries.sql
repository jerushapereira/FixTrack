-- High-priority complaints, newest first.
SELECT request_id, title, category, current_status, reported_at
FROM maintenance_requests
WHERE priority = 'High'
ORDER BY reported_at DESC;

-- Unresolved complaints are those still Pending or In Progress.
SELECT request_id, title, category, priority, current_status
FROM maintenance_requests
WHERE current_status IN ('Pending', 'In Progress')
ORDER BY priority, reported_at;

-- Complaint counts by category. HAVING keeps categories with at least two records.
SELECT category, COUNT(*) AS complaint_count
FROM maintenance_requests
GROUP BY category
HAVING COUNT(*) >= 2
ORDER BY complaint_count DESC, category;

-- Complaint counts for every location, including locations with no complaints.
SELECT l.building_name, l.area_name, COUNT(r.request_id) AS complaint_count
FROM campus_locations AS l
LEFT JOIN maintenance_requests AS r ON r.location_id = l.location_id
GROUP BY l.location_id, l.building_name, l.area_name
ORDER BY complaint_count DESC, l.building_name;

-- Earliest and latest complaint dates by category (MIN and MAX).
SELECT category, MIN(reported_at) AS first_reported, MAX(reported_at) AS last_reported
FROM maintenance_requests
GROUP BY category
ORDER BY category;

-- Average number of complaints per location, including locations with zero complaints.
SELECT ROUND(AVG(location_totals.complaint_count), 2) AS average_complaints_per_location
FROM (
    SELECT l.location_id, COUNT(r.request_id) AS complaint_count
    FROM campus_locations AS l
    LEFT JOIN maintenance_requests AS r ON r.location_id = l.location_id
    GROUP BY l.location_id
) AS location_totals;

-- Join each complaint to its reporter and location.
SELECT r.request_id, r.title, u.full_name AS reporter,
       l.building_name, l.area_name, r.current_status
FROM maintenance_requests AS r
JOIN campus_users AS u ON u.user_id = r.reporter_id
JOIN campus_locations AS l ON l.location_id = r.location_id
ORDER BY r.reported_at;

-- Assignment history, including ended assignments and the assigned worker.
SELECT r.title, w.full_name AS worker, a.assigned_at, a.ended_at
FROM assignments AS a
JOIN maintenance_requests AS r ON r.request_id = a.request_id
JOIN workers AS w ON w.worker_id = a.worker_id
ORDER BY r.title, a.assigned_at;

-- Worker workload counts active assignments only (ended_at is NULL).
SELECT w.worker_id, w.full_name,
       COUNT(a.assignment_id) AS active_assignment_count
FROM workers AS w
LEFT JOIN assignments AS a
    ON a.worker_id = w.worker_id
   AND a.ended_at IS NULL
GROUP BY w.worker_id, w.full_name
ORDER BY active_assignment_count DESC, w.full_name;

-- Nested query: show complaints reported by users who have reported more than one.
SELECT request_id, title, reporter_id, reported_at
FROM maintenance_requests
WHERE reporter_id IN (
    SELECT reporter_id
    FROM maintenance_requests
    GROUP BY reporter_id
    HAVING COUNT(*) > 1
)
ORDER BY reporter_id, reported_at;

-- Simple query-based duplicate check for unresolved complaints
-- at the same location and in the same category.
SELECT l.building_name, l.area_name, r.category,
       COUNT(*) AS unresolved_complaint_count
FROM maintenance_requests AS r
JOIN campus_locations AS l ON l.location_id = r.location_id
WHERE r.current_status IN ('Pending', 'In Progress')
GROUP BY l.location_id, l.building_name, l.area_name, r.category
HAVING COUNT(*) > 1
ORDER BY unresolved_complaint_count DESC;
