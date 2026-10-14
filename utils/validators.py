"""
Input validation functions and Pydantic models.
Makes sure dates, phone numbers, vitals, and billing amounts are valid before saving.
"""

from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import re
from typing import Tuple, Optional, List, Any, Dict

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ValidationError
)

from config import (
    DATE_FORMAT,
    DATETIME_FORMAT,
    TIME_FORMAT,
    VALID_SEX_OPTIONS,
    PATIENT_TYPES,
    VALID_PATIENT_STATUS,
    DEPARTMENTS,
    VALID_APPOINTMENT_STATUS,
    TRIAGE_CATEGORIES,
    VITAL_LIMITS,
    DISCOUNT_TYPES,
    VALID_PAYMENT_METHODS,
    STAFF_ROLES
)


# ==========================================
# Simple Validation Functions
# ==========================================

def validate_non_empty(
    text: str, field_name: str = "Field", min_length: int = 1, max_length: int = 255
) -> Tuple[bool, str]:
    """Make sure text is not blank and within character limits."""
    if not text or not str(text).strip():
        return False, f"{field_name} cannot be empty."

    cleaned = str(text).strip()
    if len(cleaned) < min_length:
        return False, f"{field_name} must be at least {min_length} characters."
    if len(cleaned) > max_length:
        return False, f"{field_name} must not exceed {max_length} characters."

    return True, cleaned


def validate_date(
    date_str: str,
    allow_future: bool = True,
    allow_past: bool = True,
    field_name: str = "Date"
) -> Tuple[bool, str]:
    """
    Check if a date is in YYYY-MM-DD format and is a real calendar date.
    Also checks whether future or past dates are allowed for this specific field.
    """
    if not date_str or not str(date_str).strip():
        return False, f"{field_name} cannot be empty."

    cleaned = str(date_str).strip()
    try:
        parsed_date = datetime.strptime(cleaned, DATE_FORMAT).date()
    except ValueError:
        return False, f"Invalid {field_name} format. Expected YYYY-MM-DD (e.g., 2024-05-18)."

    today = date.today()
    if not allow_future and parsed_date > today:
        return False, f"{field_name} cannot be a future date."
    if not allow_past and parsed_date < today:
        return False, f"{field_name} cannot be in the past."

    return True, parsed_date.strftime(DATE_FORMAT)


def validate_time(time_str: str, field_name: str = "Time") -> Tuple[bool, str]:
    """Check if time is valid in 24-hour HH:MM format."""
    if not time_str or not str(time_str).strip():
        return False, f"{field_name} cannot be empty."

    cleaned = str(time_str).strip()
    try:
        parsed_time = datetime.strptime(cleaned, TIME_FORMAT).time()
        return True, parsed_time.strftime(TIME_FORMAT)
    except ValueError:
        return False, f"Invalid {field_name} format. Expected HH:MM in 24-hour format (e.g., 09:30 or 14:15)."


def validate_phone(phone_str: str, field_name: str = "Contact number") -> Tuple[bool, str]:
    """Check if phone number is valid (supports Philippine mobile 09xx, +639xx, and landlines)."""
    if not phone_str or not str(phone_str).strip():
        return False, f"{field_name} cannot be empty."

    cleaned = str(phone_str).strip()
    if not re.match(r"^(\+)?[0-9\s\-()]{7,25}$", cleaned):
        return False, f"Invalid {field_name}. Use a valid PH format (e.g., 09171234567, +639171234567, or (02) 8123-4567)."

    digits_only = re.sub(r"\D", "", cleaned)
    if len(digits_only) < 7 or len(digits_only) > 15:
        return False, f"{field_name} must contain between 7 and 15 digits."

    return True, cleaned


def validate_sex(sex_str: str) -> Tuple[bool, str]:
    """Convert user input into Male, Female, or Other."""
    if not sex_str or not str(sex_str).strip():
        return False, "Sex cannot be empty. Please select Male, Female, or Other."

    cleaned = str(sex_str).strip().lower()
    mapping = {
        "1": "Male",
        "m": "Male",
        "male": "Male",
        "2": "Female",
        "f": "Female",
        "female": "Female",
        "3": "Other",
        "o": "Other",
        "other": "Other"
    }

    if cleaned in mapping:
        return True, mapping[cleaned]

    return False, "Invalid selection. Please choose Male, Female, or Other."


def validate_decimal_amount(
    amount_str: str,
    min_val: Decimal = Decimal("0.01"),
    max_val: Decimal = Decimal("10000000.00"),
    field_name: str = "Amount"
) -> Tuple[bool, Optional[Decimal], str]:
    """Turn a money string into a Decimal number, supporting '₱' and 'PHP'."""
    if not amount_str or not str(amount_str).strip():
        return False, None, f"{field_name} cannot be empty."

    cleaned = (
        str(amount_str).strip()
        .replace("₱", "")
        .replace("PHP", "")
        .replace("Php", "")
        .replace("php", "")
        .replace("$", "")
        .replace(",", "")
        .strip()
    )
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return False, None, f"Invalid {field_name}. Please enter a valid number (e.g., 500.00 or 1250.50)."

    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        return False, None, f"{field_name} cannot have more than 2 decimal places."

    if amount < min_val:
        return False, None, f"{field_name} must be at least {min_val:.2f}."
    if amount > max_val:
        return False, None, f"{field_name} cannot exceed {max_val:.2f}."

    amount = amount.quantize(Decimal("0.01"))
    return True, amount, f"{amount:.2f}"


def validate_menu_choice(choice_str: str, min_choice: int, max_choice: int) -> Tuple[bool, Optional[int], str]:
    """Check if the user picked a valid number from the menu options."""
    if not choice_str or not str(choice_str).strip():
        return False, None, "Input cannot be empty. Please enter a valid menu number."

    cleaned = str(choice_str).strip()
    if not cleaned.isdigit():
        return False, None, f"Invalid input '{cleaned}'. Please enter a number between {min_choice} and {max_choice}."

    val = int(cleaned)
    if val < min_choice or val > max_choice:
        return False, None, f"Choice must be between {min_choice} and {max_choice}."

    return True, val, ""


# ==========================================
# Pydantic Error Formatter
# ==========================================

def format_pydantic_error(exc: ValidationError) -> str:
    """Turn validation error messages into clean, readable bullet points."""
    lines = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err["loc"])
        msg = err["msg"]
        # Clean up error text
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        lines.append(f"• {field.title()}: {msg}")
    return "\n".join(lines)


# ==========================================
# Pydantic Validation Models
# ==========================================

class PatientCreateModel(BaseModel):
    """Validation schema for registering a new patient."""
    full_name: str = Field(..., min_length=2, max_length=150, description="Full Name of patient")
    dob: str = Field(..., description="Date of birth in YYYY-MM-DD format")
    sex: str = Field(..., description="Biological sex (Male, Female, Other)")
    contact_number: str = Field(..., description="Contact phone number")
    address: str = Field(..., min_length=3, max_length=255, description="Residential address")
    emergency_contact: str = Field(..., min_length=3, max_length=150, description="Emergency contact details")
    patient_type: str = Field(default="Outpatient", description="Patient classification")

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        cleaned = " ".join(v.strip().split())
        if len(cleaned) < 2:
            raise ValueError("Full Name must have at least 2 characters.")
        return cleaned

    @field_validator("dob")
    @classmethod
    def check_dob(cls, v: str) -> str:
        valid, res = validate_date(v, allow_future=False, allow_past=True, field_name="Date of birth")
        if not valid:
            raise ValueError(res)
        return res

    @field_validator("sex")
    @classmethod
    def normalize_sex(cls, v: str) -> str:
        valid, res = validate_sex(v)
        if not valid:
            raise ValueError(res)
        return res

    @field_validator("contact_number")
    @classmethod
    def check_phone(cls, v: str) -> str:
        valid, res = validate_phone(v, field_name="Contact number")
        if not valid:
            raise ValueError(res)
        return res

    @field_validator("address", "emergency_contact")
    @classmethod
    def clean_text(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 3:
            raise ValueError("Field must be at least 3 characters.")
        return cleaned

    @field_validator("patient_type")
    @classmethod
    def check_type(cls, v: str) -> str:
        if v not in PATIENT_TYPES:
            raise ValueError(f"Invalid patient type. Must be one of: {', '.join(PATIENT_TYPES)}")
        return v


class PatientUpdateModel(BaseModel):
    """Validation schema for updating existing patient details."""
    full_name: Optional[str] = Field(default=None, max_length=150)
    dob: Optional[str] = Field(default=None)
    sex: Optional[str] = Field(default=None)
    contact_number: Optional[str] = Field(default=None, max_length=25)
    address: Optional[str] = Field(default=None, max_length=255)
    emergency_contact: Optional[str] = Field(default=None, max_length=150)
    patient_type: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)

    @field_validator("dob")
    @classmethod
    def check_dob(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid, res = validate_date(v, allow_future=False, allow_past=True, field_name="Date of birth")
            if not valid:
                raise ValueError(res)
            return res
        return v

    @field_validator("sex")
    @classmethod
    def check_sex(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid, res = validate_sex(v)
            if not valid:
                raise ValueError(res)
            return res
        return v

    @field_validator("contact_number")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid, res = validate_phone(v, field_name="Contact number")
            if not valid:
                raise ValueError(res)
            return res
        return v

    @field_validator("status")
    @classmethod
    def check_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_PATIENT_STATUS:
            raise ValueError(f"Status must be one of: {', '.join(VALID_PATIENT_STATUS)}")
        return v


class AppointmentCreateModel(BaseModel):
    """Validation schema for booking an outpatient appointment."""
    patient_id: str = Field(..., min_length=4, max_length=20)
    appointment_date: str = Field(..., description="Date of appointment (YYYY-MM-DD)")
    appointment_time: str = Field(..., description="Time of appointment in HH:MM format")
    department: str = Field(...)
    reason: str = Field(..., min_length=2, max_length=255)
    status: str = Field(default="Scheduled")

    @field_validator("appointment_date")
    @classmethod
    def check_date(cls, v: str) -> str:
        valid, res = validate_date(v, allow_future=True, allow_past=False, field_name="Appointment date")
        if not valid:
            raise ValueError(res)
        return res

    @field_validator("appointment_time")
    @classmethod
    def check_time(cls, v: str) -> str:
        valid, res = validate_time(v, field_name="Appointment time")
        if not valid:
            raise ValueError(res)
        return res

    @field_validator("department")
    @classmethod
    def check_dept(cls, v: str) -> str:
        if v not in DEPARTMENTS:
            raise ValueError(f"Invalid department. Must be one of configured hospital departments.")
        return v

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str) -> str:
        if v not in VALID_APPOINTMENT_STATUS:
            raise ValueError(f"Status must be one of: {', '.join(VALID_APPOINTMENT_STATUS)}")
        return v


class TriageCreateModel(BaseModel):
    """Validation schema for recording nursing triage vital signs."""
    patient_id: str = Field(...)
    ticket_id: Optional[str] = Field(default=None)
    nurse_user: str = Field(..., min_length=2, max_length=100)
    chief_complaint: str = Field(..., min_length=2, max_length=500)
    allergies: str = Field(default="No Known Drug Allergies (NKDA)", max_length=255)
    temperature: float = Field(..., ge=30.0, le=45.0, description="Body temperature in Celsius")
    bp_systolic: int = Field(..., ge=50, le=260, description="Systolic blood pressure mmHg")
    bp_diastolic: int = Field(..., ge=30, le=160, description="Diastolic blood pressure mmHg")
    pulse_rate: int = Field(..., ge=30, le=220, description="Heart / pulse rate bpm")
    respiratory_rate: int = Field(..., ge=6, le=60, description="Respiratory rate breaths/min")
    oxygen_saturation: int = Field(..., ge=50, le=100, description="SpO2 percentage")
    pain_score: int = Field(default=0, ge=0, le=10, description="Pain rating scale (0-10)")
    triage_category: str = Field(default="Non-Urgent")

    @model_validator(mode="after")
    def check_bp_relationship(self) -> "TriageCreateModel":
        if self.bp_systolic <= self.bp_diastolic:
            raise ValueError("Systolic BP must be strictly greater than Diastolic BP.")
        return self

    @field_validator("triage_category")
    @classmethod
    def check_cat(cls, v: str) -> str:
        if v not in TRIAGE_CATEGORIES:
            raise ValueError(f"Triage category must be one of: {', '.join(TRIAGE_CATEGORIES)}")
        return v


class VisitCreateModel(BaseModel):
    """Validation schema for doctor consultation visits (SOAP format)."""
    patient_id: str = Field(...)
    visit_date: str = Field(...)
    department: str = Field(...)
    attending_provider: str = Field(..., min_length=2, max_length=150)
    notes: str = Field(..., min_length=2, max_length=2000)
    triage_id: Optional[str] = Field(default=None)
    chief_complaint: str = Field(..., min_length=2, max_length=500, description="Patient's stated chief complaint")
    clinical_findings: str = Field(..., min_length=2, max_length=2000, description="Objective findings or confirmed absence of abnormalities")
    diagnosis: str = Field(..., min_length=2, max_length=500, description="Clinician's diagnostic assessment")
    treatment_plan: str = Field(..., min_length=2, max_length=2000, description="Documented management plan and orders")
    visit_status: str = Field(default="Completed")

    @field_validator("department")
    @classmethod
    def check_dept(cls, v: str) -> str:
        if v not in DEPARTMENTS:
            raise ValueError("Invalid department.")
        return v


class BillItemModel(BaseModel):
    """Validation schema for an itemized service charge on a hospital bill."""
    service_description: str = Field(..., min_length=2, max_length=200)
    amount: Decimal = Field(..., gt=Decimal("0.00"), le=Decimal("10000000.00"))

    @field_validator("amount")
    @classmethod
    def check_decimal_places(cls, v: Decimal) -> Decimal:
        exp = v.as_tuple().exponent
        if isinstance(exp, int) and exp < -2:
            raise ValueError("Amount cannot have more than 2 decimal places.")
        return v.quantize(Decimal("0.01"))


class BillCreateModel(BaseModel):
    """Validation schema for generating an itemized bill."""
    patient_id: str = Field(...)
    items: List[BillItemModel] = Field(..., min_length=1)
    bill_date: str = Field(...)
    visit_id: Optional[str] = Field(default=None)
    discount_type: str = Field(default="None")
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    cashier_user: Optional[str] = Field(default=None)

    @field_validator("discount_type")
    @classmethod
    def check_discount(cls, v: str) -> str:
        if v not in DISCOUNT_TYPES:
            raise ValueError(f"Discount must be one of: {', '.join(DISCOUNT_TYPES)}")
        return v


class PaymentCreateModel(BaseModel):
    """Validation schema for recording payments and change."""
    bill_id: str = Field(...)
    payment_date: str = Field(...)
    amount: Decimal = Field(..., gt=Decimal("0.00"), le=Decimal("10000000.00"), description="Amount applied to bill")
    payment_method: str = Field(...)
    notes: Optional[str] = Field(default=None, max_length=255)
    official_receipt_no: Optional[str] = Field(default=None)
    cashier_user: Optional[str] = Field(default=None)
    amount_tendered: Optional[Decimal] = Field(default=None, gt=Decimal("0.00"), le=Decimal("10000000.00"))
    change_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))

    @field_validator("payment_method")
    @classmethod
    def check_method(cls, v: str) -> str:
        if v not in VALID_PAYMENT_METHODS:
            raise ValueError(f"Payment method must be one of: {', '.join(VALID_PAYMENT_METHODS)}")
        return v

    @field_validator("amount", "amount_tendered", "change_amount", mode="before")
    @classmethod
    def check_amount(cls, v: Any) -> Any:
        if v is None:
            return None
        dec = Decimal(str(v))
        exp = dec.as_tuple().exponent
        if isinstance(exp, int) and exp < -2:
            raise ValueError("Monetary amount cannot have more than 2 decimal places.")
        return dec.quantize(Decimal("0.01"))


class StaffUserCreateModel(BaseModel):
    """Validation schema for registering hospital staff accounts."""
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=6, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=100)
    role: str = Field(...)

    @field_validator("username")
    @classmethod
    def clean_username(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not re.match(r"^[a-z0-9_]+$", cleaned):
            raise ValueError("Username must contain only lowercase letters, numbers, and underscores.")
        return cleaned

    @field_validator("role")
    @classmethod
    def check_role(cls, v: str) -> str:
        if v not in STAFF_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(STAFF_ROLES)}")
        return v
