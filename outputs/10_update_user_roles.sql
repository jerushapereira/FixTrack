-- Replace the regular-user role label Staff with Non-Teaching Staff.
-- Existing account IDs and all other account data remain unchanged.
BEGIN;

LOCK TABLE campus_users IN SHARE ROW EXCLUSIVE MODE;

-- Update old Staff values before installing the revised role constraint.
UPDATE campus_users
SET user_role = 'Non-Teaching Staff'
WHERE user_role = 'Staff';

ALTER TABLE campus_users
DROP CONSTRAINT IF EXISTS campus_users_user_role_check;

ALTER TABLE campus_users
ADD CONSTRAINT campus_users_user_role_check
CHECK (user_role IN ('Student', 'Faculty', 'Non-Teaching Staff', 'Admin'));

COMMIT;
