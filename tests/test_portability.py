"""Regression tests for the package-free runtime and numeric edge cases."""

import io
import subprocess
import sys
import unittest
from decimal import Decimal
from unittest.mock import patch

from utils.plain_display import Console
from utils.schema import ValidationError
from utils.validators import BillCreateModel, BillItemModel, PaymentCreateModel, validate_decimal_amount


class TestPortability(unittest.TestCase):
    def test_nonfinite_money_is_rejected(self):
        for value in ("NaN", "sNaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                self.assertFalse(validate_decimal_amount(value)[0])
                with self.assertRaises(ValidationError):
                    BillItemModel(service_description="Consultation", amount=value)
                with self.assertRaises(ValidationError):
                    PaymentCreateModel(bill_id="BIL-1001", payment_date="2026-10-20",
                                       amount=value, payment_method="Cash")

    def test_nested_bill_items_and_required_list(self):
        bill = BillCreateModel(patient_id="PAT-1001", bill_date="2026-10-20",
                               items=[{"service_description": "Consultation", "amount": "50.00"}])
        self.assertEqual(bill.items[0].amount, Decimal("50.00"))
        self.assertEqual(bill.model_dump()["items"][0]["service_description"], "Consultation")
        with self.assertRaises(ValidationError):
            BillCreateModel(patient_id="PAT-1001", bill_date="2026-10-20", items=[])

    def test_phone_width_wraps_text(self):
        output = io.StringIO()
        with patch("utils.plain_display.shutil.get_terminal_size", return_value=(24, 40)):
            # Use a terminal-size object, matching shutil's public return type.
            import os
            with patch("utils.plain_display.shutil.get_terminal_size", return_value=os.terminal_size((24, 40))):
                Console(file=output).print("[bold cyan]" + "patient record " * 8 + "[/bold cyan]")
        self.assertNotIn("[bold", output.getvalue())
        self.assertTrue(all(len(line) <= 24 for line in output.getvalue().splitlines()))

    def test_package_free_entrypoint(self):
        result = subprocess.run([sys.executable, "-S", "main.py", "--help"],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("patients", result.stdout)

    def test_menu_eof_propagates_for_clean_shutdown(self):
        from utils.prompts import select_menu
        with patch("utils.prompts.is_interactive", return_value=False), patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(EOFError):
                select_menu("Test", ["Exit"])
