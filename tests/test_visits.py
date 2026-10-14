"""
Automated unit tests for Visit Records (Philippine Edition).
Tests recording clinical visits, retrieving patient visit history,
and maintaining provider records.
"""

import unittest
from database import get_connection, create_schema
from modules.patients import register_patient
from modules.visits import (
    record_visit,
    get_visit_by_id,
    get_visits_by_patient,
    get_all_visits
)


class TestVisitManagement(unittest.TestCase):
    """Test suite for clinical patient visits."""

    def setUp(self):
        """Set up in-memory database and test patient with Philippine details."""
        self.conn = get_connection(":memory:")
        create_schema(self.conn)

        self.patient_id = register_patient(
            self.conn,
            full_name="Leonor Rivera",
            dob="1984-11-22",
            sex="Female",
            contact_number="0917-404-0000",
            address="Camiling, Tarlac",
            emergency_contact="Antonio Rivera 0918-404-1111"
        )

    def tearDown(self):
        """Close connection."""
        self.conn.close()

    def test_record_and_retrieve_visit(self):
        """Verify recording a visit associates correctly with the patient."""
        vid = record_visit(
            self.conn,
            patient_id=self.patient_id,
            visit_date="2026-10-14 14:00",
            department="Emergency Room (ER)",
            attending_provider="Dr. Jose Rizal",
            notes="Minor laceration treated with stitches and anti-tetanus. Vitals normal."
        )
        self.assertTrue(vid.startswith("VST-"))

        visit = get_visit_by_id(self.conn, vid)
        self.assertIsNotNone(visit)
        self.assertEqual(visit["patient_id"], self.patient_id)
        self.assertEqual(visit["patient_name"], "Leonor Rivera")
        self.assertEqual(visit["department"], "Emergency Room (ER)")
        self.assertEqual(visit["attending_provider"], "Dr. Jose Rizal")
        self.assertEqual(visit["notes"], "Minor laceration treated with stitches and anti-tetanus. Vitals normal.")

    def test_get_visits_by_patient(self):
        """Verify patient visit history retrieval."""
        record_visit(self.conn, self.patient_id, "2026-09-01 10:00", "Outpatient Department (OPD)", "Dr. Fe del Mundo", "Annual health checkup")
        record_visit(self.conn, self.patient_id, "2026-10-01 11:30", "Cardiology", "Dr. Juan Flavier", "Follow-up ECG consultation")

        history = get_visits_by_patient(self.conn, self.patient_id)
        self.assertEqual(len(history), 2)

    def test_get_all_visits(self):
        """Verify hospital-wide visit retrieval."""
        p2 = register_patient(self.conn, "Marcelo H. del Pilar", "1918-07-04", "Male", "0919-194-5555", "Bulakan, Bulacan", "Marciana")
        record_visit(self.conn, self.patient_id, "2026-10-01 10:00", "Internal Medicine", "Dr. Fe del Mundo", "Notes A")
        record_visit(self.conn, p2, "2026-10-02 11:00", "Orthopedics", "Dr. Juan Flavier", "Notes B")

        all_visits = get_all_visits(self.conn)
        self.assertEqual(len(all_visits), 2)


    def test_record_structured_soap_consultation(self):
        """Verify doctor consultation records structured SOAP fields alongside notes."""
        vid = record_visit(
            self.conn,
            patient_id=self.patient_id,
            visit_date="2026-10-15 10:30",
            department="Internal Medicine",
            attending_provider="Dr. Jose Rizal, MD",
            notes="CC: Fever and cough. Findings: Crackles right lower lobe. Dx: Community-Acquired Pneumonia. Plan: Amoxicillin 500mg, rest, fluids.",
            triage_id="TRG-1001",
            chief_complaint="Fever and productive cough",
            clinical_findings="Crackles right lower lobe, dullness to percussion",
            diagnosis="Community-Acquired Pneumonia (Low Risk)",
            treatment_plan="Amoxicillin 500mg TID for 7 days; hydration; return in 3 days",
            visit_status="Completed"
        )
        self.assertTrue(vid.startswith("VST-"))
        visit = get_visit_by_id(self.conn, vid)
        self.assertIsNotNone(visit)
        self.assertEqual(visit["diagnosis"], "Community-Acquired Pneumonia (Low Risk)")
        self.assertEqual(visit["triage_id"], "TRG-1001")


if __name__ == "__main__":
    unittest.main()

