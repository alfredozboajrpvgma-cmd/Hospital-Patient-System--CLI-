"""
Automated unit tests for Authentication and Role-Based Access Control (RBAC).
"""

import unittest
import sqlite3

from database import get_connection, create_schema
from modules.auth import (
    hash_password,
    verify_password,
    register_user,
    authenticate_user,
    has_permission,
    set_current_session,
    get_current_session,
    clear_session,
    toggle_user_status
)


class TestAuthAndRBAC(unittest.TestCase):
    """Test suite for password hashing, authentication, permissions, and sessions."""

    def setUp(self):
        """Set up in-memory database."""
        self.conn = get_connection(":memory:")
        create_schema(self.conn)
        clear_session()

    def tearDown(self):
        """Close database connection."""
        clear_session()
        self.conn.close()

    def test_password_hashing_and_verification(self):
        """Verify password hashes with unique salts and correctly validates."""
        pwd = "SecretHospitalPassword123!"
        hashed, salt = hash_password(pwd)
        self.assertNotEqual(pwd, hashed)
        self.assertEqual(len(salt), 32)
        self.assertTrue(verify_password(pwd, hashed, salt))
        self.assertFalse(verify_password("WrongPassword", hashed, salt))

    def test_register_and_authenticate_user(self):
        """Verify user registration and authentication."""
        uid = register_user(
            self.conn,
            username="nurse_clara",
            password="nursingpass123",
            full_name="Nurse Maria Clara",
            role="Nurse"
        )
        self.assertTrue(uid.startswith("USR-"))

        # Valid login
        ok, user, msg = authenticate_user(self.conn, "nurse_clara", "nursingpass123")
        self.assertTrue(ok)
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "nurse_clara")
        self.assertEqual(user["role"], "Nurse")

        # Wrong password
        ok_fail, user_fail, msg_fail = authenticate_user(self.conn, "nurse_clara", "wrongpass")
        self.assertFalse(ok_fail)
        self.assertIsNone(user_fail)

        # Nonexistent user
        ok_no, _, _ = authenticate_user(self.conn, "unknown_user", "pass")
        self.assertFalse(ok_no)

    def test_role_based_permissions(self):
        """Verify role-based permission matrix enforces access boundaries."""
        # Administrator has universal access
        self.assertTrue(has_permission("Administrator", "patients", "view"))
        self.assertTrue(has_permission("Administrator", "billing", "payment"))
        self.assertTrue(has_permission("Administrator", "random_module", "any_action"))

        # Doctor permissions
        self.assertTrue(has_permission("Doctor", "consultations", "create"))
        self.assertTrue(has_permission("Doctor", "triage", "view"))
        self.assertFalse(has_permission("Doctor", "billing", "payment"))

        # Nurse permissions
        self.assertTrue(has_permission("Nurse", "triage", "create"))
        self.assertTrue(has_permission("Nurse", "queue", "update"))
        self.assertFalse(has_permission("Nurse", "consultations", "create"))
        self.assertFalse(has_permission("Nurse", "billing", "create"))

        # Receptionist permissions
        self.assertTrue(has_permission("Receptionist", "patients", "create"))
        self.assertTrue(has_permission("Receptionist", "appointments", "create"))
        self.assertTrue(has_permission("Receptionist", "queue", "create"))
        self.assertFalse(has_permission("Receptionist", "consultations", "create"))

        # Billing permissions
        self.assertTrue(has_permission("Billing", "billing", "payment"))
        self.assertFalse(has_permission("Billing", "consultations", "create"))
        self.assertFalse(has_permission("Billing", "triage", "create"))

    def test_session_lifecycle(self):
        """Verify setting, retrieving, and clearing user sessions."""
        self.assertIsNone(get_current_session())

        # Authenticate admin
        ok, user, _ = authenticate_user(self.conn, "admin", "admin123")
        self.assertTrue(ok)
        session = set_current_session(user)
        self.assertIsNotNone(session)
        self.assertEqual(session.username, "admin")
        self.assertEqual(session.role, "Administrator")
        self.assertTrue(session.can_access("users", "view"))

        clear_session()
        self.assertIsNone(get_current_session())

    def test_inactive_user_cannot_login(self):
        """Verify deactivated accounts are rejected at login."""
        uid = register_user(self.conn, "temp_reception", "temp123", "Temp Clerk", "Receptionist")
        toggle_user_status(self.conn, uid, "Inactive")

        ok, _, msg = authenticate_user(self.conn, "temp_reception", "temp123")
        self.assertFalse(ok)
        self.assertIn("inactive", msg.lower())


if __name__ == "__main__":
    unittest.main()
