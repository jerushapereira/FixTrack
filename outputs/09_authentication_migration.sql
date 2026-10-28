-- Authentication migration for the existing FixTrack database.
-- Run this only after backing up fixtrack and while connected to fixtrack.

BEGIN;

-- Add a nullable password hash column; existing users remain unchanged.
ALTER TABLE campus_users
ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- Find and remove the existing role CHECK by its column, not by a guessed name.
-- This handles the unnamed inline CHECK from 02_create_tables.sql and reruns.
DO $$
DECLARE
    role_check_name TEXT;
BEGIN
    FOR role_check_name IN
        SELECT DISTINCT constraint_info.conname
        FROM pg_constraint AS constraint_info
        JOIN pg_attribute AS column_info
          ON column_info.attrelid = constraint_info.conrelid
         AND column_info.attnum = ANY (constraint_info.conkey)
        WHERE constraint_info.conrelid = 'campus_users'::regclass
          AND constraint_info.contype = 'c'
          AND column_info.attname = 'user_role'
    LOOP
        EXECUTE format(
            'ALTER TABLE campus_users DROP CONSTRAINT %I',
            role_check_name
        );
    END LOOP;
END $$;

-- Recreate the role CHECK with Admin included.
ALTER TABLE campus_users
ADD CONSTRAINT campus_users_user_role_check
CHECK (user_role IN ('Student', 'Faculty', 'Staff', 'Admin'));

COMMIT;
