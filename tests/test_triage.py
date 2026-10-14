"""
Automated unit tests for Nursing Triage and Vital Signs Assessment.
"""

import unittest
from database import get_connection, create_schema
from modules.patients import register_patient
from modules.triage import (
    evaluate_vital_signs,
    record_triage,
    get_triage_by_patient,
    get_latest_triage_for_patient,
    get_triage_by_id
)


class TestTriageAndVitals(unittest.TestCase):
    """Test suite for vital signs evaluation, clinical alert rules, and triage records."""

    def setUp(self):
        """Set up in-memory database with test patient."""
        self.conn = get_connection(":memory:")
        create_schema(self.conn)

        self.patient_id = register_patient(
            self.conn,
            full_name="Gabriela Silang",
            dob="1985-04-12",
            sex="Female",
            contact_number="0918-222-3344",
            address="Vigan, Ilocos Sur",
            emergency_contact="Diego Silang 0918-222-5566"
        )

    def tearDown(self):
        """Close database connection."""
        self.conn.close()

    def test_evaluate_normal_vitals(self):
        """Verify normal vital signs produce no alert flags and Non-Urgent category."""
        alerts, category = evaluate_vital_signs(
            temperature=36.7,
            bp_sys=118,
            bp_dia=78,
            pulse=72,
            resp=16,
            spo2=99,
            pain=1
        )
        self.assertEqual(len(alerts), 0)
        self.assertEqual(category, "Non-Urgent")

    def test_evaluate_hypoxia_emergency(self):
        """Verify SpO2 below 88% flags critical hypoxia and Emergency category."""
        alerts, category = evaluate_vital_signs(
            temperature=37.0,
            bp_sys=120,
            bp_dia=80,
            pulse=80,
            resp=20,
            spo2=86,
            pain=0
        )
        self.assertEqual(category, "Emergency")
        self.assertTrue(any("HYPOXIA" in a for a in alerts))

    def test_evaluate_hypertensive_crisis(self):
        """Verify systolic BP >= 180 flags hypertensive crisis and Emergency category."""
        alerts, category = evaluate_vital_signs(
            temperature=36.8,
            bp_sys=185,
            bp_dia=110,
            pulse=88,
            resp=18,
            spo2=97,
            pain=3
        )
        self.assertEqual(category, "Emergency")
        self.assertTrue(any("HYPERTENSIVE CRISIS" in a for a in alerts))

    def test_evaluate_high_fever_and_tachycardia(self):
        """Verify high fever (>=38.5) and tachycardia (>100) trigger alert flags."""
        alerts, category = evaluate_vital_signs(
            temperature=39.1,
            bp_sys=120,
            bp_dia=80,
            pulse=115,
            resp=22,
            spo2=96,
            pain=4
        )
        self.assertEqual(category, "Urgent")
        self.assertTrue(any("HIGH FEVER" in a for a in alerts))
        self.assertTrue(any("TACHYCARDIA" in a for a in alerts))

    def test_record_and_retrieve_triage(self):
        """Verify recording nursing triage saves vitals, allergies, and chief complaint."""
        trg_id = record_triage(
            conn=self.conn,
            patient_id=self.patient_id,
            nurse_user="Nurse Joy dela Cruz, RN",
            chief_complaint="Productive cough and fever for 3 days",
            allergies="Penicillin (Rash/Anaphylaxis)",
            temperature="38.6",
            bp_systolic=120,
            bp_diastolic=80,
            pulse_rate=95,
            respiratory_rate=20,
            oxygen_saturation=96,
            pain_score=3,
            triage_category="Urgent",
            clinical_alerts="HIGH FEVER ALERT: Temp 38.6°C"
        )
        self.assertTrue(trg_id.startswith("TRG-"))

        record = get_triage_by_id(self.conn, trg_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["patient_id"], self.patient_id)
        self.assertEqual(record["chief_complaint"], "Productive cough and fever for 3 days")
        self.assertEqual(record["allergies"], "Penicillin (Rash/Anaphylaxis)")
        self.assertEqual(record["temperature"], "38.6")
        self.assertEqual(record["triage_category"], "Urgent")

        # Test latest triage helper
        latest = get_latest_triage_for_patient(self.conn, self.patient_id)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["triage_id"], trg_id)


if __name__ == "__main__":
    unittest.main()
