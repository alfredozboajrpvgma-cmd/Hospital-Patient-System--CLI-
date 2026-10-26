"""
Keeps an audit log of important actions (registrations, triage, consultations, billing).
This helps track who did what and when.
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from utils.display import (
    print_subheader,
    print_info,
    print_table,
    pause
)
from utils.validators import validate_menu_choice
from config import DATETIME_FORMAT


def log_audit_event(
    conn: sqlite3.Connection,
    user_id: str,
    username: str,
    action: str,
    target_type: str,
    target_id: str,
    details: str = ""
) -> None:
    """Save an action to the audit log. Wrapped in try/except so logging never crashes the app."""
    try:
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs (
                timestamp, user_id, username, action, target_type, target_id, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (timestamp, user_id, username, action, target_type, target_id, details))
        conn.commit()
    except Exception as exc:

        pass


def get_audit_logs(
    conn: sqlite3.Connection,
    limit: int = 50,
    target_type: Optional[str] = None
) -> List[sqlite3.Row]:
    """Get the most recent audit logs, optionally filtered by type."""
    cursor = conn.cursor()
    if target_type:
        cursor.execute("""
            SELECT * FROM audit_logs
            WHERE UPPER(target_type) = UPPER(?)
            ORDER BY log_id DESC
            LIMIT ?
        """, (target_type.strip(), limit))
    else:
        cursor.execute("""
            SELECT * FROM audit_logs
            ORDER BY log_id DESC
            LIMIT ?
        """, (limit,))
    return cursor.fetchall()


def handle_view_audit_logs(conn: sqlite3.Connection) -> None:
    """Display the activity log in a table."""
    print_subheader("Hospital System Audit Logs & Activity Trail")
    print_info("Shows timestamps, acting user, action type, and affected hospital entity.\n")

    logs = get_audit_logs(conn, limit=30)
    if not logs:
        print_info("No audit logs recorded yet.")
        pause()
        return

    headers = ["ID", "Timestamp", "User", "Action", "Entity", "Target ID", "Details"]
    rows = [
        [
            str(l["log_id"]),
            l["timestamp"],
            f"{l['username']} ({l['user_id']})",
            l["action"],
            l["target_type"],
            l["target_id"],
            (l["details"][:30] + "...") if len(l["details"]) > 30 else l["details"]
        ]
        for l in logs
    ]
    print_table(headers, rows)
    pause()
