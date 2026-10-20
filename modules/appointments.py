"""
Handles booking outpatient appointments, checking for scheduling conflicts,
and checking in patients when they arrive.
"""

import sqlite3
from datetime import datetime, date
from typing import Optional, List, Tuple

from utils.display import (
    print_subheader,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_table,
    render_notice,
    confirm_action,
    pause
)
from utils.validators import (
    validate_non_empty,
    validate_date,
    validate_time,
    validate_menu_choice
)
from config import DEPARTMENTS, DATE_FORMAT, TIME_FORMAT
from modules.audit import log_audit_event
from modules.auth import get_current_session
from modules.queue import issue_queue_ticket






def generate_appointment_id(conn: sqlite3.Connection) -> str:
    """Generate the next appointment ID like APT-1001, APT-1002, etc."""
    cursor = conn.cursor()
    cursor.execute("SELECT appointment_id FROM appointments WHERE appointment_id LIKE 'APT-%' ORDER BY appointment_id DESC")
    rows = cursor.fetchall()

    max_id_num = 1000
    for row in rows:
        aid = row["appointment_id"]
        parts = aid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_id_num:
                max_id_num = val

    next_id_num = max_id_num + 1
    return f"APT-{next_id_num}"


def check_appointment_conflict(
    conn: sqlite3.Connection,
    appointment_date: str,
    appointment_time: str,
    department: str,
    patient_id: str,
    exclude_appointment_id: Optional[str] = None
) -> Tuple[bool, str]:
    """Check if the patient or department already has a booking at this time."""
    cursor = conn.cursor()


    query_patient = """
        SELECT appointment_id FROM appointments
        WHERE patient_id = ? 
          AND appointment_date = ? 
          AND appointment_time = ?
          AND status IN ('Scheduled', 'Rescheduled')
    """
    params_patient = [patient_id, appointment_date, appointment_time]

    if exclude_appointment_id:
        query_patient += " AND appointment_id != ?"
        params_patient.append(exclude_appointment_id)

    cursor.execute(query_patient, tuple(params_patient))
    patient_conflict = cursor.fetchone()
    if patient_conflict:
        return True, f"Patient already has an active appointment ({patient_conflict['appointment_id']}) at {appointment_date} {appointment_time}."


    query_dept = """
        SELECT appointment_id FROM appointments
        WHERE department = ? 
          AND appointment_date = ? 
          AND appointment_time = ?
          AND status IN ('Scheduled', 'Rescheduled')
    """
    params_dept = [department, appointment_date, appointment_time]
    if exclude_appointment_id:
        query_dept += " AND appointment_id != ?"
        params_dept.append(exclude_appointment_id)

    cursor.execute(query_dept, tuple(params_dept))
    dept_conflict = cursor.fetchone()
    if dept_conflict:
        return True, f"The {department} department already has an appointment booked at {appointment_date} {appointment_time}."

    return False, ""


def schedule_appointment(
    conn: sqlite3.Connection,
    patient_id: str,
    appointment_date: str,
    appointment_time: str,
    department: str,
    reason: str
) -> str:
    """Save a new appointment to the database and return its ID."""
    appointment_id = generate_appointment_id(conn)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO appointments (
            appointment_id, patient_id, appointment_date,
            appointment_time, department, reason, status
        ) VALUES (?, ?, ?, ?, ?, ?, 'Scheduled');
    """, (appointment_id, patient_id, appointment_date, appointment_time, department, reason))
    conn.commit()

    session = get_current_session()
    uid = session.user_id if session else "SYSTEM"
    uname = session.username if session else "system"
    log_audit_event(conn, uid, uname, "APPOINTMENT_SCHEDULED", "Appointment", appointment_id, f"Patient {patient_id} for {department} at {appointment_date} {appointment_time}")

    return appointment_id


def get_appointment_by_id(conn: sqlite3.Connection, appointment_id: str) -> Optional[sqlite3.Row]:
    """Find an appointment by ID and join with patient name."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, p.full_name as patient_name, p.status as patient_status
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE UPPER(a.appointment_id) = UPPER(?)
    """, (appointment_id.strip(),))
    return cursor.fetchone()


def get_upcoming_appointments(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """Get all future appointments that are scheduled or rescheduled."""
    today_str = date.today().strftime(DATE_FORMAT)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, p.full_name as patient_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE a.appointment_date >= ?
          AND a.status IN ('Scheduled', 'Rescheduled')
        ORDER BY a.appointment_date ASC, a.appointment_time ASC
    """, (today_str,))
    return cursor.fetchall()


def get_appointments_by_patient(conn: sqlite3.Connection, patient_id: str) -> List[sqlite3.Row]:
    """Get the appointment history of a specific patient."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, p.full_name as patient_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE UPPER(a.patient_id) = UPPER(?)
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """, (patient_id.strip(),))
    return cursor.fetchall()


def search_appointments(conn: sqlite3.Connection, query: str) -> List[sqlite3.Row]:
    """Find appointments by searching patient ID, appointment ID, or patient name."""
    search_term = f"%{query.strip()}%"
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, p.full_name as patient_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE a.appointment_id LIKE ? 
           OR a.patient_id LIKE ? 
           OR p.full_name LIKE ?
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """, (search_term, search_term, search_term))
    return cursor.fetchall()


def reschedule_appointment(
    conn: sqlite3.Connection,
    appointment_id: str,
    new_date: str,
    new_time: str
) -> Tuple[bool, str]:
    """Move an appointment to a new date and time after checking for conflicts."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments WHERE appointment_id = ?", (appointment_id,))
    apt = cursor.fetchone()

    if not apt:
        return False, f"Appointment '{appointment_id}' not found."


    if apt["status"] == "Cancelled":
        return False, "Cannot reschedule a cancelled appointment."
    if apt["status"] == "Completed":
        return False, "Cannot reschedule an already completed appointment."
    if apt["status"] == "Checked-In":
        return False, "Cannot reschedule an appointment that has already checked in."


    conflict, msg = check_appointment_conflict(
        conn, new_date, new_time, apt["department"], apt["patient_id"], exclude_appointment_id=appointment_id
    )
    if conflict:
        return False, msg

    cursor.execute("""
        UPDATE appointments 
        SET appointment_date = ?, appointment_time = ?, status = 'Rescheduled'
        WHERE appointment_id = ?
    """, (new_date, new_time, appointment_id))
    conn.commit()

    session = get_current_session()
    uid = session.user_id if session else "SYSTEM"
    uname = session.username if session else "system"
    log_audit_event(conn, uid, uname, "APPOINTMENT_RESCHEDULED", "Appointment", appointment_id, f"Rescheduled to {new_date} {new_time}")

    return True, "Appointment rescheduled successfully."


def cancel_appointment(conn: sqlite3.Connection, appointment_id: str) -> Tuple[bool, str]:
    """Mark an appointment as Cancelled."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments WHERE appointment_id = ?", (appointment_id,))
    apt = cursor.fetchone()

    if not apt:
        return False, f"Appointment '{appointment_id}' not found."

    if apt["status"] == "Cancelled":
        return False, "Appointment is already cancelled."
    if apt["status"] == "Completed":
        return False, "Cannot cancel an appointment that has already been completed."

    cursor.execute("UPDATE appointments SET status = 'Cancelled' WHERE appointment_id = ?", (appointment_id,))
    conn.commit()

    session = get_current_session()
    uid = session.user_id if session else "SYSTEM"
    uname = session.username if session else "system"
    log_audit_event(conn, uid, uname, "APPOINTMENT_CANCELLED", "Appointment", appointment_id, "Appointment cancelled")

    return True, "Appointment has been cancelled."


def check_in_appointment(conn: sqlite3.Connection, appointment_id: str) -> Tuple[bool, str, Optional[str]]:
    """Check in a patient on arrival and give them a queue ticket."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments WHERE appointment_id = ?", (appointment_id,))
    apt = cursor.fetchone()

    if not apt:
        return False, f"Appointment '{appointment_id}' not found.", None

    if apt["status"] not in ("Scheduled", "Rescheduled"):
        return False, f"Cannot check in appointment with status '{apt['status']}'.", None

    cursor.execute("UPDATE appointments SET status = 'Checked-In' WHERE appointment_id = ?", (appointment_id,))
    conn.commit()

    ticket_id, q_num = issue_queue_ticket(conn, apt["patient_id"], apt["department"], ticket_type="Scheduled")

    session = get_current_session()
    uid = session.user_id if session else "RECEPTIONIST"
    uname = session.username if session else "receptionist"
    log_audit_event(conn, uid, uname, "APPOINTMENT_CHECKED_IN", "Appointment", appointment_id, f"Checked-in to Queue #{q_num} (Ticket: {ticket_id})")

    return True, f"Patient checked in successfully! Assigned Daily Queue #{q_num} (Ticket: {ticket_id}).", ticket_id


def mark_appointment_noshow(conn: sqlite3.Connection, appointment_id: str) -> Tuple[bool, str]:
    """Mark a missed appointment as No-Show."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments WHERE appointment_id = ?", (appointment_id,))
    apt = cursor.fetchone()

    if not apt:
        return False, f"Appointment '{appointment_id}' not found."

    if apt["status"] in ("Completed", "Cancelled", "Checked-In", "No-Show"):
        return False, f"Cannot mark appointment as No-Show with current status '{apt['status']}'."

    cursor.execute("UPDATE appointments SET status = 'No-Show' WHERE appointment_id = ?", (appointment_id,))
    conn.commit()

    session = get_current_session()
    uid = session.user_id if session else "RECEPTIONIST"
    uname = session.username if session else "receptionist"
    log_audit_event(conn, uid, uname, "APPOINTMENT_NO_SHOW", "Appointment", appointment_id, "Marked as Missed / No-Show")

    return True, "Appointment status updated to 'No-Show'."






def handle_schedule_appointment(conn: sqlite3.Connection) -> None:
    """Interactive screen for booking an appointment."""
    from modules.patients import select_patient_interactive

    print_subheader("Schedule New Appointment")
    print_info("NOTE: Heart attack, trauma, and acute cases do NOT need an appointment.")
    print_info("Emergency cases are treated immediately in the Emergency Room (ER).\n")

    try:
        patient = select_patient_interactive(
            conn,
            prompt_text="Enter Patient ID or Name for appointment (or '?' for list): ",
            include_archived=False
        )
        if not patient:
            print_warning("Scheduling cancelled.")
            pause()
            return

        print_info(f"Booking for: {patient['full_name']} (ID: {patient['patient_id']})")


        while True:
            date_input = input("Enter Appointment Date (YYYY-MM-DD): ").strip()
            if not date_input:
                print_warning("Scheduling cancelled.")
                pause()
                return
            valid, res = validate_date(date_input, allow_future=True, allow_past=False, field_name="Appointment Date")
            if valid:
                appointment_date = res
                break
            print_error(res)


        while True:
            time_input = input("Enter Appointment Time (HH:MM in 24hr format, e.g., 09:30): ").strip()
            if not time_input:
                print_warning("Scheduling cancelled.")
                pause()
                return
            valid, res = validate_time(time_input, field_name="Appointment Time")
            if valid:
                appointment_time = res
                break
            print_error(res)


        from utils.prompts import select_option, confirm_prompt
        from utils.display import render_card
        from utils.validators import AppointmentCreateModel, format_pydantic_error
        from utils.schema import ValidationError

        while True:
            dept_selected = select_option("Select Hospital Department:", DEPARTMENTS)
            if not dept_selected:
                print_warning("Scheduling cancelled.")
                pause()
                return

            department = dept_selected


            if department == "Emergency Room (ER)":
                render_notice(
                    "EMERGENCY NOTICE",
                    [
                        "Emergency Room (ER) does NOT use appointments!",
                        "Heart attack, trauma, and critical cases are treated immediately.",
                    ],
                    border_style="red",
                )
                if confirm_prompt("Do you want to log an IMMEDIATE Emergency (ER) Visit right now?", default=True):
                    from modules.visits import handle_emergency_visit
                    handle_emergency_visit(conn, preselected_patient=patient)
                    return
                else:
                    print_info("Please select a non-emergency clinic for scheduled appointments.")
                    continue
            break


        while True:
            reason_input = input("Enter Reason for Appointment: ").strip()
            if not reason_input:
                print_warning("Scheduling cancelled.")
                pause()
                return
            valid, res = validate_non_empty(reason_input, "Reason", min_length=3)
            if not valid:
                print_error(res)
                continue


            emergency_keywords = ["heart attack", "cardiac", "chest pain", "stroke", "emergency", "trauma", "unconscious", "severe bleeding"]
            if any(kw in res.lower() for kw in emergency_keywords):
                render_notice(
                    "CRITICAL MEDICAL ALERT",
                    [
                        f"'{res}' is an acute medical emergency!",
                        "A heart attack / emergency case does NOT need an appointment.",
                        "The patient must be seen immediately in the Emergency Room (ER)!",
                    ],
                    border_style="red",
                )
                if confirm_prompt("Transfer directly to Emergency ER Visit intake right now?", default=True):
                    from modules.visits import handle_emergency_visit
                    handle_emergency_visit(conn, preselected_patient=patient, default_notes=res)
                    return

            reason = res
            break


        try:
            apt_model = AppointmentCreateModel(
                patient_id=patient["patient_id"],
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                department=department,
                reason=reason
            )
        except ValidationError as exc:
            print_error(format_pydantic_error(exc))
            pause()
            return


        has_conflict, conflict_msg = check_appointment_conflict(
            conn, apt_model.appointment_date, apt_model.appointment_time, apt_model.department, apt_model.patient_id
        )
        if has_conflict:
            print_error(f"Scheduling Conflict: {conflict_msg}")
            pause()
            return


        render_card("OUTPATIENT APPOINTMENT PREVIEW", {
            "Patient": f"{patient['full_name']} ({patient['patient_id']})",
            "Date": apt_model.appointment_date,
            "Time": apt_model.appointment_time,
            "Department": apt_model.department,
            "Reason": apt_model.reason
        })

        if confirm_prompt("Confirm booking appointment?", default=True):
            apt_id = schedule_appointment(
                conn, apt_model.patient_id, apt_model.appointment_date, apt_model.appointment_time, apt_model.department, apt_model.reason
            )
            print_success(f"Appointment scheduled successfully! Appointment ID: {apt_id}")
        else:
            print_info("Booking cancelled.")

    except (KeyboardInterrupt, EOFError):
        print("\nScheduling cancelled by user.")
    pause()


def handle_view_upcoming_appointments(conn: sqlite3.Connection) -> None:
    """Show upcoming appointments ordered by date."""
    print_subheader("Upcoming Appointments")
    appointments = get_upcoming_appointments(conn)

    headers = ["Apt ID", "Patient ID", "Patient Name", "Date", "Time", "Department", "Status"]
    rows = [
        [
            a["appointment_id"],
            a["patient_id"],
            a["patient_name"],
            a["appointment_date"],
            a["appointment_time"],
            a["department"],
            a["status"]
        ]
        for a in appointments
    ]
    print_table(headers, rows, empty_message="No upcoming appointments scheduled.")
    pause()


def handle_search_appointments(conn: sqlite3.Connection) -> None:
    """Search appointments and print matching rows."""
    print_subheader("Search Appointments")
    query = input("Enter Appointment ID, Patient ID, or Patient Name: ").strip()

    if not query:
        print_error("Search term cannot be empty.")
        pause()
        return

    results = search_appointments(conn, query)
    headers = ["Apt ID", "Patient ID", "Patient Name", "Date", "Time", "Department", "Status", "Reason"]
    rows = [
        [
            a["appointment_id"],
            a["patient_id"],
            a["patient_name"],
            a["appointment_date"],
            a["appointment_time"],
            a["department"],
            a["status"],
            a["reason"]
        ]
        for a in results
    ]
    print_table(headers, rows, empty_message=f"No appointments found matching '{query}'.")
    pause()



def select_appointment_interactive(
    conn: sqlite3.Connection,
    prompt_text: str = "Enter Appointment ID (or '?' for list, '0' to cancel): "
) -> Optional[sqlite3.Row]:
    """Helper to select an appointment by ID, browse upcoming, or search by patient name."""
    while True:
        user_input = input(prompt_text).strip()
        if not user_input or user_input.lower() in ("0", "q", "cancel", "back"):
            return None

        if user_input in ("?", "list"):
            appointments = get_upcoming_appointments(conn)
            if not appointments:
                print_info("No upcoming appointments found.")
                continue
            headers = ["Apt ID", "Patient ID", "Patient Name", "Date", "Time", "Department", "Status"]
            rows = [
                [
                    a["appointment_id"],
                    a["patient_id"],
                    a["patient_name"],
                    a["appointment_date"],
                    a["appointment_time"],
                    a["department"],
                    a["status"]
                ]
                for a in appointments
            ]
            print_table(headers, rows)
            continue


        apt = get_appointment_by_id(conn, user_input)
        if apt:
            return apt


        if user_input.isdigit():
            apt = get_appointment_by_id(conn, f"APT-{user_input}")
            if apt:
                return apt


        matches = search_appointments(conn, user_input)
        if len(matches) == 1:
            print_info(f"Found match: {matches[0]['appointment_id']} - {matches[0]['patient_name']}")
            return get_appointment_by_id(conn, matches[0]["appointment_id"])
        elif len(matches) > 1:
            print_info(f"Multiple matches found ({len(matches)}). Please select an Appointment ID:")
            headers = ["Apt ID", "Patient ID", "Patient Name", "Date", "Time", "Department", "Status"]
            rows = [
                [
                    a["appointment_id"],
                    a["patient_id"],
                    a["patient_name"],
                    a["appointment_date"],
                    a["appointment_time"],
                    a["department"],
                    a["status"]
                ]
                for a in matches
            ]
            print_table(headers, rows)
            continue

        print_error(f"Appointment '{user_input}' not found. Type '?' to see upcoming appointments or '0' to cancel.")


def handle_reschedule_appointment(conn: sqlite3.Connection) -> None:
    """Ask for a new date and time to reschedule an existing booking."""
    print_subheader("Reschedule Appointment")
    apt = select_appointment_interactive(
        conn,
        prompt_text="Enter Appointment ID or Patient Name to reschedule (or '?' for list): "
    )
    if not apt:
        print_info("Rescheduling cancelled.")
        pause()
        return

    if apt["status"] in ("Cancelled", "Completed"):
        print_error(f"Cannot reschedule an appointment with status '{apt['status']}'.")
        pause()
        return

    print_info(f"Current Schedule: {apt['appointment_date']} at {apt['appointment_time']} for {apt['patient_name']} ({apt['department']})")


    while True:
        new_date_input = input("Enter New Date (YYYY-MM-DD): ").strip()
        if not new_date_input:
            print_warning("Rescheduling cancelled.")
            pause()
            return
        valid, res = validate_date(new_date_input, allow_future=True, allow_past=False, field_name="New Date")
        if valid:
            new_date = res
            break
        print_error(res)


    while True:
        new_time_input = input("Enter New Time (HH:MM in 24hr format): ").strip()
        if not new_time_input:
            print_warning("Rescheduling cancelled.")
            pause()
            return
        valid, res = validate_time(new_time_input, field_name="New Time")
        if valid:
            new_time = res
            break
        print_error(res)

    if confirm_action(f"Confirm rescheduling {apt['appointment_id']} to {new_date} {new_time}?", default_no=False):
        success, msg = reschedule_appointment(conn, apt["appointment_id"], new_date, new_time)
        if success:
            print_success(msg)
        else:
            print_error(msg)
    else:
        print_info("Rescheduling cancelled.")
    pause()


def handle_cancel_appointment(conn: sqlite3.Connection) -> None:
    """Ask for confirmation before cancelling an appointment."""
    print_subheader("Cancel Appointment")
    apt = select_appointment_interactive(
        conn,
        prompt_text="Enter Appointment ID or Patient Name to cancel (or '?' for list): "
    )
    if not apt:
        print_info("Cancellation aborted.")
        pause()
        return

    if apt["status"] == "Cancelled":
        print_warning(f"Appointment {apt['appointment_id']} is already cancelled.")
        pause()
        return

    if apt["status"] == "Completed":
        print_error("Cannot cancel an appointment that has already been completed.")
        pause()
        return

    print_warning(f"You are cancelling appointment {apt['appointment_id']} for {apt['patient_name']} on {apt['appointment_date']} at {apt['appointment_time']}.")
    if confirm_action("Are you sure you want to cancel this appointment?", default_no=True):
        success, msg = cancel_appointment(conn, apt["appointment_id"])
        if success:
            print_success(msg)
        else:
            print_error(msg)
    else:
        print_info("Cancellation aborted.")
    pause()


def handle_check_in_appointment(conn: sqlite3.Connection) -> None:
    """Check in a patient on their appointment date and issue a daily queue pass."""
    print_subheader("Appointment Check-In (Issue Queue Ticket)")
    apt = select_appointment_interactive(
        conn,
        prompt_text="Enter Appointment ID or Patient Name to check in (or '?' for list): "
    )
    if not apt:
        print_info("Check-in aborted.")
        pause()
        return

    if apt["status"] != "Scheduled" and apt["status"] != "Rescheduled":
        print_warning(f"Appointment {apt['appointment_id']} cannot be checked in (Status: {apt['status']}).")
        pause()
        return

    print_info(f"Checking in: {apt['patient_name']} for {apt['department']} ({apt['appointment_date']} {apt['appointment_time']})")
    if confirm_action("Confirm patient arrival and check-in?", default_no=False):
        success, msg, ticket_id = check_in_appointment(conn, apt["appointment_id"])
        if success:
            print_success(msg)
            print_info(f"Patient is now waiting in queue for {apt['department']}.")
        else:
            print_error(msg)
    else:
        print_info("Check-in cancelled.")
    pause()


def handle_mark_noshow(conn: sqlite3.Connection) -> None:
    """Mark an appointment as missed/no-show."""
    print_subheader("Mark Missed / No-Show Appointment")
    apt = select_appointment_interactive(
        conn,
        prompt_text="Enter Appointment ID or Patient Name to mark as No-Show: "
    )
    if not apt:
        print_info("Operation aborted.")
        pause()
        return

    if apt["status"] not in ("Scheduled", "Rescheduled"):
        print_warning(f"Appointment {apt['appointment_id']} cannot be marked as No-Show (Status: {apt['status']}).")
        pause()
        return

    print_warning(f"You are marking appointment {apt['appointment_id']} ({apt['patient_name']}) as No-Show.")
    if confirm_action("Confirm status change to No-Show?", default_no=True):
        success, msg = mark_appointment_noshow(conn, apt["appointment_id"])
        if success:
            print_success(msg)
        else:
            print_error(msg)
    else:
        print_info("Operation cancelled.")
    pause()


def appointment_menu(conn: sqlite3.Connection) -> None:
    """Menu loop for the appointment section."""
    from utils.prompts import select_menu

    choices = [
        "1. Schedule New Appointment",
        "2. View Upcoming Appointments",
        "3. Search Appointments (by ID / Patient)",
        "4. Check-In Arrived Patient (Issue Queue Pass)",
        "5. Reschedule Appointment",
        "6. Cancel Appointment",
        "7. Mark Missed / No-Show Appointment",
        "8. Return to Main Menu"
    ]

    while True:
        print_subheader("Appointment Management Menu")
        choice = select_menu("Select Appointment Management Option:", choices)
        if not choice or "Return to Main Menu" in choice:
            break

        if choice.startswith("1."):
            handle_schedule_appointment(conn)
        elif choice.startswith("2."):
            handle_view_upcoming_appointments(conn)
        elif choice.startswith("3."):
            handle_search_appointments(conn)
        elif choice.startswith("4."):
            handle_check_in_appointment(conn)
        elif choice.startswith("5."):
            handle_reschedule_appointment(conn)
        elif choice.startswith("6."):
            handle_cancel_appointment(conn)
        elif choice.startswith("7."):
            handle_mark_noshow(conn)


