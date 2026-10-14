"""
Handles our SQLite database connection, table setup, migrations, and transactions.
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Optional
from config import DATABASE_PATH, DATA_DIR


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Connect to the SQLite database.
    Enables foreign keys and lets us access columns by name.
    """
    target_path = db_path if db_path is not None else str(DATABASE_PATH)

    # Create the data folder if it does not exist yet
    if target_path != ":memory:":
        parent_dir = os.path.dirname(target_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

    conn = sqlite3.connect(target_path, check_same_thread=False, timeout=10.0)
    # SQLite turns off foreign keys by default, so we need to turn it on
    conn.execute("PRAGMA foreign_keys = ON;")
    # Row factory lets us write row['column_name'] instead of index numbers
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transaction_scope(conn: sqlite3.Connection):
    """
    Helps run multiple database steps safely.
    Saves everything on success, or cancels all changes if something fails.
    """
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _column_exists(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    """Check if a column exists in an existing SQLite table."""
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def create_schema(conn: sqlite3.Connection) -> None:
    """
    Creates all tables, constraints, migrations, and indexes.
    Safe to call anytime because it uses CREATE TABLE IF NOT EXISTS and column checks.
    """
    cursor = conn.cursor()

    # 1. Staff Users Table (Role-Based Access Control)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Administrator', 'Doctor', 'Nurse', 'Receptionist', 'Billing')),
            status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Inactive')),
            created_at TEXT NOT NULL
        );
    """)

    # 2. Patients Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            dob TEXT NOT NULL,
            sex TEXT NOT NULL CHECK(sex IN ('Male', 'Female', 'Other')),
            contact_number TEXT NOT NULL,
            address TEXT NOT NULL,
            emergency_contact TEXT NOT NULL,
            registration_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Archived'))
        );
    """)
    # Migration: Add patient_type if missing
    if not _column_exists(cursor, "patients", "patient_type"):
        try:
            cursor.execute("ALTER TABLE patients ADD COLUMN patient_type TEXT DEFAULT 'Outpatient';")
        except sqlite3.OperationalError:
            pass

    # 3. Appointments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            appointment_id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            department TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Scheduled',
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON UPDATE CASCADE
        );
    """)
    if not _column_exists(cursor, "appointments", "created_by"):
        try:
            cursor.execute("ALTER TABLE appointments ADD COLUMN created_by TEXT DEFAULT 'Receptionist';")
        except sqlite3.OperationalError:
            pass

    # 4. Daily Queue & Walk-in Tickets Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS queue_tickets (
            ticket_id TEXT PRIMARY KEY,
            queue_number INTEGER NOT NULL,
            patient_id TEXT NOT NULL,
            department TEXT NOT NULL,
            ticket_date TEXT NOT NULL,
            ticket_type TEXT NOT NULL CHECK(ticket_type IN ('Scheduled', 'Walk-in', 'Emergency')),
            status TEXT NOT NULL DEFAULT 'Waiting' CHECK(status IN ('Waiting', 'Triage', 'Consultation', 'Billing', 'Completed', 'Cancelled')),
            created_at TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON UPDATE CASCADE
        );
    """)

    # 5. Nursing Assessment & Triage Vitals Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS triage_records (
            triage_id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            ticket_id TEXT,
            triage_date TEXT NOT NULL,
            nurse_user TEXT NOT NULL,
            chief_complaint TEXT NOT NULL,
            allergies TEXT NOT NULL DEFAULT 'No Known Drug Allergies (NKDA)',
            temperature TEXT NOT NULL,
            bp_systolic INTEGER NOT NULL,
            bp_diastolic INTEGER NOT NULL,
            pulse_rate INTEGER NOT NULL,
            respiratory_rate INTEGER NOT NULL,
            oxygen_saturation INTEGER NOT NULL,
            pain_score INTEGER NOT NULL DEFAULT 0,
            triage_category TEXT NOT NULL CHECK(triage_category IN ('Emergency', 'Urgent', 'Non-Urgent')),
            clinical_alerts TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON UPDATE CASCADE
        );
    """)

    # 6. Clinical Visits & Doctor Consultations Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            visit_id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            visit_date TEXT NOT NULL,
            department TEXT NOT NULL,
            attending_provider TEXT NOT NULL,
            notes TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON UPDATE CASCADE
        );
    """)
    # Migration: Add structured clinical fields if missing
    for col, ctype, default in [
        ("triage_id", "TEXT", "NULL"),
        ("chief_complaint", "TEXT", "''"),
        ("clinical_findings", "TEXT", "''"),
        ("diagnosis", "TEXT", "''"),
        ("treatment_plan", "TEXT", "''"),
        ("visit_status", "TEXT", "'Completed'")
    ]:
        if not _column_exists(cursor, "visits", col):
            try:
                cursor.execute(f"ALTER TABLE visits ADD COLUMN {col} {ctype} DEFAULT {default};")
            except sqlite3.OperationalError:
                pass

    # 7. Bills Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            bill_id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            bill_date TEXT NOT NULL,
            total_amount TEXT NOT NULL DEFAULT '0.00',
            paid_amount TEXT NOT NULL DEFAULT '0.00',
            balance TEXT NOT NULL DEFAULT '0.00',
            status TEXT NOT NULL DEFAULT 'Unpaid' CHECK(status IN ('Unpaid', 'Partially Paid', 'Paid', 'Cancelled')),
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON UPDATE CASCADE
        );
    """)
    # Migration: Add visit_id, subtotal, discount, cancellation columns if missing
    for col, ctype, default in [
        ("visit_id", "TEXT", "NULL"),
        ("subtotal", "TEXT", "'0.00'"),
        ("discount_type", "TEXT", "'None'"),
        ("discount_amount", "TEXT", "'0.00'"),
        ("cashier_user", "TEXT", "'Cashier'"),
        ("cancellation_reason", "TEXT", "NULL")
    ]:
        if not _column_exists(cursor, "bills", col):
            try:
                cursor.execute(f"ALTER TABLE bills ADD COLUMN {col} {ctype} DEFAULT {default};")
            except sqlite3.OperationalError:
                pass

    # 8. Bill Items Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id TEXT NOT NULL,
            service_description TEXT NOT NULL,
            amount TEXT NOT NULL,
            FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE
        );
    """)

    # 9. Payments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            bill_id TEXT NOT NULL,
            payment_date TEXT NOT NULL,
            amount TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            notes TEXT,
            amount_tendered TEXT DEFAULT NULL,
            change_amount TEXT DEFAULT '0.00',
            FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON UPDATE CASCADE
        );
    """)
    for col, ctype, default in [
        ("official_receipt_no", "TEXT", "NULL"),
        ("cashier_user", "TEXT", "'Cashier'"),
        ("amount_tendered", "TEXT", "NULL"),
        ("change_amount", "TEXT", "'0.00'")
    ]:
        if not _column_exists(cursor, "payments", col):
            try:
                cursor.execute(f"ALTER TABLE payments ADD COLUMN {col} {ctype} DEFAULT {default};")
            except sqlite3.OperationalError:
                pass

    # 10. Audit Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            details TEXT
        );
    """)

    # Indexes help searches run faster as records increase
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(full_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_status ON patients(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appointment_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_date_status ON queue_tickets(ticket_date, status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_triage_patient ON triage_records(patient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_visits_patient ON visits(patient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_patient ON bills(patient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bill_items_bill ON bill_items(bill_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_bill ON payments(bill_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);")

    conn.commit()
    seed_default_users_if_empty(conn)


def seed_default_users_if_empty(conn: sqlite3.Connection) -> None:
    """Create default staff accounts for testing if the users table is empty."""
    from modules.auth import register_user

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM users")
    row = cursor.fetchone()
    if row and row["count"] > 0:
        return

    defaults = [
        ("admin", "admin123", "Engr. Hospital Administrator", "Administrator"),
        ("dr_smith", "doc123", "Dr. Jose Rizal, MD", "Doctor"),
        ("nurse_joy", "nurse123", "Nurse Joy dela Cruz, RN", "Nurse"),
        ("reception", "recep123", "Maria Clara (Admissions)", "Receptionist"),
        ("cashier", "cash123", "Juan Luna (Billing Officer)", "Billing")
    ]
    for username, pwd, name, role in defaults:
        try:
            register_user(conn, username, pwd, name, role)
        except Exception:
            pass


def init_db(db_path: Optional[str] = None) -> None:
    """Prepare the database and tables. Called once when the app starts."""
    conn = get_connection(db_path)
    try:
        create_schema(conn)
    finally:
        conn.close()
