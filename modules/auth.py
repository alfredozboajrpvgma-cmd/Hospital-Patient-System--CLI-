"""
Handles staff login, salted password hashing, user sessions,
and role-based permissions (Administrator, Doctor, Nurse, Receptionist, Billing).
"""

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Set

from utils.display import (
    print_subheader,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_table,
    confirm_action,
    pause
)
from utils.validators import validate_non_empty, validate_menu_choice
from config import STAFF_ROLES, DATETIME_FORMAT


@dataclass
class UserSession:
    """Stores the currently logged-in staff member."""
    user_id: str
    username: str
    full_name: str
    role: str
    logged_in_at: str

    def can_access(self, resource: str, action: str = "read") -> bool:
        """Check if this user's role allows them to perform an action."""
        return has_permission(self.role, resource, action)


# Global active session
_CURRENT_SESSION: Optional[UserSession] = None


def get_current_session() -> Optional[UserSession]:
    """Get the active user session."""
    return _CURRENT_SESSION


def set_current_session(user_row: sqlite3.Row) -> UserSession:
    """Save the logged-in user into the active session."""
    global _CURRENT_SESSION
    _CURRENT_SESSION = UserSession(
        user_id=user_row["user_id"],
        username=user_row["username"],
        full_name=user_row["full_name"],
        role=user_row["role"],
        logged_in_at=datetime.now().strftime(DATETIME_FORMAT)
    )
    return _CURRENT_SESSION


def clear_session() -> None:
    """Clear active session upon logout."""
    global _CURRENT_SESSION
    _CURRENT_SESSION = None


# ==========================================
# Password Hashing and Verification
# ==========================================

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash a password with salt using PBKDF2-HMAC-SHA256 so passwords are never saved in plain text."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 20000)
    return dk.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Check if the entered password matches the saved hash and salt."""
    # Check with PBKDF2-HMAC-SHA256
    computed_pbkdf2 = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 20000).hex()
    if secrets.compare_digest(computed_pbkdf2, stored_hash):
        return True

    # Fallback check for older accounts hashed with simple SHA-256
    hasher = hashlib.sha256()
    hasher.update(salt.encode("utf-8"))
    hasher.update(password.encode("utf-8"))
    computed_legacy = hasher.hexdigest()
    return secrets.compare_digest(computed_legacy, stored_hash)


# ==========================================
# Role-Based Permissions
# ==========================================

ROLE_PERMISSIONS: Dict[str, Dict[str, Set[str]]] = {
    "Administrator": {
        "*": {"all"}
    },
    "Doctor": {
        "patients": {"view"},
        "appointments": {"view"},
        "queue": {"view", "update"},
        "triage": {"view"},
        "consultations": {"view", "create", "update"},
        "reports": {"clinical"}
    },
    "Nurse": {
        "patients": {"view"},
        "appointments": {"view"},
        "queue": {"view", "update"},
        "triage": {"view", "create", "update"},
        "consultations": {"view"},
        "reports": {"triage"}
    },
    "Receptionist": {
        "patients": {"view", "create", "update", "archive"},
        "appointments": {"view", "create", "reschedule", "cancel"},
        "queue": {"view", "create", "update"},
        "triage": {"view"},
        "reports": {"reception"}
    },
    "Billing": {
        "patients": {"view"},
        "billing": {"view", "create", "payment"},
        "reports": {"financial"}
    }
}


def has_permission(role: str, resource: str, action: str = "view") -> bool:
    """
    Evaluate whether a staff role has permission to access a resource and action.
    Administrators have wildcard access.
    """
    if role not in ROLE_PERMISSIONS:
        return False

    perms = ROLE_PERMISSIONS[role]
    if "*" in perms:
        return True

    if resource not in perms:
        return False

    allowed_actions = perms[resource]
    return action in allowed_actions or "all" in allowed_actions


# ==========================================
# Database Operations
# ==========================================

def generate_user_id(conn: sqlite3.Connection) -> str:
    """Generate next staff ID like USR-1001, USR-1002."""
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id LIKE 'USR-%' ORDER BY user_id DESC")
    rows = cursor.fetchall()

    max_num = 1000
    for r in rows:
        uid = r["user_id"]
        parts = uid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_num:
                max_num = val
    return f"USR-{max_num + 1}"


def register_user(
    conn: sqlite3.Connection,
    username: str,
    password: str,
    full_name: str,
    role: str
) -> str:
    """Create a new staff user with hashed password and role assignment."""
    if role not in STAFF_ROLES:
        raise ValueError(f"Invalid role '{role}'. Allowed: {', '.join(STAFF_ROLES)}")

    pwd_hash, salt = hash_password(password)
    user_id = generate_user_id(conn)
    created_at = datetime.now().strftime(DATETIME_FORMAT)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (
            user_id, username, password_hash, salt, full_name, role, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'Active', ?);
    """, (user_id, username.strip().lower(), pwd_hash, salt, full_name.strip(), role, created_at))
    conn.commit()
    return user_id


def authenticate_user(
    conn: sqlite3.Connection,
    username: str,
    password: str
) -> Tuple[bool, Optional[sqlite3.Row], str]:
    """Check username and password to log in a staff member."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),))
    user = cursor.fetchone()

    if not user:
        return False, None, "Invalid username or password."

    if user["status"] != "Active":
        return False, None, "This staff account is currently inactive. Contact the Administrator."

    if not verify_password(password, user["password_hash"], user["salt"]):
        return False, None, "Invalid username or password."

    return True, user, "Authentication successful."


def get_all_users(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """Get all staff accounts."""
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, full_name, role, status, created_at FROM users ORDER BY role, username")
    return cursor.fetchall()


def get_active_doctors(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """Get all active doctors."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, full_name, role, status
        FROM users
        WHERE role = 'Doctor' AND status = 'Active'
        ORDER BY full_name ASC;
    """)
    return cursor.fetchall()


def toggle_user_status(conn: sqlite3.Connection, user_id: str, new_status: str) -> bool:
    """Activate or deactivate a staff account."""
    if new_status not in ("Active", "Inactive"):
        return False
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE user_id = ?", (new_status, user_id))
    conn.commit()
    return cursor.rowcount > 0


# ==========================================
# CLI Submenus and Handlers
# ==========================================

def handle_login(conn: sqlite3.Connection) -> Optional[UserSession]:
    """Screen for staff to log in with their username and password."""
    print_subheader("Staff Authentication (Login)")
    print_info("Hospital personnel must log in with their assigned role credentials.")
    print_info("Default accounts for testing: admin, dr_smith, nurse_joy, reception, cashier\n")

    attempts = 0
    while attempts < 3:
        try:
            username = input("Username (or '0' to cancel): ").strip()
            if username in ("0", "q", "exit", "cancel"):
                return None

            password = input("Password: ").strip()
            if not password:
                print_error("Password cannot be empty.")
                continue

            success, user_row, message = authenticate_user(conn, username, password)
            if success and user_row:
                session = set_current_session(user_row)
                print_success(f"Welcome, {session.full_name} ({session.role})!")
                pause()
                return session
            else:
                attempts += 1
                print_error(f"{message} (Attempt {attempts}/3)")

        except (KeyboardInterrupt, EOFError):
            print("\nLogin cancelled.")
            return None

    print_warning("Maximum login attempts reached.")
    pause()
    return None


def handle_user_management(conn: sqlite3.Connection) -> None:
    """Administrator interface to manage hospital staff accounts."""
    from utils.prompts import select_menu, select_option, confirm_prompt
    from utils.display import render_card
    from utils.validators import StaffUserCreateModel, format_pydantic_error
    from utils.schema import ValidationError

    session = get_current_session()
    if not session or session.role != "Administrator":
        print_error("Access Denied: Only Administrators can manage staff accounts.")
        pause()
        return

    choices = [
        "1. View All Staff Accounts",
        "2. Register New Staff Account",
        "3. Activate / Deactivate Staff Account",
        "4. Return to Main Menu"
    ]

    while True:
        print_subheader("Staff User Account Management")
        choice = select_menu("Select Staff Management Option:", choices)
        if not choice or "Return to Main Menu" in choice:
            break

        if choice.startswith("1."):
            users = get_all_users(conn)
            headers = ["User ID", "Username", "Full Name", "Role", "Status", "Created At"]
            rows = [
                [u["user_id"], u["username"], u["full_name"], u["role"], u["status"], u["created_at"]]
                for u in users
            ]
            print_table(headers, rows)
            pause()

        elif choice.startswith("2."):
            print_subheader("Register New Staff Account")
            username = input("Enter Username (3-30 chars, letters/numbers/underscore): ").strip().lower()
            if not username:
                print_warning("Cancelled.")
                continue

            # Check uniqueness
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM users WHERE LOWER(username) = LOWER(?)", (username,))
            if cur.fetchone():
                print_error(f"Username '{username}' already exists.")
                pause()
                continue

            password = input("Enter Password (min 6 characters): ").strip()
            full_name = input("Enter Full Name (e.g. Dr. Maria Santos, MD): ").strip()

            role = select_option("Select Hospital Staff Role:", STAFF_ROLES)
            if not role:
                print_warning("Cancelled.")
                continue

            # Validate with Pydantic
            try:
                user_model = StaffUserCreateModel(
                    username=username,
                    password=password,
                    full_name=full_name,
                    role=role
                )
            except ValidationError as exc:
                print_error(format_pydantic_error(exc))
                pause()
                continue

            render_card("STAFF ACCOUNT REGISTRATION PREVIEW", {
                "Username": user_model.username,
                "Full Name": user_model.full_name,
                "Hospital Role": user_model.role
            })

            if confirm_prompt(f"Create account for {user_model.full_name} as {user_model.role}?", default=True):
                uid = register_user(conn, user_model.username, user_model.password, user_model.full_name, user_model.role)
                print_success(f"Staff account created! User ID: {uid}")
            pause()

        elif choice.startswith("3."):
            print_subheader("Activate / Deactivate Staff Account")
            users = get_all_users(conn)
            user_choices = [f"{u['user_id']} - {u['username']} ({u['full_name']} - {u['role']}) [{u['status']}]" for u in users]
            user_choices.append("Cancel")

            picked_str = select_menu("Select User Account to Toggle Status:", user_choices)
            if not picked_str or picked_str == "Cancel":
                continue

            picked_uid = picked_str.split(" - ")[0].strip()
            target_user = next((u for u in users if u["user_id"] == picked_uid), None)
            if not target_user:
                continue

            if target_user["username"] == "admin":
                print_error("Cannot deactivate the master admin account.")
                pause()
                continue

            new_status = "Inactive" if target_user["status"] == "Active" else "Active"
            if confirm_prompt(f"Change status of {target_user['username']} to {new_status}?", default=False):
                toggle_user_status(conn, target_user["user_id"], new_status)
                print_success(f"User {target_user['username']} is now {new_status}.")
            pause()

