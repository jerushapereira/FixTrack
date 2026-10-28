"""Track whether the designated Admin must replace the temporary password.

This state stores only an account ID and a status, never a password or password hash.
"""

import json
import os
from pathlib import Path

PROJECT_INSTANCE_DIR = Path(__file__).resolve().parent / "instance"


def read_admin_password_state(state_file):
    """Read the local password-change marker; return None when it is absent or invalid."""
    try:
        state = json.loads(Path(state_file).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(state, dict) or not isinstance(state.get("user_id"), int):
        return None
    if state.get("state") not in {"change_required", "changed"}:
        return None
    return state


def write_admin_password_state(state_file, user_id, state):
    """Atomically save a non-secret Admin password-change state."""
    if not isinstance(user_id, int) or state not in {"change_required", "changed"}:
        raise ValueError("Invalid Admin password state.")
    destination = Path(state_file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps({"user_id": user_id, "state": state}), encoding="utf-8")
    os.replace(temporary, destination)
