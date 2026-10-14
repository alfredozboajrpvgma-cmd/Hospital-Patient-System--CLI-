"""
Automated unit tests for Appointment Management (Philippine Edition).
Uses an in-memory SQLite database to test scheduling, conflicts,
rescheduling, and cancellations.
"""

import unittest
import sqlite3

from database import get_connection, create_schema
from modules.patients import register_patient
from modules.appointments import (
    schedule_appointment,
    get_appointment_by_id,
    get_upcoming_appointments,
    check_appointment_conflict,
    reschedule_appointment,
    cancel_appointment,
    check_in_appointment,
    mark_appointment_noshow
)


class TestAppointmentManagement(unittest.TestCase):
    """Test suite for appointment scheduling, conflicts, and status updates."""

    def setUp(self):
        """Set up in-memory database with schema and a test patient."""
        self.conn = get_connection(":memory:")
        create_schema(self.conn)

        # Register test patient with Philippine details
        self.patient_id = register_patient(
            self.conn,
            full_name="Juan dela Cruz",
            dob="1995-08-10",
            sex="Male",
            contact_number="0917-123-4567",
            address="Sampaloc, Manila",
            emergency_contact="Maria dela Cruz 0918-987-6543"
        )

    def tearDown(self):
        """Close database connection."""
        self.conn.close()

    def test_schedule_valid_appointment(self):
        """Verify scheduling a valid appointment creates a record with status 'Scheduled'."""
        apt_id = schedule_appointment(
            self.conn,
            patient_id=self.patient_id,
            appointment_date="2026-12-01",
            appointment_time="10:30",
            department="Cardiology",
            reason="Routine checkup"
        )
        self.assertTrue(apt_id.startswith("APT-"))

        apt = get_appointment_by_id(self.conn, apt_id)
        self.assertIsNotNone(apt)
        self.assertEqual(apt["patient_id"], self.patient_id)
        self.assertEqual(apt["appointment_date"], "2026-12-01")
        self.assertEqual(apt["appointment_time"], "10:30")
        self.assertEqual(apt["department"], "Cardiology")
        self.assertEqual(apt["status"], "Scheduled")

    def test_foreign_key_enforcement_nonexistent_patient(self):
        """Verify SQLite foreign key constraints reject an appointment for a nonexistent patient."""
        with self.assertRaises(sqlite3.IntegrityError):
            schedule_appointment(
                self.conn,
                patient_id="PAT-9999",  # Does not exist
                appointment_date="2026-12-01",
                appointment_time="11:00",
                department="Internal Medicine",
                reason="Invalid appointment"
            )

    def test_conflict_detection_same_patient(self):
        """Verify conflict detection when the same patient books overlapping times."""
        schedule_appointment(
            self.conn,
            patient_id=self.patient_id,
            appointment_date="2026-12-05",
            appointment_time="14:00",
            department="Internal Medicine",
            reason="Blood test"
        )

        has_conflict, msg = check_appointment_conflict(
            self.conn,
            appointment_date="2026-12-05",
            appointment_time="14:00",
            department="Cardiology",
            patient_id=self.patient_id
        )
        self.assertTrue(has_conflict)
        self.assertIn("already has an active appointment", msg)

    def test_conflict_detection_same_department(self):
        """Verify conflict detection when two different patients book the same department and slot."""
        patient_2 = register_patient(
            self.conn, "Pedro Penduko", "2000-01-01", "Male", "0920-555-7890", "Quezon City", "Lola Guida"
        )

        schedule_appointment(
            self.conn,
            patient_id=self.patient_id,
            appointment_date="2026-12-10",
            appointment_time="09:00",
            department="Orthopedics",
            reason="Knee pain"
        )

        has_conflict, msg = check_appointment_conflict(
            self.conn,
            appointment_date="2026-12-10",
            appointment_time="09:00",
            department="Orthopedics",
            patient_id=patient_2
        )
        self.assertTrue(has_conflict)
        self.assertIn("Orthopedics department already has an appointment booked", msg)

    def test_reschedule_appointment(self):
        """Verify rescheduling an appointment updates date/time and marks status 'Rescheduled'."""
        apt_id = schedule_appointment(
            self.conn,
            patient_id=self.patient_id,
            appointment_date="2026-12-15",
            appointment_time="11:00",
            department="Outpatient Department (OPD)",
            reason="Flu symptoms"
        )

        success, msg = reschedule_appointment(self.conn, apt_id, "2026-12-16", "15:00")
        self.assertTrue(success)

        apt = get_appointment_by_id(self.conn, apt_id)
        self.assertEqual(apt["appointment_date"], "2026-12-16")
        self.assertEqual(apt["appointment_time"], "15:00")
        self.assertEqual(apt["status"], "Rescheduled")

    def test_cancel_appointment(self):
        """Verify cancelling an appointment marks status 'Cancelled' and prevents further rescheduling."""
        apt_id = schedule_appointment(
            self.conn,
            patient_id=self.patient_id,
            appointment_date="2026-12-20",
            appointment_time="10:00",
            department="Pediatrics",
            reason="Consultation"
        )

        success, msg = cancel_appointment(self.conn, apt_id)
        self.assertTrue(success)

        apt = get_appointment_by_id(self.conn, apt_id)
        self.assertEqual(apt["status"], "Cancelled")

        # Attempt to reschedule cancelled appointment must fail
        reschedule_success, reschedule_msg = reschedule_appointment(self.conn, apt_id, "2026-12-21", "10:00")
        self.assertFalse(reschedule_success)
        self.assertIn("Cannot reschedule a cancelled appointment", reschedule_msg)


    def test_check_in_appointment_issues_queue_ticket(self):
        """Verify checking in a patient sets status to 'Checked-In' and issues a queue ticket."""
        apt_id = schedule_appointment(
            self.conn,
            patient_id=self.patient_id,
            appointment_date="2026-12-20",
            appointment_time="11:00",
            department="Cardiology",
            reason="Checkup"
        )
        ok, msg, ticket_id = check_in_appointment(self.conn, apt_id)
        self.assertTrue(ok)
        self.assertIsNotNone(ticket_id)
        self.assertTrue(ticket_id.startswith("TKT-"))

        apt = get_appointment_by_id(self.conn, apt_id)
        self.assertEqual(apt["status"], "Checked-In")

    def test_mark_appointment_noshow(self):
        """Verify missed appointments transition to 'No-Show' status."""
        apt_id = schedule_appointment(
            self.conn,
            patient_id=self.patient_id,
            appointment_date="2026-12-20",
            appointment_time="14:00",
            department="Orthopedics",
            reason="Knee consultation"
        )
        ok, msg = mark_appointment_noshow(self.conn, apt_id)
        self.assertTrue(ok)

        apt = get_appointment_by_id(self.conn, apt_id)
        self.assertEqual(apt["status"], "No-Show")


if __name__ == "__main__":
    unittest.main()

