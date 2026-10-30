-- Add the fictional demonstration records requested for FixTrack.
-- This script is safe to rerun: it skips existing users and request titles.
-- New sample users have no password hash and therefore cannot log in.
BEGIN;

-- Add only the missing regular sample users; keep the preconfigured Admin unchanged.
INSERT INTO campus_users (full_name, email, user_role, password_hash)
SELECT sample.full_name, sample.email, sample.user_role, NULL
FROM (VALUES
    ('Aarav Sharma', 'aarav.sharma@example.com', 'Student'),
    ('Ananya Desai', 'ananya.desai@example.com', 'Student'),
    ('Rohan Mehta', 'rohan.mehta@example.com', 'Student'),
    ('Priya Nair', 'priya.nair@example.com', 'Faculty'),
    ('Karan Shah', 'karan.shah@example.com', 'Faculty'),
    ('Sneha Patil', 'sneha.patil@example.com', 'Non-Teaching Staff')
) AS sample(full_name, email, user_role)
WHERE NOT EXISTS (
    SELECT 1 FROM campus_users AS existing
    WHERE lower(existing.email) = lower(sample.email)
);

-- Locations and workers already meet the requested 5–10 record range.
-- Use the existing locations and workers without duplicating them.

-- Insert each sample request with the normal Pending initial status.
-- The existing insert trigger records that initial status in status_history.
INSERT INTO maintenance_requests
    (reporter_id, location_id, title, description, category, priority)
SELECT u.user_id, l.location_id, sample.title, sample.description,
       sample.category, sample.priority
FROM (VALUES
    ('aarav.sharma@example.com', 'Engineering Block', 'Room 204', 'Lab light flickering', 'Light flickers near lab benches.', 'Electrical', 'High'),
    ('ananya.desai@example.com', 'Library', 'Ground Floor', 'Library chair repair', 'A study chair has a loose leg.', 'Furniture', 'Low'),
    ('rohan.mehta@example.com', 'Science Block', 'Laboratory 2', 'Lab computer not starting', 'One workstation does not power on.', 'Computer Hardware', 'High'),
    ('priya.nair@example.com', 'Administration Block', 'Room 12', 'Washbasin tap leaking', 'The tap continues to drip after closing.', 'Plumbing', 'Medium'),
    ('karan.shah@example.com', 'Engineering Block', 'Room 204', 'Electrical socket loose', 'A wall socket is loose and should be checked.', 'Electrical', 'High'),
    ('sneha.patil@example.com', 'Student Center', 'Cafeteria', 'Canteen sink blocked', 'Water drains slowly from the sink.', 'Plumbing', 'Medium'),
    ('aarav.sharma@example.com', 'Library', 'Ground Floor', 'Library door hinge squeaks', 'The entrance door hinge needs maintenance.', 'Civil', 'Low'),
    ('ananya.desai@example.com', 'Administration Block', 'Room 12', 'Corridor light not working', 'The corridor light is not turning on.', 'Electrical', 'Medium'),
    ('rohan.mehta@example.com', 'Engineering Block', 'Room 204', 'Projector computer overheating', 'The lab computer becomes unusually hot.', 'Computer Hardware', 'High'),
    ('priya.nair@example.com', 'Science Block', 'Laboratory 2', 'Laboratory ventilation check', 'Please inspect the ventilation fan.', 'General Maintenance', 'Medium'),
    ('karan.shah@example.com', 'Sports Complex', 'Changing Room', 'Changing room bench loose', 'One bench needs tightening.', 'Furniture', 'Low'),
    ('sneha.patil@example.com', 'Student Center', 'Cafeteria', 'Cafeteria floor tile cracked', 'A floor tile near the counter is cracked.', 'Civil', 'High')
) AS sample(email, building_name, area_name, title, description, category, priority)
JOIN campus_users AS u ON lower(u.email) = lower(sample.email)
JOIN campus_locations AS l
  ON l.building_name = sample.building_name AND l.area_name = sample.area_name
WHERE NOT EXISTS (
    SELECT 1 FROM maintenance_requests AS existing
    WHERE existing.reporter_id = u.user_id AND existing.title = sample.title
);

-- Move selected requests from their real initial Pending status.
-- The existing status-change trigger records every actual change.
UPDATE maintenance_requests AS r
SET current_status = sample.current_status
FROM (VALUES
    ('Library chair repair', 'Resolved'),
    ('Lab computer not starting', 'In Progress'),
    ('Electrical socket loose', 'In Progress'),
    ('Canteen sink blocked', 'Resolved'),
    ('Corridor light not working', 'Resolved'),
    ('Projector computer overheating', 'Pending'),
    ('Laboratory ventilation check', 'In Progress'),
    ('Cafeteria floor tile cracked', 'Resolved')
) AS sample(title, current_status)
WHERE r.title = sample.title
  AND r.current_status IS DISTINCT FROM sample.current_status;

-- Add ten assignments using the existing reassignment procedure.
-- Existing matching assignment records are left unchanged on a rerun.
DO $$
DECLARE
    item RECORD;
    request_key INTEGER;
    worker_key INTEGER;
BEGIN
    FOR item IN
        SELECT * FROM (VALUES
            ('Lab light flickering', 'Ravi Shah'),
            ('Library chair repair', 'Maya Das'),
            ('Lab computer not starting', 'Ethan Cole'),
            ('Washbasin tap leaking', 'Noah Singh'),
            ('Electrical socket loose', 'Lena Ortiz'),
            ('Canteen sink blocked', 'Noah Singh'),
            ('Library door hinge squeaks', 'Maya Das'),
            ('Corridor light not working', 'Ravi Shah'),
            ('Projector computer overheating', 'Ethan Cole'),
            ('Laboratory ventilation check', 'Sara Ali')
        ) AS assignments(request_title, worker_name)
    LOOP
        SELECT request_id INTO request_key
        FROM maintenance_requests WHERE title = item.request_title;
        SELECT worker_id INTO worker_key
        FROM workers WHERE full_name = item.worker_name;

        IF request_key IS NOT NULL AND worker_key IS NOT NULL
           AND NOT EXISTS (
               SELECT 1 FROM assignments
               WHERE request_id = request_key AND worker_id = worker_key
           ) THEN
            CALL assign_worker(request_key, worker_key);
        END IF;
    END LOOP;
END $$;

COMMIT;
