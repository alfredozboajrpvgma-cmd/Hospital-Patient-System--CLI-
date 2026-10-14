# Hospital Patient Management System (CLI)
## System Documentation & Presentation Guide

This guide explains how the system works, how the source code is organized, and how to run a live demonstration for your project presentation.

---

# Table of Contents
1. [Project Overview](#1-project-overview)
2. [System Structure & Database Design](#2-system-structure--database-design)
3. [Step-by-Step Code Walkthrough](#3-step-by-step-code-walkthrough)
4. [Presentation & Live Demo Guide](#4-presentation--live-demo-guide)
5. [Core Programming Concepts in Simple Terms](#5-core-programming-concepts-in-simple-terms)

---

## 1. Project Overview

### What is this system?
The **Hospital Patient Management System** is a terminal-based program built using Python 3 and SQLite. It handles the daily records of a hospital or clinic:
- Registering and updating patient profiles
- Booking and managing doctor appointments
- Recording clinical consultation notes
- Itemized billing and payments in Philippine Peso (PHP / ₱)
- Generating summary reports and stats

### Why did we make it?
Small clinics and health centers in the Philippines often use manual paper logbooks. Paper logbooks cause real everyday problems:
1. **Hard to search:** Finding an old patient folder takes minutes of flipping through pages.
2. **Double booking:** Two patients accidentally get scheduled with the same doctor at the same time.
3. **Calculation mistakes:** Adding up multiple service fees and subtracting partial payments by hand can lead to math errors and missing centavos.
4. **Accidental loss of records:** If a paper card gets damaged or thrown away, the patient's medical history is gone.

This CLI system solves those problems using an organized SQLite database, input validation, double-booking checks, and exact Decimal calculations for billing.

### Philippine Clinic Features
- **Currency:** All billing is in Philippine Peso (PHP / ₱).
- **Payment Methods:** Cash, PhilHealth benefits, GCash, Maya, HMO cards (Maxicare, Intellicare, etc.), Credit/Debit cards, and Bank Transfer.
- **Phone Numbers:** Validates Philippine mobile numbers (`0917-123-4567` or `+639181234567`) and landlines.
- **Departments:** OPD, Emergency Room, Pediatrics, Internal Medicine, Surgery, OB-GYN, Cardiology, etc.

### Tech Stack
- **Language:** Python 3 (standard library only)
- **Database:** SQLite 3 (built into Python via `sqlite3`)
- **Testing:** Python's built-in `unittest` module (27 automated tests)
- **Dependencies:** None! No `pip install` required.

---

## 2. System Structure & Database Design

### Project Folders and Files
```
Hospital Patient System (CLI)/
├── main.py                     # Starts the program and displays the main menu
├── database.py                 # Connects to SQLite and creates tables
├── config.py                   # Lists departments, payment options, and settings
├── requirements.txt            # Notes standard library dependencies
├── README.md                   # Quick overview and setup instructions
├── SYSTEM_DOCUMENTATION_AND_DEFENSE_GUIDE.md  # System documentation guide
├── data/
│   └── hospital.db             # SQLite database file (created on first run)
├── modules/
│   ├── patients.py             # Add, view, edit, search, and archive patients
│   ├── appointments.py         # Book, view, reschedule, and cancel appointments
│   ├── visits.py               # Doctor notes and consultation history
│   ├── billing.py              # Invoices, itemized charges, and payments
│   └── reports.py              # Patient counts, revenue totals, and dashboard
├── utils/
│   ├── display.py              # Formats clean tables, banners, and headers
│   └── validators.py           # Checks valid dates, times, phone numbers, and money
└── tests/
    ├── test_patients.py        # Automated tests for patient logic
    ├── test_appointments.py    # Automated tests for booking and conflict checks
    ├── test_billing.py         # Automated tests for invoice math and payments
    ├── test_visits.py          # Automated tests for visit records
    └── test_validators.py      # Automated tests for validation helpers
```

### Database Tables (SQLite)

The database uses 6 relational tables linked by foreign keys:

1. **`patients`**
   - Columns: `patient_id` (PK, e.g. `PAT-1001`), `full_name`, `dob`, `sex`, `contact_number`, `address`, `emergency_contact`, `registration_date`, `status` (`Active` or `Archived`).
   - Purpose: Holds basic profile information.

2. **`appointments`**
   - Columns: `appointment_id` (PK, e.g. `APT-1001`), `patient_id` (FK), `appointment_date`, `appointment_time`, `department`, `reason`, `status` (`Scheduled`, `Rescheduled`, `Completed`, `Cancelled`).
   - Purpose: Tracks upcoming and past doctor appointments.

3. **`visits`**
   - Columns: `visit_id` (PK, e.g. `VST-1001`), `patient_id` (FK), `visit_date`, `department`, `attending_provider`, `notes`.
   - Purpose: Stores consultation notes and medical observations.

4. **`bills`**
   - Columns: `bill_id` (PK, e.g. `BIL-1001`), `patient_id` (FK), `bill_date`, `total_amount`, `paid_amount`, `balance`, `status` (`Unpaid`, `Partially Paid`, `Paid`).
   - Purpose: Main invoice record with total amount and current balance.

5. **`bill_items`**
   - Columns: `item_id` (PK, autoincrement), `bill_id` (FK linked with CASCADE), `service_description`, `amount`.
   - Purpose: Line items on the bill (e.g. Doctor's PF, X-ray, Blood test).

6. **`payments`**
   - Columns: `payment_id` (PK, e.g. `PAY-1001`), `bill_id` (FK), `payment_date`, `amount`, `payment_method`, `notes`.
   - Purpose: Tracks each payment made toward a bill.

---

## 3. Step-by-Step Code Walkthrough

### How the Program Runs From Start to Finish

1. **Starting Up (`main.py` -> `init_db()`):**
   - When you type `py main.py`, the program calls `database.init_db()`.
   - It creates the `data/` folder if it doesn't exist yet.
   - It connects to `data/hospital.db` and runs `PRAGMA foreign_keys = ON;`.
   - It runs `CREATE TABLE IF NOT EXISTS` for all 6 tables. If tables already exist, it leaves your existing data untouched.
   - It sets `conn.row_factory = sqlite3.Row` so we can read query results by column name (like `row["full_name"]`).

2. **Main Menu Loop:**
   - Shows the 6 numbered choices (Patients, Appointments, Visits, Billing, Reports, Exit).
   - Asks for your choice and validates that it is a number between 1 and 6.

3. **Submenu Routing:**
   - If you press 1, it calls `patient_menu(conn)`.
   - If you press 2, it calls `appointment_menu(conn)`, and so on.
   - Each submenu has its own loop with options to add, view, update, or go back.

4. **Input Validation Loops (`while True:`):**
   - Whenever the user types data (like a date, phone number, or money amount), the code checks it using helper functions in `utils/validators.py`.
   - If the input is wrong, it prints a clean error message and asks again without crashing the program.
   - If the input is correct, it breaks out of the loop and continues.

5. **Saving to SQLite:**
   - Values are inserted into the database using parameterized queries (`?` placeholders) to prevent SQL injection.
   - `conn.commit()` saves changes to disk. If an error happens, `conn.rollback()` cancels the changes so data stays clean.

6. **Exiting:**
   - When you choose Exit, the program asks for confirmation and closes the SQLite database connection safely.

---

### Important Functions to Know

#### 1. Connecting to the Database (`database.py`)
```python
conn = sqlite3.connect(target_path, check_same_thread=False, timeout=10.0)
conn.execute("PRAGMA foreign_keys = ON;")
conn.row_factory = sqlite3.Row
```
- `PRAGMA foreign_keys = ON;` is essential because SQLite has foreign keys turned off by default. Turning it on ensures appointments and bills can only be created for patients that actually exist.
- `conn.row_factory = sqlite3.Row` lets us read query rows by name (e.g. `row["full_name"]`) instead of index numbers (like `row[1]`).

#### 2. Generating Sequential IDs (`modules/patients.py`)
```python
def generate_patient_id(conn):
    # Find the highest existing patient ID and add 1
    # Gives us clean IDs like PAT-1001, PAT-1002, PAT-1003
```
- It queries existing IDs, takes the number after the dash (`-`), finds the highest number, and adds 1.
- We use prefixes like `PAT-`, `APT-`, `VST-`, and `BIL-` so you can instantly tell what kind of record you are looking at.

#### 3. Preventing Double Booking (`modules/appointments.py`)
```python
def check_appointment_conflict(conn, appointment_date, appointment_time, department, patient_id):
```
- Checks two things before booking:
  1. Is the patient already scheduled for another consultation at this exact date and time?
  2. Is the selected department already booked by someone else at this exact date and time?
- If either condition is true, it stops and warns the user instead of double-booking.

#### 4. Handling Payments, Cash Tendered, and Change (`modules/billing.py`)
```python
def record_payment(conn, bill_id, amount, payment_method, notes="", amount_tendered=None):
```
- Checks that the payment/tendered amount is greater than 0.
- Supports cash payments that exceed the outstanding balance (Cash Tendered):
  - Automatically calculates exact change (`change = amount_tendered - current_balance`).
  - Caps the amount credited towards the bill to `current_balance`.
  - Prominently displays the change due (*Sukli*) in a Rich panel and prints it on the Official Receipt.
- Computes `new_balance = max(0, current_balance - applied_amount)` using Python's `Decimal` type to prevent floating-point rounding errors.
- Updates the bill's status:
  - If the new balance is 0, status transitions to `Paid`.
  - If a balance remains (partial payment), status becomes `Partially Paid`.
- Records `amount`, `amount_tendered`, and `change_amount` in `payments` and updates `bills` atomically within a single ACID transaction.

#### 5. Soft-Delete / Archiving (`modules/patients.py`)
```python
def archive_patient(conn, patient_id):
    # Sets status = 'Archived' instead of running DELETE FROM patients
```
- Instead of wiping the patient row from the database, it changes their status to `Archived`.
- This keeps their old consultation notes and past billing records intact for hospital records.

---

## 4. Presentation & Live Demo Guide

### Quick Presentation Outline (10-Minute Guide)

| Part | What to Cover | Time |
| :--- | :--- | :--- |
| **1. Intro** | Introduce yourself, project title, and what the system is for. | 1 min |
| **2. Problem** | Explain the common problems of manual paper logbooks in clinics. | 1.5 min |
| **3. Solution & Tech** | Explain why you chose Python 3, SQLite, and Philippine localization. | 1.5 min |
| **4. Live Demo** | Show the program running: add patient, book appointment, make a bill, pay. | 4 min |
| **5. Code Highlight** | Show 1 or 2 important functions (conflict checking and Decimal billing). | 1 min |
| **6. Wrap-up** | Short summary and conclusion. | 1 min |

---

### Step-by-Step Live Demo Script

Follow these steps during your live presentation so your demo goes smoothly:

1. **Start the program:**
   - Run `py main.py` in the terminal.
   - Point out that it connects to SQLite and displays the welcome banner and main menu.

2. **Register a new patient:**
   - Choose `1` (Patient Management), then `1` (Register New Patient).
   - Enter details:
     - Name: `Juan dela Cruz`
     - DOB: `1992-06-15`
     - Sex: `1` (Male)
     - Contact: `0917-123-4567`
     - Address: `Brgy. San Antonio, Pasig City`
     - Emergency Contact: `Maria dela Cruz 0918-765-4321`
   - Show that the system automatically assigns `PAT-1001`.

3. **Demonstrate input validation:**
   - Try entering an invalid phone number (like `123`) or a future birthday (`2099-01-01`).
   - Show how the program catches the error with a friendly message instead of crashing.

4. **Book an appointment & show conflict checking:**
   - Go to Main Menu -> `2` (Appointments) -> `1` (Schedule Appointment).
   - Book for `PAT-1001`, Date: `2026-11-20`, Time: `10:00`, Department: `1` (OPD).
   - System creates `APT-1001`.
   - Now try booking the exact same slot (`2026-11-20` at `10:00` for OPD).
   - Show the panel that the system detects the conflict and prevents double booking.

5. **Create a bill & make a payment:**
   - Go to Main Menu -> `4` (Billing) -> `1` (Generate Bill).
   - Add Item 1: `Consultation Fee`, `₱500.00`.
   - Add Item 2: `Complete Blood Count (CBC)`, `₱350.50`.
   - Press Enter to finish adding items. Total is `₱850.50`. Confirm to save (`BIL-1001`).
   - Choose `2` (Record Payment).
   - Select Bill `BIL-1001`. Pay `₱500.00` using GCash (Choice `4`).
   - Show that the bill updates to `Partially Paid` with a remaining balance of `₱350.50`.

6. **Show Executive Dashboard:**
   - Go to Main Menu -> `5` (Reports) -> `1` (Executive Dashboard).
   - Point out how all numbers (registered patients, scheduled appointments, total billed, total paid, balance) match your actions in real time.

---

## 5. Core Programming Concepts in Simple Terms

### 1. Modularity (Separation of Concerns)
* **Real-life analogy:** In a hospital, the receptionist, the doctor, the laboratory technician, and the cashier each have their own job in separate rooms.
* **In code:** Instead of one giant file, we have `patients.py` for patient records, `billing.py` for invoices, and `main.py` as the front desk directing you to the right menu.

### 2. Validation Loops (`while True:`)
* **Real-life analogy:** An ATM won't dispense cash until you enter a valid 4-digit PIN. If you enter letters or the wrong length, it immediately prompts you again.
* **In code:**
  ```python
  while True:
      choice = input("Enter choice: ")
      valid, num, err = validate_menu_choice(choice, 1, 6)
      if valid:
          break
      print(f"[ERROR] {err}")
  ```

### 3. Database Transactions (`commit` vs `rollback`)
* **Real-life analogy:** Sending money online: your account is deducted AND the recipient gets credited. If the bank's system goes down midway, your money is refunded.
* **In code:**
  ```python
  try:
      cursor.execute("INSERT INTO payments ...")
      cursor.execute("UPDATE bills SET balance = ...")
      conn.commit()  # Both succeeded!
  except Exception:
      conn.rollback()  # An error happened; cancel everything!
  ```

---

## Developer Credits
* **Developer:** Alfredo Jr. Z. Boa
* **Year Level:** 2nd Year Student
* **University:** Batangas State University - The National Engineering University (BatStateU - TNEU)

---

*Created exclusively for a school project in Westmead International School.*

