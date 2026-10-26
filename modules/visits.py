"""
Handles doctor consultations, SOAP clinical notes (Subjective, Objective, Assessment, Plan),
and direct Emergency Room (ER) fast-track intake.
"""

import sqlite3
from datetime import datetime
from typing import Optional, List

from utils.display import (
    print_subheader,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_table,
    render_card,
    render_notice,
    confirm_action,
    pause,
)
from utils.validators import (
    validate_non_empty,
    validate_date,
    validate_menu_choice
)
from config import DEPARTMENTS, DATETIME_FORMAT
from modules.audit import log_audit_event
from modules.auth import get_current_session
from modules.triage import get_latest_triage_for_patient, record_triage, evaluate_vital_signs






def generate_visit_id(conn: sqlite3.Connection) -> str:
    """Generate the next visit ID like VST-1001, VST-1002."""
    cursor = conn.cursor()
    cursor.execute("SELECT visit_id FROM visits WHERE visit_id LIKE 'VST-%' ORDER BY visit_id DESC")
    rows = cursor.fetchall()


    max_id_num = 1000
    for row in rows:
        vid = row["visit_id"]
        parts = vid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_id_num:
                max_id_num = val

    next_id_num = max_id_num + 1
    return f"VST-{next_id_num}"


def record_visit(
    conn: sqlite3.Connection,
    patient_id: str,
    visit_date: str,
    department: str,
    attending_provider: str,
    notes: str,
    triage_id: Optional[str] = None,
    chief_complaint: str = "",
    clinical_findings: str = "",
    diagnosis: str = "",
    treatment_plan: str = "",
    visit_status: str = "Completed"
) -> str:
    """Save a doctor consultation record (with SOAP notes) into SQLite."""
    visit_id = generate_visit_id(conn)
    cursor = conn.cursor()


    cursor.execute("PRAGMA table_info(visits)")
    cols = [r[1] for r in cursor.fetchall()]

    if "triage_id" in cols:
        cursor.execute("""
            INSERT INTO visits (
                visit_id, patient_id, visit_date, department,
                attending_provider, notes, triage_id, chief_complaint,
                clinical_findings, diagnosis, treatment_plan, visit_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            visit_id, patient_id, visit_date, department,
            attending_provider, notes, triage_id, chief_complaint,
            clinical_findings, diagnosis, treatment_plan, visit_status
        ))
    else:
        cursor.execute("""
            INSERT INTO visits (
                visit_id, patient_id, visit_date, department,
                attending_provider, notes
            ) VALUES (?, ?, ?, ?, ?, ?);
        """, (visit_id, patient_id, visit_date, department, attending_provider, notes))
    conn.commit()

    session = get_current_session()
    uid = session.user_id if session else "DOCTOR"
    uname = session.username if session else attending_provider
    log_audit_event(conn, uid, uname, "CONSULTATION_LOGGED", "Visit", visit_id, f"Patient {patient_id} in {department} by {attending_provider}")

    return visit_id


def get_visit_by_id(conn: sqlite3.Connection, visit_id: str) -> Optional[sqlite3.Row]:
    """Get full visit details with patient contact info."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.*, p.full_name as patient_name, p.dob, p.contact_number
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        WHERE UPPER(v.visit_id) = UPPER(?)
    """, (visit_id.strip(),))
    return cursor.fetchone()


def get_visits_by_patient(conn: sqlite3.Connection, patient_id: str) -> List[sqlite3.Row]:
    """Get all past visits for one patient, sorted by newest first."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.*, p.full_name as patient_name
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        WHERE UPPER(v.patient_id) = UPPER(?)
        ORDER BY v.visit_date DESC
    """, (patient_id.strip(),))
    return cursor.fetchall()


def get_all_visits(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """Get all recorded visits across the hospital."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.*, p.full_name as patient_name
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        ORDER BY v.visit_date DESC
    """)
    return cursor.fetchall()






def handle_emergency_visit(
    conn: sqlite3.Connection,
    preselected_patient: Optional[sqlite3.Row] = None,
    default_notes: str = ""
) -> Optional[str]:
    """Direct Emergency Room (ER) intake without needing an appointment."""
    from modules.patients import select_patient_interactive, register_patient, get_patient_by_id
    from modules.auth import get_active_doctors
    from modules.queue import issue_queue_ticket, close_patient_active_queue_ticket
    from utils.prompts import select_option, select_menu, confirm_prompt

    render_notice(
        "🚨 EMERGENCY ROOM (ER) CLINICAL INTAKE",
        [
            "NO APPOINTMENT NEEDED — acute emergencies are prioritized immediately.",
            "Ordinary appointment scheduling is bypassed for acute Emergency Room care.",
        ],
        border_style="red",
    )
    print()

    patient = preselected_patient
    if not patient:
        print("Emergency Patient Intake:")
        print("  1. Look up existing patient (by name or ID)")
        print("  2. Fast-Track Emergency Walk-In Registration (New Patient)")
        print("  0. Cancel")
        mode = input("Enter choice (1-2, or 0 to Cancel): ").strip()

        if mode in ("0", "q", "cancel"):
            print_warning("Emergency intake cancelled.")
            return None
        elif mode == "2":
            print_subheader("Fast-Track Emergency Walk-In Patient Registration")
            name = input("Patient Full Name (or press Enter for 'Emergency Walk-in Patient'): ").strip() or "Emergency Walk-in Patient"
            dob = input("Date of Birth (YYYY-MM-DD, or press Enter for default 1990-01-01): ").strip() or "1990-01-01"
            sex = input("Sex (1. Male, 2. Female, 3. Other) [1]: ").strip()
            sex_val = "Female" if sex == "2" else "Male"
            contact = input("Contact Number (or press Enter if unknown): ").strip() or "0900-000-0000"
            pid = register_patient(
                conn, name, dob, sex_val, contact,
                address="Emergency Triage Intake",
                emergency_contact="ER Admitting Staff",
                patient_type="Emergency"
            )
            patient = get_patient_by_id(conn, pid)
            print_success(f"Emergency patient registered: {patient['full_name']} ({pid})")
        else:
            patient = select_patient_interactive(conn, prompt_text="Enter Patient ID or Name: ")
            if not patient:
                print_warning("Emergency intake cancelled.")
                return None


    tid, q_num = issue_queue_ticket(conn, patient["patient_id"], "Emergency Room (ER)", ticket_type="Emergency")
    print_info(f"🚨 Priority ER Queue Ticket #{q_num} issued ({tid}) with Emergency Prioritization.")

    print_info(f"Admitting patient to ER: {patient['full_name']} ({patient['patient_id']})")
    department = "Emergency Room (ER)"
    visit_date = datetime.now().strftime(DATETIME_FORMAT)
    print(f"  Department: {department}")
    print(f"  Timestamp:  {visit_date} (Immediate Assessment)")


    session = get_current_session()
    if session and session.role == "Doctor":
        provider = session.full_name
        print_info(f"  Attending Physician: {provider} (Authenticated Physician)")
    else:
        doctors = get_active_doctors(conn)
        if doctors:
            doc_choices = [f"{d['full_name']} ({d['username']})" for d in doctors]
            chosen = select_option("Select Attending ER Physician from Registered Staff:", doc_choices)
            provider = chosen.split(" (")[0] if chosen else doctors[0]["full_name"]
        else:
            provider = session.full_name if session else "Dr. ER Duty Physician"
        print_info(f"  Attending Physician: {provider}")


    if default_notes:
        print(f"\nReported Chief Complaint / Condition: {default_notes}")
        extra = input("Document Emergency Treatment / Interventions Administered: ").strip()
        notes = f"{default_notes}. Interventions: {extra}".strip() if extra else default_notes
    else:
        while True:
            notes_in = input("\nER Clinical Assessment & Immediate Interventions (Required): ").strip()
            if notes_in:
                notes = notes_in
                break
            print_error("Emergency documentation cannot be empty. Record clinical assessment and acute interventions.")

    vid = record_visit(conn, patient["patient_id"], visit_date, department, provider, notes)
    close_patient_active_queue_ticket(conn, patient["patient_id"], new_status="Billing")
    print()
    print_success(f"Emergency clinical record saved! Visit ID: {vid}")
    print_info(f"Patient {patient['full_name']} clinical assessment logged in {department}.")

    if confirm_action("\nDo you want to proceed to Billing for ER medication and services now?", default_no=True):
        from modules.billing import handle_generate_bill
        handle_generate_bill(conn, preselected_patient_id=patient["patient_id"], visit_id=vid)
    else:
        pause()
    return vid


def handle_record_visit(conn: sqlite3.Connection) -> None:
    """Interactive screen for recording a doctor consultation using the SOAP format."""
    from modules.patients import select_patient_interactive
    from modules.auth import get_active_doctors
    from modules.queue import close_patient_active_queue_ticket

    print_subheader("Record Patient Clinical Consultation (SOAP)")
    try:
        patient = select_patient_interactive(conn, prompt_text="Enter Patient ID or Name for visit (or '?' for list): ")
        if not patient:
            print_warning("Operation cancelled.")
            pause()
            return


        triage = get_latest_triage_for_patient(conn, patient["patient_id"])
        triage_id = None
        if triage:
            triage_id = triage["triage_id"]
            triage_fields = {
                "Triage Record": f"{triage['triage_id']} ({triage['triage_date']})",
                "Triage Nurse": triage["nurse_user"],
                "Chief Complaint": triage["chief_complaint"],
                "Allergies": triage["allergies"],
                "Vital Signs": (
                    f"Temp: {triage['temperature']}°C | "
                    f"BP: {triage['bp_systolic']}/{triage['bp_diastolic']} | "
                    f"HR: {triage['pulse_rate']} bpm | "
                    f"SpO2: {triage['oxygen_saturation']}% | "
                    f"Pain: {triage['pain_score']}/10"
                ),
            }
            if triage["clinical_alerts"] and triage["clinical_alerts"] != "None":
                triage_fields["⚠️ Clinical Alerts"] = triage["clinical_alerts"]
            render_card("🏥 PRE-CONSULTATION NURSING TRIAGE REVIEW", triage_fields, border_style="yellow")
        else:
            print()
            print_warning("⚠️  CLINICAL ADVISORY: No nursing triage assessment or vital signs recorded for this patient.")
            print_warning("    Physician should confirm and measure vital signs during the clinical evaluation.\n")

        visit_date = datetime.now().strftime(DATETIME_FORMAT)
        from utils.prompts import select_option, confirm_prompt
        from utils.display import render_card
        from utils.validators import VisitCreateModel, format_pydantic_error
        from utils.schema import ValidationError

        clinic_depts = [d for d in DEPARTMENTS if d != "Emergency Room (ER)"]
        department = select_option("Select Clinical Department / Clinic:", clinic_depts) or "Outpatient Department (OPD)"


        session = get_current_session()
        reassign_note = ""
        if session and session.role == "Doctor":
            attending_provider = session.full_name
            print_info(f"Attending Physician: {attending_provider} (Authenticated Doctor Account)")
        elif session and session.role == "Administrator":
            doctors = get_active_doctors(conn)
            if doctors:
                doc_choices = [f"{d['full_name']} ({d['username']})" for d in doctors]
                chosen = select_option("Select Attending Physician (Admin Reassignment):", doc_choices)
                if not chosen:
                    print_warning("Consultation cancelled.")
                    pause()
                    return
                attending_provider = chosen.split(" (")[0]
                reassign_note = f" (Reassigned by Admin: {session.username})"
            else:
                attending_provider = session.full_name
                print_info(f"Attending Physician: {attending_provider}")
        else:
            doctors = get_active_doctors(conn)
            if doctors:
                doc_choices = [f"{d['full_name']} ({d['username']})" for d in doctors]
                chosen = select_option("Select Attending Physician from Registered Staff:", doc_choices)
                if not chosen:
                    print_warning("Consultation cancelled.")
                    pause()
                    return
                attending_provider = chosen.split(" (")[0]
            else:
                attending_provider = session.full_name if session else "Dr. Attending Physician"
                print_info(f"Attending Physician: {attending_provider}")


        print("\nClinical Consultation Documentation (SOAP Format):")


        while True:
            default_cc = triage["chief_complaint"] if triage else ""
            if default_cc:
                use_triage = confirm_prompt(f"Use triage chief complaint '{default_cc}'?", default=True)
                if use_triage:
                    chief_complaint = default_cc
                    break
            cc_in = input("  1. Subjective History / Stated Chief Complaint: ").strip()
            if cc_in:
                chief_complaint = cc_in
                break
            print_error("Chief complaint is mandatory and cannot be empty.")


        while True:
            findings_in = input("  2. Objective Physical Findings & Observations (or 'normal' if none): ").strip()
            if findings_in.lower() in ("normal", "unremarkable", "none", "nil", "no abnormal findings"):
                if confirm_prompt("Confirm that physical examination was performed and is unremarkable?", default=True):
                    clinical_findings = "Physical examination confirmed unremarkable; no acute abnormalities detected."
                    break
            elif len(findings_in) >= 2:
                clinical_findings = findings_in
                break
            else:
                print_error("Documentation required: Document physical examination findings or explicitly confirm normal/unremarkable.")


        while True:
            diag_in = input("  3. Assessment / Clinical Diagnosis (Required): ").strip()
            if len(diag_in) >= 2:
                diagnosis = diag_in
                break
            print_error("Clinical diagnosis cannot be empty. Must be documented by the attending clinician.")


        while True:
            plan_in = input("  4. Treatment Plan / Prescriptions / Follow-up Orders: ").strip()
            if len(plan_in) >= 2:
                treatment_plan = plan_in
                break
            elif confirm_prompt("Confirm no active medications or procedural interventions indicated at this time?", default=False):
                treatment_plan = "No active medication or procedural intervention indicated; patient advised to follow up if symptoms persist."
                break
            else:
                print_error("Treatment plan is mandatory and must reflect the clinician's documented instructions.")


        notes = f"CC: {chief_complaint}. Findings: {clinical_findings}. Dx: {diagnosis}. Plan: {treatment_plan}{reassign_note}"


        try:
            visit_model = VisitCreateModel(
                patient_id=patient["patient_id"],
                visit_date=visit_date,
                department=department,
                attending_provider=attending_provider,
                notes=notes,
                triage_id=triage_id,
                chief_complaint=chief_complaint,
                clinical_findings=clinical_findings,
                diagnosis=diagnosis,
                treatment_plan=treatment_plan
            )
        except ValidationError as exc:
            print_error(format_pydantic_error(exc))
            pause()
            return


        render_card("CLINICAL CONSULTATION SUMMARY", {
            "Patient": f"{patient['full_name']} ({patient['patient_id']})",
            "Timestamp": visit_model.visit_date,
            "Department": visit_model.department,
            "Attending Physician": visit_model.attending_provider,
            "Chief Complaint": visit_model.chief_complaint,
            "Clinical Diagnosis": visit_model.diagnosis,
            "Treatment Plan": visit_model.treatment_plan
        })

        if confirm_prompt("Save this clinical consultation record?", default=True):
            vid = record_visit(
                conn=conn,
                patient_id=visit_model.patient_id,
                visit_date=visit_model.visit_date,
                department=visit_model.department,
                attending_provider=visit_model.attending_provider,
                notes=visit_model.notes,
                triage_id=visit_model.triage_id,
                chief_complaint=visit_model.chief_complaint,
                clinical_findings=visit_model.clinical_findings,
                diagnosis=visit_model.diagnosis,
                treatment_plan=visit_model.treatment_plan
            )

            closed_tid = close_patient_active_queue_ticket(conn, patient["patient_id"], new_status="Billing")
            print_success(f"Consultation record logged successfully! Visit ID: {vid}")
            if closed_tid:
                print_info(f"Daily queue ticket {closed_tid} updated to 'Billing'.")

            if confirm_prompt("Proceed to generate itemized bill for this consultation?", default=True):
                from modules.billing import handle_generate_bill
                handle_generate_bill(conn, preselected_patient_id=patient["patient_id"], visit_id=vid)
        else:
            print_info("Visit entry cancelled.")

    except (KeyboardInterrupt, EOFError):
        print("\nOperation cancelled by user.")
    pause()


def handle_view_patient_visits(conn: sqlite3.Connection) -> None:
    """View all visits made by one patient."""
    from modules.patients import select_patient_interactive

    print_subheader("View Patient Visit History")
    patient = select_patient_interactive(conn, prompt_text="Enter Patient ID or Name to view history (or '?' for list): ")
    if not patient:
        print_info("Operation cancelled.")
        pause()
        return

    visits = get_visits_by_patient(conn, patient["patient_id"])
    print_info(f"Visit history for {patient['full_name']} ({patient['patient_id']}):")


    headers = ["Visit ID", "Date & Time", "Department", "Provider", "Notes"]
    rows = [
        [
            v["visit_id"],
            v["visit_date"],
            v["department"],
            v["attending_provider"],
            (v["notes"][:35] + "...") if len(v["notes"]) > 35 else v["notes"]
        ]
        for v in visits
    ]
    print_table(headers, rows, empty_message=f"No visit records found for patient {patient['patient_id']}.")
    pause()


def handle_view_all_visits(conn: sqlite3.Connection) -> None:
    """Show every visit recorded in the hospital."""
    print_subheader("All Hospital Visit Records")
    visits = get_all_visits(conn)

    headers = ["Visit ID", "Patient ID", "Patient Name", "Date & Time", "Department", "Provider"]
    rows = [
        [
            v["visit_id"],
            v["patient_id"],
            v["patient_name"],
            v["visit_date"],
            v["department"],
            v["attending_provider"]
        ]
        for v in visits
    ]
    print_table(headers, rows, empty_message="No hospital visits recorded yet.")
    pause()


def handle_view_visit_details(conn: sqlite3.Connection) -> None:
    """Show the complete details and full notes of a single visit."""
    print_subheader("Visit Record Details")
    vid_input = input("Enter Visit ID (e.g. VST-1001 or 1001): ").strip()
    if not vid_input:
        print_error("Visit ID is required.")
        pause()
        return

    if vid_input.isdigit():
        vid_input = f"VST-{vid_input}"

    visit = get_visit_by_id(conn, vid_input)
    if not visit:
        print_error(f"Visit with ID '{vid_input}' not found.")
        pause()
        return

    from utils.display import render_card
    render_card(f"CLINICAL VISIT DOSSIER: {visit['visit_id']}", {
        "Visit ID": visit["visit_id"],
        "Patient": f"{visit['patient_name']} ({visit['patient_id']})",
        "Date of Birth": visit["dob"],
        "Contact Number": visit["contact_number"],
        "Visit Timestamp": visit["visit_date"],
        "Department": visit["department"],
        "Attending Physician": visit["attending_provider"],
        "Clinical Notes": visit["notes"]
    })
    pause()


def visit_menu(conn: sqlite3.Connection) -> None:
    """Submenu for handling patient visits."""
    from utils.prompts import select_menu

    choices = [
        "1. 🚨 Emergency Room (ER) Intake (Immediate Care)",
        "2. Record Regular Clinical Visit",
        "3. View Patient Visit History",
        "4. View All Hospital Visits",
        "5. View Specific Visit Details",
        "6. Return to Main Menu"
    ]

    while True:
        print_subheader("Visit Records Menu")
        choice = select_menu("Select Visit Records Option:", choices)
        if not choice or "Return to Main Menu" in choice:
            break

        if choice.startswith("1."):
            handle_emergency_visit(conn)
        elif choice.startswith("2."):
            handle_record_visit(conn)
        elif choice.startswith("3."):
            handle_view_patient_visits(conn)
        elif choice.startswith("4."):
            handle_view_all_visits(conn)
        elif choice.startswith("5."):
            handle_view_visit_details(conn)

