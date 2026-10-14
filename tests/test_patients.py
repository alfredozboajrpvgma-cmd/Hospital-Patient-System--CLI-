"""
Automated unit tests for Patient Management (Philippine Edition).
Uses an in-memory SQLite database to ensure clean, isolated test runs.
"""

import unittest
import sqlite3

from database import get_connection, create_schema
from modules.patients import (
    register_patient,
    get_patient_by_id,
    get_all_patients,
    search_patients,
    update_patient,
    archive_patient,
    reactivate_patient,
    check_potential_duplicate
)


class TestPatientManagement(unittest.TestCase):
    """Test suite for patient registration, search, updates, and archiving."""

    def setUp(self):
        """Set up an isolated in-memory database with fresh schema before each test."""
        self.conn = get_connection(":memory:")
        create_schema(self.conn)

    def tearDown(self):
        """Close connection and discard memory database."""
        self.conn.close()

    def test_register_and_retrieve_patient(self):
        """Verify patient registration generates valid ID and stores all fields."""
        pid = register_patient(
            self.conn,
            full_name="Juan dela Cruz",
            dob="1990-05-14",
            sex="Male",
            contact_number="0917-123-4567",
            address="Brgy. San Antonio, Pasig City, Metro Manila",
            emergency_contact="Maria dela Cruz 0918-765-4321"
        )
        self.assertTrue(pid.startswith("PAT-"))

        patient = get_patient_by_id(self.conn, pid)
        self.assertIsNotNone(patient)
        self.assertEqual(patient["patient_id"], pid)
        self.assertEqual(patient["full_name"], "Juan dela Cruz")
        self.assertEqual(patient["dob"], "1990-05-14")
        self.assertEqual(patient["sex"], "Male")
        self.assertEqual(patient["contact_number"], "0917-123-4567")
        self.assertEqual(patient["address"], "Brgy. San Antonio, Pasig City, Metro Manila")
        self.assertEqual(patient["emergency_contact"], "Maria dela Cruz 0918-765-4321")
        self.assertEqual(patient["status"], "Active")

    def test_sequential_id_generation(self):
        """Verify patient IDs increment sequentially."""
        pid1 = register_patient(self.conn, "Jose Rizal", "1991-01-01", "Male", "0917-111-2222", "Calamba, Laguna", "Saturnina")
        pid2 = register_patient(self.conn, "Maria Clara", "1992-02-02", "Female", "0918-333-4444", "San Diego, Manila", "Kapitan Tiago")
        pid3 = register_patient(self.conn, "Andres Bonifacio", "1993-03-03", "Male", "0919-555-6666", "Tondo, Manila", "Gregoria de Jesus")

        self.assertEqual(pid1, "PAT-1001")
        self.assertEqual(pid2, "PAT-1002")
        self.assertEqual(pid3, "PAT-1003")

    def test_search_patients(self):
        """Verify search by ID and case-insensitive name matching."""
        pid1 = register_patient(self.conn, "Emilio Aguinaldo", "1960-07-13", "Male", "0920-111-2233", "Kawit, Cavite", "Hilaria")
        pid2 = register_patient(self.conn, "Gabriela Silang", "1980-11-05", "Female", "0921-444-5566", "Vigan, Ilocos Sur", "Diego")

        # Search by exact name
        results = search_patients(self.conn, "Emilio")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["patient_id"], pid1)

        # Search by case-insensitive substring
        results_silang = search_patients(self.conn, "silang")
        self.assertEqual(len(results_silang), 1)
        self.assertEqual(results_silang[0]["patient_id"], pid2)

        # Search by ID
        results_id = search_patients(self.conn, pid1)
        self.assertEqual(len(results_id), 1)
        self.assertEqual(results_id[0]["full_name"], "Emilio Aguinaldo")

        # Nonexistent search
        results_none = search_patients(self.conn, "Lapu-Lapu")
        self.assertEqual(len(results_none), 0)

    def test_update_patient(self):
        """Verify updating patient records."""
        pid = register_patient(self.conn, "Apolinario Mabini", "1985-02-19", "Male", "0917-888-9999", "Tanauan, Batangas", "Inocencio")
        
        success = update_patient(
            self.conn,
            pid,
            contact_number="0918-000-1111",
            address="Nagcarlan, Laguna"
        )
        self.assertTrue(success)

        updated = get_patient_by_id(self.conn, pid)
        self.assertEqual(updated["contact_number"], "0918-000-1111")
        self.assertEqual(updated["address"], "Nagcarlan, Laguna")
        self.assertEqual(updated["full_name"], "Apolinario Mabini")  # Unmodified

    def test_archive_and_reactivate_patient(self):
        """Verify soft-deletion (archive) and reactivation."""
        pid = register_patient(self.conn, "Melchora Aquino", "1988-06-18", "Female", "0917-777-6655", "Balintawak, Quezon City", "Estanislao")

        # Archive
        self.assertTrue(archive_patient(self.conn, pid))
        patient = get_patient_by_id(self.conn, pid)
        self.assertEqual(patient["status"], "Archived")

        # Verify active filter excludes archived
        active_patients = get_all_patients(self.conn, filter_status="Active")
        self.assertEqual(len(active_patients), 0)

        # Reactivate
        self.assertTrue(reactivate_patient(self.conn, pid))
        patient_reactivated = get_patient_by_id(self.conn, pid)
        self.assertEqual(patient_reactivated["status"], "Active")

    def test_check_potential_duplicate(self):
        """Verify duplicate patient check finds existing records with identical name, dob, and phone."""
        register_patient(self.conn, "Teresa Magbanua", "1984-03-22", "Female", "0922-333-4455", "Pototan, Iloilo", "Alejandro")

        dup = check_potential_duplicate(self.conn, "Teresa Magbanua", "1984-03-22", "0922-333-4455")
        self.assertIsNotNone(dup)
        self.assertEqual(dup["full_name"], "Teresa Magbanua")

        no_dup = check_potential_duplicate(self.conn, "Teresa Magbanua", "1990-01-01", "0922-333-4455")
        self.assertIsNone(no_dup)


if __name__ == "__main__":
    unittest.main()
