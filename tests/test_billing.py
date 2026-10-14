"""
Automated unit tests for Billing and Payments (Philippine Edition).
Verifies Decimal monetary calculations, partial and full payments,
Philippine healthcare payment channels (PhilHealth, GCash, Maya, Cash),
balance tracking, overpayment rejection, and financial statistics.
"""

import unittest
from decimal import Decimal

from database import get_connection, create_schema
from modules.patients import register_patient
from modules.billing import (
    create_bill,
    get_bill_by_id,
    get_bill_items,
    get_payments_by_bill,
    record_payment
)
from modules.reports import get_financial_statistics


class TestBillingManagement(unittest.TestCase):
    """Test suite for hospital billing, itemization, payments, and balances."""

    def setUp(self):
        """Set up in-memory database with schema and a test patient."""
        self.conn = get_connection(":memory:")
        create_schema(self.conn)

        self.patient_id = register_patient(
            self.conn,
            full_name="Cardo Dalisay",
            dob="1980-05-20",
            sex="Male",
            contact_number="0917-555-8899",
            address="Brgy. Commonwealth, Quezon City",
            emergency_contact="Alyana Dalisay 0918-444-7766"
        )

    def tearDown(self):
        """Close database connection."""
        self.conn.close()

    def test_create_bill_with_multiple_items(self):
        """Verify bill creation calculates exact Decimal sum for itemized services."""
        items = [
            ("Doctor's Professional Fee (PF)", Decimal("800.00")),
            ("Complete Blood Count (CBC)", Decimal("350.50")),
            ("Chest X-Ray PA View", Decimal("650.25"))
        ]
        bill_id = create_bill(self.conn, self.patient_id, items, bill_date="2026-10-15")
        self.assertTrue(bill_id.startswith("BIL-"))

        bill = get_bill_by_id(self.conn, bill_id)
        self.assertIsNotNone(bill)
        self.assertEqual(Decimal(str(bill["total_amount"])), Decimal("1800.75"))
        self.assertEqual(Decimal(str(bill["paid_amount"])), Decimal("0.00"))
        self.assertEqual(Decimal(str(bill["balance"])), Decimal("1800.75"))
        self.assertEqual(bill["status"], "Unpaid")

        bill_items = get_bill_items(self.conn, bill_id)
        self.assertEqual(len(bill_items), 3)

    def test_partial_payment(self):
        """Verify partial payment updates paid amount, balance, and sets status to 'Partially Paid'."""
        items = [("Dental Prophylaxis", Decimal("1500.00"))]
        bill_id = create_bill(self.conn, self.patient_id, items)

        success, msg, pay_id = record_payment(
            self.conn, bill_id, Decimal("500.00"), "GCash", notes="GCash Ref: 1029384756"
        )
        self.assertTrue(success)
        self.assertIsNotNone(pay_id)
        self.assertTrue(pay_id.startswith("PAY-"))

        bill = get_bill_by_id(self.conn, bill_id)
        self.assertEqual(Decimal(str(bill["paid_amount"])), Decimal("500.00"))
        self.assertEqual(Decimal(str(bill["balance"])), Decimal("1000.00"))
        self.assertEqual(bill["status"], "Partially Paid")

        payments = get_payments_by_bill(self.conn, bill_id)
        self.assertEqual(len(payments), 1)
        self.assertEqual(Decimal(str(payments[0]["amount"])), Decimal("500.00"))

    def test_full_payment(self):
        """Verify full payment transitions bill to 'Paid' with zero balance."""
        items = [("Physical Therapy Session", Decimal("1200.00"))]
        bill_id = create_bill(self.conn, self.patient_id, items)

        # Pay initial amount with PhilHealth deduction
        record_payment(self.conn, bill_id, Decimal("600.00"), "PhilHealth", notes="Case rate benefit")
        # Pay remaining balance with Maya
        success, msg, _ = record_payment(self.conn, bill_id, Decimal("600.00"), "Maya", notes="Maya Wallet")
        self.assertTrue(success)

        bill = get_bill_by_id(self.conn, bill_id)
        self.assertEqual(Decimal(str(bill["paid_amount"])), Decimal("1200.00"))
        self.assertEqual(Decimal(str(bill["balance"])), Decimal("0.00"))
        self.assertEqual(bill["status"], "Paid")

        # Attempt additional payment when balance is 0 must fail
        over_pay_success, over_msg, _ = record_payment(self.conn, bill_id, Decimal("100.00"), "Cash")
        self.assertFalse(over_pay_success)
        self.assertIn("already fully paid", over_msg)

    def test_payment_exceeding_balance_calculates_change(self):
        """Verify payment exceeding outstanding balance succeeds, calculates change, and settles bill."""
        items = [("Vaccination", Decimal("1500.00"))]
        bill_id = create_bill(self.conn, self.patient_id, items)

        # Patient tenders ₱2000 for a ₱1500 bill -> Change is ₱500
        success, msg, pay_id = record_payment(self.conn, bill_id, Decimal("2000.00"), "Cash")
        self.assertTrue(success)
        self.assertIn("CHANGE: ₱500.00", msg)

        # Confirm bill is fully paid with 0 balance
        bill = get_bill_by_id(self.conn, bill_id)
        self.assertEqual(Decimal(str(bill["balance"])), Decimal("0.00"))
        self.assertEqual(Decimal(str(bill["paid_amount"])), Decimal("1500.00"))
        self.assertEqual(bill["status"], "Paid")

        # Verify payment transaction recorded amount_tendered and change
        payments = get_payments_by_bill(self.conn, bill_id)
        self.assertEqual(len(payments), 1)
        self.assertEqual(Decimal(str(payments[0]["amount"])), Decimal("1500.00"))
        self.assertEqual(Decimal(str(payments[0]["amount_tendered"])), Decimal("2000.00"))
        self.assertEqual(Decimal(str(payments[0]["change_amount"])), Decimal("500.00"))

    def test_payment_with_explicit_amount_tendered_and_change(self):
        """Verify payment with explicit amount_tendered records change properly."""
        items = [("Laboratory Analysis", Decimal("800.00"))]
        bill_id = create_bill(self.conn, self.patient_id, items)

        success, msg, pay_id = record_payment(
            self.conn,
            bill_id,
            amount=Decimal("800.00"),
            payment_method="Cash",
            amount_tendered=Decimal("1000.00")
        )
        self.assertTrue(success)
        self.assertIn("CHANGE: ₱200.00", msg)

        bill = get_bill_by_id(self.conn, bill_id)
        self.assertEqual(Decimal(str(bill["balance"])), Decimal("0.00"))
        self.assertEqual(Decimal(str(bill["paid_amount"])), Decimal("800.00"))
        self.assertEqual(bill["status"], "Paid")

    def test_reject_zero_and_negative_payment(self):
        """Verify zero and negative payments are rejected."""
        items = [("Consultation", Decimal("500.00"))]
        bill_id = create_bill(self.conn, self.patient_id, items)

        success_zero, _, _ = record_payment(self.conn, bill_id, Decimal("0.00"), "Cash")
        self.assertFalse(success_zero)

        success_neg, _, _ = record_payment(self.conn, bill_id, Decimal("-150.00"), "Cash")
        self.assertFalse(success_neg)

    def test_financial_statistics_reporting(self):
        """Verify financial statistics accurately aggregate multiple bills and payments."""
        # Bill 1: ₱1000 total, ₱1000 paid (Status: Paid)
        b1 = create_bill(self.conn, self.patient_id, [("Service A", Decimal("1000.00"))])
        record_payment(self.conn, b1, Decimal("1000.00"), "Cash")

        # Bill 2: ₱2000 total, ₱500 paid (Status: Partially Paid, ₱1500 balance)
        b2 = create_bill(self.conn, self.patient_id, [("Service B", Decimal("2000.00"))])
        record_payment(self.conn, b2, Decimal("500.00"), "PhilHealth")

        # Bill 3: ₱3000 total, ₱0 paid (Status: Unpaid, ₱3000 balance)
        create_bill(self.conn, self.patient_id, [("Service C", Decimal("3000.00"))])

        stats = get_financial_statistics(self.conn)
        self.assertEqual(stats["total_bills"], 3)
        self.assertEqual(stats["total_billed"], Decimal("6000.00"))
        self.assertEqual(stats["total_paid"], Decimal("1500.00"))
        self.assertEqual(stats["total_balance"], Decimal("4500.00"))
        self.assertEqual(stats["status_counts"]["Paid"], 1)
        self.assertEqual(stats["status_counts"]["Partially Paid"], 1)
        self.assertEqual(stats["status_counts"]["Unpaid"], 1)

    def test_senior_citizen_20_percent_discount(self):
        """Verify 20% Philippine statutory discount for Senior Citizens (RA 9994)."""
        items = [
            ("Consultation Fee", Decimal("1000.00")),
            ("Laboratory Blood Chemistry", Decimal("1000.00"))
        ]
        subtotal = Decimal("2000.00")
        discount_20 = (subtotal * Decimal("0.20")).quantize(Decimal("0.01"))
        self.assertEqual(discount_20, Decimal("400.00"))

        bill_id = create_bill(
            self.conn,
            self.patient_id,
            items,
            visit_id="VST-1001",
            discount_type="Senior Citizen (20%)",
            discount_amount=discount_20
        )
        bill = get_bill_by_id(self.conn, bill_id)
        self.assertIsNotNone(bill)
        self.assertEqual(Decimal(str(bill["total_amount"])), Decimal("1600.00"))
        self.assertEqual(Decimal(str(bill["balance"])), Decimal("1600.00"))
        self.assertEqual(bill["visit_id"], "VST-1001")
        self.assertEqual(bill["discount_type"], "Senior Citizen (20%)")

    def test_payment_issues_official_receipt_and_tracks_cashier(self):
        """Verify payment recording generates a sequential Official Receipt (OR) and tracks cashier."""
        items = [("Cardiology ECG", Decimal("500.00"))]
        bill_id = create_bill(self.conn, self.patient_id, items)

        ok, msg, pid = record_payment(
            self.conn,
            bill_id,
            Decimal("500.00"),
            payment_method="GCash",
            official_receipt_no="OR-2026-9999",
            cashier_user="Maria Cashier"
        )
        self.assertTrue(ok)
        self.assertIn("Official Receipt: OR-2026-9999", msg)

        cur = self.conn.cursor()
        cur.execute("SELECT * FROM payments WHERE payment_id = ?", (pid,))
        payment = cur.fetchone()
        self.assertEqual(payment["official_receipt_no"], "OR-2026-9999")
        self.assertEqual(payment["cashier_user"], "Maria Cashier")


if __name__ == "__main__":
    unittest.main()

