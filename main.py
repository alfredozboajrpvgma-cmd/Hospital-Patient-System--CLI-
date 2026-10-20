"""
Main entry point for the Hospital Patient System (CLI).
Connects to SQLite, checks staff login, and displays role-based menus.
"""

import sys
import sqlite3
from typing import List

# Make sure Windows terminal displays the Philippine Peso symbol (₱) correctly
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from database import init_db, get_connection
from utils.display import (
    console,
    print_header,
    print_subheader,
    print_error,
    print_warning,
    print_info,
    confirm_action,
    pause
)
from utils.prompts import select_menu, confirm_prompt

from modules.auth import (
    handle_login,
    get_current_session,
    clear_session,
    handle_user_management
)
from modules.patients import (
    patient_menu,
    handle_register_patient,
    handle_search_patients,
    handle_view_all_patients,
    handle_view_patient_details
)
from modules.appointments import (
    appointment_menu,
    handle_schedule_appointment,
    handle_view_upcoming_appointments,
    handle_check_in_appointment
)
from modules.queue import (
    queue_menu,
    handle_view_daily_queue,
    handle_issue_walkin_ticket
)
from modules.triage import (
    triage_menu,
    handle_record_triage,
    handle_view_patient_triage
)
from modules.visits import (
    visit_menu,
    handle_record_visit,
    handle_view_patient_visits,
    handle_emergency_visit
)
from modules.billing import (
    billing_menu,
    handle_generate_bill,
    handle_record_payment,
    handle_view_outstanding_bills
)
from modules.reports import (
    reports_menu,
    handle_comprehensive_dashboard,
    handle_triage_alerts_report,
    handle_financial_report
)


def get_role_menu_choices(role: str) -> List[str]:
    """Get menu options tailored to the logged-in staff role."""
    if role == "Administrator":
        return [
            "1. 🚨 Emergency Room (ER) Care (Immediate Intake)",
            "2. Patient Management (Registration & Records)",
            "3. Outpatient Appointment Management",
            "4. Daily Patient Queue & Walk-In Board",
            "5. Nursing Triage & Vital Signs Assessment",
            "6. Physician Clinical Consultations (SOAP)",
            "7. Billing, Philippine Discounts & Official Receipts",
            "8. Hospital Reports & System Analytics",
            "9. Staff User Accounts & Role Permissions",
            "10. Switch User / Logout",
            "11. Exit System"
        ]
    elif role == "Doctor":
        return [
            "1. 🚨 Emergency Room (ER) Care (Immediate Intake)",
            "2. Daily Patient Queue Board",
            "3. Physician Clinical Consultations (SOAP)",
            "4. View Patient Medical Records & History",
            "5. Review Nursing Triage & Vital Signs History",
            "6. Clinical Consultation Statistics",
            "7. Switch User / Logout",
            "8. Exit System"
        ]
    elif role == "Nurse":
        return [
            "1. 🚨 Emergency Room (ER) Care (Immediate Intake)",
            "2. Daily Patient Queue Board",
            "3. Nursing Assessment & Triage (Vitals & Allergies)",
            "4. View Patient Triage History & Alert Logs",
            "5. View Patient Profiles",
            "6. Switch User / Logout",
            "7. Exit System"
        ]
    elif role == "Receptionist":
        return [
            "1. 🚨 Emergency Room (ER) Care (Immediate Intake)",
            "2. Patient Registration & Search",
            "3. Appointment Scheduling & Check-In",
            "4. Daily Patient Queue & Walk-In Pass Issuance",
            "5. View Hospital Patient Registry",
            "6. Switch User / Logout",
            "7. Exit System"
        ]
    elif role == "Billing":
        return [
            "1. Generate Itemized Hospital Bill (Senior/PWD Discounts)",
            "2. Record Payment & Issue Official Receipt (OR)",
            "3. View Outstanding Unpaid Patient Balances",
            "4. Financial & Revenue Reports (PHP)",
            "5. Look Up Patient Records",
            "6. Switch User / Logout",
            "7. Exit System"
        ]
    return ["1. Logout", "2. Exit System"]


def run_authenticated_session(conn: sqlite3.Connection) -> bool:
    """Run the main menu for the logged-in staff member."""
    session = get_current_session()
    if not session:
        return True

    role = session.role
    user_str = f"{session.full_name} ({session.role})"
    title = f"PHILIPPINE HOSPITAL INFORMATION SYSTEM | Staff: {user_str}"
    choices = get_role_menu_choices(role)

    while True:
        choice = select_menu(title, choices)
        if not choice:
            if confirm_prompt("Do you wish to exit the Hospital System?", default=False):
                return False
            continue

        if "Switch User / Logout" in choice or "Logout" in choice:
            clear_session()
            print_info("Logged out successfully.")
            pause()
            return True

        if "Exit" in choice:
            if confirm_prompt("Are you sure you want to exit the application?", default=False):
                return False
            continue

        choice_num = int(choice.split(".")[0])

        # Route by Role
        if role == "Administrator":
            if choice_num == 1:
                handle_emergency_visit(conn)
            elif choice_num == 2:
                patient_menu(conn)
            elif choice_num == 3:
                appointment_menu(conn)
            elif choice_num == 4:
                queue_menu(conn)
            elif choice_num == 5:
                triage_menu(conn)
            elif choice_num == 6:
                visit_menu(conn)
            elif choice_num == 7:
                billing_menu(conn)
            elif choice_num == 8:
                reports_menu(conn)
            elif choice_num == 9:
                handle_user_management(conn)

        elif role == "Doctor":
            if choice_num == 1:
                handle_emergency_visit(conn)
            elif choice_num == 2:
                handle_view_daily_queue(conn)
            elif choice_num == 3:
                handle_record_visit(conn)
            elif choice_num == 4:
                handle_view_patient_visits(conn)
            elif choice_num == 5:
                handle_view_patient_triage(conn)
            elif choice_num == 6:
                handle_comprehensive_dashboard(conn)

        elif role == "Nurse":
            if choice_num == 1:
                handle_emergency_visit(conn)
            elif choice_num == 2:
                handle_view_daily_queue(conn)
            elif choice_num == 3:
                handle_record_triage(conn)
            elif choice_num == 4:
                handle_view_patient_triage(conn)
            elif choice_num == 5:
                handle_search_patients(conn)

        elif role == "Receptionist":
            if choice_num == 1:
                handle_emergency_visit(conn)
            elif choice_num == 2:
                patient_menu(conn)
            elif choice_num == 3:
                appointment_menu(conn)
            elif choice_num == 4:
                queue_menu(conn)
            elif choice_num == 5:
                handle_view_all_patients(conn)

        elif role == "Billing":
            if choice_num == 1:
                handle_generate_bill(conn)
            elif choice_num == 2:
                handle_record_payment(conn)
            elif choice_num == 3:
                handle_view_outstanding_bills(conn)
            elif choice_num == 4:
                handle_financial_report(conn)
            elif choice_num == 5:
                handle_search_patients(conn)


def run_interactive_app() -> None:
    """Start the interactive terminal application."""
    try:
        init_db()
        conn = get_connection()
    except (sqlite3.Error, OSError) as exc:
        print_error(f"Failed to initialize hospital database: {exc}")
        sys.exit(1)

    print_header(
        "Philippine Hospital Patient Management System (CLI)",
        subtitle="Role-Based Hospital Clinical, Queue, Triage & Billing Operations"
    )
    print_info("Philippine Health Standards: PhilHealth, Senior Citizen (20%), PWD (20%), Emergency Room fast-track.")

    try:
        while True:
            # Ask user to log in first
            session = get_current_session()
            if not session:
                session = handle_login(conn)
                if not session:
                    print_info("Exiting Hospital Patient System. Goodbye!")
                    break

            # Run menu for the logged-in user
            keep_running = run_authenticated_session(conn)
            if not keep_running:
                print_info("Thank you for using the Hospital Patient Management System. Goodbye!")
                break
    except (EOFError, KeyboardInterrupt):
        print_info("Hospital system closed.")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main() -> None:
    """Start the interactive app, or run CLI commands if arguments were passed."""
    if len(sys.argv) > 1 and sys.argv[1] not in ("interactive",):
        from cli import app
        app()
    else:
        run_interactive_app()


if __name__ == "__main__":
    main()
