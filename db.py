"""Small PostgreSQL connection helper used by the app and setup command."""

import os
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv

load_dotenv()


class DatabaseUnavailable(Exception):
    """Raised when database settings or the PostgreSQL connection are unavailable."""


def connect_to_database():
    """Open a connection using settings from environment variables."""
    required_settings = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing_settings = [name for name in required_settings if not os.getenv(name)]

    if missing_settings:
        names = ", ".join(missing_settings)
        raise DatabaseUnavailable(f"Missing database settings: {names}.")

    try:
        port = int(os.environ["DB_PORT"])
        return psycopg2.connect(
            host=os.environ["DB_HOST"],
            port=port,
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            connect_timeout=5,
        )
    except (ValueError, psycopg2.Error) as error:
        raise DatabaseUnavailable("Could not connect to PostgreSQL.") from error


@contextmanager
def database_connection():
    """Commit successful work, roll back failed work, and always close the connection."""
    connection = connect_to_database()
    try:
        yield connection
        connection.commit()
    except psycopg2.Error:
        connection.rollback()
        # Keep PostgreSQL error types so routes can safely distinguish duplicate
        # emails and foreign-key dependencies without exposing database details.
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
