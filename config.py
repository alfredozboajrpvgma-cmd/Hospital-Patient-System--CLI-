"""
Settings and constants for the Hospital Patient System.
We keep these in one place so we don't have to hardcode names, paths, or options in other files.
"""

import sys
import os
from pathlib import Path


if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent


DATA_DIR = Path(os.environ.get("HOSPITAL_DATA_DIR", str(BASE_DIR / "data"))).expanduser()
DATABASE_PATH = DATA_DIR / "hospital.db"


CURRENCY_SYMBOL = "₱"
CURRENCY_CODE = "PHP"


DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
TIME_FORMAT = "%H:%M"


DEPARTMENTS = [
    "Outpatient Department (OPD)",
    "Emergency Room (ER)",
    "Internal Medicine",
    "Pediatrics",
    "Obstetrics and Gynecology (OB-GYN)",
    "Surgery",
    "Cardiology",
    "Orthopedics",
    "Radiology",
    "Laboratory & Diagnostics"
]


VALID_SEX_OPTIONS = ["Male", "Female", "Other"]
VALID_PATIENT_STATUS = ["Active", "Archived"]
PATIENT_TYPES = ["Outpatient", "Inpatient", "Emergency"]


STAFF_ROLES = ["Administrator", "Doctor", "Nurse", "Receptionist", "Billing"]


SCHEDULED_DEPARTMENTS = [
    "Outpatient Department (OPD)",
    "Internal Medicine",
    "Pediatrics",
    "Obstetrics and Gynecology (OB-GYN)",
    "Surgery",
    "Cardiology",
    "Orthopedics",
    "Radiology",
    "Laboratory & Diagnostics"
]


VALID_APPOINTMENT_STATUS = ["Scheduled", "Checked-In", "Completed", "Cancelled", "Rescheduled", "No-Show"]


QUEUE_STATUSES = ["Waiting", "Triage", "Consultation", "Billing", "Completed", "Cancelled"]
VALID_QUEUE_TRANSITIONS = {
    "Waiting": ["Triage", "Consultation", "Cancelled"],
    "Triage": ["Consultation", "Waiting", "Cancelled"],
    "Consultation": ["Billing", "Completed", "Cancelled"],
    "Billing": ["Completed", "Cancelled"],
    "Completed": [],
    "Cancelled": []
}


TRIAGE_CATEGORIES = ["Emergency", "Urgent", "Non-Urgent"]


VITAL_LIMITS = {
    "temp_min": 30.0,
    "temp_max": 45.0,
    "temp_fever": 38.0,
    "temp_high_fever": 38.5,
    "temp_hypo": 35.5,
    "bp_sys_min": 50,
    "bp_sys_max": 260,
    "bp_sys_crisis": 180,
    "bp_sys_hypo": 90,
    "bp_dia_min": 30,
    "bp_dia_max": 160,
    "bp_dia_crisis": 120,
    "bp_dia_hypo": 60,
    "pulse_min": 30,
    "pulse_max": 220,
    "pulse_tachy": 100,
    "pulse_brady": 55,
    "resp_min": 6,
    "resp_max": 60,
    "resp_tachy": 24,
    "resp_brady": 10,
    "spo2_min": 50,
    "spo2_max": 100,
    "spo2_hypoxia": 92,
    "spo2_severe_hypoxia": 88
}


DISCOUNT_TYPES = [
    "None",
    "Senior Citizen (20%)",
    "PWD (20%)",
    "PhilHealth Benefit",
    "Charity / Social Service"
]


VALID_BILL_STATUS = ["Unpaid", "Partially Paid", "Paid", "Cancelled"]
VALID_PAYMENT_METHODS = [
    "Cash",
    "PhilHealth",
    "HMO / Health Card",
    "GCash",
    "Maya",
    "Credit Card",
    "Debit Card",
    "Bank Transfer"
]

