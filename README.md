# Hospital Patient System Beginner Guide


This guide is for group members who are still learning Python. It explains how to install the system, use every main feature, understand the files and database, and prepare for a project demonstration. Technical terms are explained before they are used. File names and menu labels match the program so you can find them easily.

The guide covers Pydroid setup, patient workflows, billing examples, staff accounts, reports, code structure, database tables, troubleshooting, and presentation practice. Use fictional patient information for school demonstrations. Clinical alerts and discounts describe this project's behavior; they do not establish that the application is ready for real hospital use.

Documentation date: 20 October 2026. Branch: `alfredo/pydroid-compatibility`. Functional code baseline: `97b7662`. This documentation update also removes Python source comments without changing the program's instructions. The README and Word document contain the same main information. Both are available in the `docs-pydroid-v1` documentation release on GitHub.

## How to use this guide

Start with Sections 1 to 3 to install and open the application. Use Sections 4 to 9 while practicing workflows. Sections 10 to 12 explain the code and troubleshooting. The final sections provide presentation practice and the complete reference.

- 1 Understanding the system
- 2 Installing the application
- 3 Logging in and using menus
- 4 Patient registration and records
- 5 Appointments check in and the daily queue
- 6 Nursing triage and vital signs
- 7 Consultations and emergency intake
- 8 Bills discounts payments and receipts
- 9 Reports audit logs and staff accounts
- 10 How the source code works
- 11 Programming terms explained simply
- 12 Backups troubleshooting and limitations
- 13 Demonstration and presentation practice
- 14 Final submission checklist
- 15 Database reference
- 16 Menu and status reference
- 17 Sources and version information

## 1 Understanding the system

The Hospital Patient System is a CLI application. CLI means Command Line Interface: you type answers in a terminal instead of using a website. The Rich library displays colored tables, panels, and status labels.

Think of the application as a clinic's digital logbook. It stores patient profiles, appointments, arrival tickets, nursing assessments, consultations, bills, payments, and reports. Records connect through IDs, so the patient's full profile does not have to be copied into every transaction.

Python runs the instructions. SQLite stores records in a local file named `data/hospital.db`. Rich formats the display. Custom validation code checks inputs before the normal workflows save them. Pydantic and Pydantic Core are not required.

### The usual patient workflow

1. Reception registers a patient or finds an existing profile.
2. Reception schedules an appointment or issues a walk-in ticket.
3. When an appointment patient arrives, staff check in the appointment and issue a queue ticket.
4. The nurse records the assessment and vital signs.
5. The doctor records the consultation and SOAP notes.
6. Billing creates an itemized bill and records payment.
7. Staff review reports and the activity history.

Emergency Room intake provides a separate path without an ordinary appointment. The screens available to you depend on the staff role used at login.

### What is included and what is outside the scope

The system includes patient records, outpatient appointments, a daily queue, triage, consultations, Philippine Peso billing, staff accounts, audit logs, and reports. Inpatient is currently a patient classification. There is no complete ward, bed assignment, or admission management module.

This is a local application. It does not include cloud synchronization, a shared online database, SMS reminders, online payment processing, or automatic PhilHealth verification. Selecting GCash or a card records the payment method; it does not charge an external account.

## 2 Installing the application

### Android with Pydroid 3

1. Download the source ZIP for the `alfredo/pydroid-compatibility` branch from GitHub and extract it. The source ZIP and the documentation attachments are separate downloads.
2. Keep the complete project folder. It must contain `main.py`, `database.py`, `config.py`, `cli.py`, `requirements.txt`, `modules/`, and `utils/`. Downloading only main.py will not work.
3. Place the project in a folder Pydroid can read and write. Grant the requested access to that folder when Android asks.
4. In the Pydroid Pip screen, install `rich==13.9.4`. You can also use the terminal commands below from the project folder.
5. Open main.py and run it. Use Pydroid's terminal mode if its editor output panel does not display colors correctly.
6. Log in with a demo account, enter the displayed menu number, and press Enter.

```sh
pip install -r requirements.txt
python main.py
```

An internet connection is needed for the first package installation. Normal record operations run locally afterward. The project does not need Pydantic, Pydantic Core, a separate database server, or a compiler for its dependencies.

### Windows macOS and Linux

Use Python 3.8 or later with SQLite support. Open a terminal in the project folder and run these commands. On Windows, you can use `py` instead of `python` if that is the available launcher.

```sh
python -m pip install -r requirements.txt
python main.py
```

Pydroid 3 is an Android application. On an iPhone or iPad, a different Python environment with SQLite and console input is needed. The iOS runtime has not been verified. Windows automated checks have been completed, but actual Android device testing is still needed before claiming that every device is supported.

### Colors and small screens

Wide terminals display normal tables with several columns. On narrow screens, Rich displays each record in a bordered Field/Value table so all fields remain readable. The information stays the same; only its arrangement changes.

Colors are detected automatically. If the Pydroid terminal does not show them, you can create a small launcher file in the same project folder:

```python
import os
os.environ["HOSPITAL_COLOR"] = "always"
from main import main
main()
```

Set `HOSPITAL_COLOR=never` for monochrome output. If Rich is missing, the application uses a plain-text fallback. Install Rich for the full colored interface. Questionary is optional and enables arrow-key menus; numbered menus work without it.

## 3 Logging in and using menus

A new database receives demo staff accounts on its first startup. Use these for practice. These passwords are public demo credentials and should not be treated as protection for real patient information.

| Role | Username | Demo password |
| --- | --- | --- |
| Administrator | admin | admin123 |
| Doctor | dr_smith | doc123 |
| Nurse | nurse_joy | nurse123 |
| Receptionist | reception | recep123 |
| Billing | cashier | cash123 |

### Responsibilities of each role

The Administrator has the full main menu and staff management. The Receptionist usually registers patients, schedules appointments, and manages arrivals. The Nurse records triage and vital signs. The Doctor records consultations and reviews medical history. Billing creates bills, records payments, and reviews financial reports.

The code includes a role permissions map and role-specific menus. However, not every shared screen or low-level function checks permissions separately. CLI lookup commands also run without an interactive login. Describe this accurately as role-based menu access with current limitations, rather than complete security on every access path.

### Menu controls

Read the option label as well as its number. Menu numbers differ between roles. At a numbered prompt, enter the displayed number and press Enter. A menu often accepts `0` or an empty answer to cancel, but follow the current prompt because cancellation is not identical in every field.

Patient lookup accepts a patient ID, part of a name, or `list` to browse. `PAT-1001` is only an example; use the actual ID created in your database. Review previews before answering Yes or `y` to save.

Switch User / Logout returns to the login screen. Exit System closes the application after confirmation. When the screen says Press Enter to continue, press Enter to return to the next screen.

## 4 Patient registration and records

### Registering a patient

1. Log in as Administrator or Receptionist.
2. Open Patient Management or Patient Registration and choose Register New Patient.
3. Enter the full name, birthdate, sex, contact number, address, emergency contact, and patient type.
4. Read any validation messages. A future birthdate is rejected, and `123` is not a valid contact number.
5. Review the summary, confirm the save, and note the generated patient ID.

A fictional practice profile can use Demo Patient One, birthdate 1995-04-12, Female, contact 09171234567, address Demo Address, and emergency contact Demo Guardian 09181234567. These numbers are sample inputs and should not be called.

Registration warns about a possible duplicate using the name, birthdate, and contact number. This does not prove that two matching names belong to the same person. The user must review the profile before continuing.

### Searching viewing editing and archiving

Search finds patients by ID or part of a name. View Details shows the profile. Update changes entered fields after checks. In the update form, pressing Enter without a new value normally keeps the current value; read the prompt before proceeding.

Archive changes Active to Archived while preserving consultation and billing history. Reactivation changes the profile back to Active. To reactivate through the interface, choose Update Patient Details, select the archived patient, and confirm reactivation before editing. Many operational lookups exclude archived profiles, while other screens deliberately allow them to be viewed.

Archiving is called a soft delete. The record is no longer used as an active profile, but its history remains. Do not delete the database file to archive one patient.

## 5 Appointments check in and the daily queue

### Scheduling an appointment

1. Find the active patient first.
2. Open Outpatient Appointment Management and choose the scheduling option.
3. Enter the date as `YYYY-MM-DD`, the time as 24-hour `HH:MM`, the department, and the reason.
4. Select an outpatient department. ER uses immediate intake instead of ordinary appointment scheduling.
5. Review and confirm the appointment. Note its ID beginning with `APT-`.

The scheduling flow checks whether the patient or department already has an active booking at the exact same date and time. If Cardiology is booked at 10:00, choose another slot. The current logic matches exact slots; it does not calculate appointment-duration overlaps or maintain a separate calendar for each doctor.

### Rescheduling cancellation no show and check in

Reschedule moves an eligible appointment after another conflict check. Cancel marks it Cancelled. No-Show records an eligible missed appointment. Status checks prevent some changes after check-in or completion.

Check-In records arrival. Use an appointment for today's date during practice so the sequence is easy to follow. In the current code, status is the enforced check-in condition; there is no explicit same-day check. Check-in creates a ticket for the current daily queue and changes the appointment to Checked-In. An appointment and a queue ticket are separate records.

### Walk in tickets and the queue board

For a patient without an appointment, choose the Walk-In Ticket option, select an active profile, and choose the department. The queue number belongs to the day. The ticket ID identifies the stored ticket record.

The daily board lists Emergency tickets first, Scheduled tickets next, and Walk-in tickets last. Within each ticket type, it sorts by queue number. The board is not sorted solely by the nursing triage category.

The common sequence is Waiting -> Triage -> Consultation -> Billing -> Completed. Some alternative steps are allowed, such as Waiting -> Consultation. Completed and Cancelled are final states with no normal next transition. The reference section lists every allowed transition.

After saving a normal consultation, its screen attempts to move the patient's active queue ticket to Billing. A finished consultation does not mean that the bill has been paid. Review queue status and bill status separately.

## 6 Nursing triage and vital signs

Triage is the initial nursing assessment. The nurse selects the patient and enters the complaint, allergies, temperature, blood pressure, pulse, respiratory rate, oxygen saturation, pain score, and urgency category. The nurse's name comes from the current session. An optional ticket reference exists in the function and database, but not every menu path fills it automatically.

1. Log in as Nurse or Administrator and open the nursing triage option.
2. Select the patient and verify the identity.
3. Enter the chief complaint and allergies. NKDA means No Known Drug Allergies and is the model's default.
4. Enter measured vital signs. Temperature uses Celsius; BP uses mmHg; pulse uses beats per minute; respiratory rate uses breaths per minute; SpO2 uses percent; pain uses 0 to 10.
5. Read the alerts and suggested category. Confirm or adjust the final category, review the summary, and save.
6. Use the history screen to review previous assessments.

| Input | Accepted range in the validation model |
| --- | --- |
| Temperature | 30.0 to 45.0 Celsius |
| Systolic blood pressure | 50 to 260 mmHg |
| Diastolic blood pressure | 30 to 160 mmHg |
| Pulse | 30 to 220 bpm |
| Respiratory rate | 6 to 60 breaths per minute |
| Oxygen saturation | 50 to 100 percent |
| Pain score | 0 to 10 |

Systolic BP must be greater than diastolic BP. An accepted input range is a program boundary, not a statement that every accepted value is normal or clinically safe. A correctly formatted value can still trigger an alert.

The rules are in `evaluate_vital_signs()` and the thresholds are in `config.py`. The categories are Emergency, Urgent, and Non-Urgent. These are project rules requiring qualified clinical review before real use. They do not provide an automatic diagnosis.

Current rules suggest Emergency for SpO2 below 88, systolic BP at least 180 or diastolic BP at least 120, or respiratory rate below 10. Urgent triggers include SpO2 below 92; BP below 90 systolic or 60 diastolic; pulse above 100 or below 55; temperature at least 38.5 or below 35.5; respiration above 24; and pain at least 8. Temperature at least 38.0 also adds a fever alert. A later Urgent condition does not lower an existing Emergency suggestion. The nurse selects the final category.

## 7 Consultations and emergency intake

### Normal consultations using SOAP

SOAP organizes clinical notes. Subjective means what the patient reports. Objective means the examination findings. Assessment means the clinician's documented diagnosis or assessment. Plan means the treatment, orders, or follow-up entered by the clinician.

1. Log in as Doctor or Administrator and open the clinical consultation option.
2. Select the patient and department, and review the latest triage if available.
3. A Doctor session uses that authenticated doctor's identity. Other paths support staff selection or documented reassignment.
4. Enter the chief complaint, physical findings, diagnosis, and treatment plan.
5. If the examination is normal or unremarkable, confirm that explicitly. Missing information is not automatically treated as a normal examination.
6. Review and save. Note the `VST-` visit ID. The screen can then continue to billing.

The normal consultation screen requires SOAP content and validates it before saving. The low-level `record_visit()` function has defaults for structured fields, so not every possible code path is as strict as the normal interactive screen.

### Emergency Room intake

ER intake does not require an ordinary appointment. Select an existing patient or use fast-track registration. The workflow issues an Emergency ticket in ER, selects the attending provider, records emergency assessment and interventions, saves the visit, and can continue to billing.

The ER screen uses its own notes flow rather than the normal step-by-step SOAP prompts. Explain the appointment bypass and ticket priority during the demonstration. Do not present an outpatient appointment as a requirement for an emergency case.

Fast-track registration uses placeholder values when profile details are unknown. Its current sex mapping stores Female for option 2 and Male for other input, so it does not preserve Other. This is a known limitation. Use an existing correctly registered fictional profile if the demonstration needs the Other classification.

## 8 Bills discounts payments and receipts

### Creating an itemized bill

Select the patient and the consultation link if available. Enter each service description and charge, such as Consultation PHP 500.00 and Laboratory PHP 250.00. Bill items are the individual charges. The bill is the summary containing the total, payments, remaining balance, and status.

Choose None, Senior Citizen, PWD, PhilHealth Benefit, or Charity / Social Service. The current interface calculates 20 percent for Senior Citizen and PWD. Other benefit or adjustment amounts are entered by the user. There is no online eligibility check or automatic official case-rate lookup.

Review the patient, subtotal, discount, and final total before confirming. These are simplified project calculations. Do not claim that the application automatically implements every real billing, tax, legal, or benefits rule.

### Sample calculation

| Item | Amount |
| --- | --- |
| Consultation | PHP 500.00 |
| Laboratory | PHP 250.00 |
| Subtotal | PHP 750.00 |
| Example 20 percent discount | PHP 150.00 |
| Amount due | PHP 600.00 |
| Cash handed over | PHP 1000.00 |
| Applied payment | PHP 600.00 |
| Change | PHP 400.00 |
| Remaining balance | PHP 0.00 |

The code uses `Decimal` for money calculations. Decimal is more suitable than an ordinary binary float for amounts, discounts, and change. Money is stored as text in SQLite so it can be converted back to Decimal without first passing through float.

### Recording a payment

1. Select an unpaid or partially paid bill and review the current balance.
2. Enter the payment or cash tendered as requested, and choose the payment method.
3. Review the applied amount, change, and projected remaining balance.
4. Confirm once. Note the `PAY-` ID and receipt number.
5. View the receipt and verify the bill status.

For a PHP 200.00 partial payment against PHP 600.00 due, the balance becomes PHP 400.00 and the status becomes Partially Paid. A settled bill becomes Paid. Extra cash is change, not extra revenue. The displayed receipt is an application record; it does not prove external payment settlement or tax accreditation.

The duplicate-payment check matches the bill, applied amount, method, and payment date value. Equal payments within the same timestamp precision or entered date can be flagged even if the user intended separate payments. Review payment history before retrying rather than repeatedly submitting the same transaction.

### Cancellations and outstanding bills

Bill cancellation requires a reason and rejects bills with a recorded payment. It is not a refund workflow. Financial statistics exclude Cancelled bills from billed, collected, and outstanding totals. Outstanding Bills displays remaining balances according to the module's filters.

## 9 Reports audit logs and staff accounts

### Reports

Patient statistics show total, active, and archived profiles. Appointment reports summarize statuses. Visit reports group consultations. Financial reports show billed, collected, and balance totals. The dashboard combines patient counts, daily appointments, queue activity, consultations, and finances. Daily registration and triage alerts reports are also available.

Read each metric's label: not every dashboard figure is limited to today. Appointment and queue counts can be daily while consultation and financial totals can cover all stored records. Reports use the current local database. Zero or empty results are normal when no matching data exists.

### Audit logs

An audit log is an activity notebook containing the timestamp, actor, action, target record, and details. Patient registration and recorded payments are examples of logged activities. The reporting menu provides the audit viewer.

The log is stored in the same local SQLite file. It is not an unchangeable forensic record and does not prove that every action is covered. Some code paths use a fallback actor such as SYSTEM when no session exists.

### Staff management

The staff-management screen checks that the session is Administrator. It can list accounts, create a username and password with a name and role, and activate or deactivate accounts. Usernames must be unique. The input model requires a password of at least six characters.

The screen does not allow the master `admin` account to be deactivated. There is no complete password recovery workflow. Practice with demo accounts and coordinate account changes with the group.

The current code stores salted PBKDF2-HMAC-SHA256 password hashes using 20000 iterations. A hash is a derived value used to verify a password, rather than the original password itself. Legacy SHA256 verification remains for old accounts. Login uses ordinary `input()`, so the typed password is visible in the terminal.

## 10 How the source code works

### Startup to exit

`main()` checks the command-line arguments. A normal `python main.py` launch calls `run_interactive_app()`. A subcommand such as `patients list` uses `cli.py` and argparse instead.

Interactive startup calls `init_db()`, opens the database, creates or updates the schema, and adds demo accounts if the users table is empty. A login loop then authenticates a staff member. The program keeps a UserSession in memory, displays that role's menu, and routes the chosen option to a module handler. It closes the connection on exit.

### Optional CLI commands

Subcommands are terminal shortcuts. They currently run without interactive login. Use them only on a trusted demonstration device. Use the normal interactive application to demonstrate staff roles.

```sh
python main.py --help
python main.py interactive
python main.py database initialize
python main.py patients list
python main.py patients list --status Active
python main.py patients search "Demo Patient"
python main.py patients view PAT-1001
python main.py appointments list
python main.py appointments list --date 2026-10-20
python main.py reports daily
python main.py reports dashboard
```

Replace the sample patient ID and date with your own records. The short option `-s` means `--status`, and `-d` means `--date`. Database initialize sets up or updates the schema; it does not delete or reset all records.

### File guide

| File | Main responsibility |
| --- | --- |
| main.py | Entry point, login loop, role menus, and routing |
| cli.py | argparse shortcuts for lookups and reports |
| config.py | Paths, departments, statuses, thresholds, and options |
| database.py | Connection, ten tables, migrations, indexes, and demo accounts |
| modules/auth.py | Hashing, login, sessions, role map, staff management |
| modules/patients.py | Register, search, view, edit, archive, reactivate |
| modules/appointments.py | Schedule, conflicts, reschedule, cancel, check-in, no-show |
| modules/queue.py | Ticket IDs, daily numbers, sorting, and status movement |
| modules/triage.py | Vital signs, alert rules, and assessment history |
| modules/visits.py | Normal SOAP consultation, ER intake, and visit history |
| modules/billing.py | Bills, items, discounts, payments, receipts, cancellation |
| modules/reports.py | Patient, appointment, consultation, financial reports, dashboard |
| modules/audit.py | Write and retrieve activity logs |
| utils/display.py | Rich tables, cards, colors, and narrow-screen layout |
| utils/plain_display.py | Plain output when Rich is unavailable |
| utils/prompts.py | Numbered or optional arrow-key choices and patient lookup |
| utils/validators.py | Specific validation rules and input models |
| utils/schema.py | Standard-library engine for fields and validation errors |
| Package init files | The __init__.py package markers in modules and utils |

The project also contains `requirements.txt` for Rich installation, this README, and `.gitignore` to exclude local data and development files from Git. The helper files are used by other modules and should not be deleted simply because they are not the entry point.

### Screen handlers and database functions

`handle_register_patient()` asks questions, validates input, displays a preview, and asks for confirmation. `register_patient()` creates the database row. Separating screen interaction from data operations makes the code easier to read and check.

The same pattern appears in `handle_record_payment()` and `record_payment()`. Validation in a screen does not automatically exist in every low-level function. When modifying a feature, inspect both the handler and the save function.

### Three code ideas to explain

A parameterized query keeps the SQL instruction separate from user values. The question mark is a placeholder, and the patient ID is passed as data:

```python
cursor.execute(
    "SELECT * FROM patients WHERE patient_id = ?",
    (patient_id,)
)
```

`conn.commit()` saves pending database changes. `conn.rollback()` cancels a pending transaction after failure. There is a `transaction_scope()` helper, and some functions use their own commit and rollback logic. Not every multi-step workflow is one transaction.

Generated IDs combine a prefix and the next number. `generate_patient_id()` finds the highest PAT number and adds one. APT, VST, BIL, and PAY follow similar patterns. Sequential IDs are readable, but they are not a global online ID service and have concurrency limitations.

## 11 Programming terms explained simply

A variable is a named container for a value, such as `patient_id`. A string is text, such as `"PAT-1001"`. An integer is a whole number, such as a queue number. A list is an ordered collection, such as the department choices. A dictionary connects names to values, such as statistics with total and active keys.

A function is a reusable task, such as `get_connection()`. A parameter is an input to a function, and a return value is its result. A module is a Python file you can import. A package is a folder of related modules.

An `if` statement makes a decision: if a bill is already paid, reject another payment. A loop repeats instructions: a menu continues until the user exits. `try/except` handles errors: handled input or database failures can produce a message rather than ending the program unexpectedly.

A class defines structured data or behavior. The UserSession dataclass stores the user ID, name, role, and login time. PatientCreateModel describes input fields and rules. A decorator such as `@field_validator` marks the function that should validate a particular field.

Validation checks whether input follows rules. Authentication checks who logged in. Authorization checks which actions the role may use. Hashing creates a checkable derived password value. A salt adds a separate per-account value so matching passwords do not produce matching stored hashes.

A primary key uniquely identifies a row. A foreign key links a row to another table. JOIN combines related records for a query. An index helps searches find records faster. A migration updates an existing database structure, such as adding a column without starting with a new database.

The retained name `format_pydantic_error()` does not mean Pydantic is installed. Its ValidationError class and schema engine come from `utils/schema.py`. Python `#` comments have been removed from the runtime source. Menu text and strings used by the application, including CLI help, remain.

## 12 Backups troubleshooting and limitations

### Backing up and restoring records

1. Exit the application so no write is in progress.
2. Copy `data/hospital.db` to a separate backup location. If `HOSPITAL_DATA_DIR` is configured, back up the file from that directory instead.
3. Include the date in the backup name so you can identify the latest copy.
4. To restore, close the application, keep a copy of the current database, and place the selected backup in the active data directory as hospital.db.
5. Start the application and verify expected records before continuing.

The source ZIP is not a backup of entered records. The database is excluded from Git through `.gitignore`. This application does not encrypt the database. Protect the device and backup files, and do not upload real patient data to a public repository or release.

### Common problems

- No module named rich: install rich==13.9.4 through Pydroid Pip. Use the same Python environment for installation and execution.
- No module named modules or utils: the folder is incomplete or the wrong copy is open. Extract the complete source ZIP and open main.py inside it.
- Cannot open database or permission denied: use a writable folder and check Pydroid storage access. Do not immediately delete the database.
- Missing colors or visible ANSI codes: use terminal mode. Choose auto or never if the output panel does not support ANSI; do not force colors in that panel.
- Login fails: check spelling, password, and account status. The login flow allows three failed attempts. Startup does not reset an existing users table.
- Archived patient cannot be selected: reactivate the profile through patient management if it should be active again.
- Appointment conflict: choose another date, time, or department, or reschedule the existing appointment.
- Check-in is rejected: confirm that the appointment is Scheduled or Rescheduled. The current code checks status rather than same-day eligibility; still review the intended arrival date before confirming.
- Invalid queue transition: review the current state and allowed next states. Completed and Cancelled are final.
- Duplicate payment warning: review the payment list and receipt before retrying. Do not repeatedly submit the same payment to bypass the warning.
- Empty report: verify the local database and date filters. An empty result is normal when there are no matching records.
- Records appear missing after moving the project: another copy or database location may be open. Find and back up the old hospital.db before restoring it.

### Limitations to explain during the defense

The security model uses local storage and basic role menus. There is no encrypted database, full password recovery flow, or login guard on every CLI command. Clinical rules are fixed and discount logic is simplified. Separate commits occur in some workflows, so linked operations are not always one atomic transaction. Multi-device synchronization and high-concurrency deployment have not been verified.

Duplicate-payment matching can flag equal payments with the same date value. The regular SOAP screen is stricter than some direct save paths. The audit history is useful but not tamper-proof. The tests were excluded from the runtime branch for distribution; they are not included in the current source download.

## 13 Demonstration and presentation practice

### Before the demonstration

Install Rich and run the application before presentation day. Use fictional data in a practice database or back up existing demonstration records. Check the device date, terminal size, login accounts, and power supply. Write down generated IDs; do not assume every used database will start at 1001.

### One complete practice workflow

1. As Administrator, explain the modules and register Demo Patient One.
2. Show validation with an invalid phone input, then enter a valid sample. Do not save the incorrect input.
3. Schedule an appointment for today at a free future time. Use the actual date instead of a date copied from an old guide.
4. Check in the appointment and display its ticket. Show that walk-in ticket creation is a different arrival path.
5. Switch to Nurse and enter fictional training vitals, such as 36.8 C, BP 120/80, pulse 75, respiration 18, SpO2 98, and pain 0. These are training inputs only.
6. Switch to Doctor and enter a fictional SOAP scenario. Use clinician-provided demonstration text or clearly fictional observations; do not present treatment advice as an automatically generated diagnosis.
7. Save the consultation, show the queue change to Billing, and continue to billing or switch to the Billing account.
8. Create the PHP 750.00 sample bill, apply the example discount, record PHP 1000.00 cash against PHP 600.00 due, and show PHP 400.00 change.
9. Display the receipt, patient history, financial report, and audit entries. If queue completion is still needed, review and advance the ticket through the queue menu.
10. As a separate scenario, show ER intake and explain why it does not require an ordinary appointment. Finish with logout and Exit.

### Suggested division of work

One member can explain the problem, scope, and installation. Another can demonstrate patients, appointments, and the queue. Another can handle triage, SOAP, and ER. Another can explain billing, reports, and audit logs. Another can cover the database, files, limitations, and questions. Combine related topics if there are fewer members. Everyone should practice the complete workflow even when each person presents only one part.

For a 10 to 12 minute presentation, allow about two minutes for the purpose and setup, six for the main workflow, two for the code and database, and two for limitations and questions. Adjust the timing to your teacher's requirements.

### Sample defense answers

Why Python and SQLite: Python is readable for a student project, and SQLite works without a separate server. The tradeoff is local storage and limited sharing.

Why Decimal: money calculations need predictable decimal values for discounts, partial payments, and change. Ordinary floats use binary representation and can produce rounding artifacts.

Why archive instead of delete: archiving preserves past consultations and billing links while removing the profile from regular active-patient operations.

Why no Pydantic: custom standard-library validation avoids a Pydantic Core dependency in Pydroid. Rich is the normal interface requirement.

Does it diagnose patients or process GCash: no. It displays rule-based alerts and records a payment method. Clinical decisions and real payment settlement are separate responsibilities.

Is it ready for a real hospital: it is a school prototype. Real deployment needs access-control review, privacy and security work, clinical validation, device testing, and operational requirements.

## 14 Final submission checklist

- The application opens from the complete source folder and demo login works.
- Colored tables appear in the target terminal and remain readable on the phone.
- A fictional patient can be registered, found, edited, archived, and reactivated.
- The appointment conflict example, check-in, walk-in ticket, and valid queue transition work.
- Triage and a normal SOAP consultation can be saved, and the ER entry point is available.
- The sample bill, partial payment, full settlement, change, and receipt can be explained.
- Financial totals, outstanding bills, and relevant audit entries can be reviewed.
- A backup exists and no real patient information is included in public uploads.
- The group understands the files, ten database tables, and current limitations.
- The GitHub branch is alfredo/pydroid-compatibility and both documentation formats are in Releases.

## 15 Database reference

The following reference is generated from the SQLite structure created by `create_schema()` after migrations. There are ten application tables. SQLite's internal sqlite_sequence table is not included in that count.

One patient can have many appointments, tickets, triage assessments, visits, and bills. One bill can have many items and payments. Only declared foreign keys are enforced as database relationships. Other reference fields, such as visit_id in bills, are application-level links in the current schema.

### users

Staff login accounts and roles. Stores password_hash and salt rather than the original password.

Primary key: `user_id`.

Columns: `user_id`, `username`, `password_hash`, `salt`, `full_name`, `role`, `status`, `created_at`.

This table has no declared foreign key.

### patients

Patient profiles. The central record linked to clinical and billing information.

Primary key: `patient_id`.

Columns: `patient_id`, `full_name`, `dob`, `sex`, `contact_number`, `address`, `emergency_contact`, `registration_date`, `status`, `patient_type`.

This table has no declared foreign key.

### appointments

Scheduled outpatient appointments and their statuses.

Primary key: `appointment_id`.

Columns: `appointment_id`, `patient_id`, `appointment_date`, `appointment_time`, `department`, `reason`, `status`, `created_by`.

Declared foreign keys: `patient_id` -> `patients.patient_id`.

### queue_tickets

Arrival tickets, department, date, ticket type, and queue stage.

Primary key: `ticket_id`.

Columns: `ticket_id`, `queue_number`, `patient_id`, `department`, `ticket_date`, `ticket_type`, `status`, `created_at`.

Declared foreign keys: `patient_id` -> `patients.patient_id`.

### triage_records

Nursing assessments, measured vital signs, category, and alerts.

Primary key: `triage_id`.

Columns: `triage_id`, `patient_id`, `ticket_id`, `triage_date`, `nurse_user`, `chief_complaint`, `allergies`, `temperature`, `bp_systolic`, `bp_diastolic`, `pulse_rate`, `respiratory_rate`, `oxygen_saturation`, `pain_score`, `triage_category`, `clinical_alerts`.

Declared foreign keys: `patient_id` -> `patients.patient_id`.

### visits

Doctor consultations and ER visits, including structured SOAP fields.

Primary key: `visit_id`.

Columns: `visit_id`, `patient_id`, `visit_date`, `department`, `attending_provider`, `notes`, `triage_id`, `chief_complaint`, `clinical_findings`, `diagnosis`, `treatment_plan`, `visit_status`.

Declared foreign keys: `patient_id` -> `patients.patient_id`.

### bills

Invoice summary, subtotal, discount, total, paid amount, balance, and cancellation reason.

Primary key: `bill_id`.

Columns: `bill_id`, `patient_id`, `bill_date`, `total_amount`, `paid_amount`, `balance`, `status`, `visit_id`, `subtotal`, `discount_type`, `discount_amount`, `cashier_user`, `cancellation_reason`.

Declared foreign keys: `patient_id` -> `patients.patient_id`.

### bill_items

Individual services or charges belonging to a bill.

Primary key: `item_id`.

Columns: `item_id`, `bill_id`, `service_description`, `amount`.

Declared foreign keys: `bill_id` -> `bills.bill_id`.

### payments

Recorded payments, channel, receipt, cashier, tendered amount, and change.

Primary key: `payment_id`.

Columns: `payment_id`, `bill_id`, `payment_date`, `amount`, `payment_method`, `notes`, `amount_tendered`, `change_amount`, `official_receipt_no`, `cashier_user`.

Declared foreign keys: `bill_id` -> `bills.bill_id`.

### audit_logs

Activity history with actor, timestamp, action, target record, and details.

Primary key: `log_id`.

Columns: `log_id`, `timestamp`, `user_id`, `username`, `action`, `target_type`, `target_id`, `details`.

This table has no declared foreign key.

## 16 Menu and status reference

The following lists contain the actual main menus for each role, module submenus, allowed queue transitions, statuses, and departments. Menu numbers are role-specific. Follow the displayed labels and the workflow instructions in this guide.

### Administrator main menu

1. Emergency Room (ER) Care (Immediate Intake)
2. Patient Management (Registration & Records)
3. Outpatient Appointment Management
4. Daily Patient Queue & Walk-In Board
5. Nursing Triage & Vital Signs Assessment
6. Physician Clinical Consultations (SOAP)
7. Billing, Philippine Discounts & Official Receipts
8. Hospital Reports & System Analytics
9. Staff User Accounts & Role Permissions
10. Switch User / Logout
11. Exit System

### Doctor main menu

1. Emergency Room (ER) Care (Immediate Intake)
2. Daily Patient Queue Board
3. Physician Clinical Consultations (SOAP)
4. View Patient Medical Records & History
5. Review Nursing Triage & Vital Signs History
6. Clinical Consultation Statistics
7. Switch User / Logout
8. Exit System

### Nurse main menu

1. Emergency Room (ER) Care (Immediate Intake)
2. Daily Patient Queue Board
3. Nursing Assessment & Triage (Vitals & Allergies)
4. View Patient Triage History & Alert Logs
5. View Patient Profiles
6. Switch User / Logout
7. Exit System

### Receptionist main menu

1. Emergency Room (ER) Care (Immediate Intake)
2. Patient Registration & Search
3. Appointment Scheduling & Check-In
4. Daily Patient Queue & Walk-In Pass Issuance
5. View Hospital Patient Registry
6. Switch User / Logout
7. Exit System

### Billing main menu

1. Generate Itemized Hospital Bill (Senior/PWD Discounts)
2. Record Payment & Issue Official Receipt (OR)
3. View Outstanding Unpaid Patient Balances
4. Financial & Revenue Reports (PHP)
5. Look Up Patient Records
6. Switch User / Logout
7. Exit System

### Patient management submenu

1. Register New Patient
2. View All Patients
3. Search Patients (by ID or Name)
4. View Patient Details
5. Update Patient Details
6. Archive Patient Record
7. Return to Main Menu

### Appointment submenu

1. Schedule New Appointment
2. View Upcoming Appointments
3. Search Appointments (by ID / Patient)
4. Check-In Arrived Patient (Issue Queue Pass)
5. Reschedule Appointment
6. Cancel Appointment
7. Mark Missed / No-Show Appointment
8. Return to Main Menu

### Daily queue submenu

1. View Today's Hospital Queue Board
2. Issue Walk-In Queue Ticket
3. Advance Patient Queue Status
4. Return to Main Menu

### Nursing triage submenu

1. Perform Patient Triage & Vitals Assessment
2. View Patient Triage & Vital Signs History
3. Return to Main Menu

### Clinical consultation submenu

1. Emergency Room (ER) Intake (Immediate Care)
2. Record Regular Clinical Visit
3. View Patient Visit History
4. View All Hospital Visits
5. View Specific Visit Details
6. Return to Main Menu

### Billing submenu

1. Generate New Hospital Bill
2. Record Payment for Bill
3. View All Bills
4. View Outstanding Bills
5. View Bill Invoice Details
6. View Patient Billing History
7. Cancel Unpaid Bill Invoice
8. Return to Main Menu

### Reports submenu

1. Hospital Executive Dashboard (Overview)
2. Patient Demographics & Daily Registrations
3. Clinical Triage Urgency & Alert Logs
4. Appointment Workload Statistics
5. Clinical Visits & Consultation Summary
6. Financial & Revenue Report (PHP)
7. System Audit Trail & Security Logs
8. Return to Main Menu

### Staff management submenu

1. View All Staff Accounts
2. Register New Staff Account
3. Activate / Deactivate Staff Account
4. Return to Main Menu

### Queue transitions

| Current status | Allowed next status |
| --- | --- |
| Waiting | Triage, Consultation, Cancelled |
| Triage | Consultation, Waiting, Cancelled |
| Consultation | Billing, Completed, Cancelled |
| Billing | Completed, Cancelled |
| Completed | None |
| Cancelled | None |

### Appointment and billing statuses

Appointment statuses: Scheduled, Checked-In, Completed, Cancelled, Rescheduled, No-Show.

Bill statuses: Unpaid, Partially Paid, Paid, Cancelled.

Patient statuses: Active and Archived. Staff statuses: Active and Inactive.

### Configured departments

- Outpatient Department (OPD)
- Emergency Room (ER)
- Internal Medicine
- Pediatrics
- Obstetrics and Gynecology (OB-GYN)
- Surgery
- Cardiology
- Orthopedics
- Radiology
- Laboratory & Diagnostics

## 17 Sources and version information

The primary source is the alfredo/pydroid-compatibility code, using functional baseline 97b7662. The guide was checked against main.py, cli.py, config.py, database.py, all modules, and the validation and display helpers.

After source comment removal, 82 automated tests passed on Windows with Rich, including 32, 48, and 100-column table checks. Syntax trees were also compared to confirm that the executable instructions stayed the same. This is not Android or iOS device certification. The update adds documentation and removes source comments without adding application features.

Repository: https://github.com/alfredozboajrpvgma-cmd/Hospital-Patient-System--CLI-

Runtime branch: https://github.com/alfredozboajrpvgma-cmd/Hospital-Patient-System--CLI-/tree/alfredo/pydroid-compatibility

Documentation release: https://github.com/alfredozboajrpvgma-cmd/Hospital-Patient-System--CLI-/releases/tag/docs-pydroid-v1

Rich terminal reference: https://rich.readthedocs.io/en/stable/console.html
