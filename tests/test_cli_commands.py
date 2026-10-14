"""
Automated unit tests for Typer CLI commands in cli.py.
Verifies argument parsing, exit codes, help messages, and output formatting.
"""

import unittest
from typer.testing import CliRunner

from cli import app
from database import get_connection, create_schema
from modules.patients import register_patient


class TestCliCommands(unittest.TestCase):
    """Test suite for Typer CLI commands."""

    def setUp(self):
        """Set up CLI test runner."""
        self.runner = CliRunner()

    def test_cli_help(self):
        """Verify root help output displays available subcommands."""
        result = self.runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Philippine Hospital Patient Management System", result.output)
        self.assertIn("patients", result.output)
        self.assertIn("appointments", result.output)
        self.assertIn("reports", result.output)
        self.assertIn("database", result.output)

    def test_patients_subcommands_help(self):
        """Verify patients subcommands list and search."""
        result = self.runner.invoke(app, ["patients", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("search", result.output)
        self.assertIn("view", result.output)

    def test_database_initialize_command(self):
        """Verify database initialize command executes successfully."""
        result = self.runner.invoke(app, ["database", "initialize"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("initialized", result.output)
        self.assertIn("successfully", result.output)

    def test_patients_list_command(self):
        """Verify patients list command returns exit code 0."""
        result = self.runner.invoke(app, ["patients", "list"])
        self.assertEqual(result.exit_code, 0)

    def test_appointments_list_command(self):
        """Verify appointments list command returns exit code 0."""
        result = self.runner.invoke(app, ["appointments", "list"])
        self.assertEqual(result.exit_code, 0)

    def test_reports_dashboard_command(self):
        """Verify reports dashboard command executes and renders cards."""
        result = self.runner.invoke(app, ["reports", "dashboard"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("PHILIPPINE HOSPITAL EXECUTIVE DASHBOARD", result.output)

    def test_reports_daily_command(self):
        """Verify reports daily registration command executes."""
        result = self.runner.invoke(app, ["reports", "daily"])
        self.assertEqual(result.exit_code, 0)

    def test_patient_view_nonexistent_fails(self):
        """Verify searching for an invalid patient ID returns exit code 1."""
        result = self.runner.invoke(app, ["patients", "view", "PAT-999999"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("not found", result.output)
