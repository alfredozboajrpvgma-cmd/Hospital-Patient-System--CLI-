"""
Automated unit tests for Rich terminal display components in utils/display.py.
Verifies table formatting, semantic status badge styling, panel cards, and dashboard metrics.
"""

import unittest
from decimal import Decimal
from io import StringIO
import sys
import os
from unittest.mock import patch

from utils import display

from utils.display import (
    print_header,
    print_subheader,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_table,
    render_card,
    render_dashboard,
    _style_cell_content
)


class TestRichDisplay(unittest.TestCase):
    """Test suite for Rich formatting utilities."""

    @unittest.skipUnless(display.RICH_AVAILABLE, "Rich is not installed")
    def test_colored_tables_at_phone_and_desktop_widths(self):
        from rich.console import Console
        from rich.text import Text
        for width in (32, 48, 100):
            with self.subTest(width=width):
                output = StringIO()
                with patch.dict(os.environ, {"TERM": "xterm"}):
                    terminal = Console(file=output, width=width, height=40, force_terminal=True,
                                       color_system="standard", legacy_windows=False)
                with patch.object(display, "console", terminal):
                    print_table(["Patient ID", "Name", "Status"],
                                [["PAT-1001", "Maria Santos", "Active"]])
                rendered = output.getvalue()
                self.assertIn("\x1b[", rendered)
                decoded = Text.from_ansi(rendered).plain
                self.assertIn("Maria Santos", decoded)
                self.assertIn("PAT-1001", decoded)
                self.assertIn("│", decoded)
                self.assertTrue(all(len(line) <= width for line in decoded.splitlines()))

    @unittest.skipUnless(display.RICH_AVAILABLE, "Rich is not installed")
    def test_phone_table_keeps_all_columns(self):
        from rich.console import Console
        output = StringIO()
        terminal = Console(file=output, width=40, height=40, legacy_windows=False)
        with patch.object(display, "console", terminal):
            print_table(["Patient ID", "Full Name", "Department", "Status"],
                        [["PAT-1001", "Maria Santos", "Cardiology", "Active"]])
        for value in ("Field", "Value", "Cardiology", "Active", "PAT-1001"):
            self.assertIn(value, output.getvalue())

    def test_semantic_status_styling(self):
        """Verify semantic badge markup is added to status columns."""
        self.assertIn("bold green", _style_cell_content("status", "Active"))
        self.assertIn("dim red", _style_cell_content("status", "Archived"))
        self.assertIn("bold yellow", _style_cell_content("status", "Scheduled"))
        self.assertIn("bold red", _style_cell_content("status", "Unpaid"))
        self.assertIn("bold red", _style_cell_content("triage_category", "Emergency"))
        self.assertIn("bold yellow", _style_cell_content("urgency", "Urgent"))
        self.assertIn("bold cyan", _style_cell_content("total_amount", "₱1,500.00"))

    def test_print_table_runs_without_error(self):
        """Verify print_table executes cleanly with rows and when empty."""
        headers = ["ID", "Name", "Status"]
        rows = [["PAT-1001", "Maria Santos", "Active"], ["PAT-1002", "Juan Luna", "Archived"]]
        # Should execute without throwing any exception
        print_table(headers, rows, alignments=["left", "left", "center"], title="Test Table")
        # Empty table
        print_table(headers, [], empty_message="No rows.")

    def test_render_card_runs_without_error(self):
        """Verify render_card creates key-value panel without exceptions."""
        data = {
            "Patient ID": "PAT-1001",
            "Full Name": "Maria Santos",
            "Status": "Active"
        }
        render_card("PATIENT PROFILE", data)

    def test_render_dashboard_runs_without_error(self):
        """Verify render_dashboard formats metrics across cards."""
        render_dashboard(
            active_patients=10,
            total_patients=12,
            appointments_today=3,
            patients_waiting=2,
            completed_consultations=5,
            unpaid_bills_count=1,
            total_billed=Decimal("5000.00"),
            total_paid=Decimal("4000.00"),
            outstanding_balance=Decimal("1000.00")
        )

    def test_status_alert_messages_run(self):
        """Verify alert banners execute cleanly."""
        print_header("Test Hospital Header", subtitle="Test Subtitle")
        print_subheader("Test Subheader")
        print_success("Operation completed successfully.")
        print_error("Failed to perform action.")
        print_warning("Notice regarding changes.")
        print_info("Informational advisory.")
