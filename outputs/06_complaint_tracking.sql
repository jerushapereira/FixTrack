-- Run this script while connected to the fixtrack database.

-- Find location and category pairs with multiple unresolved complaints.
-- Pending and In Progress are treated as unresolved.
SELECT l.building_name, l.area_name, r.category,
       COUNT(*) AS unresolved_complaint_count
FROM maintenance_requests AS r
JOIN campus_locations AS l ON l.location_id = r.location_id
WHERE r.current_status IN ('Pending', 'In Progress')
GROUP BY l.location_id, l.building_name, l.area_name, r.category
HAVING COUNT(*) > 1
ORDER BY l.building_name, l.area_name, r.category;

-- Example pre-insert check for an Electrical complaint at Engineering Block, Room 204.
-- If duplicate_exists is true, an unresolved complaint already exists for that place and category.
-- If false, continue with the new complaint INSERT.
SELECT EXISTS (
    SELECT 1
    FROM maintenance_requests AS r
    JOIN campus_locations AS l ON l.location_id = r.location_id
    WHERE l.building_name = 'Engineering Block'
      AND l.area_name = 'Room 204'
      AND r.category = 'Electrical'
      AND r.current_status IN ('Pending', 'In Progress')
) AS duplicate_exists;

-- Show high-priority complaints that are still unresolved.
SELECT request_id, title, category, current_status, reported_at
FROM maintenance_requests
WHERE priority = 'High'
  AND current_status IN ('Pending', 'In Progress')
ORDER BY reported_at;

-- Show all complaints from highest to lowest priority, then by report date.
SELECT request_id, title, priority, current_status, reported_at
FROM maintenance_requests
ORDER BY CASE priority
             WHEN 'High' THEN 1
             WHEN 'Medium' THEN 2
             WHEN 'Low' THEN 3
         END,
         reported_at;

-- Count complaints in each priority group.
SELECT priority, COUNT(*) AS complaint_count
FROM maintenance_requests
GROUP BY priority
ORDER BY priority;

-- The seven-day threshold selects unresolved requests reported before now minus seven days.
SELECT request_id, title, priority, current_status, reported_at
FROM maintenance_requests
WHERE current_status IN ('Pending', 'In Progress')
  AND reported_at < CURRENT_TIMESTAMP - INTERVAL '7 days'
ORDER BY reported_at;
