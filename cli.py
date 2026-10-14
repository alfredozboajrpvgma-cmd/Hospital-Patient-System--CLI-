"""
Command-line subcommands using Typer.
Allows quick lookups, lists, and summary reports directly from the terminal.
"""

import sys
import sqlite3
from typing import Optional
from datetime import date
import typer
from rich import box
from rich.table import Table

from database import init_db, get_connection
from utils.display import (
    console,
    print_header,
    print_subheader,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_table,
    render_card,
    render_dashboard
)
from config import CURRENCY_SYMBOL, CURRENCY_CODE, DATE_FORMAT

app = typer.Typer(
    name="hospital",
    help="Philippine Hospital Patient Management System CLI Commands.",
    add_completion=False
)

patients_app = typer.Typer(name="patients", help="Manage and search hospital patient records.")
appointments_app = typer.Typer(name="appointments", help="View and inspect outpatient appointments.")
reports_app = typer.Typer(name="reports", help="Hospital statistical summaries and daily metrics.")
database_app = typer.Typer(name="database", help="Hospital database maintenance and initialization.")

app.add_typer(patients_app)
app.add_typer(appointments_app)
app.add_typer(reports_app)
app.add_typer(database_app)


# ==========================================
# Database Commands
# ==========================================

@database_app.command("initialize")
def cmd_database_initialize() -> None:
    """Set up the SQLite database and default demo accounts."""
    try:
        init_db()
        print_success("Hospital SQLite database schema and seed users initialized successfully.")
    except Exception as exc:
        print_error(f"Failed to initialize database: {exc}")
        raise typer.Exit(code=1)


# ==========================================
# Patient Commands
# ==========================================

@patients_app.command("list")
def cmd_patients_list(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status: 'Active' or 'Archived'")
) -> None:
    """List hospital patients, with optional status filter."""
    from modules.patients import get_all_patients

    conn = get_connection()
    try:
        patients = get_all_patients(conn, filter_status=status)
        headers = ["Patient ID", "Full Name", "DOB", "Sex", "Contact", "Status"]
        rows = [
            [p["patient_id"], p["full_name"], p["dob"], p["sex"], p["contact_number"], p["status"]]
            for p in patients
        ]
        print_table(headers, rows, empty_message=f"No patients found with status='{status or 'any'}'.")
    finally:
        conn.close()


@patients_app.command("search")
def cmd_patients_search(
    query: str = typer.Argument(..., help="Patient ID or partial name to search")
) -> None:
    """Search for patients by full name or ID."""
    from modules.patients import search_patients

    conn = get_connection()
    try:
        results = search_patients(conn, query)
        if not results:
            print_warning(f"No patients found matching '{query}'.")
            raise typer.Exit(code=1)

        headers = ["Patient ID", "Full Name", "DOB", "Sex", "Contact", "Status"]
        rows = [
            [p["patient_id"], p["full_name"], p["dob"], p["sex"], p["contact_number"], p["status"]]
            for p in results
        ]
        print_table(headers, rows)
    finally:
        conn.close()


@patients_app.command("view")
def cmd_patients_view(
    patient_id: str = typer.Argument(..., help="Patient ID (e.g. PAT-1001)")
) -> None:
    """View complete profile of a patient by ID."""
    from modules.patients import get_patient_by_id

    conn = get_connection()
    try:
        patient = get_patient_by_id(conn, patient_id)
        if not patient:
            print_error(f"Patient with ID '{patient_id}' not found.")
            raise typer.Exit(code=1)

        pt_keys = patient.keys()
        pt_type = patient["patient_type"] if "patient_type" in pt_keys else "Outpatient"
        render_card(f"PATIENT DOSSIER: {patient['patient_id']} ({patient['status']})", {
            "Patient ID": patient["patient_id"],
            "Full Name": patient["full_name"],
            "Date of Birth": patient["dob"],
            "Sex": patient["sex"],
            "Classification": pt_type,
            "Contact Number": patient["contact_number"],
            "Address": patient["address"],
            "Emergency Contact": patient["emergency_contact"],
            "Registration Date": patient["registration_date"],
            "Record Status": patient["status"]
        })
    finally:
        conn.close()


# ==========================================
# Appointment Commands
# ==========================================

@appointments_app.command("list")
def cmd_appointments_list(
    target_date: Optional[str] = typer.Option(None, "--date", "-d", help="Filter by date (YYYY-MM-DD)")
) -> None:
    """List scheduled appointments."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if target_date:
            cursor.execute("""
                SELECT a.appointment_id, a.patient_id, p.full_name as patient_name,
                       a.appointment_date, a.appointment_time, a.department, a.status
                FROM appointments a
                JOIN patients p ON a.patient_id = p.patient_id
                WHERE a.appointment_date = ?
                ORDER BY a.appointment_time ASC;
            """, (target_date,))
        else:
            cursor.execute("""
                SELECT a.appointment_id, a.patient_id, p.full_name as patient_name,
                       a.appointment_date, a.appointment_time, a.department, a.status
                FROM appointments a
                JOIN patients p ON a.patient_id = p.patient_id
                WHERE a.appointment_date >= date('now')
                ORDER BY a.appointment_date ASC, a.appointment_time ASC;
            """)
        appointments = cursor.fetchall()

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
        title = f"Appointments for {target_date}" if target_date else "Upcoming Scheduled Appointments"
        print_table(headers, rows, empty_message="No appointments found.", title=title)
    finally:
        conn.close()


# ==========================================
# Report Commands
# ==========================================

@reports_app.command("daily")
def cmd_reports_daily() -> None:
    """Show daily patient intake registrations and operational metrics."""
    conn = get_connection()
    try:
        from modules.reports import handle_daily_registration_report
        handle_daily_registration_report(conn)
    finally:
        conn.close()


@reports_app.command("dashboard")
def cmd_reports_dashboard() -> None:
    """Show the real-time hospital executive dashboard."""
    conn = get_connection()
    try:
        from modules.reports import (
            get_patient_statistics,
            get_financial_statistics
        )
        p_stats = get_patient_statistics(conn)
        f_stats = get_financial_statistics(conn)

        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM appointments
            WHERE appointment_date = date('now') AND status IN ('Scheduled', 'Rescheduled');
        """)
        appts_today = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT COUNT(*) as count FROM queue_tickets
            WHERE ticket_date = date('now') AND status = 'Waiting';
        """)
        queue_waiting = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM visits WHERE visit_status = 'Completed';")
        v_total = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM bills WHERE status != 'Paid';")
        unpaid_bills_cnt = cursor.fetchone()["count"]

        render_dashboard(
            active_patients=p_stats["active"],
            total_patients=p_stats["total"],
            appointments_today=appts_today,
            patients_waiting=queue_waiting,
            completed_consultations=v_total,
            unpaid_bills_count=unpaid_bills_cnt,
            total_billed=f_stats["total_billed"],
            total_paid=f_stats["total_paid"],
            outstanding_balance=f_stats["total_balance"]
        )
    finally:
        conn.close()


@app.command("interactive")
def cmd_interactive() -> None:
    """Launch the full interactive Questionary & Rich hospital system."""
    from main import run_interactive_app
    run_interactive_app()


def run_cli() -> None:
    """CLI execution entrypoint."""
    app()


if __name__ == "__main__":
    run_cli()
