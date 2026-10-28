-- Safe INSERT, UPDATE, and DELETE demonstration.
-- The transaction is rolled back at the end, so sample records are unchanged.
BEGIN;

-- INSERT one temporary demonstration user.
INSERT INTO campus_users (full_name, email, user_role)
VALUES ('DML Demonstration User', 'dml.demo@fixtrack.example', 'Staff');

-- UPDATE the temporary user inserted above.
UPDATE campus_users
SET full_name = 'DML Demo User Updated'
WHERE email = 'dml.demo@fixtrack.example';

-- DELETE only the temporary user inserted above.
DELETE FROM campus_users
WHERE email = 'dml.demo@fixtrack.example';

-- Undo the demonstration so no permanent row is added or removed.
ROLLBACK;
