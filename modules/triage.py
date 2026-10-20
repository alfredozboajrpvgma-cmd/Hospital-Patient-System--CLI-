"""
Handles nursing triage, vital signs screening (BP, pulse, temp, SpO2),
allergy checks, pain score, and urgency classification (Emergency, Urgent, Non-Urgent).
"""

import sqlite3
from datetime import datetime, date
from typing import Optional, List, Tuple, Dict, Any

from utils.display import (
    print_subheader,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_table,
    render_card,
    confirm_action,
    pause
)
from utils.validators import (
    validate_non_empty,
    validate_menu_choice
)
from config import (
    DATETIME_FORMAT,
    DATE_FORMAT,
    TRIAGE_CATEGORIES,
    VITAL_LIMITS
)
from modules.audit import log_audit_event
from modules.auth import get_current_session


def evaluate_vital_signs(
    temperature: float,
    bp_sys: int,
    bp_dia: int,
    pulse: int,
    resp: int,
    spo2: int,
    pain: int
) -> Tuple[List[str], str]:
    """
    Check vital signs against standard clinical limits.
    Returns any warnings and a suggested category (Emergency, Urgent, Non-Urgent).
    """
    alerts = []
    category = "Non-Urgent"


    if spo2 < VITAL_LIMITS["spo2_severe_hypoxia"]:
        alerts.append(f"CRITICAL HYPOXIA: SpO2 {spo2}% (Threshold < {VITAL_LIMITS['spo2_severe_hypoxia']}%)")
        category = "Emergency"
    elif spo2 < VITAL_LIMITS["spo2_hypoxia"]:
        alerts.append(f"HYPOXIA ALERT: SpO2 {spo2}% (Threshold < {VITAL_LIMITS['spo2_hypoxia']}%)")
        if category != "Emergency":
            category = "Urgent"


    if bp_sys >= VITAL_LIMITS["bp_sys_crisis"] or bp_dia >= VITAL_LIMITS["bp_dia_crisis"]:
        alerts.append(f"HYPERTENSIVE CRISIS RANGE: BP {bp_sys}/{bp_dia} mmHg")
        category = "Emergency"
    elif bp_sys < VITAL_LIMITS["bp_sys_hypo"] or bp_dia < VITAL_LIMITS["bp_dia_hypo"]:
        alerts.append(f"HYPOTENSION ALERT: BP {bp_sys}/{bp_dia} mmHg")
        if category != "Emergency":
            category = "Urgent"


    if pulse > VITAL_LIMITS["pulse_tachy"]:
        alerts.append(f"TACHYCARDIA ALERT: Heart Rate {pulse} bpm")
        if category != "Emergency":
            category = "Urgent"
    elif pulse < VITAL_LIMITS["pulse_brady"]:
        alerts.append(f"BRADYCARDIA ALERT: Heart Rate {pulse} bpm")
        if category != "Emergency":
            category = "Urgent"


    if temperature >= VITAL_LIMITS["temp_high_fever"]:
        alerts.append(f"HIGH FEVER ALERT: Temp {temperature:.1f}°C")
        if category != "Emergency":
            category = "Urgent"
    elif temperature >= VITAL_LIMITS["temp_fever"]:
        alerts.append(f"FEVER PRESENT: Temp {temperature:.1f}°C")
    elif temperature < VITAL_LIMITS["temp_hypo"]:
        alerts.append(f"HYPOTHERMIA RISK: Temp {temperature:.1f}°C")
        if category != "Emergency":
            category = "Urgent"


    if resp > VITAL_LIMITS["resp_tachy"]:
        alerts.append(f"TACHYPNEA: Respiratory Rate {resp} breaths/min")
        if category != "Emergency":
            category = "Urgent"
    elif resp < VITAL_LIMITS["resp_brady"]:
        alerts.append(f"BRADYPNEA / RESPIRATORY DEPRESSION: {resp} breaths/min")
        category = "Emergency"


    if pain >= 8:
        alerts.append(f"SEVERE ACUTE PAIN: Score {pain}/10")
        if category != "Emergency":
            category = "Urgent"

    return alerts, category


def generate_triage_id(conn: sqlite3.Connection) -> str:
    """Generate next triage ID like TRG-1001."""
    cursor = conn.cursor()
    cursor.execute("SELECT triage_id FROM triage_records WHERE triage_id LIKE 'TRG-%' ORDER BY triage_id DESC")
    rows = cursor.fetchall()

    max_val = 1000
    for r in rows:
        tid = r["triage_id"]
        parts = tid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_val:
                max_val = val
    return f"TRG-{max_val + 1}"


def record_triage(
    conn: sqlite3.Connection,
    patient_id: str,
    nurse_user: str,
    chief_complaint: str,
    allergies: str,
    temperature: str,
    bp_systolic: int,
    bp_diastolic: int,
    pulse_rate: int,
    respiratory_rate: int,
    oxygen_saturation: int,
    pain_score: int,
    triage_category: str,
    clinical_alerts: str = "",
    ticket_id: Optional[str] = None,
    triage_date: Optional[str] = None
) -> str:
    """Save nursing triage assessment to the database."""
    triage_id = generate_triage_id(conn)
    date_val = triage_date or datetime.now().strftime(DATETIME_FORMAT)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO triage_records (
            triage_id, patient_id, ticket_id, triage_date, nurse_user,
            chief_complaint, allergies, temperature, bp_systolic, bp_diastolic,
            pulse_rate, respiratory_rate, oxygen_saturation, pain_score,
            triage_category, clinical_alerts
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        triage_id, patient_id, ticket_id, date_val, nurse_user,
        chief_complaint, allergies, temperature, bp_systolic, bp_diastolic,
        pulse_rate, respiratory_rate, oxygen_saturation, pain_score,
        triage_category, clinical_alerts
    ))
    conn.commit()


    session = get_current_session()
    u_id = session.user_id if session else "NURSE"
    u_name = session.username if session else nurse_user
    log_audit_event(conn, u_id, u_name, "TRIAGE_RECORDED", "TriageRecord", triage_id, f"Patient {patient_id} - Category: {triage_category}")

    return triage_id


def get_triage_by_patient(conn: sqlite3.Connection, patient_id: str) -> List[sqlite3.Row]:
    """Get all past triage assessments for a patient."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, p.full_name as patient_name
        FROM triage_records t
        JOIN patients p ON t.patient_id = p.patient_id
        WHERE UPPER(t.patient_id) = UPPER(?)
        ORDER BY t.triage_date DESC
    """, (patient_id.strip(),))
    return cursor.fetchall()


def get_latest_triage_for_patient(conn: sqlite3.Connection, patient_id: str) -> Optional[sqlite3.Row]:
    """Get the most recent triage record for a patient."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM triage_records
        WHERE UPPER(patient_id) = UPPER(?)
        ORDER BY triage_date DESC
        LIMIT 1
    """, (patient_id.strip(),))
    return cursor.fetchone()


def get_triage_by_id(conn: sqlite3.Connection, triage_id: str) -> Optional[sqlite3.Row]:
    """Find a triage record by its ID."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, p.full_name as patient_name, p.dob, p.sex
        FROM triage_records t
        JOIN patients p ON t.patient_id = p.patient_id
        WHERE UPPER(t.triage_id) = UPPER(?)
    """, (triage_id.strip(),))
    return cursor.fetchone()






def handle_record_triage(
    conn: sqlite3.Connection,
    preselected_patient: Optional[sqlite3.Row] = None,
    ticket_id: Optional[str] = None
) -> Optional[str]:
    """Interactive screen for nurses to record patient vitals and allergies."""
    from modules.patients import select_patient_interactive

    print_subheader("Nursing Triage & Patient Assessment")
    print_info("Nursing Documentation: Patient vitals, stated chief complaint, and allergy screening.\n")

    patient = preselected_patient
    if not patient:
        patient = select_patient_interactive(conn, prompt_text="Enter Patient ID or Name for Triage Assessment: ", include_archived=False)
        if not patient:
            print_warning("Triage assessment cancelled.")
            pause()
            return None

    session = get_current_session()
    nurse_name = session.full_name if session else "Nurse Duty Officer"

    print_info(f"Assessing Patient: {patient['full_name']} ({patient['patient_id']})")
    print_info(f"Assessing Nurse:   {nurse_name}")

    try:

        while True:
            complaint = input("\nStated Chief Complaint (e.g., severe headache, chest tightness): ").strip()
            if not complaint:
                print_error("Chief complaint cannot be empty.")
                continue
            break


        print("\nAllergy Screening:")
        print("  Document known drug, food, or latex allergies. Type 'NKDA' if none known.")
        allergies_in = input("Known Allergies [NKDA]: ").strip()
        allergies = allergies_in if allergies_in else "No Known Drug Allergies (NKDA)"


        print("\nEnter Vital Signs:")


        while True:
            t_str = input("  Temperature (°C, e.g. 36.8): ").strip()
            try:
                temp = float(t_str)
                if not (VITAL_LIMITS["temp_min"] <= temp <= VITAL_LIMITS["temp_max"]):
                    print_error(f"Value out of physiological range ({VITAL_LIMITS['temp_min']}°C - {VITAL_LIMITS['temp_max']}°C). Check input.")
                    continue
                break
            except ValueError:
                print_error("Please enter a valid numeric temperature.")


        while True:
            bp_sys_str = input("  Systolic BP (mmHg, e.g. 120): ").strip()
            try:
                bp_sys = int(bp_sys_str)
                if not (VITAL_LIMITS["bp_sys_min"] <= bp_sys <= VITAL_LIMITS["bp_sys_max"]):
                    print_error(f"Systolic out of range ({VITAL_LIMITS['bp_sys_min']} - {VITAL_LIMITS['bp_sys_max']}).")
                    continue
                break
            except ValueError:
                print_error("Please enter a whole number for systolic BP.")

        while True:
            bp_dia_str = input("  Diastolic BP (mmHg, e.g. 80): ").strip()
            try:
                bp_dia = int(bp_dia_str)
                if not (VITAL_LIMITS["bp_dia_min"] <= bp_dia <= VITAL_LIMITS["bp_dia_max"]):
                    print_error(f"Diastolic out of range ({VITAL_LIMITS['bp_dia_min']} - {VITAL_LIMITS['bp_dia_max']}).")
                    continue
                break
            except ValueError:
                print_error("Please enter a whole number for diastolic BP.")


        while True:
            pulse_str = input("  Pulse / Heart Rate (bpm, e.g. 78): ").strip()
            try:
                pulse = int(pulse_str)
                if not (VITAL_LIMITS["pulse_min"] <= pulse <= VITAL_LIMITS["pulse_max"]):
                    print_error(f"Pulse out of range ({VITAL_LIMITS['pulse_min']} - {VITAL_LIMITS['pulse_max']}).")
                    continue
                break
            except ValueError:
                print_error("Please enter an integer pulse rate.")


        while True:
            resp_str = input("  Respiratory Rate (breaths/min, e.g. 16): ").strip()
            try:
                resp = int(resp_str)
                if not (VITAL_LIMITS["resp_min"] <= resp <= VITAL_LIMITS["resp_max"]):
                    print_error(f"Respiratory rate out of range ({VITAL_LIMITS['resp_min']} - {VITAL_LIMITS['resp_max']}).")
                    continue
                break
            except ValueError:
                print_error("Please enter an integer respiratory rate.")


        while True:
            spo2_str = input("  Oxygen Saturation SpO2 (%, e.g. 98): ").strip()
            try:
                spo2 = int(spo2_str)
                if not (VITAL_LIMITS["spo2_min"] <= spo2 <= VITAL_LIMITS["spo2_max"]):
                    print_error(f"SpO2 out of range ({VITAL_LIMITS['spo2_min']} - {VITAL_LIMITS['spo2_max']}%).")
                    continue
                break
            except ValueError:
                print_error("Please enter an integer SpO2 percentage.")


        while True:
            pain_str = input("  Pain Score (0 to 10, where 0=No Pain, 10=Worst Possible) [0]: ").strip() or "0"
            try:
                pain = int(pain_str)
                if not (0 <= pain <= 10):
                    print_error("Pain score must be between 0 and 10.")
                    continue
                break
            except ValueError:
                print_error("Please enter a whole number between 0 and 10.")


        alerts, suggested_cat = evaluate_vital_signs(temp, bp_sys, bp_dia, pulse, resp, spo2, pain)

        screening_fields = {
            "Patient": f"{patient['full_name']} ({patient['patient_id']})",
            "Chief Complaint": complaint,
            "Allergies": allergies,
            "Vital Signs": (
                f"T: {temp:.1f}°C | BP: {bp_sys}/{bp_dia} | "
                f"HR: {pulse} bpm | RR: {resp} | SpO2: {spo2}% | Pain: {pain}/10"
            ),
            "Suggested Category": suggested_cat,
        }
        if alerts:
            screening_fields["⚠️ Physiological Alerts"] = "; ".join(alerts)
        else:
            screening_fields["Alert Status"] = "All vital signs within normal reference ranges."
        render_card("TRIAGE ASSESSMENT CLINICAL SCREENING", screening_fields, border_style="yellow")


        from utils.prompts import select_option, select_menu, confirm_prompt
        from utils.display import render_card
        from utils.validators import TriageCreateModel, format_pydantic_error
        from utils.schema import ValidationError

        final_cat = select_option(
            f"Select Final Triage Urgency Category (Suggested: {suggested_cat}):",
            TRIAGE_CATEGORIES,
            default=suggested_cat
        ) or suggested_cat

        alert_text = " | ".join(alerts) if alerts else "None"


        try:
            trg_model = TriageCreateModel(
                patient_id=patient["patient_id"],
                ticket_id=ticket_id,
                nurse_user=nurse_name,
                chief_complaint=complaint,
                allergies=allergies,
                temperature=temp,
                bp_systolic=bp_sys,
                bp_diastolic=bp_dia,
                pulse_rate=pulse,
                respiratory_rate=resp,
                oxygen_saturation=spo2,
                pain_score=pain,
                triage_category=final_cat
            )
        except ValidationError as exc:
            print_error(format_pydantic_error(exc))
            pause()
            return None


        render_card("NURSING TRIAGE ASSESSMENT SUMMARY", {
            "Patient": f"{patient['full_name']} ({patient['patient_id']})",
            "Triage Nurse": trg_model.nurse_user,
            "Chief Complaint": trg_model.chief_complaint,
            "Allergies": trg_model.allergies,
            "Vital Signs": f"Temp: {trg_model.temperature:.1f}°C | BP: {trg_model.bp_systolic}/{trg_model.bp_diastolic} | HR: {trg_model.pulse_rate} bpm | SpO2: {trg_model.oxygen_saturation}% | Pain: {trg_model.pain_score}/10",
            "Assigned Category": trg_model.triage_category,
            "Clinical Alert Flags": alert_text
        })

        if confirm_prompt("Confirm and save nursing triage record?", default=True):
            trg_id = record_triage(
                conn=conn,
                patient_id=trg_model.patient_id,
                nurse_user=trg_model.nurse_user,
                chief_complaint=trg_model.chief_complaint,
                allergies=trg_model.allergies,
                temperature=f"{trg_model.temperature:.1f}",
                bp_systolic=trg_model.bp_systolic,
                bp_diastolic=trg_model.bp_diastolic,
                pulse_rate=trg_model.pulse_rate,
                respiratory_rate=trg_model.respiratory_rate,
                oxygen_saturation=trg_model.oxygen_saturation,
                pain_score=trg_model.pain_score,
                triage_category=trg_model.triage_category,
                clinical_alerts=alert_text,
                ticket_id=ticket_id
            )
            print_success(f"Triage record saved successfully! Triage ID: {trg_id}")
            print_info(f"Patient is categorized as '{final_cat}'. Ready for Physician Consultation.")
            pause()
            return trg_id

    except (KeyboardInterrupt, EOFError):
        print("\nTriage cancelled.")
        pause()
    return None


def handle_view_patient_triage(conn: sqlite3.Connection) -> None:
    """View vital signs and triage history for a patient."""
    from modules.patients import select_patient_interactive

    print_subheader("Patient Triage & Vital Signs History")
    patient = select_patient_interactive(conn, prompt_text="Enter Patient ID or Name to view vitals history: ")
    if not patient:
        return

    records = get_triage_by_patient(conn, patient["patient_id"])
    if not records:
        print_info(f"No triage records found for patient {patient['patient_id']}.")
        pause()
        return

    headers = ["Triage ID", "Date", "Nurse", "BP", "Temp", "HR", "SpO2", "Pain", "Category", "Alerts"]
    rows = [
        [
            r["triage_id"],
            r["triage_date"].split()[0],
            r["nurse_user"],
            f"{r['bp_systolic']}/{r['bp_diastolic']}",
            f"{r['temperature']}°C",
            f"{r['pulse_rate']}",
            f"{r['oxygen_saturation']}%",
            f"{r['pain_score']}/10",
            r["triage_category"],
            (r["clinical_alerts"][:20] + "...") if r["clinical_alerts"] and len(r["clinical_alerts"]) > 20 else (r["clinical_alerts"] or "None")
        ]
        for r in records
    ]
    print_table(headers, rows)
    pause()


def triage_menu(conn: sqlite3.Connection) -> None:
    """Triage and nursing assessment menu loop."""
    from utils.prompts import select_menu

    choices = [
        "1. Perform Patient Triage & Vitals Assessment",
        "2. View Patient Triage & Vital Signs History",
        "3. Return to Main Menu"
    ]

    while True:
        print_subheader("Nursing Triage & Vitals Assessment Menu")
        choice = select_menu("Select Nursing Triage Option:", choices)
        if not choice or "Return to Main Menu" in choice:
            break

        if choice.startswith("1."):
            handle_record_triage(conn)
        elif choice.startswith("2."):
            handle_view_patient_triage(conn)
