"""Interactive password setup for existing FixTrack users."""

import argparse
import getpass
import sys

import psycopg2

from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash

from db import DatabaseUnavailable, database_connection


def set_password(email):
    """Set a password hash for an existing campus user."""
    password = getpass.getpass("New password (input is hidden): ")
    confirmation = getpass.getpass("Enter the same password again: ")

    if not password:
        print("Password cannot be empty.", file=sys.stderr)
        return 1
    if password != confirmation:
        print("The passwords did not match.", file=sys.stderr)
        return 1
    if len(password) < 12:
        print("Use a password with at least 12 characters.", file=sys.stderr)
        return 1

    password_hash = generate_password_hash(password)
    with database_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT user_id, full_name FROM campus_users WHERE email = %s",
                (email,),
            )
            user = cursor.fetchone()
            if not user:
                print("No existing campus user has that email.", file=sys.stderr)
                return 1

            cursor.execute(
                "UPDATE campus_users SET password_hash = %s WHERE user_id = %s",
                (password_hash, user["user_id"]),
            )

    # Never display the entered password or its hash.
    print(f"Password set for existing user {user['full_name']} ({email}).")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Set a password for an existing FixTrack user.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    password_parser = subcommands.add_parser("set-password", help="Set a password for an existing user.")
    password_parser.add_argument("email", help="Email address of an existing campus user.")

    arguments = parser.parse_args()
    try:
        if arguments.command == "set-password":
            return set_password(arguments.email.strip())
    except DatabaseUnavailable as error:
        print(f"Database setup failed: {error}", file=sys.stderr)
        return 1
    except psycopg2.Error:
        print("Database setup failed. Check PostgreSQL and the selected user account.", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
