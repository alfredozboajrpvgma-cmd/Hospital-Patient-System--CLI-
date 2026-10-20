"""
Screen formatting and styling using Rich.
Provides colored banners, tables, alert badges, and summary cards.
"""

from typing import List, Any, Optional, Dict
from decimal import Decimal
import sys
import os

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    from rich.columns import Columns
    from rich.padding import Padding
    from rich.constrain import Constrain
    RICH_AVAILABLE = True
except ImportError:
    from utils.plain_display import Console, Table, Panel, Text, box, Columns, Padding, Constrain
    RICH_AVAILABLE = False


if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


_color_mode = os.environ.get("HOSPITAL_COLOR", "auto").lower()
if _color_mode == "always" and os.environ.get("TERM", "dumb") in ("dumb", "unknown"):
    os.environ["TERM"] = "xterm"
console = Console(
    highlight=False,
    force_terminal=True if _color_mode == "always" else None,
    no_color=_color_mode == "never",
    color_system="standard" if _color_mode == "always" else "auto",
)


CONTENT_MAX = 100


def _ui_width(preferred: Optional[int] = None) -> int:
    """Return a readable content width capped for wide terminals."""
    term = console.width or CONTENT_MAX
    cap = preferred if preferred is not None else CONTENT_MAX
    return max(10, min(term, cap))


def _print_centered(renderable, width: Optional[int] = None) -> None:
    """Print a renderable in a centered content band (works on wide terminals)."""
    band = width if width is not None else _ui_width()
    left = max(0, ((console.width or band) - band) // 2)
    console.print(Padding(renderable, (0, 0, 0, left)))


def print_header(title: str, subtitle: Optional[str] = None, width: Optional[int] = None) -> None:
    """Print a styled section header panel."""
    band = _ui_width(width)
    content = Text()
    content.append(f"  {title.upper()}  ", style="bold white on navy_blue")
    if subtitle:
        content.append(f"\n  {subtitle}", style="italic cyan")

    panel = Panel(
        content,
        border_style="bold cyan",
        box=box.ROUNDED,
        padding=(0, 1),
        width=band,
        expand=True,
    )
    console.print()
    _print_centered(panel, width=band)


def print_subheader(title: str, width: Optional[int] = None) -> None:
    """Print a section divider centered within the content band."""
    band = _ui_width(width)
    console.print()
    _print_centered(Panel(
        Text(f" {title.upper()} ", style="bold cyan", justify="center"),
        border_style="bright_blue",
        box=box.ROUNDED,
        padding=(0, 1),
        width=band,
        expand=True,
    ), width=band)


def print_success(message: str) -> None:
    """Print a green success message."""
    console.print(f"[bold green][SUCCESS][/bold green] [green]{message}[/green]")


def print_error(message: str) -> None:
    """Print a red error message."""
    console.print(f"[bold red][ERROR][/bold red] [bright_red]{message}[/bright_red]")


def print_warning(message: str) -> None:
    """Print a yellow warning message."""
    console.print(f"[bold yellow][WARNING][/bold yellow] [yellow]{message}[/yellow]")


def print_info(message: str) -> None:
    """Print a cyan informational note."""
    console.print(f"[bold cyan][INFO][/bold cyan] [cyan]{message}[/cyan]")


def _style_cell_content(col_header: str, val_str: str) -> str:
    """Add colors to status texts (e.g., green for Active/Paid, red for Cancelled)."""
    header_lower = col_header.lower()
    val_lower = val_str.lower()


    if "status" in header_lower:
        if val_lower in ("active", "completed", "paid", "checked-in"):
            return f"[bold green]{val_str}[/bold green]"
        elif val_lower in ("archived", "cancelled", "no-show"):
            return f"[dim red]{val_str}[/dim red]"
        elif val_lower in ("scheduled", "rescheduled", "waiting", "partially paid"):
            return f"[bold yellow]{val_str}[/bold yellow]"
        elif val_lower in ("unpaid",):
            return f"[bold red]{val_str}[/bold red]"
        elif val_lower in ("triage", "consultation"):
            return f"[bold cyan]{val_str}[/bold cyan]"


    if "category" in header_lower or "urgency" in header_lower:
        if "emergency" in val_lower:
            return f"[bold red]🚨 {val_str}[/bold red]"
        elif val_lower == "urgent":
            return f"[bold yellow]⚠️ {val_str}[/bold yellow]"
        elif "non-urgent" in val_lower:
            return f"[bold green]ℹ️ {val_str}[/bold green]"


    if "amount" in header_lower or "total" in header_lower or "balance" in header_lower or "paid" in header_lower:
        if "₱" in val_str or "php" in val_lower:
            return f"[bold cyan]{val_str}[/bold cyan]"

    return val_str


def print_table(
    headers: List[str],
    rows: List[List[Any]],
    alignments: Optional[List[str]] = None,
    empty_message: str = "No records found.",
    title: Optional[str] = None
) -> None:
    """Print records in a clean table with borders and colored statuses."""
    width = _ui_width()


    if RICH_AVAILABLE and rows and width < max(60, len(headers) * 12):
        for number, row in enumerate(rows, 1):
            compact = Table(
                title=f"{title or 'Records'} ({number}/{len(rows)})",
                box=box.ROUNDED, border_style="bright_blue", width=width,
                show_header=True, header_style="bold cyan", show_lines=True,
            )
            compact.add_column("Field", style="cyan", ratio=1, overflow="fold")
            compact.add_column("Value", ratio=2, overflow="fold")
            for index, header in enumerate(headers):
                value = row[index] if index < len(row) else ""
                value = str(value) if value is not None else ""
                compact.add_row(Text(header), Text.from_markup(_style_cell_content(header, value)))
            _print_centered(compact, width=width)
        _print_centered(Text(f"Total records: {len(rows)}", style="dim"), width=width)
        return
    if not rows:
        console.print()
        _print_centered(Panel(
            f"[italic dim]{empty_message}[/italic dim]",
            border_style="dim",
            box=box.ROUNDED,
            width=width,
            expand=True,
        ), width=width)
        console.print()
        return

    table = Table(
        title=title,
        title_style="bold cyan",
        header_style="bold white on #1e3a8a",
        border_style="bright_blue",
        box=box.ROUNDED,
        show_header=True,
        show_lines=False,
        pad_edge=True,
        expand=True,
        width=width,
    )

    num_cols = len(headers)
    if not alignments:
        alignments = ["left"] * num_cols

    for idx, header in enumerate(headers):
        align = alignments[idx] if idx < len(alignments) else "left"
        justify = "left"
        if align == "right":
            justify = "right"
        elif align == "center":
            justify = "center"


        table.add_column(header, justify=justify, no_wrap=(idx == 0 or "date" in header.lower()))

    for row in rows:
        formatted_row = []
        for idx in range(num_cols):
            val = row[idx] if idx < len(row) else ""
            val_str = str(val if val is not None else "")
            styled = _style_cell_content(headers[idx], val_str)
            formatted_row.append(styled)
        table.add_row(*formatted_row)

    console.print()
    _print_centered(table, width=width)
    _print_centered(Text(f"  Total records: {len(rows)}", style="dim"), width=width)
    console.print()


def render_card(title: str, fields: Dict[str, Any], border_style: str = "cyan") -> None:
    """Display information in a boxed card format."""
    band = _ui_width()
    label_width = min(28, max(6, band // 3), max((len(str(k)) for k in fields), default=8) + 1)
    grid = Table.grid(padding=(0, 2), expand=True)
    grid.add_column(style="bold cyan", justify="right", width=label_width, overflow="fold")
    grid.add_column(style="white", overflow="fold")

    for key, val in fields.items():
        val_str = str(val) if val is not None else "-"
        grid.add_row(f"{key}:", val_str)

    panel = Panel(
        grid,
        title=f"[bold]{title}[/bold]",
        border_style=border_style,
        box=box.ROUNDED,
        width=band,
        expand=True,
        padding=(0, 1),
    )
    _print_centered(panel, width=band)


def render_notice(
    title: str,
    lines: List[str],
    border_style: str = "yellow",
    width: Optional[int] = None,
) -> None:
    """Display a multi-line notice panel (replaces fixed-width ASCII banners)."""
    band = _ui_width(width)
    body = Text()
    for i, line in enumerate(lines):
        if i:
            body.append("\n")
        body.append(line)

    panel = Panel(
        body,
        title=f"[bold]{title}[/bold]",
        border_style=border_style,
        box=box.ROUNDED,
        padding=(0, 2),
        width=band,
        expand=True,
    )
    console.print()
    _print_centered(panel, width=band)


def render_dashboard(
    active_patients: int,
    total_patients: int,
    appointments_today: int,
    patients_waiting: int,
    completed_consultations: int,
    unpaid_bills_count: int,
    total_billed: Decimal,
    total_paid: Decimal,
    outstanding_balance: Decimal
) -> None:
    """
    Render the executive hospital dashboard using Rich Panels and Columns.
    Guarantees actual SQLite values with clean empty states.
    """
    width = _ui_width()
    console.print()
    _print_centered(Panel(
        Text(" PHILIPPINE HOSPITAL EXECUTIVE DASHBOARD ", style="bold cyan", justify="center"),
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 1),
        width=width,
        expand=True,
    ), width=width)


    p_text = Text()
    p_text.append(f"Active Patients:   ", style="bold")
    p_text.append(f"{active_patients}\n", style="bold green")
    p_text.append(f"Total Registered:  ", style="dim")
    p_text.append(f"{total_patients}\n", style="cyan")
    p_text.append(f"Status:            ", style="dim")
    p_text.append("Operational", style="green")
    card_patients = Panel(p_text, title="[bold cyan]👥 Patient Care[/bold cyan]", border_style="cyan", box=box.ROUNDED)


    q_text = Text()
    q_text.append(f"Appts Scheduled Today: ", style="bold")
    q_text.append(f"{appointments_today}\n", style="bold yellow" if appointments_today > 0 else "dim")
    q_text.append(f"Queue Waiting:         ", style="bold")
    q_text.append(f"{patients_waiting}\n", style="bold red" if patients_waiting > 5 else "green")
    q_text.append(f"Consultations Done:    ", style="dim")
    q_text.append(f"{completed_consultations}", style="cyan")
    card_ops = Panel(q_text, title="[bold blue]🏥 Clinical Ops[/bold blue]", border_style="blue", box=box.ROUNDED)


    f_text = Text()
    f_text.append(f"Total Billed:    ", style="dim")
    f_text.append(f"₱{total_billed:,.2f}\n", style="bold white")
    f_text.append(f"Total Collected: ", style="dim")
    f_text.append(f"₱{total_paid:,.2f}\n", style="bold green")
    f_text.append(f"Outstanding Bal: ", style="bold")
    f_text.append(f"₱{outstanding_balance:,.2f}\n", style="bold red" if outstanding_balance > 0 else "green")
    f_text.append(f"Unpaid Invoices: ", style="dim")
    f_text.append(f"{unpaid_bills_count}", style="yellow" if unpaid_bills_count > 0 else "green")
    card_fin = Panel(f_text, title="[bold green]💰 Financial Overview[/bold green]", border_style="green", box=box.ROUNDED)

    columns = Columns([card_patients, card_ops, card_fin], equal=True, expand=True)

    if (console.width or CONTENT_MAX) > CONTENT_MAX:
        _print_centered(Constrain(columns, width=width), width=width)
    else:
        console.print(columns)
    console.print()


def confirm_action(prompt: str = "Are you sure you want to proceed?", default_no: bool = True) -> bool:
    """
    Prompt the user to confirm with y or n.
    Uses Questionary if available and interactive; falls back gracefully to standard input.
    """
    try:
        import questionary
        if sys.stdin.isatty():
            return questionary.confirm(prompt, default=not default_no).ask() or False
    except Exception:
        pass

    options = "[y/N]" if default_no else "[Y/n]"
    while True:
        try:
            choice = input(f"{prompt} {options}: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Operation cancelled.[/dim]")
            return False

        if not choice:
            return not default_no
        if choice in ("y", "yes"):
            return True
        if choice in ("n", "no"):
            return False

        console.print("[yellow]Please enter 'y' for Yes or 'n' for No.[/yellow]")


def pause(message: str = "\nPress Enter to continue...") -> None:
    """Pause execution until the user presses Enter."""
    try:
        input(message)
    except (KeyboardInterrupt, EOFError):
        console.print()
