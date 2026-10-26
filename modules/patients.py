"""
Handles registering new patients, searching records, updating info,
and archiving patient files.
"""

import sqlite3
from datetime import date
from typing import Optional, List, Dict, Any

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
from utils.validators import (
    validate_non_empty,
    validate_date,
    validate_phone,
    validate_sex,
    validate_menu_choice
)
import re
from config import DATE_FORMAT, PATIENT_TYPES
from modules.audit import log_audit_event
from modules.auth import get_current_session






def generate_patient_id(conn: sqlite3.Connection) -> str:
    """Generate the next patient ID like PAT-1001 by finding the highest ID and adding 1."""
    cursor = conn.cursor()
    cursor.execute("SELECT patient_id FROM patients WHERE patient_id LIKE 'PAT-%' ORDER BY patient_id DESC")
    rows = cursor.fetchall()
    
    max_id_num = 1000
    for row in rows:
        pid = row["patient_id"]
        parts = pid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_id_num:
                max_id_num = val
                
    next_id_num = max_id_num + 1
    return f"PAT-{next_id_num}"


def register_patient(
    conn: sqlite3.Connection,
    full_name: str,
    dob: str,
    sex: str,
    contact_number: str,
    address: str,
    emergency_contact: str,
    registration_date: Optional[str] = None,
    patient_type: str = "Outpatient"
) -> str:
    """Save a new patient into the database and return their assigned ID."""
    patient_id = generate_patient_id(conn)
    reg_date = registration_date or date.today().strftime(DATE_FORMAT)

    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(patients)")
    cols = [r[1] for r in cursor.fetchall()]

    if "patient_type" in cols:
        cursor.execute("""
            INSERT INTO patients (
                patient_id, full_name, dob, sex, contact_number,
                address, emergency_contact, registration_date, status, patient_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?);
        """, (
            patient_id, full_name, dob, sex, contact_number,
            address, emergency_contact, reg_date, patient_type
        ))
    else:
        cursor.execute("""
            INSERT INTO patients (
                patient_id, full_name, dob, sex, contact_number,
                address, emergency_contact, registration_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active');
        """, (
            patient_id, full_name, dob, sex, contact_number,
            address, emergency_contact, reg_date
        ))
    conn.commit()


    session = get_current_session()
    uid = session.user_id if session else "SYSTEM"
    uname = session.username if session else "system"
    log_audit_event(conn, uid, uname, "PATIENT_REGISTERED", "Patient", patient_id, f"Registered: {full_name} ({patient_type})")

    return patient_id


def check_potential_duplicate(
    conn: sqlite3.Connection,
    full_name: str,
    dob: str,
    contact_number: str
) -> Optional[sqlite3.Row]:
    """Check if someone with the same name, birthday, and contact number is already registered."""
    norm_name = " ".join(full_name.strip().lower().split())
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM patients 
        WHERE LOWER(TRIM(full_name)) = LOWER(?) AND dob = ? AND contact_number = ?
    """, (norm_name, dob, contact_number.strip()))
    return cursor.fetchone()


def get_patient_by_id(conn: sqlite3.Connection, patient_id: str) -> Optional[sqlite3.Row]:
    """Look up a single patient using their ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE UPPER(patient_id) = UPPER(?)", (patient_id.strip(),))
    return cursor.fetchone()


def get_all_patients(
    conn: sqlite3.Connection,
    filter_status: Optional[str] = None
) -> List[sqlite3.Row]:
    """Get all patients, or filter by Active / Archived."""
    cursor = conn.cursor()
    if filter_status:
        cursor.execute("SELECT * FROM patients WHERE status = ? ORDER BY patient_id ASC", (filter_status,))
    else:
        cursor.execute("SELECT * FROM patients ORDER BY patient_id ASC")
    return cursor.fetchall()


def search_patients(conn: sqlite3.Connection, query: str) -> List[sqlite3.Row]:
    """Find patients by matching part of their ID or name."""
    search_term = f"%{query.strip()}%"
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM patients 
        WHERE patient_id LIKE ? OR full_name LIKE ?
        ORDER BY patient_id ASC
    """, (search_term, search_term))
    return cursor.fetchall()


def select_patient_interactive(
    conn: sqlite3.Connection,
    prompt_text: str = "Enter Patient ID or Name (or '?' for list): ",
    include_archived: bool = True
) -> Optional[sqlite3.Row]:
    """Helper to let the user pick a patient by ID, name, or interactive search."""
    from utils.prompts import interactive_patient_lookup
    return interactive_patient_lookup(conn, prompt_text=prompt_text, include_archived=include_archived)


def update_patient(
    conn: sqlite3.Connection,
    patient_id: str,
    **fields: Any
) -> bool:
    """Update patient details like address, phone number, or classification."""
    allowed_fields = {
        "full_name", "dob", "sex", "contact_number",
        "address", "emergency_contact", "status", "patient_type"
    }
    updates = []
    values = []


    for key, value in fields.items():
        if key in allowed_fields and value is not None:
            updates.append(f"{key} = ?")
            values.append(value)

    if not updates:
        return False

    values.append(patient_id)
    query = f"UPDATE patients SET {', '.join(updates)} WHERE patient_id = ?"
    cursor = conn.cursor()
    cursor.execute(query, tuple(values))
    conn.commit()

    success = cursor.rowcount > 0
    if success:
        session = get_current_session()
        uid = session.user_id if session else "SYSTEM"
        uname = session.username if session else "system"
        log_audit_event(conn, uid, uname, "PATIENT_UPDATED", "Patient", patient_id, f"Fields updated: {', '.join(fields.keys())}")

    return success


def archive_patient(conn: sqlite3.Connection, patient_id: str) -> bool:
    """Archive a patient instead of deleting them, keeping their medical records safe."""
    cursor = conn.cursor()
    cursor.execute("UPDATE patients SET status = 'Archived' WHERE patient_id = ?", (patient_id,))
    conn.commit()

    success = cursor.rowcount > 0
    if success:
        session = get_current_session()
        uid = session.user_id if session else "SYSTEM"
        uname = session.username if session else "system"
        log_audit_event(conn, uid, uname, "PATIENT_ARCHIVED", "Patient", patient_id, "Record archived (soft-deleted)")

    return success


def reactivate_patient(conn: sqlite3.Connection, patient_id: str) -> bool:
    """Restore an archived patient back to Active status."""
    cursor = conn.cursor()
    cursor.execute("UPDATE patients SET status = 'Active' WHERE patient_id = ?", (patient_id,))
    conn.commit()

    success = cursor.rowcount > 0
    if success:
        session = get_current_session()
        uid = session.user_id if session else "SYSTEM"
        uname = session.username if session else "system"
        log_audit_event(conn, uid, uname, "PATIENT_REACTIVATED", "Patient", patient_id, "Record reactivated to Active")

    return success






def handle_register_patient(conn: sqlite3.Connection) -> None:
    """Ask for patient details, validate with Pydantic, and save to database."""
    from utils.validators import PatientCreateModel, format_pydantic_error
    from utils.prompts import select_option, confirm_prompt
    from utils.display import render_card

    print_subheader("Register New Patient")
    print("Leave input blank or press Ctrl+C to cancel at any prompt.\n")

    try:

        name_input = input("Enter Full Name: ").strip()
        if not name_input:
            print_warning("Registration cancelled.")
            return


        dob_input = input("Enter Date of Birth (YYYY-MM-DD): ").strip()
        if not dob_input:
            print_warning("Registration cancelled.")
            return


        sex_input = select_option("Select Sex:", ["Male", "Female", "Other"])
        if not sex_input:
            print_warning("Registration cancelled.")
            return


        contact_input = input("Enter Contact Number (e.g. 09171234567 or +639171234567): ").strip()
        if not contact_input:
            print_warning("Registration cancelled.")
            return


        address_input = input("Enter Address (Street/Subdivision, Brgy, City/Municipality, Province): ").strip()
        if not address_input:
            print_warning("Registration cancelled.")
            return


        emerg_input = input("Enter Emergency Contact (Full Name & Contact No.): ").strip()
        if not emerg_input:
            print_warning("Registration cancelled.")
            return


        ptype_input = select_option("Select Patient Classification:", PATIENT_TYPES) or "Outpatient"


        try:
            validated = PatientCreateModel(
                full_name=name_input,
                dob=dob_input,
                sex=sex_input,
                contact_number=contact_input,
                address=address_input,
                emergency_contact=emerg_input,
                patient_type=ptype_input
            )
        except Exception as exc:
            from utils.schema import ValidationError
            if isinstance(exc, ValidationError):
                print_error(format_pydantic_error(exc))
            else:
                print_error(str(exc))
            pause()
            return


        duplicate = check_potential_duplicate(conn, validated.full_name, validated.dob, validated.contact_number)
        if duplicate:
            print_warning(f"An existing patient record ({duplicate['patient_id']}) matches this Name, DOB, and Phone!")
            if not confirm_prompt("Do you still want to register this as a new record?", default=False):
                print_info("Registration aborted.")
                return


        render_card("NEW PATIENT REGISTRATION SUMMARY", {
            "Full Name": validated.full_name,
            "Date of Birth": validated.dob,
            "Sex": validated.sex,
            "Contact Number": validated.contact_number,
            "Address": validated.address,
            "Emergency Contact": validated.emergency_contact,
            "Classification": validated.patient_type
        })

        if confirm_prompt("Confirm patient registration and create hospital record?", default=True):
            pid = register_patient(
                conn,
                full_name=validated.full_name,
                dob=validated.dob,
                sex=validated.sex,
                contact_number=validated.contact_number,
                address=validated.address,
                emergency_contact=validated.emergency_contact,
                patient_type=validated.patient_type
            )
            print_success(f"Patient registered successfully! Assigned Hospital ID: {pid}")
        else:
            print_info("Registration cancelled.")

    except (KeyboardInterrupt, EOFError):
        print("\nRegistration cancelled by user.")
    pause()


def handle_view_all_patients(conn: sqlite3.Connection) -> None:
    """Display all registered patients in a table."""
    print_subheader("All Registered Patients")
    patients = get_all_patients(conn)

    headers = ["Patient ID", "Full Name", "DOB", "Sex", "Contact", "Status"]
    rows = [
        [
            p["patient_id"],
            p["full_name"],
            p["dob"],
            p["sex"],
            p["contact_number"],
            p["status"]
        ]
        for p in patients
    ]
    print_table(headers, rows, empty_message="No patient records found in database.")
    pause()


def handle_search_patients(conn: sqlite3.Connection) -> None:
    """Find patients by matching their ID or part of their name."""
    print_subheader("Search Patients")
    query = input("Enter Patient ID or Name to search: ").strip()

    if not query:
        print_error("Search term cannot be empty.")
        pause()
        return

    results = search_patients(conn, query)
    headers = ["Patient ID", "Full Name", "DOB", "Sex", "Contact", "Status"]
    rows = [
        [
            p["patient_id"],
            p["full_name"],
            p["dob"],
            p["sex"],
            p["contact_number"],
            p["status"]
        ]
        for p in results
    ]
    print_table(headers, rows, empty_message=f"No patients found matching '{query}'.")
    pause()


def handle_view_patient_details(conn: sqlite3.Connection) -> None:
    """Show the complete profile of a specific patient in a Rich panel card."""
    from utils.display import render_card

    print_subheader("View Patient Details")
    patient = select_patient_interactive(conn, prompt_text="Enter Patient ID or Name to view details (or '?' for list): ")
    if not patient:
        print_info("Operation cancelled.")
        pause()
        return

    pt_keys = patient.keys()
    pt_type = patient["patient_type"] if "patient_type" in pt_keys else "Outpatient"
    render_card(f"PATIENT DOSSIER: {patient['patient_id']} ({patient['status']})", {
        "Patient ID": patient["patient_id"],
        "Full Name": patient["full_name"],
        "Date of Birth": patient["dob"],
        "Sex": patient["sex"],
        "Classification": pt_type,
        "Contact Number": patient["contact_number"],
        "Address": patient["address"],
        "Emergency Contact": patient["emergency_contact"],
        "Registration Date": patient["registration_date"],
        "Record Status": patient["status"]
    })
    pause()


def handle_update_patient(conn: sqlite3.Connection) -> None:
    """Let the user edit patient fields while keeping current values if left blank."""
    print_subheader("Update Patient Record")
    patient = select_patient_interactive(conn, prompt_text="Enter Patient ID or Name to update (or '?' for list): ")
    if not patient:
        print_info("Operation cancelled.")
        pause()
        return


    if patient["status"] == "Archived":
        print_warning("This patient record is currently ARCHIVED.")
        if confirm_action("Would you like to reactivate this patient first?", default_no=True):
            reactivate_patient(conn, patient["patient_id"])
            print_success(f"Patient {patient['patient_id']} has been reactivated.")
        else:
            print_info("Cannot modify an archived record.")
            pause()
            return

    print(f"\nEditing record for {patient['patient_id']} ({patient['full_name']})")
    print("Press Enter without typing to keep the current value.\n")

    updated_fields: Dict[str, Any] = {}

    try:

        new_name = input(f"Full Name [{patient['full_name']}]: ").strip()
        if new_name:
            val, res = validate_non_empty(new_name, "Full Name", min_length=2)
            if val:
                updated_fields["full_name"] = res
            else:
                print_error(f"Keeping existing name due to error: {res}")


        new_dob = input(f"Date of Birth [{patient['dob']}]: ").strip()
        if new_dob:
            val, res = validate_date(new_dob, allow_future=False, allow_past=True, field_name="DOB")
            if val:
                updated_fields["dob"] = res
            else:
                print_error(f"Keeping existing DOB due to error: {res}")


        new_sex = input(f"Sex [{patient['sex']}]: ").strip()
        if new_sex:
            val, res = validate_sex(new_sex)
            if val:
                updated_fields["sex"] = res
            else:
                print_error(f"Keeping existing sex due to error: {res}")


        new_phone = input(f"Contact Number [{patient['contact_number']}]: ").strip()
        if new_phone:
            val, res = validate_phone(new_phone, "Contact number")
            if val:
                updated_fields["contact_number"] = res
            else:
                print_error(f"Keeping existing contact due to error: {res}")


        new_addr = input(f"Address [{patient['address']}]: ").strip()
        if new_addr:
            val, res = validate_non_empty(new_addr, "Address", min_length=3)
            if val:
                updated_fields["address"] = res
            else:
                print_error(f"Keeping existing address due to error: {res}")


        new_emerg = input(f"Emergency Contact [{patient['emergency_contact']}]: ").strip()
        if new_emerg:
            val, res = validate_non_empty(new_emerg, "Emergency contact", min_length=3)
            if val:
                updated_fields["emergency_contact"] = res
            else:
                print_error(f"Keeping existing emergency contact due to error: {res}")

        if not updated_fields:
            print_info("No changes were made.")
            pause()
            return

        if confirm_action("\nSave updated patient details?", default_no=False):
            if update_patient(conn, patient["patient_id"], **updated_fields):
                print_success(f"Patient {patient['patient_id']} updated successfully.")
            else:
                print_error("Failed to update patient record.")
        else:
            print_info("Updates discarded.")

    except (KeyboardInterrupt, EOFError):
        print("\nUpdate cancelled by user.")
    pause()


def handle_archive_patient(conn: sqlite3.Connection) -> None:
    """Ask for confirmation before archiving a patient."""
    print_subheader("Archive Patient Record")
    patient = select_patient_interactive(conn, prompt_text="Enter Patient ID or Name to archive (or '?' for list): ")
    if not patient:
        print_info("Operation cancelled.")
        pause()
        return

    if patient["status"] == "Archived":
        print_warning(f"Patient {patient['patient_id']} is already archived.")
        pause()
        return

    print_warning(f"You are about to archive patient {patient['patient_id']} - {patient['full_name']}.")
    print_info("Archiving preserves historical visits, appointments, and billing data while marking the patient inactive.")

    if confirm_action("Are you sure you want to archive this record?", default_no=True):
        if archive_patient(conn, patient["patient_id"]):
            print_success(f"Patient {patient['patient_id']} has been archived.")
        else:
            print_error("Failed to archive patient record.")
    else:
        print_info("Archiving cancelled.")
    pause()


def patient_menu(conn: sqlite3.Connection) -> None:
    """Menu loop for the patient section."""
    from utils.prompts import select_menu

    choices = [
        "1. Register New Patient",
        "2. View All Patients",
        "3. Search Patients (by ID or Name)",
        "4. View Patient Details",
        "5. Update Patient Details",
        "6. Archive Patient Record",
        "7. Return to Main Menu"
    ]

    while True:
        print_subheader("Patient Management Menu")
        choice = select_menu("Select Patient Management Option:", choices)
        if not choice or "Return to Main Menu" in choice:
            break

        if choice.startswith("1."):
            handle_register_patient(conn)
        elif choice.startswith("2."):
            handle_view_all_patients(conn)
        elif choice.startswith("3."):
            handle_search_patients(conn)
        elif choice.startswith("4."):
            handle_view_patient_details(conn)
        elif choice.startswith("5."):
            handle_update_patient(conn)
        elif choice.startswith("6."):
            handle_archive_patient(conn)

