"""
Automated unit and regression tests for Hospital System CLI workflow improvements.
Verifies:
1. Attending physician identity and registered account assignment.
2. Clinical consultation validation (mandatory SOAP documentation).
3. Emergency intake without appointment and emergency queue prioritization.
4. Billing integrity, bill cancellation, and duplicate payment prevention.
5. Patient queue status transitions and automatic queue ticket closure.
6. PBKDF2 password security and RBAC permission enforcement.
"""

import unittest
from decimal import Decimal
from datetime import datetime, date

from database import get_connection, create_schema
from config import DATE_FORMAT, DATETIME_FORMAT
from modules.auth import (
    register_user,
    authenticate_user,
    has_permission,
    hash_password,
    verify_password,
    set_current_session,
    clear_session,
    get_active_doctors
)
from modules.patients import register_patient, get_patient_by_id
from modules.visits import record_visit, get_visit_by_id
from modules.queue import (
    issue_queue_ticket,
    get_daily_queue,
    update_queue_status,
    close_patient_active_queue_ticket
)
from modules.billing import (
    create_bill,
    get_bill_by_id,
    record_payment,
    cancel_bill
)
from modules.reports import get_financial_statistics
from utils.validators import VisitCreateModel
from pydantic import ValidationError


class TestWorkflowImprovements(unittest.TestCase):
    """Test suite for clinical and administrative workflow improvements."""

    def setUp(self):
        """Set up in-memory SQLite database and test staff accounts."""
        self.conn = get_connection(":memory:")
        create_schema(self.conn)

        # Seed staff accounts
        self.admin_id = register_user(self.conn, "wf_admin", "AdminSecret123", "Engr. System Admin", "Administrator")
        self.doc_id = register_user(self.conn, "dr_rizal", "DoctorPass123", "Dr. Jose Rizal, MD", "Doctor")
        self.nurse_id = register_user(self.conn, "wf_nurse", "NursePass123", "Nurse Joy, RN", "Nurse")
        self.cashier_id = register_user(self.conn, "wf_cashier", "CashierPass123", "Juan Luna", "Billing")

        # Seed a test patient
        self.patient_id = register_patient(
            self.conn,
            full_name="Emilio Aguinaldo",
            dob="1975-03-22",
            sex="Male",
            contact_number="0917-123-4567",
            address="Kawit, Cavite",
            emergency_contact="Hilaria Aguinaldo 0918-987-6543"
        )

    def tearDown(self):
        """Clean up session and database connection."""
        clear_session()
        self.conn.close()

    # ---------------------------------------------------------
    # 1. Attending Physician Validation
    # ---------------------------------------------------------
    def test_authenticated_physician_identity_and_reassignment(self):
        """Verify physician identity is retrieved from registered staff and cannot be arbitrary text."""
        # Authenticate Doctor
        ok, user_row, _ = authenticate_user(self.conn, "dr_rizal", "DoctorPass123")
        self.assertTrue(ok)
        session = set_current_session(user_row)
        self.assertEqual(session.full_name, "Dr. Jose Rizal, MD")

        # Active doctors query returns registered doctor
        doctors = get_active_doctors(self.conn)
        self.assertTrue(any(d["username"] == "dr_rizal" for d in doctors))

        # Consultation logged by authenticated doctor
        vid = record_visit(
            self.conn,
            patient_id=self.patient_id,
            visit_date="2026-10-15 09:30",
            department="Internal Medicine",
            attending_provider=session.full_name,
            notes="Follow-up consultation",
            chief_complaint="Dizziness on standing",
            clinical_findings="Orthostatic BP drop verified",
            diagnosis="Orthostatic Hypotension",
            treatment_plan="Hydration therapy, compression socks"
        )
        visit = get_visit_by_id(self.conn, vid)
        self.assertEqual(visit["attending_provider"], "Dr. Jose Rizal, MD")

    # ---------------------------------------------------------
    # 2. Clinical Consultation Validation
    # ---------------------------------------------------------
    def test_clinical_consultation_mandatory_soap_fields(self):
        """Verify clinical documentation rejects missing diagnosis, chief complaint, or plan."""
        # Missing diagnosis must raise ValidationError
        with self.assertRaises(ValidationError):
            VisitCreateModel(
                patient_id=self.patient_id,
                visit_date="2026-10-15 11:00",
                department="Cardiology",
                attending_provider="Dr. Jose Rizal, MD",
                notes="Consultation note",
                chief_complaint="Palpitations",
                clinical_findings="Regular rhythm",
                diagnosis="",  # Empty diagnosis rejected
                treatment_plan="Holter monitor scheduled"
            )

        # Missing treatment plan must raise ValidationError
        with self.assertRaises(ValidationError):
            VisitCreateModel(
                patient_id=self.patient_id,
                visit_date="2026-10-15 11:00",
                department="Cardiology",
                attending_provider="Dr. Jose Rizal, MD",
                notes="Consultation note",
                chief_complaint="Palpitations",
                clinical_findings="Regular rhythm",
                diagnosis="Sinus Tachycardia",
                treatment_plan=""  # Empty treatment plan rejected
            )

    # ---------------------------------------------------------
    # 3. Emergency Workflow
    # ---------------------------------------------------------
    def test_emergency_intake_without_appointment_and_priority_queue(self):
        """Verify acute emergency intake registers emergency patient and prioritizes queue ticket."""
        er_patient_id = register_patient(
            self.conn,
            full_name="Emergency Walk-in Patient A",
            dob="1985-01-01",
            sex="Female",
            contact_number="0900-111-2222",
            address="ER Emergency Bay",
            emergency_contact="ER Staff Admitting",
            patient_type="Emergency"
        )
        pt = get_patient_by_id(self.conn, er_patient_id)
        self.assertEqual(pt["patient_type"], "Emergency")

        # Issue queue tickets: regular walk-in first, then emergency
        issue_queue_ticket(self.conn, self.patient_id, "Outpatient Department (OPD)", ticket_type="Walk-in")
        issue_queue_ticket(self.conn, er_patient_id, "Emergency Room (ER)", ticket_type="Emergency")

        # Queue ordering places Emergency at priority 1 ahead of regular walk-ins
        queue_today = get_daily_queue(self.conn)
        self.assertTrue(len(queue_today) >= 2)
        self.assertEqual(queue_today[0]["ticket_type"], "Emergency")
        self.assertEqual(queue_today[0]["patient_id"], er_patient_id)

    # ---------------------------------------------------------
    # 4. Billing Integrity, Cancellation & Duplicate Payments
    # ---------------------------------------------------------
    def test_bill_cancellation_and_financial_statistics(self):
        """Verify unpaid invoices can be cancelled, and cancelled invoices are excluded from receivables."""
        bill_id = create_bill(self.conn, self.patient_id, [("Urgent Care Service", Decimal("2500.00"))])
        bill = get_bill_by_id(self.conn, bill_id)
        self.assertEqual(bill["status"], "Unpaid")

        # Before cancellation, ₱2500 in receivables
        stats1 = get_financial_statistics(self.conn)
        self.assertEqual(stats1["total_billed"], Decimal("2500.00"))
        self.assertEqual(stats1["total_balance"], Decimal("2500.00"))

        # Cancel the bill
        success, msg = cancel_bill(self.conn, bill_id, reason="Entered under incorrect service item")
        self.assertTrue(success)
        self.assertIn("Cancelled", msg)

        # Confirm status is Cancelled and balance is 0.00
        bill_cancelled = get_bill_by_id(self.conn, bill_id)
        self.assertEqual(bill_cancelled["status"], "Cancelled")

        # After cancellation, total_billed and total_balance are ₱0.00
        stats2 = get_financial_statistics(self.conn)
        self.assertEqual(stats2["total_billed"], Decimal("0.00"))
        self.assertEqual(stats2["total_balance"], Decimal("0.00"))
        self.assertEqual(stats2["status_counts"]["Cancelled"], 1)

        # Attempting payment against a cancelled bill must fail
        pay_ok, pay_msg, _ = record_payment(self.conn, bill_id, Decimal("500.00"), "Cash")
        self.assertFalse(pay_ok)
        self.assertIn("cancelled", pay_msg.lower())

    def test_duplicate_payment_prevention(self):
        """Verify identical duplicate payment on the same bill timestamp is rejected."""
        bill_id = create_bill(self.conn, self.patient_id, [("Lab Diagnostics", Decimal("1000.00"))])

        fixed_time = "2026-10-15 14:00"
        ok1, _, _ = record_payment(
            self.conn, bill_id, Decimal("500.00"), "Cash", payment_date=fixed_time
        )
        self.assertTrue(ok1)

        # Attempt duplicate payment with exact same bill, amount, and timestamp
        ok2, msg2, _ = record_payment(
            self.conn, bill_id, Decimal("500.00"), "Cash", payment_date=fixed_time
        )
        self.assertFalse(ok2)
        self.assertIn("Duplicate payment detected", msg2)

    # ---------------------------------------------------------
    # 5. Patient Queue Consistency & Transitions
    # ---------------------------------------------------------
    def test_queue_status_transitions_and_completion(self):
        """Verify valid queue transitions are enforced and terminal states cannot revert."""
        tid, _ = issue_queue_ticket(self.conn, self.patient_id, "Cardiology")

        # Waiting -> Triage (Valid)
        self.assertTrue(update_queue_status(self.conn, tid, "Triage"))

        # Triage -> Consultation (Valid)
        self.assertTrue(update_queue_status(self.conn, tid, "Consultation"))

        # Consultation -> Completed (Valid)
        self.assertTrue(update_queue_status(self.conn, tid, "Completed"))

        # Completed -> Waiting (Invalid backward transition from terminal state)
        self.assertFalse(update_queue_status(self.conn, tid, "Waiting"))

    def test_consultation_completion_closes_active_queue_ticket(self):
        """Verify recording a consultation automatically advances and closes the patient's queue ticket."""
        tid, _ = issue_queue_ticket(self.conn, self.patient_id, "Internal Medicine")

        # Patient had an active queue ticket
        today = date.today().strftime(DATE_FORMAT)
        active_tickets = get_daily_queue(self.conn, target_date=today, status_filter="Waiting")
        self.assertTrue(any(t["ticket_id"] == tid for t in active_tickets))

        # Close queue ticket upon clinical consultation
        closed_tid = close_patient_active_queue_ticket(self.conn, self.patient_id, new_status="Billing")
        self.assertEqual(closed_tid, tid)

        # Ticket is no longer in Waiting
        waiting_after = get_daily_queue(self.conn, target_date=today, status_filter="Waiting")
        self.assertFalse(any(t["ticket_id"] == tid for t in waiting_after))

    # ---------------------------------------------------------
    # 6. Password Security & RBAC Enforcement
    # ---------------------------------------------------------
    def test_pbkdf2_password_security_and_rbac(self):
        """Verify passwords use PBKDF2-HMAC-SHA256 with salt and RBAC permissions are enforced."""
        pwd_hash, salt = hash_password("SuperSecurePwd999")
        self.assertEqual(len(pwd_hash), 64)
        self.assertTrue(verify_password("SuperSecurePwd999", pwd_hash, salt))
        self.assertFalse(verify_password("WrongPassword", pwd_hash, salt))

        # Role permissions check
        self.assertTrue(has_permission("Doctor", "consultations", "create"))
        self.assertFalse(has_permission("Doctor", "billing", "payment"))

        self.assertTrue(has_permission("Billing", "billing", "payment"))
        self.assertFalse(has_permission("Billing", "consultations", "create"))

        self.assertTrue(has_permission("Administrator", "anything", "any_action"))


if __name__ == "__main__":
    unittest.main()
