"""
Handles hospital bills, itemized charges, Philippine discounts (Senior, PWD, PhilHealth),
and payments (Cash with change/sukli, GCash, Maya).
"""

import sqlite3
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Tuple

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
    pause
)
from utils.validators import (
    validate_non_empty,
    validate_decimal_amount,
    validate_menu_choice
)
from config import (
    VALID_PAYMENT_METHODS,
    DATE_FORMAT,
    DATETIME_FORMAT,
    CURRENCY_SYMBOL,
    CURRENCY_CODE,
    DISCOUNT_TYPES
)
from modules.audit import log_audit_event
from modules.auth import get_current_session






def generate_bill_id(conn: sqlite3.Connection) -> str:
    """Generate the next bill ID like BIL-1001, BIL-1002."""
    cursor = conn.cursor()
    cursor.execute("SELECT bill_id FROM bills WHERE bill_id LIKE 'BIL-%' ORDER BY bill_id DESC")
    rows = cursor.fetchall()


    max_id_num = 1000
    for row in rows:
        bid = row["bill_id"]
        parts = bid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_id_num:
                max_id_num = val

    next_id_num = max_id_num + 1
    return f"BIL-{next_id_num}"


def generate_payment_id(conn: sqlite3.Connection) -> str:
    """Generate the next payment ID like PAY-1001, PAY-1002."""
    cursor = conn.cursor()
    cursor.execute("SELECT payment_id FROM payments WHERE payment_id LIKE 'PAY-%' ORDER BY payment_id DESC")
    rows = cursor.fetchall()


    max_id_num = 1000
    for row in rows:
        pid = row["payment_id"]
        parts = pid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_id_num:
                max_id_num = val

    next_id_num = max_id_num + 1
    return f"PAY-{next_id_num}"


def generate_official_receipt_no(conn: sqlite3.Connection) -> str:
    """Generate the next receipt number like OR-2026-1001."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM payments")
    cnt = cursor.fetchone()["count"]
    return f"OR-{date.today().year}-{1001 + cnt}"


def create_bill(
    conn: sqlite3.Connection,
    patient_id: str,
    items: List[Tuple[str, Decimal]],
    bill_date: Optional[str] = None,
    visit_id: Optional[str] = None,
    discount_type: str = "None",
    discount_amount: Decimal = Decimal("0.00"),
    cashier_user: Optional[str] = None
) -> str:
    """Save a new bill and its line items to the database."""
    if not items:
        raise ValueError("Cannot create a bill with zero items.")

    bill_id = generate_bill_id(conn)
    date_val = bill_date or date.today().strftime(DATE_FORMAT)


    subtotal = sum((amount for _, amount in items), Decimal("0.00"))
    total_amount = max(Decimal("0.00"), subtotal - discount_amount)
    subtotal_str = f"{subtotal:.2f}"
    discount_str = f"{discount_amount:.2f}"
    total_str = f"{total_amount:.2f}"
    paid_str = "0.00"
    balance_str = total_str
    status = "Unpaid"

    session = get_current_session()
    c_user = cashier_user or (session.full_name if session else "Cashier")

    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(bills)")
    cols = [r[1] for r in cursor.fetchall()]

    if "visit_id" in cols:
        cursor.execute("""
            INSERT INTO bills (
                bill_id, patient_id, bill_date, total_amount, paid_amount, balance, status,
                visit_id, subtotal, discount_type, discount_amount, cashier_user
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            bill_id, patient_id, date_val, total_str, paid_str, balance_str, status,
            visit_id, subtotal_str, discount_type, discount_str, c_user
        ))
    else:
        cursor.execute("""
            INSERT INTO bills (
                bill_id, patient_id, bill_date, total_amount, paid_amount, balance, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (bill_id, patient_id, date_val, total_str, paid_str, balance_str, status))


    for desc, amt in items:
        cursor.execute("""
            INSERT INTO bill_items (bill_id, service_description, amount)
            VALUES (?, ?, ?);
        """, (bill_id, desc, f"{amt:.2f}"))

    conn.commit()

    uid = session.user_id if session else "CASHIER"
    uname = session.username if session else c_user
    log_audit_event(conn, uid, uname, "BILL_CREATED", "Bill", bill_id, f"Patient {patient_id} - Total: {CURRENCY_SYMBOL}{total_str} (Disc: {discount_type})")

    return bill_id


def get_bill_by_id(conn: sqlite3.Connection, bill_id: str) -> Optional[sqlite3.Row]:
    """Find a bill and patient info by bill ID."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, p.full_name as patient_name, p.contact_number
        FROM bills b
        JOIN patients p ON b.patient_id = p.patient_id
        WHERE UPPER(b.bill_id) = UPPER(?)
    """, (bill_id.strip(),))
    return cursor.fetchone()


def get_bill_items(conn: sqlite3.Connection, bill_id: str) -> List[sqlite3.Row]:
    """Get all line items charged on a bill."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM bill_items WHERE UPPER(bill_id) = UPPER(?) ORDER BY item_id ASC
    """, (bill_id.strip(),))
    return cursor.fetchall()


def get_payments_by_bill(conn: sqlite3.Connection, bill_id: str) -> List[sqlite3.Row]:
    """Get all payments made for a bill."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM payments WHERE UPPER(bill_id) = UPPER(?) ORDER BY payment_date ASC
    """, (bill_id.strip(),))
    return cursor.fetchall()


def get_all_bills(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """Get every bill in the database, newest first."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, p.full_name as patient_name
        FROM bills b
        JOIN patients p ON b.patient_id = p.patient_id
        ORDER BY b.bill_date DESC, b.bill_id DESC
    """)
    return cursor.fetchall()


def get_outstanding_bills(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """Get all bills that still have an unpaid balance."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, p.full_name as patient_name
        FROM bills b
        JOIN patients p ON b.patient_id = p.patient_id
        WHERE b.status IN ('Unpaid', 'Partially Paid') AND CAST(b.balance AS REAL) > 0
        ORDER BY b.bill_date DESC
    """)
    return cursor.fetchall()


def get_bills_by_patient(conn: sqlite3.Connection, patient_id: str) -> List[sqlite3.Row]:
    """Get all bills belonging to a single patient."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, p.full_name as patient_name
        FROM bills b
        JOIN patients p ON b.patient_id = p.patient_id
        WHERE UPPER(b.patient_id) = UPPER(?)
        ORDER BY b.bill_date DESC
    """, (patient_id.strip(),))
    return cursor.fetchall()


def record_payment(
    conn: sqlite3.Connection,
    bill_id: str,
    amount: Decimal,
    payment_method: str,
    notes: str = "",
    payment_date: Optional[str] = None,
    official_receipt_no: Optional[str] = None,
    cashier_user: Optional[str] = None,
    amount_tendered: Optional[Decimal] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Record a payment against a bill, calculate balance and change (sukli),
    and update invoice status (Paid or Partially Paid).
    """
    if amount <= Decimal("0.00"):
        return False, "Payment amount must be greater than 0.", None

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bills WHERE UPPER(bill_id) = UPPER(?)", (bill_id.strip(),))
    bill = cursor.fetchone()

    if not bill:
        return False, f"Bill '{bill_id}' not found.", None

    current_balance = Decimal(str(bill["balance"]))
    current_paid = Decimal(str(bill["paid_amount"]))
    total_amount = Decimal(str(bill["total_amount"]))


    if bill["status"] == "Cancelled":
        return False, f"Bill '{bill_id}' has been cancelled. Payments cannot be accepted.", None

    if current_balance <= Decimal("0.00"):
        return False, f"Bill '{bill_id}' is already fully paid.", None


    if amount_tendered is not None:
        tendered = amount_tendered
        applied = min(amount, current_balance)
        change = max(Decimal("0.00"), tendered - applied)
    else:

        if amount > current_balance:
            tendered = amount
            applied = current_balance
            change = amount - current_balance
        else:
            tendered = amount
            applied = amount
            change = Decimal("0.00")


    new_paid = current_paid + applied
    new_balance = max(Decimal("0.00"), current_balance - applied)


    if new_balance == Decimal("0.00"):
        new_status = "Paid"
    else:
        new_status = "Partially Paid"

    payment_id = generate_payment_id(conn)
    pay_date = payment_date or datetime.now().strftime(DATETIME_FORMAT)
    or_no = official_receipt_no or generate_official_receipt_no(conn)

    session = get_current_session()
    c_user = cashier_user or (session.full_name if session else "Cashier")


    full_notes = notes.strip() if notes else ""
    if change > Decimal("0.00"):
        change_note = f"Tendered: {CURRENCY_SYMBOL}{tendered:.2f} | Change: {CURRENCY_SYMBOL}{change:.2f}"
        if change_note not in full_notes:
            full_notes = f"{full_notes} [{change_note}]".strip() if full_notes else change_note

    try:

        cursor.execute("""
            SELECT payment_id FROM payments
            WHERE UPPER(bill_id) = UPPER(?) AND amount = ? AND payment_method = ? AND payment_date = ?
        """, (bill["bill_id"], f"{applied:.2f}", payment_method, pay_date))
        dup = cursor.fetchone()
        if dup:
            return False, f"Duplicate payment detected: Payment '{dup['payment_id']}' for {CURRENCY_SYMBOL}{applied:.2f} via {payment_method} was already recorded on {pay_date}.", None

        cursor.execute("PRAGMA table_info(payments)")
        cols = [r[1] for r in cursor.fetchall()]

        fields = ["payment_id", "bill_id", "payment_date", "amount", "payment_method", "notes"]
        vals = [payment_id, bill["bill_id"], pay_date, f"{applied:.2f}", payment_method, full_notes]

        if "official_receipt_no" in cols:
            fields.append("official_receipt_no")
            vals.append(or_no)
        if "cashier_user" in cols:
            fields.append("cashier_user")
            vals.append(c_user)
        if "amount_tendered" in cols:
            fields.append("amount_tendered")
            vals.append(f"{tendered:.2f}")
        if "change_amount" in cols:
            fields.append("change_amount")
            vals.append(f"{change:.2f}")

        placeholders = ", ".join(["?"] * len(fields))
        col_names = ", ".join(fields)
        cursor.execute(f"INSERT INTO payments ({col_names}) VALUES ({placeholders});", tuple(vals))

        cursor.execute("""
            UPDATE bills
            SET paid_amount = ?, balance = ?, status = ?
            WHERE bill_id = ?;
        """, (f"{new_paid:.2f}", f"{new_balance:.2f}", new_status, bill["bill_id"]))

        conn.commit()

        uid = session.user_id if session else "CASHIER"
        uname = session.username if session else c_user
        log_audit_event(
            conn, uid, uname, "PAYMENT_RECORDED", "Payment", payment_id,
            f"Applied: {CURRENCY_SYMBOL}{applied:.2f} (Tendered: {CURRENCY_SYMBOL}{tendered:.2f}, Change: {CURRENCY_SYMBOL}{change:.2f}) via {payment_method} (OR: {or_no}) for Bill {bill['bill_id']}"
        )

        if change > Decimal("0.00"):
            msg = (
                f"Payment of {CURRENCY_SYMBOL}{applied:.2f} recorded successfully via {payment_method}! "
                f"(Tendered: {CURRENCY_SYMBOL}{tendered:.2f} | CHANGE: {CURRENCY_SYMBOL}{change:.2f}) "
                f"(Official Receipt: {or_no}) Remaining balance: {CURRENCY_SYMBOL}{new_balance:.2f}"
            )
        else:
            msg = (
                f"Payment of {CURRENCY_SYMBOL}{applied:.2f} recorded successfully via {payment_method}! "
                f"(Official Receipt: {or_no}) Remaining balance: {CURRENCY_SYMBOL}{new_balance:.2f}"
            )

        if new_status == "Paid":
            try:
                from modules.queue import close_patient_active_queue_ticket
                close_patient_active_queue_ticket(conn, bill["patient_id"], new_status="Completed")
            except Exception:
                pass

        return True, msg, payment_id
    except Exception as exc:
        conn.rollback()
        return False, f"Failed to record payment: {exc}", None


def cancel_bill(conn: sqlite3.Connection, bill_id: str, reason: str = "") -> Tuple[bool, str]:
    """Cancel an unpaid bill. Only allowed if nothing has been paid yet."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bills WHERE UPPER(bill_id) = UPPER(?)", (bill_id.strip(),))
    bill = cursor.fetchone()
    if not bill:
        return False, f"Bill '{bill_id}' not found."

    if bill["status"] == "Cancelled":
        return False, f"Bill '{bill_id}' is already cancelled."

    paid = Decimal(str(bill["paid_amount"]))
    if paid > Decimal("0.00"):
        return False, f"Cannot cancel Bill '{bill_id}' because payments totaling {CURRENCY_SYMBOL}{paid:.2f} have already been collected."

    cursor.execute("""
        UPDATE bills
        SET status = 'Cancelled', balance = '0.00', cancellation_reason = ?
        WHERE bill_id = ?;
    """, (reason or "Cancelled by Billing Officer", bill["bill_id"]))
    conn.commit()

    session = get_current_session()
    uid = session.user_id if session else "BILLING"
    uname = session.username if session else "billing"
    log_audit_event(conn, uid, uname, "BILL_CANCELLED", "Bill", bill["bill_id"], f"Cancelled invoice: {reason}")
    return True, f"Bill '{bill['bill_id']}' has been marked as Cancelled."


def select_bill_interactive(
    conn: sqlite3.Connection,
    prompt_text: str = "Enter Bill ID (or '?' for list, '0' to cancel): ",
    only_outstanding: bool = False
) -> Optional[sqlite3.Row]:
    """Helper to pick a bill by ID or browse a list."""
    while True:
        b_input = input(prompt_text).strip()
        if not b_input or b_input.lower() in ("0", "q", "cancel", "back"):
            return None

        if b_input in ("?", "list"):
            bills = get_outstanding_bills(conn) if only_outstanding else get_all_bills(conn)
            if not bills:
                empty_msg = "No outstanding unpaid bills found." if only_outstanding else "No bills found in database."
                print_info(empty_msg)
                continue
            headers = ["Bill ID", "Patient ID", "Patient Name", "Date", f"Total ({CURRENCY_CODE})", f"Paid ({CURRENCY_CODE})", f"Balance ({CURRENCY_CODE})", "Status"]
            alignments = ["left", "left", "left", "left", "right", "right", "right", "left"]
            rows = [
                [
                    b["bill_id"],
                    b["patient_id"],
                    b["patient_name"],
                    b["bill_date"],
                    f"{Decimal(str(b['total_amount'])):.2f}",
                    f"{Decimal(str(b['paid_amount'])):.2f}",
                    f"{Decimal(str(b['balance'])):.2f}",
                    b["status"]
                ]
                for b in bills
            ]
            print_table(headers, rows, alignments=alignments)
            continue

        bill = get_bill_by_id(conn, b_input)
        if bill:
            return bill

        if b_input.isdigit():
            bill = get_bill_by_id(conn, f"BIL-{b_input}")
            if bill:
                return bill

        print_error(f"Bill '{b_input}' not found. Type '?' to see bills or '0' to cancel.")






def handle_generate_bill(
    conn: sqlite3.Connection,
    preselected_patient_id: Optional[str] = None,
    visit_id: Optional[str] = None
) -> Optional[str]:
    """Create a new hospital bill with items, discounts, and optional visit link."""
    from modules.patients import get_patient_by_id, select_patient_interactive

    print_subheader("Generate New Hospital Bill")
    try:
        if preselected_patient_id:
            patient = get_patient_by_id(conn, preselected_patient_id)
        else:
            patient = select_patient_interactive(
                conn,
                prompt_text="Enter Patient ID or Name to bill (or '?' for list): "
            )

        if not patient:
            print_warning("Billing cancelled.")
            pause()
            return None

        print_info(f"Generating bill for: {patient['full_name']} ({patient['patient_id']})")
        if visit_id:
            print_info(f"Linked Clinical Visit: {visit_id}")

        print("\nEnter service items one by one. Enter empty description when finished.\n")

        items: List[Tuple[str, Decimal]] = []


        while True:
            item_num = len(items) + 1
            desc_input = input(f"Item #{item_num} Description (or press Enter to finish): ").strip()
            if not desc_input:
                if items:
                    break
                else:
                    print_warning("Bill creation cancelled (no items added).")
                    pause()
                    return None

            valid_desc, desc = validate_non_empty(desc_input, f"Item #{item_num} Description", min_length=2)
            if not valid_desc:
                print_error(desc)
                continue


            while True:
                charge_input = input(f"Item #{item_num} Amount ({CURRENCY_SYMBOL}): ").strip()
                valid_amt, amt_decimal, err = validate_decimal_amount(charge_input, field_name=f"Charge for '{desc}'")
                if valid_amt and amt_decimal is not None:
                    items.append((desc, amt_decimal))
                    print_info(f"Added: {desc} -> {CURRENCY_SYMBOL}{amt_decimal:.2f}")
                    break
                print_error(err)

        subtotal = sum((amt for _, amt in items), Decimal("0.00"))


        from utils.prompts import select_option, confirm_prompt
        from utils.display import render_card
        from utils.validators import BillCreateModel, BillItemModel, format_pydantic_error
        from utils.schema import ValidationError

        chosen_discount = select_option("Select Philippine Statutory Discount / Benefit:", DISCOUNT_TYPES) or "None"

        discount_amount = Decimal("0.00")
        if chosen_discount in ("Senior Citizen (20%)", "PWD (20%)"):
            id_no = input(f"Enter {chosen_discount.split()[0]} Identification Card Number: ").strip() or "VERIFIED"
            discount_amount = (subtotal * Decimal("0.20")).quantize(Decimal("0.01"))
            print_info(f"Applied 20% statutory discount: -{CURRENCY_SYMBOL}{discount_amount:.2f} (ID Card: {id_no})")
        elif chosen_discount == "PhilHealth Benefit":
            ph_str = input("Enter PhilHealth Case Rate deduction amount (₱): ").strip()
            v_ph, ph_val, _ = validate_decimal_amount(ph_str, max_val=subtotal)
            if v_ph and ph_val:
                discount_amount = ph_val
        elif chosen_discount == "Charity / Social Service":
            ch_str = input("Enter Social Service / Charity adjustment (₱): ").strip()
            v_ch, ch_val, _ = validate_decimal_amount(ch_str, max_val=subtotal)
            if v_ch and ch_val:
                discount_amount = ch_val

        final_total = max(Decimal("0.00"), subtotal - discount_amount)


        try:
            bill_items_models = [BillItemModel(service_description=d, amount=a) for d, a in items]
            bill_model = BillCreateModel(
                patient_id=patient["patient_id"],
                items=bill_items_models,
                bill_date=date.today().strftime(DATE_FORMAT),
                visit_id=visit_id,
                discount_type=chosen_discount,
                discount_amount=discount_amount
            )
        except ValidationError as exc:
            print_error(format_pydantic_error(exc))
            pause()
            return None


        render_card("HOSPITAL INVOICE SUMMARY", {
            "Patient": f"{patient['full_name']} ({patient['patient_id']})",
            "Visit Ref": visit_id or "Outpatient (Direct)",
            "Total Itemized Services": len(items),
            "Gross Subtotal": f"{CURRENCY_SYMBOL}{subtotal:,.2f}",
            "Statutory Adjustment": f"{chosen_discount} (-{CURRENCY_SYMBOL}{discount_amount:,.2f})" if discount_amount > 0 else "None",
            "Net Payable": f"{CURRENCY_SYMBOL}{final_total:,.2f}"
        })

        if confirm_prompt("Confirm and generate hospital bill?", default=True):
            bill_id = create_bill(
                conn=conn,
                patient_id=bill_model.patient_id,
                items=items,
                visit_id=visit_id,
                discount_type=bill_model.discount_type,
                discount_amount=bill_model.discount_amount
            )
            print_success(f"Bill created successfully! Assigned Bill ID: {bill_id}")
            pause()
            return bill_id
        else:
            print_info("Bill generation cancelled.")

    except (KeyboardInterrupt, EOFError):
        print("\nOperation cancelled by user.")
    pause()
    return None


def handle_record_payment(conn: sqlite3.Connection) -> None:
    """Record a payment, pick payment channel, and compute change if overpaid."""
    print_subheader("Record Bill Payment & Dispense Change")
    try:
        bill = select_bill_interactive(
            conn,
            prompt_text="Enter Bill ID to record payment (or '?' for unpaid bills): ",
            only_outstanding=True
        )
        if not bill:
            print_warning("Payment cancelled.")
            pause()
            return

        cur_balance = Decimal(str(bill["balance"]))
        if cur_balance <= Decimal("0.00"):
            print_warning(f"Bill {bill['bill_id']} is already PAID IN FULL. No payment needed.")
            pause()
            return


        print_info(f"Bill: {bill['bill_id']} | Patient: {bill['patient_name']}")
        print(f"  Total Amount:        {CURRENCY_SYMBOL}{Decimal(str(bill['total_amount'])):.2f}")
        print(f"  Already Paid:        {CURRENCY_SYMBOL}{Decimal(str(bill['paid_amount'])):.2f}")
        print(f"  Outstanding Balance: {CURRENCY_SYMBOL}{cur_balance:.2f}")


        while True:
            amt_input = input(f"\nEnter payment / amount tendered [PHP] (Balance Due: {CURRENCY_SYMBOL}{cur_balance:.2f}): ").strip()
            if not amt_input:
                print_warning("Payment cancelled.")
                pause()
                return

            valid, tendered_amount, err = validate_decimal_amount(
                amt_input, min_val=Decimal("0.01"), field_name="Payment / tendered amount"
            )
            if valid and tendered_amount is not None:
                break
            print_error(err)


        if tendered_amount >= cur_balance:
            pay_amount = cur_balance
            change_due = (tendered_amount - cur_balance).quantize(Decimal("0.01"))
        else:
            pay_amount = tendered_amount
            change_due = Decimal("0.00")

        if change_due > Decimal("0.00"):
            print_success(f"Amount tendered exceeds balance! Change to return (Sukli): {CURRENCY_SYMBOL}{change_due:,.2f}")


        from utils.prompts import select_option, confirm_prompt
        from utils.display import render_card
        from utils.validators import PaymentCreateModel, format_pydantic_error
        from utils.schema import ValidationError

        payment_method = select_option("Select Payment Channel (PH Healthcare & E-Wallets):", VALID_PAYMENT_METHODS)
        if not payment_method:
            print_warning("Payment cancelled.")
            pause()
            return

        notes = input("Enter optional transaction notes / reference number: ").strip() or None


        try:
            pay_model = PaymentCreateModel(
                bill_id=bill["bill_id"],
                payment_date=date.today().strftime(DATE_FORMAT),
                amount=pay_amount,
                amount_tendered=tendered_amount,
                change_amount=change_due,
                payment_method=payment_method,
                notes=notes
            )
        except ValidationError as exc:
            print_error(format_pydantic_error(exc))
            pause()
            return


        card_info = {
            "Bill Reference": pay_model.bill_id,
            "Patient Name": bill["patient_name"],
            "Outstanding Balance": f"{CURRENCY_SYMBOL}{cur_balance:,.2f}",
            "Amount Tendered": f"{CURRENCY_SYMBOL}{tendered_amount:,.2f}",
            "Amount Applied to Bill": f"{CURRENCY_SYMBOL}{pay_model.amount:,.2f}",
            "CHANGE DUE (Sukli)": f"{CURRENCY_SYMBOL}{change_due:,.2f}",
            "Payment Channel": pay_model.payment_method,
            "Projected Remaining Balance": f"{CURRENCY_SYMBOL}{max(Decimal('0.00'), cur_balance - pay_model.amount):,.2f}"
        }
        if pay_model.notes:
            card_info["Reference Notes"] = pay_model.notes

        render_card("PAYMENT COLLECTION & CHANGE SUMMARY", card_info)


        confirm_label = (
            f"Confirm recording payment of {CURRENCY_SYMBOL}{pay_model.amount:.2f} "
            f"(Tendered: {CURRENCY_SYMBOL}{tendered_amount:.2f} | Change: {CURRENCY_SYMBOL}{change_due:.2f}) "
            f"via {pay_model.payment_method}?"
        )
        if confirm_prompt(confirm_label, default=True):
            success, msg, pay_id = record_payment(
                conn,
                pay_model.bill_id,
                pay_model.amount,
                pay_model.payment_method,
                pay_model.notes or "",
                amount_tendered=tendered_amount
            )
            if success:
                print_success(f"{msg} (Payment ID: {pay_id})")
                if change_due > Decimal("0.00"):
                    render_notice(
                        "CASH CHANGE DISPENSED",
                        [f"CHANGE TO RETURN TO PATIENT (SUKLI): {CURRENCY_SYMBOL}{change_due:,.2f}"],
                        border_style="green",
                    )
            else:
                print_error(msg)
        else:
            print_info("Payment cancelled.")

    except (KeyboardInterrupt, EOFError):
        print("\nPayment cancelled by user.")
    pause()


def handle_view_all_bills(conn: sqlite3.Connection) -> None:
    """Show all hospital bills in a table."""
    print_subheader("All Hospital Bills")
    bills = get_all_bills(conn)

    headers = ["Bill ID", "Patient ID", "Patient Name", "Date", f"Total ({CURRENCY_CODE})", f"Paid ({CURRENCY_CODE})", f"Balance ({CURRENCY_CODE})", "Status"]
    alignments = ["left", "left", "left", "left", "right", "right", "right", "left"]
    rows = [
        [
            b["bill_id"],
            b["patient_id"],
            b["patient_name"],
            b["bill_date"],
            f"{Decimal(str(b['total_amount'])):.2f}",
            f"{Decimal(str(b['paid_amount'])):.2f}",
            f"{Decimal(str(b['balance'])):.2f}",
            b["status"]
        ]
        for b in bills
    ]
    print_table(headers, rows, alignments=alignments, empty_message="No bills found in the database.")
    pause()


def handle_view_outstanding_bills(conn: sqlite3.Connection) -> None:
    """Show only bills that still have an unpaid balance."""
    print_subheader("Outstanding Hospital Bills")
    bills = get_outstanding_bills(conn)

    headers = ["Bill ID", "Patient ID", "Patient Name", "Date", f"Total ({CURRENCY_CODE})", f"Paid ({CURRENCY_CODE})", f"Balance ({CURRENCY_CODE})", "Status"]
    alignments = ["left", "left", "left", "left", "right", "right", "right", "left"]
    rows = [
        [
            b["bill_id"],
            b["patient_id"],
            b["patient_name"],
            b["bill_date"],
            f"{Decimal(str(b['total_amount'])):.2f}",
            f"{Decimal(str(b['paid_amount'])):.2f}",
            f"{Decimal(str(b['balance'])):.2f}",
            b["status"]
        ]
        for b in bills
    ]
    print_table(headers, rows, alignments=alignments, empty_message="No outstanding bills! All invoices are fully paid.")
    pause()


def handle_view_bill_details(conn: sqlite3.Connection) -> None:
    """Print an itemized invoice with service items and payments."""
    print_subheader("Bill Invoice Details")
    bill = select_bill_interactive(
        conn,
        prompt_text="Enter Bill ID to view invoice details (or '?' for list): "
    )
    if not bill:
        print_info("Operation cancelled.")
        pause()
        return

    items = get_bill_items(conn, bill["bill_id"])
    payments = get_payments_by_bill(conn, bill["bill_id"])

    render_card(f"HOSPITAL INVOICE: {bill['bill_id']}", {
        "Patient": f"{bill['patient_name']} ({bill['patient_id']})",
        "Contact": bill["contact_number"],
        "Invoice Date": bill["bill_date"],
        "Status": bill["status"],
    })

    service_lines = []
    for idx, item in enumerate(items, 1):
        amt = Decimal(str(item["amount"]))
        service_lines.append(f"{idx}. {item['service_description']}  —  {CURRENCY_SYMBOL}{amt:,.2f}")
    if not service_lines:
        service_lines.append("No service items on this invoice.")
    service_lines.extend([
        "",
        f"TOTAL AMOUNT:         {CURRENCY_SYMBOL}{Decimal(str(bill['total_amount'])):,.2f}",
        f"PAID AMOUNT:          {CURRENCY_SYMBOL}{Decimal(str(bill['paid_amount'])):,.2f}",
        f"OUTSTANDING BALANCE:  {CURRENCY_SYMBOL}{Decimal(str(bill['balance'])):,.2f}",
    ])
    render_notice("ITEMIZED SERVICES", service_lines, border_style="cyan")


    if payments:
        payment_lines = []
        for p in payments:
            amt = Decimal(str(p["amount"]))
            note_str = f" ({p['notes']})" if p["notes"] else ""
            tendered_str = ""
            p_keys = p.keys() if hasattr(p, "keys") else []
            if "amount_tendered" in p_keys and p["amount_tendered"]:
                t_amt = Decimal(str(p["amount_tendered"]))
                c_amt = Decimal(str(p["change_amount"])) if ("change_amount" in p_keys and p["change_amount"]) else Decimal("0.00")
                if c_amt > Decimal("0.00"):
                    tendered_str = f" [Tendered: {CURRENCY_SYMBOL}{t_amt:.2f} | Change: {CURRENCY_SYMBOL}{c_amt:.2f}]"
            payment_lines.append(
                f"{p['payment_date']} | {p['payment_id']} | {p['payment_method']} | "
                f"{CURRENCY_SYMBOL}{amt:.2f}{tendered_str}{note_str}"
            )
        render_notice("PAYMENT TRANSACTIONS", payment_lines, border_style="green")
    else:
        render_notice("PAYMENT TRANSACTIONS", ["No payments recorded for this bill."], border_style="dim")
    pause()


def handle_view_patient_billing(conn: sqlite3.Connection) -> None:
    """Show all bills belonging to one specific patient."""
    from modules.patients import select_patient_interactive

    print_subheader("Patient Billing History")
    patient = select_patient_interactive(
        conn,
        prompt_text="Enter Patient ID or Name to view billing (or '?' for list): "
    )
    if not patient:
        print_info("Operation cancelled.")
        pause()
        return

    bills = get_bills_by_patient(conn, patient["patient_id"])
    print_info(f"Billing records for: {patient['full_name']} ({patient['patient_id']})")

    headers = ["Bill ID", "Date", f"Total ({CURRENCY_CODE})", f"Paid ({CURRENCY_CODE})", f"Balance ({CURRENCY_CODE})", "Status"]
    alignments = ["left", "left", "right", "right", "right", "left"]
    rows = [
        [
            b["bill_id"],
            b["bill_date"],
            f"{Decimal(str(b['total_amount'])):.2f}",
            f"{Decimal(str(b['paid_amount'])):.2f}",
            f"{Decimal(str(b['balance'])):.2f}",
            b["status"]
        ]
        for b in bills
    ]
    print_table(headers, rows, alignments=alignments, empty_message=f"No bills on record for {patient['patient_id']}.")
    pause()


def handle_cancel_bill(conn: sqlite3.Connection) -> None:
    """Cancel an unpaid bill."""
    from utils.prompts import confirm_prompt
    print_subheader("Cancel Unpaid Hospital Bill")
    bill = select_bill_interactive(
        conn,
        prompt_text="Enter Bill ID to cancel (or '?' for unpaid bills): ",
        only_outstanding=True
    )
    if not bill:
        print_info("Operation cancelled.")
        pause()
        return

    paid = Decimal(str(bill["paid_amount"]))
    if paid > Decimal("0.00"):
        print_error(f"Cannot cancel Bill {bill['bill_id']}: Payments totaling {CURRENCY_SYMBOL}{paid:.2f} have already been collected.")
        pause()
        return

    print_info(f"Target Bill: {bill['bill_id']} | Patient: {bill['patient_name']} | Balance: {CURRENCY_SYMBOL}{Decimal(str(bill['balance'])):.2f}")
    reason = input("Enter official reason for cancellation: ").strip() or "Voided by Billing Officer"

    if confirm_prompt(f"Confirm cancellation of Bill {bill['bill_id']} for {bill['patient_name']}?", default=False):
        ok, msg = cancel_bill(conn, bill["bill_id"], reason)
        if ok:
            print_success(msg)
        else:
            print_error(msg)
    else:
        print_info("Cancellation aborted.")
    pause()


def billing_menu(conn: sqlite3.Connection) -> None:
    """Submenu for handling bills and payments."""
    from utils.prompts import select_menu

    choices = [
        "1. Generate New Hospital Bill",
        "2. Record Payment for Bill",
        "3. View All Bills",
        "4. View Outstanding Bills",
        "5. View Bill Invoice Details",
        "6. View Patient Billing History",
        "7. Cancel Unpaid Bill Invoice",
        "8. Return to Main Menu"
    ]

    while True:
        print_subheader("Billing & Payment Menu")
        choice = select_menu("Select Billing & Payment Option:", choices)
        if not choice or "Return to Main Menu" in choice:
            break

        if choice.startswith("1."):
            handle_generate_bill(conn)
        elif choice.startswith("2."):
            handle_record_payment(conn)
        elif choice.startswith("3."):
            handle_view_all_bills(conn)
        elif choice.startswith("4."):
            handle_view_outstanding_bills(conn)
        elif choice.startswith("5."):
            handle_view_bill_details(conn)
        elif choice.startswith("6."):
            handle_view_patient_billing(conn)
        elif choice.startswith("7."):
            handle_cancel_bill(conn)

