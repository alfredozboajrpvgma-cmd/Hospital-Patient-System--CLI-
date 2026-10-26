"""
Interactive menu and choice prompts using Questionary.
Lets users pick options using arrow keys, with a numbered fallback if needed.
"""

import sys
import sqlite3
from typing import List, Optional, Callable, Tuple, Any

try:
    import questionary
    from questionary import Choice
    _QUESTIONARY_AVAILABLE = True
except ImportError:
    _QUESTIONARY_AVAILABLE = False

from utils.display import console, print_error, print_warning, print_info


def is_interactive() -> bool:
    """Check if standard input is attached to an interactive terminal."""
    return _QUESTIONARY_AVAILABLE and hasattr(sys.stdin, "isatty") and sys.stdin.isatty()


def select_menu(
    title: str,
    choices: List[str],
    default: Optional[str] = None
) -> Optional[str]:
    """Show a menu where the user can pick an option using arrow keys."""
    if not choices:
        return None

    if is_interactive():
        try:
            choice = questionary.select(
                message=title,
                choices=choices,
                default=default,
                style=questionary.Style([
                    ("qmark", "fg:#38bdf8 bold"),
                    ("question", "fg:#f8fafc bold"),
                    ("answer", "fg:#4ade80 bold"),
                    ("pointer", "fg:#38bdf8 bold"),
                    ("highlighted", "fg:#38bdf8 bold"),
                    ("selected", "fg:#4ade80"),
                ]),
                use_indicator=True,
                use_shortcuts=False
            ).ask()
            return choice
        except (KeyboardInterrupt, EOFError):
            return None
        except Exception:

            pass


    console.print(f"\n[bold cyan]{title}[/bold cyan]")
    for idx, opt in enumerate(choices, 1):
        label = opt.split(". ", 1)[1] if opt.split(". ", 1)[0].isdigit() else opt
        console.print(f"  {idx}. {label}")
    
    try:
        user_input = input(f"Enter choice (1-{len(choices)}, or 0 to cancel): ").strip()
        if user_input in ("0", "q", "exit", "back", ""):
            return None
        if user_input.isdigit() and 1 <= int(user_input) <= len(choices):
            return choices[int(user_input) - 1]
    except KeyboardInterrupt:
        return None

    return None


def select_option(
    message: str,
    choices: List[str],
    default: Optional[str] = None
) -> Optional[str]:
    """Ask the user to pick one value from a list (e.g., Sex, Department)."""
    return select_menu(message, choices, default=default)


def confirm_prompt(
    message: str,
    default: bool = False
) -> bool:
    """Yes/No confirmation prompt (y/n)."""
    if is_interactive():
        try:
            res = questionary.confirm(message, default=default).ask()
            return bool(res)
        except (KeyboardInterrupt, EOFError):
            return False
        except Exception:
            pass

    from utils.display import confirm_action
    return confirm_action(message, default_no=not default)


def ask_text(
    message: str,
    default: str = "",
    validate_func: Optional[Callable[[str], Tuple[bool, str]]] = None,
    allow_empty: bool = False
) -> Optional[str]:
    """Ask the user for text input with optional validation."""
    while True:
        try:
            if is_interactive():
                try:
                    val = questionary.text(
                        message=message,
                        default=default
                    ).ask()
                except Exception:
                    val = input(f"{message} [{default}]: " if default else f"{message}: ")
            else:
                val = input(f"{message} [{default}]: " if default else f"{message}: ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Input cancelled.[/dim]")
            return None

        if val is None:
            return None

        cleaned = val.strip() if val else default.strip()

        if not cleaned:
            if allow_empty:
                return ""
            console.print("[dim]Input cancelled.[/dim]")
            return None

        if validate_func:
            valid, res = validate_func(cleaned)
            if not valid:
                print_error(res)
                continue
            return res

        return cleaned


def interactive_patient_lookup(
    conn: sqlite3.Connection,
    prompt_text: str = "Search patient (type Name, ID, or 'list' to browse): ",
    include_archived: bool = False
) -> Optional[sqlite3.Row]:
    """Search for a patient by ID, name, or pick from a list."""
    from modules.patients import get_patient_by_id, search_patients, get_all_patients

    while True:
        try:
            query = input(prompt_text).strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            return None

        if not query or query.lower() in ("0", "q", "cancel", "back", "exit"):
            return None


        patient = get_patient_by_id(conn, query)
        if not patient and query.isdigit():
            patient = get_patient_by_id(conn, f"PAT-{query}")

        if patient:
            if not include_archived and patient["status"] == "Archived":
                print_error(f"Patient {patient['full_name']} ({patient['patient_id']}) is ARCHIVED. Reactivate first.")
                continue
            return patient


        if query.lower() in ("?", "list", "all"):
            all_pts = get_all_patients(conn, filter_status=None if include_archived else "Active")
            if not all_pts:
                print_warning("No patients registered yet.")
                return None

            choices = [f"{p['patient_id']} - {p['full_name']} ({p['contact_number']}) [{p['status']}]" for p in all_pts]
            choices.append("Cancel")

            selected = select_menu("Select Patient from Registry:", choices)
            if not selected or selected == "Cancel":
                continue

            chosen_id = selected.split(" - ")[0].strip()
            return get_patient_by_id(conn, chosen_id)


        results = search_patients(conn, query)
        if not results:
            print_error(f"No patient found matching '{query}'. Enter 'list' to browse all, or try again.")
            continue

        if len(results) == 1:
            chosen = results[0]
            if not include_archived and chosen["status"] == "Archived":
                print_error(f"Patient {chosen['full_name']} ({chosen['patient_id']}) is ARCHIVED. Reactivate first.")
                continue
            print_info(f"Selected: {chosen['full_name']} ({chosen['patient_id']})")
            return chosen


        choices = [f"{p['patient_id']} - {p['full_name']} ({p['contact_number']}) [{p['status']}]" for p in results]
        choices.append("Cancel")
        selected = select_menu(f"Found {len(results)} matching patients. Choose one:", choices)
        if not selected or selected == "Cancel":
            continue

        chosen_id = selected.split(" - ")[0].strip()
        return get_patient_by_id(conn, chosen_id)
