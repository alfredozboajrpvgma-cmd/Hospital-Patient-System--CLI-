"""
Automated unit tests for Patient Queue and Walk-in Management.
"""

import unittest
from database import get_connection, create_schema
from modules.patients import register_patient
from modules.queue import (
    issue_queue_ticket,
    get_daily_queue,
    update_queue_status,
    get_queue_ticket_by_id
)


class TestQueueManagement(unittest.TestCase):
    """Test suite for queue token generation, daily numbers, and priority ordering."""

    def setUp(self):
        """Set up in-memory database with test patients."""
        self.conn = get_connection(":memory:")
        create_schema(self.conn)

        self.p1 = register_patient(self.conn, "Juan dela Cruz", "1990-01-01", "Male", "0917-111-2222", "Manila", "Maria")
        self.p2 = register_patient(self.conn, "Jose Rizal", "1985-05-05", "Male", "0918-333-4444", "Calamba", "Saturnina")
        self.p3 = register_patient(self.conn, "Melchora Aquino", "1940-01-06", "Female", "0919-555-6666", "Quezon City", "Juan")

    def tearDown(self):
        """Close connection."""
        self.conn.close()

    def test_sequential_daily_queue_numbering(self):
        """Verify queue numbers increment sequentially for a given day."""
        t1, q1 = issue_queue_ticket(self.conn, self.p1, "Outpatient Department (OPD)", "Walk-in", ticket_date="2026-10-15")
        t2, q2 = issue_queue_ticket(self.conn, self.p2, "Pediatrics", "Walk-in", ticket_date="2026-10-15")
        t3, q3 = issue_queue_ticket(self.conn, self.p3, "Cardiology", "Scheduled", ticket_date="2026-10-15")

        self.assertEqual(q1, 1)
        self.assertEqual(q2, 2)
        self.assertEqual(q3, 3)
        self.assertTrue(t1.startswith("TKT-"))

        # Different day resets queue number
        t_next, q_next = issue_queue_ticket(self.conn, self.p1, "Cardiology", "Walk-in", ticket_date="2026-10-16")
        self.assertEqual(q_next, 1)

    def test_queue_status_progression(self):
        """Verify queue status transitions."""
        tid, _ = issue_queue_ticket(self.conn, self.p1, "OPD", "Walk-in", ticket_date="2026-10-15")
        ticket = get_queue_ticket_by_id(self.conn, tid)
        self.assertEqual(ticket["status"], "Waiting")

        # Advance to Triage
        self.assertTrue(update_queue_status(self.conn, tid, "Triage"))
        self.assertEqual(get_queue_ticket_by_id(self.conn, tid)["status"], "Triage")

        # Advance to Consultation
        self.assertTrue(update_queue_status(self.conn, tid, "Consultation"))
        self.assertEqual(get_queue_ticket_by_id(self.conn, tid)["status"], "Consultation")

        # Advance to Completed
        self.assertTrue(update_queue_status(self.conn, tid, "Completed"))
        self.assertEqual(get_queue_ticket_by_id(self.conn, tid)["status"], "Completed")

    def test_emergency_priority_sorting(self):
        """Verify emergency tickets take precedence in the queue display."""
        # Walk-in arrives first
        issue_queue_ticket(self.conn, self.p1, "Internal Medicine", "Walk-in", ticket_date="2026-10-15")
        # Scheduled arrives second
        issue_queue_ticket(self.conn, self.p2, "Internal Medicine", "Scheduled", ticket_date="2026-10-15")
        # Emergency arrives third
        issue_queue_ticket(self.conn, self.p3, "Emergency Room (ER)", "Emergency", ticket_date="2026-10-15")

        queue = get_daily_queue(self.conn, "2026-10-15")
        self.assertEqual(len(queue), 3)
        # First in sorted list must be the Emergency case
        self.assertEqual(queue[0]["ticket_type"], "Emergency")
        self.assertEqual(queue[0]["patient_id"], self.p3)


if __name__ == "__main__":
    unittest.main()
