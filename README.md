# Hospital Patient System (CLI)

A terminal-based hospital information system written in Python and SQLite for managing outpatient visits, emergency intake, nursing triage, doctor consultations, and cashier billing. Built as a college project for Batangas State University (BatStateU - TNEU).

The application runs with Python's standard library only. Android users need **Pydroid 3**; no pip packages, Pydantic, or Pydantic Core are required. Numbered menus and wrapped text support basic terminals and phone consoles. Existing Rich and Questionary installations can optionally enhance the interface.

---

## What the System Does

The system models the typical flow of patients through a Philippine clinic or district hospital:

1. **Patient Registration & Records**: Keeps track of active and archived patients, addresses, emergency contacts, and contact numbers (supports Philippine mobile and landline formats).
2. **Emergency Room (ER) Fast-Track**: Acute cases (trauma, chest pain, stroke) bypass the regular appointment calendar and go straight to emergency clinical assessment and priority queueing.
3. **Outpatient Appointments & Daily Queue**: Receptionists can schedule upcoming appointments, check in arriving patients, and issue daily queue numbers (e.g., `#1`, `#2`, `#3`) for clinic routing.
4. **Nursing Triage**: Nurses screen patient vital signs (temperature, blood pressure, heart rate, respiratory rate, SpO2, and pain scale) and record allergies (e.g., Penicillin, NSAIDs, or NKDA) before the patient sees the doctor.
5. **Doctor Consultations (SOAP Notes)**: Physicians review triage records and document consultations using the standard SOAP clinical format:
   - **S**ubjective: Patient-stated chief complaint and history.
   - **O**bjective: Physical examination observations.
   - **A**ssessment: Diagnostic impression.
   - **P**lan: Treatment orders, prescriptions, or follow-up advice.
6. **Cashier Billing & Payments**: Generates itemized hospital bills in Philippine Pesos (`₱`), applies statutory discounts (Senior Citizen 20%, PWD 20%, PhilHealth case rates), accepts multiple payment channels (Cash, GCash, Maya, cards), calculates cash change (*sukli*), and issues Official Receipts (OR).
7. **System Audit Logs & Reports**: Records user actions (who logged in, registered a patient, entered vitals, or recorded payments) and generates revenue and departmental statistics.

---

## Default Login Credentials

The system uses Role-Based Access Control (RBAC) with salted password hashing (PBKDF2-HMAC-SHA256). When you first launch the app, these default accounts are created automatically:

| Role | Username | Password | Staff Member & Access Scope |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | **Engr. Hospital Administrator** — Full system access, staff account management, audit logs, and reports. |
| **Doctor** | `dr_smith` | `doc123` | **Dr. Jose Rizal, MD** — Consultations (SOAP notes), clinical history, triage reviews, and clinical statistics. |
| **Nurse** | `nurse_joy` | `nurse123` | **Nurse Joy, RN** — Nursing triage, vital signs entry, allergy screening, and patient lookups. |
| **Receptionist** | `reception` | `recep123` | **Maria Clara** — Patient registration, search, appointment booking, check-ins, and walk-in queue tickets. |
| **Billing Officer** | `cashier` | `cash123` | **Juan Luna** — Invoices, Senior/PWD discounts, PhilHealth deductions, cash payments & change, and receipts. |

---

## Philippine Healthcare Features

- **Currency**: Philippine Peso (`₱` / `PHP`) using Python's `Decimal` module to prevent rounding errors.
- **Cash Tendered & Change**: When patients pay in cash, the cashier can enter the amount handed over (e.g., ₱1,000 for a ₱350 bill), and the system calculates and displays the exact change (*sukli*).
- **Statutory Discounts**:
  - **Senior Citizen 20% Discount** (RA 9994) with Senior Citizen ID recording.
  - **PWD 20% Discount** (RA 10754) with PWD ID recording.
  - **PhilHealth Benefit** case rate deductions.
  - **Charity / Social Service** fee adjustments.
- **Payment Channels**: Cash, GCash, Maya, PhilHealth, HMO / Health Cards, Credit/Debit Cards, and Bank Transfer.
- **Phone Validation**: Accepts Philippine formats like `0917-123-4567`, `+639181234567`, and Metro Manila landlines `(02) 8123-4567`.

---

## Runtime and Compatibility

- Python 3.8+ with SQLite: Android (Pydroid 3), Windows, macOS, and Linux.
- Standard-library validation, `argparse` subcommands, and SQLite storage.
- Rich and Questionary are optional; the app works without them.
- Pydroid 3 is an Android app. iPhone/iPad require a separate Python environment with SQLite and console input; this version has not been tested on iOS.
- Physical Android device verification remains necessary; automated checks run on Windows without third-party packages.

## Project Structure

```
Hospital Patient System (CLI)/
├── main.py                     # Entry point (interactive menu or CLI command router)
├── cli.py                      # Standard-library argparse subcommands
├── database.py                 # SQLite schema, migrations, connection, and seed accounts
├── config.py                   # Constants, departments, vital sign ranges, and discount rates
├── requirements.txt            # Documents that no pip packages are required
├── README.md                   # Project documentation
├── SYSTEM_DOCUMENTATION_AND_DEFENSE_GUIDE.md # Defense notes and technical explanation
├── data/
│   └── hospital.db             # SQLite database file (created on first run)
├── modules/
│   ├── auth.py                 # User authentication, PBKDF2 hashing, and RBAC checks
│   ├── patients.py             # Patient registration, search, and soft-delete archival
│   ├── appointments.py         # Scheduling, conflict checks, and check-ins
│   ├── queue.py                # Daily queue ticket numbers and status transitions
│   ├── triage.py               # Vital signs entry, screening alert rules, and allergies
│   ├── visits.py               # Clinical consultations (SOAP format) and ER intake
│   ├── billing.py              # Invoices, Philippine discounts, payments, change, and receipts
│   ├── audit.py                # System audit trail logger
│   └── reports.py              # Operational and financial summary calculations
├── utils/
│   ├── display.py              # Rich tables, panels, cards, and dashboard
│   ├── prompts.py              # Questionary interactive inputs with fallback
│   └── validators.py           # Input schemas and validation rules
└── tests/
    ├── test_auth.py            # RBAC and session tests
    ├── test_patients.py        # Patient management and duplicate check tests
    ├── test_appointments.py    # Conflict detection and appointment tests
    ├── test_queue.py           # Queue generation and status update tests
    ├── test_triage.py          # Vital sign assessment tests
    ├── test_visits.py          # Clinical consultation tests
    ├── test_billing.py         # Billing, discounts, payments, and change tests
    ├── test_validators.py      # Procedural validator tests
    ├── test_pydantic_models.py # Input schema tests
    ├── test_rich_display.py    # Terminal rendering tests
    ├── test_cli_commands.py    # CLI command tests
    └── test_workflow_improvements.py # Comprehensive workflow integration tests
```

---

## Installation & How to Run

### Android / Pydroid 3

1. Copy or extract the **entire project folder** to a writable location on your device. Keep `modules/` and `utils/` beside `main.py`.
2. Open `main.py` in Pydroid 3 and press Run.
3. Enter menu numbers and press Enter. Log in using a demo account below.
4. No pip installation or compiler is needed. The database is created at `data/hospital.db` beside the project.

If Android denies storage access, move the project into a folder Pydroid can write to and grant its requested file access. Back up `data/hospital.db` before moving or updating the project. You may override the data directory using the `HOSPITAL_DATA_DIR` environment variable before launching Python.

### Desktop Requirements

Python 3.8 or newer with SQLite. No external packages are required.

### 2. Run the Interactive App
Launch the main menu:
```powershell
python main.py
# or on Windows:
py main.py
```
Log in using one of the demo credentials (e.g. `admin` / `admin123` or `dr_smith` / `doc123`). Use the **Arrow Keys** to navigate and **Enter** to select options.

### 3. Run CLI Subcommands (Optional)
You can also run quick administrative lookups directly from your terminal:
```powershell
# Show all available subcommands
py main.py --help

# List registered patients
py main.py patients list

# Search for a patient by name or ID
py main.py patients search "Juan"

# View patient details
py main.py patients view PAT-1001

# List upcoming appointments
py main.py appointments list

# View the real-time Executive Hospital Dashboard
py main.py reports dashboard

# View daily registration numbers
py main.py reports daily

# Initialize or verify the database tables
py main.py database initialize
```

---

## Running Automated Tests

All tests run against temporary in-memory databases (`:memory:`), so running tests will never modify or delete your actual records in `data/hospital.db`.

To run all 75 unit tests:
```powershell
python -m unittest discover tests
# or:
py -m unittest discover tests
```

Expected output:
```text
Ran 75 tests in ~13s

OK
```

---

## Author

* **Developer:** Alfredo Jr. Z. Boa
* **Year Level:** 2nd Year Student
* **Program:** Bachelor of Science in Information Technology
* **University:** Batangas State University - The National Engineering University (BatStateU - TNEU)

---

*Created exclusively for a school project in Westmead International School.*

