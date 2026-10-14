"""
Handles the daily patient queue, walk-in tickets, and routing
patients from triage to doctor consultation and billing.
"""

import sqlite3
from datetime import date, datetime
from typing import Optional, List, Tuple

from utils.display import (
    print_subheader,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_table,
    confirm_action,
    pause
)
from utils.validators import validate_menu_choice
from config import DATE_FORMAT, DATETIME_FORMAT, QUEUE_STATUSES, DEPARTMENTS
from modules.audit import log_audit_event
from modules.auth import get_current_session


def get_next_daily_queue_number(conn: sqlite3.Connection, ticket_date: str) -> int:
    """Get the next daily queue number (starts at 1 every morning)."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MAX(queue_number) as max_num FROM queue_tickets
        WHERE ticket_date = ?
    """, (ticket_date,))
    row = cursor.fetchone()
    if row and row["max_num"]:
        return row["max_num"] + 1
    return 1


def generate_ticket_id(conn: sqlite3.Connection) -> str:
    """Generate a unique ticket ID like TKT-1001."""
    cursor = conn.cursor()
    cursor.execute("SELECT ticket_id FROM queue_tickets WHERE ticket_id LIKE 'TKT-%' ORDER BY ticket_id DESC")
    rows = cursor.fetchall()

    max_val = 1000
    for r in rows:
        tid = r["ticket_id"]
        parts = tid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_val:
                max_val = val
    return f"TKT-{max_val + 1}"


def issue_queue_ticket(
    conn: sqlite3.Connection,
    patient_id: str,
    department: str,
    ticket_type: str = "Walk-in",
    ticket_date: Optional[str] = None
) -> Tuple[str, int]:
    """Create a new queue ticket for a patient."""
    t_date = ticket_date or date.today().strftime(DATE_FORMAT)
    q_num = get_next_daily_queue_number(conn, t_date)
    ticket_id = generate_ticket_id(conn)
    created_at = datetime.now().strftime(DATETIME_FORMAT)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO queue_tickets (
            ticket_id, queue_number, patient_id, department, ticket_date, ticket_type, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'Waiting', ?);
    """, (ticket_id, q_num, patient_id, department, t_date, ticket_type, created_at))
    conn.commit()

    session = get_current_session()
    user_id = session.user_id if session else "SYSTEM"
    username = session.username if session else "system"
    log_audit_event(conn, user_id, username, "QUEUE_TICKET_ISSUED", "QueueTicket", ticket_id, f"Queue #{q_num} for {department} ({ticket_type})")

    return ticket_id, q_num


def get_daily_queue(
    conn: sqlite3.Connection,
    target_date: Optional[str] = None,
    status_filter: Optional[str] = None
) -> List[sqlite3.Row]:
    """Get queue tickets for a date, with emergency tickets shown first."""
    t_date = target_date or date.today().strftime(DATE_FORMAT)
    cursor = conn.cursor()

    query = """
        SELECT q.*, p.full_name as patient_name, p.contact_number
        FROM queue_tickets q
        JOIN patients p ON q.patient_id = p.patient_id
        WHERE q.ticket_date = ?
    """
    params = [t_date]

    if status_filter:
        query += " AND q.status = ?"
        params.append(status_filter)

    # Put Emergency tickets at the top, then Scheduled, then Walk-ins
    query += """
        ORDER BY 
            CASE q.ticket_type 
                WHEN 'Emergency' THEN 1 
                WHEN 'Scheduled' THEN 2 
                ELSE 3 
            END ASC,
            q.queue_number ASC
    """
    cursor.execute(query, tuple(params))
    return cursor.fetchall()


def update_queue_status(conn: sqlite3.Connection, ticket_id: str, new_status: str, enforce_transitions: bool = True) -> bool:
    """Update a ticket's status (Waiting -> Triage -> Consultation -> Billing -> Completed)."""
    if new_status not in QUEUE_STATUSES:
        return False

    cursor = conn.cursor()
    cursor.execute("SELECT status FROM queue_tickets WHERE ticket_id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    if not ticket:
        return False

    current_status = ticket["status"]
    if current_status == new_status:
        return True

    # Check if the status change is valid
    from config import VALID_QUEUE_TRANSITIONS
    if enforce_transitions:
        allowed = VALID_QUEUE_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            return False

    cursor.execute("UPDATE queue_tickets SET status = ? WHERE ticket_id = ?", (new_status, ticket_id))
    conn.commit()

    session = get_current_session()
    user_id = session.user_id if session else "SYSTEM"
    username = session.username if session else "system"
    log_audit_event(conn, user_id, username, "QUEUE_STATUS_UPDATED", "QueueTicket", ticket_id, f"Status changed from {current_status} to {new_status}")

    return cursor.rowcount > 0


def close_patient_active_queue_ticket(
    conn: sqlite3.Connection,
    patient_id: str,
    new_status: str = "Completed",
    target_date: Optional[str] = None
) -> Optional[str]:
    """Close any active queue ticket for a patient once their visit or payment is done."""
    t_date = target_date or date.today().strftime(DATE_FORMAT)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticket_id, status FROM queue_tickets
        WHERE UPPER(patient_id) = UPPER(?) AND ticket_date = ?
          AND status IN ('Waiting', 'Triage', 'Consultation')
        ORDER BY created_at DESC
        LIMIT 1;
    """, (patient_id.strip(), t_date))
    row = cursor.fetchone()
    if not row:
        return None

    tid = row["ticket_id"]
    cursor.execute("UPDATE queue_tickets SET status = ? WHERE ticket_id = ?", (new_status, tid))
    conn.commit()

    session = get_current_session()
    uid = session.user_id if session else "SYSTEM"
    uname = session.username if session else "system"
    log_audit_event(conn, uid, uname, "QUEUE_TICKET_CLOSED", "QueueTicket", tid, f"Status updated to {new_status} upon clinical consultation/visit completion")
    return tid


def get_queue_ticket_by_id(conn: sqlite3.Connection, ticket_id: str) -> Optional[sqlite3.Row]:
    """Retrieve ticket details with patient name."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT q.*, p.full_name as patient_name
        FROM queue_tickets q
        JOIN patients p ON q.patient_id = p.patient_id
        WHERE UPPER(q.ticket_id) = UPPER(?)
    """, (ticket_id.strip(),))
    return cursor.fetchone()


# ==========================================
# CLI Submenus and Handlers
# ==========================================

def handle_view_daily_queue(conn: sqlite3.Connection) -> None:
    """Display the active daily queue."""
    today_str = date.today().strftime(DATE_FORMAT)
    print_subheader(f"Hospital Daily Queue Board — {today_str}")

    tickets = get_daily_queue(conn, today_str)
    if not tickets:
        print_info("No patients currently in today's queue.")
        pause()
        return

    headers = ["Queue #", "Ticket ID", "Patient Name", "Department", "Type", "Status", "Arrived At"]
    rows = [
        [
            f"#{t['queue_number']}",
            t["ticket_id"],
            t["patient_name"],
            t["department"],
            t["ticket_type"],
            t["status"],
            t["created_at"].split()[-1] if " " in t["created_at"] else t["created_at"]
        ]
        for t in tickets
    ]
    print_table(headers, rows)
    pause()


def handle_issue_walkin_ticket(conn: sqlite3.Connection) -> None:
    """Issue a queue number for a walk-in patient arriving at the hospital."""
    from modules.patients import select_patient_interactive

    from utils.prompts import select_option, select_menu, confirm_prompt
    from utils.display import render_card

    print_subheader("Issue Walk-In Queue Ticket")
    patient = select_patient_interactive(conn, prompt_text="Enter Patient ID or Name for Queue Ticket: ", include_archived=False)
    if not patient:
        print_warning("Queue ticket issuance cancelled.")
        pause()
        return

    print_info(f"Issuing queue ticket for: {patient['full_name']} ({patient['patient_id']})")
    dept = select_option("Select Clinical Department:", DEPARTMENTS)
    if not dept:
        print_warning("Queue ticket issuance cancelled.")
        pause()
        return

    ticket_type = "Emergency" if "Emergency" in dept else "Walk-in"

    if confirm_prompt(f"Issue queue ticket for {patient['full_name']} in {dept}?", default=True):
        tid, q_num = issue_queue_ticket(conn, patient["patient_id"], dept, ticket_type=ticket_type)
        render_card("HOSPITAL QUEUE PASS ISSUED", {
            "Queue Number": f"#{q_num} ({ticket_type})",
            "Ticket Reference": tid,
            "Patient": patient["full_name"],
            "Department": dept,
            "Status": "Waiting (Proceed to Nursing Triage)"
        })
    pause()


def handle_advance_queue_status(conn: sqlite3.Connection) -> None:
    """Move a patient to their next step in the hospital queue."""
    from utils.prompts import select_option, select_menu
    today_str = date.today().strftime(DATE_FORMAT)
    print_subheader("Update Patient Queue Status")

    tickets = get_daily_queue(conn, today_str)
    active = [t for t in tickets if t["status"] not in ("Completed", "Cancelled")]
    if not active:
        print_info("No active queue tickets waiting to be updated.")
        pause()
        return

    headers = ["#", "Queue #", "Patient Name", "Department", "Current Status"]
    rows = [
        [str(i), f"#{t['queue_number']}", t["patient_name"], t["department"], t["status"]]
        for i, t in enumerate(active, 1)
    ]
    print_table(headers, rows)

    ticket_choices = [f"#{t['queue_number']} - {t['patient_name']} ({t['department']}) [{t['status']}]" for t in active]
    ticket_choices.append("Cancel")

    chosen_str = select_menu("Select Ticket to Advance:", ticket_choices)
    if not chosen_str or chosen_str == "Cancel":
        return

    chosen_q_num = int(chosen_str.split(" - ")[0].replace("#", ""))
    chosen = next((t for t in active if t["queue_number"] == chosen_q_num), None)
    if not chosen:
        return

    print_info(f"Selected: #{chosen['queue_number']} - {chosen['patient_name']} (Current Status: {chosen['status']})")
    from config import VALID_QUEUE_TRANSITIONS
    allowed = VALID_QUEUE_TRANSITIONS.get(chosen["status"], [])
    if not allowed:
        print_info(f"Ticket #{chosen['queue_number']} is in terminal state '{chosen['status']}' and cannot be transitioned further.")
        pause()
        return

    new_st = select_option(f"Select Next Queue Status (Current: {chosen['status']}):", allowed)
    if not new_st:
        return

    if update_queue_status(conn, chosen["ticket_id"], new_st):
        print_success(f"Ticket #{chosen['queue_number']} status updated to '{new_st}'.")
    else:
        print_error(f"Cannot transition ticket #{chosen['queue_number']} from '{chosen['status']}' to '{new_st}'.")
    pause()


def queue_menu(conn: sqlite3.Connection) -> None:
    """Queue management menu loop."""
    from utils.prompts import select_menu

    choices = [
        "1. View Today's Hospital Queue Board",
        "2. Issue Walk-In Queue Ticket",
        "3. Advance Patient Queue Status",
        "4. Return to Main Menu"
    ]

    while True:
        print_subheader("Patient Queue & Triage Routing Menu")
        choice = select_menu("Select Queue Management Option:", choices)
        if not choice or "Return to Main Menu" in choice:
            break

        if choice.startswith("1."):
            handle_view_daily_queue(conn)
        elif choice.startswith("2."):
            handle_issue_walkin_ticket(conn)
        elif choice.startswith("3."):
            handle_advance_queue_status(conn)
