"""
Automated unit tests for Rich terminal display components in utils/display.py.
Verifies table formatting, semantic status badge styling, panel cards, and dashboard metrics.
"""

import unittest
from decimal import Decimal
from io import StringIO
import sys

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
