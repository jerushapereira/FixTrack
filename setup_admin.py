"""One-time, explicitly confirmed setup for FixTrack's designated Admin."""

import getpass
import os
import re
import sys

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash

from auth_security import PROJECT_INSTANCE_DIR, write_admin_password_state
from db import DatabaseUnavailable, database_connection

load_dotenv()


def main():
    email = os.getenv("FIXTRACK_ADMIN_EMAIL", "").strip().lower()
    if not email:
        print("Set FIXTRACK_ADMIN_EMAIL in .env before running this command.", file=sys.stderr)
        return 1
    if len(email) > 150 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        print("FIXTRACK_ADMIN_EMAIL must be a valid email address of at most 150 characters.", file=sys.stderr)
        return 1

    name_for_new_account = None
    other_admins = []
    target = None
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT user_id, full_name, user_role FROM campus_users WHERE lower(email) = %s", (email,))
                matches = cursor.fetchall()
                if len(matches) > 1:
                    print("Multiple existing accounts match the configured email by case. Resolve that data conflict before setup.", file=sys.stderr)
                    return 1
                target = matches[0] if matches else None
                cursor.execute("SELECT user_id, email, full_name FROM campus_users WHERE user_role = 'Admin' AND lower(email) <> %s ORDER BY user_id", (email,))
                other_admins = cursor.fetchall()
    except (DatabaseUnavailable, psycopg2.Error):
        print("Could not read the FixTrack database. Check PostgreSQL and .env settings.", file=sys.stderr)
        return 1

    if other_admins:
        print("Other Admin account(s) already exist. No roles were changed; resolve that explicitly before setup.", file=sys.stderr)
        return 1

    if target:
        print("Designated account: " + target["full_name"] + " <" + email + ">")
    else:
        name_for_new_account = input("Full name for the new Admin account: ").strip()
        if not name_for_new_account or len(name_for_new_account) > 100:
            print("Enter a name between 1 and 100 characters.", file=sys.stderr)
            return 1
        print("A new account will be created for " + email + ".")
    password = getpass.getpass("Enter the temporary local demonstration password (input hidden): ")
    confirmation_password = getpass.getpass("Enter it again (input hidden): ")
    if not password or password != confirmation_password:
        print("The hidden password entries were empty or did not match. No changes were made.", file=sys.stderr)
        return 1
    print("This one-time setup stores a Werkzeug hash and a non-secret password-change marker.")
    confirmation = input("Type the designated email exactly to continue: ").strip().lower()
    if confirmation != email:
        print("Cancelled. No database changes were made.")
        return 1

    password_hash = generate_password_hash(password)
    del password, confirmation_password
    state_file = PROJECT_INSTANCE_DIR / "admin_password_state.json"
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("LOCK TABLE campus_users IN SHARE ROW EXCLUSIVE MODE")
                cursor.execute("SELECT user_id FROM campus_users WHERE lower(email) = %s FOR UPDATE", (email,))
                matches = cursor.fetchall()
                if len(matches) > 1:
                    print("Multiple accounts match the configured email. No changes were made.", file=sys.stderr)
                    return 1
                designated_id = matches[0]["user_id"] if matches else None
                cursor.execute("SELECT user_id FROM campus_users WHERE user_role = 'Admin' ORDER BY user_id FOR UPDATE")
                admin_ids = [row["user_id"] for row in cursor.fetchall()]
                if any(admin_id != designated_id for admin_id in admin_ids):
                    print("Another Admin account exists. No roles or passwords were changed.", file=sys.stderr)
                    return 1
                if designated_id is None:
                    cursor.execute("INSERT INTO campus_users (full_name, email, user_role, password_hash) VALUES (%s, %s, 'Admin', %s) RETURNING user_id", (name_for_new_account, email, password_hash))
                    designated_id = cursor.fetchone()["user_id"]
                cursor.execute("UPDATE campus_users SET user_role = 'Admin', password_hash = %s WHERE user_id = %s", (password_hash, designated_id))
                write_admin_password_state(state_file, designated_id, "change_required")
    except (DatabaseUnavailable, psycopg2.Error, OSError):
        print("Admin setup failed. No partial transaction was committed.", file=sys.stderr)
        return 1

    print("The designated Admin account is ready. No password or hash was displayed.")
    print("Change the temporary password through POST /api/auth/change-password before deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
