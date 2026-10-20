"""
Generates summary reports and charts directly from SQLite:
- Patient counts (active vs. archived)
- Appointments by status and department
- Visit counts by department and date
- Financial numbers (total billed, collected, and outstanding balance in PHP)
"""

import sqlite3
from decimal import Decimal
from typing import Dict, Any, List

from utils.display import (
    print_subheader,
    print_info,
    print_table,
    render_card,
    pause
)
from utils.validators import validate_menu_choice
from config import CURRENCY_SYMBOL, CURRENCY_CODE


# ==========================================
# Database Aggregation Queries
# ==========================================

def get_patient_statistics(conn: sqlite3.Connection) -> Dict[str, int]:
    """Count total, active, and archived patients."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN status = 'Archived' THEN 1 ELSE 0 END) as archived
        FROM patients;
    """)
    row = cursor.fetchone()
    return {
        "total": row["total"] if row and row["total"] else 0,
        "active": row["active"] if row and row["active"] else 0,
        "archived": row["archived"] if row and row["archived"] else 0,
    }


def get_appointment_statistics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Count appointments by status and department."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM appointments;")
    total = cursor.fetchone()["total"]

    # Count by status (Scheduled, Rescheduled, Completed, Cancelled)
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM appointments 
        GROUP BY status;
    """)
    status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

    # Count by department
    cursor.execute("""
        SELECT department, COUNT(*) as count 
        FROM appointments 
        GROUP BY department 
        ORDER BY count DESC;
    """)
    dept_counts = cursor.fetchall()

    return {
        "total": total,
        "by_status": status_counts,
        "by_department": dept_counts
    }


def get_visit_summary(conn: sqlite3.Connection, group_by: str = "department") -> List[sqlite3.Row]:
    """Count consultations grouped by department or date."""
    cursor = conn.cursor()
    if group_by == "month":
        cursor.execute("""
            SELECT SUBSTR(visit_date, 1, 7) as period, COUNT(*) as count
            FROM visits
            GROUP BY period
            ORDER BY period DESC;
        """)
    elif group_by == "date":
        cursor.execute("""
            SELECT SUBSTR(visit_date, 1, 10) as period, COUNT(*) as count
            FROM visits
            GROUP BY period
            ORDER BY period DESC
            LIMIT 15;
        """)
    else:  # Department
        cursor.execute("""
            SELECT department as period, COUNT(*) as count
            FROM visits
            GROUP BY department
            ORDER BY count DESC;
        """)
    return cursor.fetchall()


def get_financial_statistics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Calculate total billed, total paid, and total unpaid balance using Decimal."""
    cursor = conn.cursor()

    cursor.execute("SELECT total_amount, paid_amount, balance, status FROM bills;")
    bills = cursor.fetchall()

    total_billed = Decimal("0.00")
    total_paid = Decimal("0.00")
    total_balance = Decimal("0.00")
    status_counts = {"Unpaid": 0, "Partially Paid": 0, "Paid": 0, "Cancelled": 0}

    # Add up amounts from all bills (skip cancelled ones)
    for b in bills:
        st = b["status"]
        status_counts[st] = status_counts.get(st, 0) + 1
        # Cancelled bills are voided, so ignore them in financial totals
        if st != "Cancelled":
            total_billed += Decimal(str(b["total_amount"]))
            total_paid += Decimal(str(b["paid_amount"]))
            total_balance += Decimal(str(b["balance"]))

    return {
        "total_bills": len(bills),
        "total_billed": total_billed,
        "total_paid": total_paid,
        "total_balance": total_balance,
        "status_counts": status_counts
    }


# ==========================================
# CLI Submenu and Handlers
# ==========================================

def handle_patient_report(conn: sqlite3.Connection) -> None:
    """Show patient population summary on screen."""
    print_subheader("Patient Demographics Report")
    stats = get_patient_statistics(conn)

    render_card("PATIENT RECORDS SUMMARY", {
        "Total Registered Patients": stats["total"],
        "Active Patients": stats["active"],
        "Archived Patients": stats["archived"],
    })
    pause()


def handle_appointment_report(conn: sqlite3.Connection) -> None:
    """Show appointment totals by status and department."""
    print_subheader("Appointment Statistics Report")
    stats = get_appointment_statistics(conn)

    status_fields = {"Total Appointments Booked": stats["total"]}
    for st in ["Scheduled", "Rescheduled", "Completed", "Cancelled"]:
        status_fields[f"Status — {st}"] = stats["by_status"].get(st, 0)
    render_card("APPOINTMENT STATISTICS", status_fields)

    dept_fields = {}
    if stats["by_department"]:
        for row in stats["by_department"]:
            dept_fields[row["department"]] = row["count"]
    else:
        dept_fields["(No data)"] = "—"
    render_card("BREAKDOWN BY DEPARTMENT", dept_fields, border_style="blue")
    pause()


def handle_visit_report(conn: sqlite3.Connection) -> None:
    """Show visits broken down by department and recent daily activity."""
    print_subheader("Clinical Visits Summary")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM visits;")
    total_visits = cursor.fetchone()["count"]

    print_info(f"Total Hospital Visits Recorded: {total_visits}")

    print("\n--- Visits by Department ---")
    dept_rows = get_visit_summary(conn, group_by="department")
    headers_dept = ["Department", "Total Visits"]
    data_dept = [[r["period"], r["count"]] for r in dept_rows]
    print_table(headers_dept, data_dept, alignments=["left", "right"], empty_message="No visits recorded yet.")

    print("\n--- Recent Daily Visit Activity (Last 15 Days Active) ---")
    daily_rows = get_visit_summary(conn, group_by="date")
    headers_daily = ["Date", "Visits Logged"]
    data_daily = [[r["period"], r["count"]] for r in daily_rows]
    print_table(headers_daily, data_daily, alignments=["left", "right"], empty_message="No daily activity recorded.")

    pause()


def handle_financial_report(conn: sqlite3.Connection) -> None:
    """Show overall hospital earnings, collections, and unpaid balances."""
    print_subheader("Hospital Financial & Billing Summary")
    stats = get_financial_statistics(conn)

    render_card("FINANCIAL REVENUE AND BILLING OVERVIEW", {
        "Total Invoices Generated": stats["total_bills"],
        "Total Billed Amount": f"{CURRENCY_SYMBOL}{stats['total_billed']:,.2f}",
        "Total Payments Received": f"{CURRENCY_SYMBOL}{stats['total_paid']:,.2f}",
        "Total Outstanding Balance": f"{CURRENCY_SYMBOL}{stats['total_balance']:,.2f}",
        "Paid In Full": stats["status_counts"].get("Paid", 0),
        "Partially Paid": stats["status_counts"].get("Partially Paid", 0),
        "Unpaid": stats["status_counts"].get("Unpaid", 0),
    }, border_style="green")
    pause()


def handle_comprehensive_dashboard(conn: sqlite3.Connection) -> None:
    """Show an all-in-one Rich summary of patients, appointments, visits, and revenue."""
    p_stats = get_patient_statistics(conn)
    f_stats = get_financial_statistics(conn)

    cursor = conn.cursor()
    # Appointments scheduled for today
    cursor.execute("""
        SELECT COUNT(*) as count FROM appointments
        WHERE appointment_date = date('now') AND status IN ('Scheduled', 'Rescheduled');
    """)
    appts_today = cursor.fetchone()["count"]

    # Patients waiting in daily queue today
    cursor.execute("""
        SELECT COUNT(*) as count FROM queue_tickets
        WHERE ticket_date = date('now') AND status = 'Waiting';
    """)
    queue_waiting = cursor.fetchone()["count"]

    # Completed clinical visits
    cursor.execute("SELECT COUNT(*) as count FROM visits WHERE visit_status = 'Completed';")
    v_total = cursor.fetchone()["count"]

    # Unpaid / partially paid bills count
    cursor.execute("SELECT COUNT(*) as count FROM bills WHERE status != 'Paid';")
    unpaid_bills_cnt = cursor.fetchone()["count"]

    from utils.display import render_dashboard
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
    pause()


def handle_triage_alerts_report(conn: sqlite3.Connection) -> None:
    """Show breakdown of triage urgency and flagged physiological alerts."""
    print_subheader("Clinical Triage Urgency & Physiological Alert Flags")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT triage_category, COUNT(*) as count
        FROM triage_records
        GROUP BY triage_category;
    """)
    cat_counts = {row["triage_category"]: row["count"] for row in cursor.fetchall()}

    render_card("NURSING TRIAGE URGENCY DISTRIBUTION", {
        "🚨 Emergency (Immediate)": cat_counts.get("Emergency", 0),
        "⚠️  Urgent": cat_counts.get("Urgent", 0),
        "ℹ️  Non-Urgent": cat_counts.get("Non-Urgent", 0),
    }, border_style="red")

    # Fetch recent clinical alerts
    cursor.execute("""
        SELECT t.triage_id, t.triage_date, p.full_name, t.triage_category, t.clinical_alerts
        FROM triage_records t
        JOIN patients p ON t.patient_id = p.patient_id
        WHERE t.clinical_alerts IS NOT NULL AND t.clinical_alerts != 'None' AND t.clinical_alerts != ''
        ORDER BY t.triage_date DESC
        LIMIT 10;
    """)
    alerts = cursor.fetchall()
    if alerts:
        print("\nRecent Flagged Physiological Alerts (Review by Qualified Doctor):")
        headers = ["Triage ID", "Timestamp", "Patient", "Category", "Screening Flags"]
        rows = [
            [a["triage_id"], a["triage_date"], a["full_name"], a["triage_category"], a["clinical_alerts"][:40]]
            for a in alerts
        ]
        print_table(headers, rows)
    else:
        print_info("No abnormal physiological screening flags recorded.")
    pause()


def handle_daily_registration_report(conn: sqlite3.Connection) -> None:
    """Show daily patient intake registrations."""
    print_subheader("Daily Patient Registration History")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT registration_date, COUNT(*) as count
        FROM patients
        GROUP BY registration_date
        ORDER BY registration_date DESC
        LIMIT 15;
    """)
    records = cursor.fetchall()

    headers = ["Registration Date", "New Patients Registered"]
    rows = [[r["registration_date"], str(r["count"])] for r in records]
    print_table(headers, rows, empty_message="No registration records found.")
    pause()


def reports_menu(conn: sqlite3.Connection) -> None:
    """Submenu for hospital reports and summaries."""
    from modules.audit import handle_view_audit_logs
    from utils.prompts import select_menu

    choices = [
        "1. Hospital Executive Dashboard (Overview)",
        "2. Patient Demographics & Daily Registrations",
        "3. Clinical Triage Urgency & Alert Logs",
        "4. Appointment Workload Statistics",
        "5. Clinical Visits & Consultation Summary",
        "6. Financial & Revenue Report (PHP)",
        "7. System Audit Trail & Security Logs",
        "8. Return to Main Menu"
    ]

    while True:
        print_subheader("Hospital Reports & Analytics Menu")
        choice = select_menu("Select Report Option:", choices)
        if not choice or "Return to Main Menu" in choice:
            break

        if choice.startswith("1."):
            handle_comprehensive_dashboard(conn)
        elif choice.startswith("2."):
            handle_patient_report(conn)
            handle_daily_registration_report(conn)
        elif choice.startswith("3."):
            handle_triage_alerts_report(conn)
        elif choice.startswith("4."):
            handle_appointment_report(conn)
        elif choice.startswith("5."):
            handle_visit_report(conn)
        elif choice.startswith("6."):
            handle_financial_report(conn)
        elif choice.startswith("7."):
            handle_view_audit_logs(conn)

