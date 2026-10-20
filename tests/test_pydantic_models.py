"""
Automated unit tests for Pydantic v2 schemas in utils/validators.py.
Verifies data type enforcement, boundaries, normalization, and staff-friendly error formatting.
"""

import unittest
from decimal import Decimal
from utils.schema import ValidationError

from utils.validators import (
    PatientCreateModel,
    PatientUpdateModel,
    AppointmentCreateModel,
    TriageCreateModel,
    VisitCreateModel,
    BillItemModel,
    BillCreateModel,
    PaymentCreateModel,
    StaffUserCreateModel,
    format_pydantic_error
)


class TestPydanticValidators(unittest.TestCase):
    """Test suite for structured Pydantic input models."""

    def test_patient_create_valid(self):
        """Test valid patient creation and normalization."""
        data = {
            "full_name": "  Maria   Santos  ",
            "dob": "1995-04-12",
            "sex": "female",
            "contact_number": "0917-123-4567",
            "address": "Pasig City, Metro Manila",
            "emergency_contact": "Pedro Santos 0918-111-2222",
            "patient_type": "Outpatient"
        }
        model = PatientCreateModel(**data)
        self.assertEqual(model.full_name, "Maria Santos")
        self.assertEqual(model.sex, "Female")
        self.assertEqual(model.dob, "1995-04-12")

    def test_patient_create_invalid_dob_future(self):
        """Test rejection of future birthdate."""
        data = {
            "full_name": "Juan Luna",
            "dob": "2099-01-01",
            "sex": "Male",
            "contact_number": "0917-123-4567",
            "address": "Manila",
            "emergency_contact": "Maria 0918-111-2222"
        }
        with self.assertRaises(ValidationError) as ctx:
            PatientCreateModel(**data)
        err_msg = format_pydantic_error(ctx.exception)
        self.assertIn("cannot be a future date", err_msg)

    def test_patient_create_invalid_phone(self):
        """Test rejection of invalid phone numbers."""
        data = {
            "full_name": "Juan Luna",
            "dob": "1990-01-01",
            "sex": "Male",
            "contact_number": "123",
            "address": "Manila",
            "emergency_contact": "Maria 0918-111-2222"
        }
        with self.assertRaises(ValidationError) as ctx:
            PatientCreateModel(**data)
        err_msg = format_pydantic_error(ctx.exception)
        self.assertTrue("Use a valid PH format" in err_msg or "must contain between 7 and 15 digits" in err_msg)

    def test_appointment_create_valid_and_invalid(self):
        """Test outpatient appointment scheduling validation."""
        valid_data = {
            "patient_id": "PAT-1001",
            "appointment_date": "2026-11-20",
            "appointment_time": "14:30",
            "department": "Internal Medicine",
            "reason": "Blood pressure consultation"
        }
        model = AppointmentCreateModel(**valid_data)
        self.assertEqual(model.department, "Internal Medicine")

        # Invalid department
        invalid_dept = valid_data.copy()
        invalid_dept["department"] = "Nonexistent Department"
        with self.assertRaises(ValidationError):
            AppointmentCreateModel(**invalid_dept)

        # Past date rejected
        past_date = valid_data.copy()
        past_date["appointment_date"] = "2020-01-01"
        with self.assertRaises(ValidationError) as ctx:
            AppointmentCreateModel(**past_date)
        self.assertIn("cannot be in the past", format_pydantic_error(ctx.exception))

    def test_triage_vital_signs_validation(self):
        """Test clinical vitals limits and systolic > diastolic invariant."""
        valid_triage = {
            "patient_id": "PAT-1001",
            "nurse_user": "nurse_joy",
            "chief_complaint": "Severe headache and dizziness",
            "allergies": "Penicillin",
            "temperature": 37.5,
            "bp_systolic": 130,
            "bp_diastolic": 85,
            "pulse_rate": 78,
            "respiratory_rate": 18,
            "oxygen_saturation": 98,
            "pain_score": 4,
            "triage_category": "Urgent"
        }
        model = TriageCreateModel(**valid_triage)
        self.assertEqual(model.pain_score, 4)

        # Systolic <= Diastolic rejected
        bad_bp = valid_triage.copy()
        bad_bp["bp_systolic"] = 80
        bad_bp["bp_diastolic"] = 90
        with self.assertRaises(ValidationError) as ctx:
            TriageCreateModel(**bad_bp)
        self.assertIn("Systolic BP must be strictly greater than Diastolic BP", format_pydantic_error(ctx.exception))

        # Abnormal temperature out of physiological range
        bad_temp = valid_triage.copy()
        bad_temp["temperature"] = 55.0
        with self.assertRaises(ValidationError):
            TriageCreateModel(**bad_temp)

    def test_billing_and_payment_models(self):
        """Test bill items, discounts, and payments Decimal constraints."""
        item1 = BillItemModel(service_description="Consultation", amount=Decimal("500.00"))
        self.assertEqual(item1.amount, Decimal("500.00"))

        # Negative amount rejected
        with self.assertRaises(ValidationError):
            BillItemModel(service_description="Negative Fee", amount=Decimal("-100.00"))

        # More than 2 decimal places rejected
        with self.assertRaises(ValidationError):
            BillItemModel(service_description="Invalid Decimals", amount=Decimal("12.345"))

        # Valid Bill
        bill = BillCreateModel(
            patient_id="PAT-1001",
            items=[item1],
            bill_date="2026-10-15",
            discount_type="Senior Citizen (20%)",
            discount_amount=Decimal("100.00")
        )
        self.assertEqual(len(bill.items), 1)

        # Valid Payment
        pmt = PaymentCreateModel(
            bill_id="BIL-1001",
            payment_date="2026-10-15",
            amount=Decimal("400.00"),
            payment_method="GCash"
        )
        self.assertEqual(pmt.payment_method, "GCash")

        # Invalid payment method
        with self.assertRaises(ValidationError):
            PaymentCreateModel(
                bill_id="BIL-1001",
                payment_date="2026-10-15",
                amount=Decimal("400.00"),
                payment_method="Bitcoin"
            )

    def test_staff_user_model(self):
        """Test staff user model validation and character restrictions."""
        user = StaffUserCreateModel(
            username="dr_reyes",
            password="securepassword123",
            full_name="Dr. Maria Reyes, MD",
            role="Doctor"
        )
        self.assertEqual(user.username, "dr_reyes")

        # Invalid username characters
        with self.assertRaises(ValidationError):
            StaffUserCreateModel(
                username="dr.reyes!",
                password="securepassword123",
                full_name="Dr. Maria Reyes, MD",
                role="Doctor"
            )

        # Invalid role
        with self.assertRaises(ValidationError):
            StaffUserCreateModel(
                username="fakeuser",
                password="securepassword123",
                full_name="Fake User",
                role="Superuser"
            )

    def test_visit_create_model_soap_validation(self):
        """Test clinical consultation SOAP documentation requirements."""
        valid_visit = {
            "patient_id": "PAT-1001",
            "visit_date": "2026-10-15 10:00",
            "department": "Internal Medicine",
            "attending_provider": "Dr. Jose Rizal, MD",
            "notes": "Full consultation record",
            "chief_complaint": "Recurrent episodic tension headaches",
            "clinical_findings": "Pupils equal and reactive, cranial nerves intact",
            "diagnosis": "Tension-type Headache",
            "treatment_plan": "Paracetamol 500mg PRN, sleep hygiene counseling"
        }
        visit = VisitCreateModel(**valid_visit)
        self.assertEqual(visit.attending_provider, "Dr. Jose Rizal, MD")

        # Incomplete documentation: missing chief complaint rejected
        bad_visit = valid_visit.copy()
        bad_visit["chief_complaint"] = ""
        with self.assertRaises(ValidationError):
            VisitCreateModel(**bad_visit)

        # Incomplete documentation: missing treatment plan rejected
        bad_visit2 = valid_visit.copy()
        bad_visit2["treatment_plan"] = ""
        with self.assertRaises(ValidationError):
            VisitCreateModel(**bad_visit2)
