"""
Automated unit tests for validation utilities.
Verifies dates, times, phone numbers, sex inputs, monetary decimals, and menu choices.
"""

import unittest
from decimal import Decimal
from utils.validators import (
    validate_date,
    validate_time,
    validate_phone,
    validate_sex,
    validate_decimal_amount,
    validate_menu_choice,
    validate_non_empty
)


class TestValidators(unittest.TestCase):
    """Test suite for input validation functions."""

    def test_validate_date(self):
        """Test date validation with formats and boundary checks."""
        # Valid date
        valid, val = validate_date("2020-05-18", allow_future=True, allow_past=True)
        self.assertTrue(valid)
        self.assertEqual(val, "2020-05-18")

        # Leap year valid
        valid_leap, _ = validate_date("2024-02-29", allow_future=True, allow_past=True)
        self.assertTrue(valid_leap)

        # Leap year invalid
        invalid_leap, err = validate_date("2023-02-29", allow_future=True, allow_past=True)
        self.assertFalse(invalid_leap)
        self.assertIn("Invalid Date format", err)

        # Future date rejected when allow_future=False
        valid_fut, err_fut = validate_date("2099-01-01", allow_future=False, allow_past=True)
        self.assertFalse(valid_fut)
        self.assertIn("cannot be a future date", err_fut)

        # Past date rejected when allow_past=False
        valid_past, err_past = validate_date("1990-01-01", allow_future=True, allow_past=False)
        self.assertFalse(valid_past)
        self.assertIn("cannot be in the past", err_past)

    def test_validate_time(self):
        """Test 24-hour time validation."""
        valid, t = validate_time("09:45")
        self.assertTrue(valid)
        self.assertEqual(t, "09:45")

        valid_23, t_23 = validate_time("23:59")
        self.assertTrue(valid_23)

        invalid_hour, _ = validate_time("25:00")
        self.assertFalse(invalid_hour)

        invalid_minute, _ = validate_time("12:65")
        self.assertFalse(invalid_minute)

        invalid_str, _ = validate_time("not-a-time")
        self.assertFalse(invalid_str)

    def test_validate_phone(self):
        """Test contact number validation with Philippine and international formats."""
        # Philippine 11-digit mobile
        valid_ph1, phone1 = validate_phone("09171234567")
        self.assertTrue(valid_ph1)

        valid_ph2, phone2 = validate_phone("0917-123-4567")
        self.assertTrue(valid_ph2)

        # Philippine international format
        valid_intl, _ = validate_phone("+639171234567")
        self.assertTrue(valid_intl)

        valid_intl_space, _ = validate_phone("+63 917 123 4567")
        self.assertTrue(valid_intl_space)

        # Philippine Metro Manila landline
        valid_landline, _ = validate_phone("(02) 8123-4567")
        self.assertTrue(valid_landline)

        too_short, err = validate_phone("123")
        self.assertFalse(too_short)

        invalid_chars, _ = validate_phone("0917-ABC-1234")
        self.assertFalse(invalid_chars)

    def test_validate_sex(self):
        """Test normalization of patient sex choices."""
        valid_m, val_m = validate_sex("1")
        self.assertTrue(valid_m)
        self.assertEqual(val_m, "Male")

        valid_f, val_f = validate_sex("female")
        self.assertTrue(valid_f)
        self.assertEqual(val_f, "Female")

        valid_o, val_o = validate_sex("o")
        self.assertTrue(valid_o)
        self.assertEqual(val_o, "Other")

        invalid, _ = validate_sex("invalid_choice")
        self.assertFalse(invalid)

    def test_validate_decimal_amount(self):
        """Test monetary amount parsing and bounds with Philippine Peso symbols."""
        valid, val, _ = validate_decimal_amount("45.50")
        self.assertTrue(valid)
        self.assertEqual(val, Decimal("45.50"))

        # Strip Philippine Peso sign (₱) and commas
        valid_peso, val_peso, _ = validate_decimal_amount("₱1,250.75")
        self.assertTrue(valid_peso)
        self.assertEqual(val_peso, Decimal("1250.75"))

        # Strip 'PHP' prefix
        valid_php, val_php, _ = validate_decimal_amount("PHP 5,000.00")
        self.assertTrue(valid_php)
        self.assertEqual(val_php, Decimal("5000.00"))

        # Too many decimal places rejected
        invalid_places, _, err_p = validate_decimal_amount("12.345")
        self.assertFalse(invalid_places)
        self.assertIn("cannot have more than 2 decimal places", err_p)

        # Negative amount rejected
        invalid_neg, _, _ = validate_decimal_amount("-50.00")
        self.assertFalse(invalid_neg)

        # Non-numeric rejected
        invalid_str, _, _ = validate_decimal_amount("abc")
        self.assertFalse(invalid_str)

    def test_validate_menu_choice(self):
        """Test numbered menu selection."""
        valid, num, _ = validate_menu_choice("3", 1, 6)
        self.assertTrue(valid)
        self.assertEqual(num, 3)

        out_of_bounds, _, _ = validate_menu_choice("7", 1, 6)
        self.assertFalse(out_of_bounds)

        non_digit, _, _ = validate_menu_choice("abc", 1, 6)
        self.assertFalse(non_digit)


if __name__ == "__main__":
    unittest.main()
