-- FixTrack sample data for a fresh database.
-- Insert parent records first so later foreign keys can find them.

INSERT INTO campus_users (full_name, email, user_role) VALUES
    ('Asha Patel', 'asha.patel@example.edu', 'Student'),
    ('Mateo Kim', 'mateo.kim@example.edu', 'Student'),
    ('Imani Brooks', 'imani.brooks@example.edu', 'Student'),
    ('Elena Ruiz', 'elena.ruiz@example.edu', 'Faculty'),
    ('Omar Haddad', 'omar.haddad@example.edu', 'Staff'),
    ('Nia Chen', 'nia.chen@example.edu', 'Student');

INSERT INTO campus_locations (building_name, area_name) VALUES
    ('Engineering Block', 'Room 204'),
    ('Library', 'Ground Floor'),
    ('Science Block', 'Laboratory 2'),
    ('Student Center', 'Cafeteria'),
    ('Administration Block', 'Room 12'),
    ('Sports Complex', 'Changing Room');

INSERT INTO workers (full_name, phone, specialization) VALUES
    ('Ravi Shah', '555-0101', 'Electrical'),
    ('Lena Ortiz', '555-0102', 'Electrical'),
    ('Noah Singh', '555-0103', 'Plumbing'),
    ('Maya Das', '555-0104', 'Carpentry'),
    ('Ethan Cole', '555-0105', 'Network Support'),
    ('Sara Ali', '555-0106', 'HVAC');

-- Insert 12 maintenance requests using the unique email and location keys.
INSERT INTO maintenance_requests
    (reporter_id, location_id, title, description, category, priority, current_status, reported_at)
VALUES
    ((SELECT user_id FROM campus_users WHERE email = 'asha.patel@example.edu'),
     (SELECT location_id FROM campus_locations WHERE building_name = 'Engineering Block' AND area_name = 'Room 204'),
     'Ceiling light flickering in lab', 'The ceiling light near the lab entrance flickers.', 'Electrical', 'High', 'In Progress', TIMESTAMP '2026-10-01 09:00:00'),
    ((SELECT user_id FROM campus_users WHERE email = 'mateo.kim@example.edu'),
     (SELECT location_id FROM campus_locations WHERE building_name = 'Engineering Block' AND area_name = 'Room 204'),
     'Second report of lab light problem', 'A second report for the flickering ceiling light.', 'Electrical', 'High', 'In Progress', TIMESTAMP '2026-10-02 10:15:00'),
    ((SELECT user_id FROM campus_users WHERE email = 'mateo.kim@example.edu'),
     (SELECT location_id FROM campus_locations WHERE building_name = 'Library' AND area_name = 'Ground Floor'),
     'Library washbasin is leaking', 'Water is leaking below the ground-floor washbasin.', 'Plumbing', 'High', 'Resolved', TIMESTAMP '2026-10-03 08:30:00'),
    ((SELECT user_id FROM campus_users WHERE email = 'imani.brooks@example.edu'),
     (SELECT location_id FROM campus_locations WHERE building_name = 'Engineering Block' AND area_name = 'Room 204'),
     'Lab table has a loose leg', 'One leg of the table moves when it is used.', 'Furniture', 'Medium', 'Pending', TIMESTAMP '2026-10-04 11:00:00'),
    ((SELECT user_id FROM campus_users WHERE email = 'omar.haddad@example.edu'),
     (SELECT location_id FROM campus_locations WHERE building_name = 'Student Center' AND area_name = 'Cafeteria'),
     'Cafeteria sink drain is blocked', 'Water drains slowly from the main cafeteria sink.', 'Plumbing', 'Medium', 'In Progress', TIMESTAMP '2026-10-05 09:20:00'),
    ((SELECT user_id FROM campus_users WHERE email = 'elena.ruiz@example.edu'),
     (SELECT location_id FROM campus_locations WHERE building_name = 'Science Block' AND area_name = 'Laboratory 2'),
     'Network outlet is offline', 'The network outlet beside the laboratory desk has no connection.', 'Network', 'Medium', 'Resolved', TIMESTAMP '2026-10-06 13:10:00'),
    ((SELECT user_id FROM campus_users WHERE email = 'nia.chen@example.edu'),
     (SELECT location_id FROM campus_locations WHERE building_name = 'Library' AND area_name = 'Ground Floor'),
     'Reading area floor needs cleaning', 'A spill remains on the floor near the reading area.', 'Cleaning', 'Low', 'Pending', TIMESTAMP '2026-10-07 10:45:00'),
    ((SELECT user_id FROM campus_users WHERE email = 'elena.ruiz@example.edu'),
     (SELECT location_id FROM campus_locations WHERE building_name = 'Administration Block' AND area_name = 'Room 12'),
     'Room air conditioner is weak', 'The air conditioner is running but not cooling the room.', 'HVAC', 'High', 'In Progress', TIMESTAMP '2026-10-08 08:50:00'),
    ((SELECT user_id FROM campus_users WHERE email = 'imani.brooks@example.edu'),
     (SELECT location_id FROM campus_locations WHERE building_name = 'Sports Complex' AND area_name = 'Changing Room'),
     'Shower valve is stuck', 'The changing-room shower valve is difficult to turn.', 'Plumbing', 'Medium', 'Resolved', TIMESTAMP '2026-10-09 14:00:00'),
    ((SELECT user_id FROM campus_users WHERE email = 'asha.patel@example.edu'),
     (SELECT location_id FROM campus_locations WHERE building_name = 'Student Center' AND area_name = 'Cafeteria'),
     'Cafeteria exit sign is not lit', 'The sign above the cafeteria exit is not illuminated.', 'Safety', 'High', 'In Progress', TIMESTAMP '2026-10-10 12:05:00'),
    ((SELECT user_id FROM campus_users WHERE email = 'mateo.kim@example.edu'),
     (SELECT location_id FROM campus_locations WHERE building_name = 'Library' AND area_name = 'Ground Floor'),
     'Library chair upholstery is torn', 'The upholstery is torn on a chair in the reading area.', 'Furniture', 'Low', 'Pending', TIMESTAMP '2026-10-11 09:40:00'),
    ((SELECT user_id FROM campus_users WHERE email = 'nia.chen@example.edu'),
     (SELECT location_id FROM campus_locations WHERE building_name = 'Science Block' AND area_name = 'Laboratory 2'),
     'Laboratory wall socket is loose', 'The wall socket near the rear bench moves when touched.', 'Electrical', 'Medium', 'Resolved', TIMESTAMP '2026-10-12 15:25:00');

-- Insert 10 assignment records. A non-NULL ended_at marks a past assignment.
INSERT INTO assignments (request_id, worker_id, assigned_at, ended_at)
VALUES
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Ceiling light flickering in lab'),
     (SELECT worker_id FROM workers WHERE phone = '555-0101'), TIMESTAMP '2026-10-01 10:00:00', TIMESTAMP '2026-10-02 11:00:00'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Ceiling light flickering in lab'),
     (SELECT worker_id FROM workers WHERE phone = '555-0102'), TIMESTAMP '2026-10-02 11:00:00', NULL),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Second report of lab light problem'),
     (SELECT worker_id FROM workers WHERE phone = '555-0102'), TIMESTAMP '2026-10-02 11:00:00', NULL),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Library washbasin is leaking'),
     (SELECT worker_id FROM workers WHERE phone = '555-0103'), TIMESTAMP '2026-10-03 09:00:00', TIMESTAMP '2026-10-04 12:00:00'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Cafeteria sink drain is blocked'),
     (SELECT worker_id FROM workers WHERE phone = '555-0103'), TIMESTAMP '2026-10-05 10:00:00', NULL),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Network outlet is offline'),
     (SELECT worker_id FROM workers WHERE phone = '555-0105'), TIMESTAMP '2026-10-06 14:00:00', TIMESTAMP '2026-10-07 11:30:00'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Room air conditioner is weak'),
     (SELECT worker_id FROM workers WHERE phone = '555-0106'), TIMESTAMP '2026-10-08 09:30:00', NULL),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Shower valve is stuck'),
     (SELECT worker_id FROM workers WHERE phone = '555-0103'), TIMESTAMP '2026-10-09 15:00:00', TIMESTAMP '2026-10-10 10:00:00'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Cafeteria exit sign is not lit'),
     (SELECT worker_id FROM workers WHERE phone = '555-0101'), TIMESTAMP '2026-10-10 13:00:00', NULL),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Laboratory wall socket is loose'),
     (SELECT worker_id FROM workers WHERE phone = '555-0101'), TIMESTAMP '2026-10-12 16:00:00', TIMESTAMP '2026-10-13 12:00:00');

-- Insert status history manually. Each request has an initial Pending entry,
-- followed by later entries where its current status changed.
INSERT INTO status_history (request_id, status, changed_at, note)
VALUES
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Ceiling light flickering in lab'), 'Pending', TIMESTAMP '2026-10-01 09:00:00', 'Request reported.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Ceiling light flickering in lab'), 'In Progress', TIMESTAMP '2026-10-02 11:00:00', 'Worker reassigned and repair started.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Second report of lab light problem'), 'Pending', TIMESTAMP '2026-10-02 10:15:00', 'Request reported.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Second report of lab light problem'), 'In Progress', TIMESTAMP '2026-10-02 11:00:00', 'Worker assigned.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Library washbasin is leaking'), 'Pending', TIMESTAMP '2026-10-03 08:30:00', 'Request reported.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Library washbasin is leaking'), 'In Progress', TIMESTAMP '2026-10-03 09:00:00', 'Repair started.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Library washbasin is leaking'), 'Resolved', TIMESTAMP '2026-10-04 12:00:00', 'Leak repaired.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Lab table has a loose leg'), 'Pending', TIMESTAMP '2026-10-04 11:00:00', 'Request reported.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Cafeteria sink drain is blocked'), 'Pending', TIMESTAMP '2026-10-05 09:20:00', 'Request reported.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Cafeteria sink drain is blocked'), 'In Progress', TIMESTAMP '2026-10-05 10:00:00', 'Worker assigned.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Network outlet is offline'), 'Pending', TIMESTAMP '2026-10-06 13:10:00', 'Request reported.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Network outlet is offline'), 'In Progress', TIMESTAMP '2026-10-06 14:00:00', 'Network check started.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Network outlet is offline'), 'Resolved', TIMESTAMP '2026-10-07 11:30:00', 'Connection restored.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Reading area floor needs cleaning'), 'Pending', TIMESTAMP '2026-10-07 10:45:00', 'Request reported.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Room air conditioner is weak'), 'Pending', TIMESTAMP '2026-10-08 08:50:00', 'Request reported.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Room air conditioner is weak'), 'In Progress', TIMESTAMP '2026-10-08 09:30:00', 'Inspection started.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Shower valve is stuck'), 'Pending', TIMESTAMP '2026-10-09 14:00:00', 'Request reported.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Shower valve is stuck'), 'In Progress', TIMESTAMP '2026-10-09 15:00:00', 'Repair started.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Shower valve is stuck'), 'Resolved', TIMESTAMP '2026-10-10 10:00:00', 'Valve repaired.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Cafeteria exit sign is not lit'), 'Pending', TIMESTAMP '2026-10-10 12:05:00', 'Request reported.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Cafeteria exit sign is not lit'), 'In Progress', TIMESTAMP '2026-10-10 13:00:00', 'Electrical check started.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Library chair upholstery is torn'), 'Pending', TIMESTAMP '2026-10-11 09:40:00', 'Request reported.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Laboratory wall socket is loose'), 'Pending', TIMESTAMP '2026-10-12 15:25:00', 'Request reported.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Laboratory wall socket is loose'), 'In Progress', TIMESTAMP '2026-10-12 16:00:00', 'Electrical repair started.'),
    ((SELECT request_id FROM maintenance_requests WHERE title = 'Laboratory wall socket is loose'), 'Resolved', TIMESTAMP '2026-10-13 12:00:00', 'Socket secured.');

