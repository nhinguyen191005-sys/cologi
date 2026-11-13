from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.db import IntegrityError
from django.test import TestCase

from masterdata.models import Supplier, Outlet, TransportProvider
from masterdata.management.commands.import_masterdata import CONFIG


def excel_column(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def valid_sheets():
    sheets = {}

    values_by_sheet = {
        "04_Suppliers": {
            "supplier_code": "SUP-TEST-IMPORT",
            "supplier_name": "Import Test Supplier",
            "contact_name": None,
            "phone": None,
            "email": None,
            "address": None,
            "is_active": "1",
        },
        "05_Outlets": {
            "outlet_code": "OUT-TEST-IMPORT",
            "outlet_name": "Import Test Outlet",
            "address": "Da Nang",
            "contact_name": None,
            "phone": None,
            "is_active": "1",
        },
        "45_Transport_Providers": {
            "provider_code": "TP-TEST-IMPORT",
            "provider_name": "Import Test Provider",
            "provider_type": "EXTERNAL",
            "service_region": "Da Nang",
            "contact_email": "carrier@example.test",
            "is_active": "1",
        },
    }

    for config in CONFIG:
        fields = config["fields"]
        headers = {
            excel_column(index): field
            for index, field in enumerate(fields, start=1)
        }
        values = {
            excel_column(index): values_by_sheet[config["sheet"]][field]
            for index, field in enumerate(fields, start=1)
        }
        sheets[config["sheet"]] = [headers, values]

    return sheets


class ImportMasterdataCommandTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.workbook = Path(self.temp_dir.name) / "test.xlsx"
        self.workbook.write_bytes(b"mock workbook")
        self.sheets = valid_sheets()

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_command(self, *args):
        output = StringIO()
        with redirect_stdout(output):
            call_command(
                "import_masterdata",
                "--workbook",
                str(self.workbook),
                *args,
            )
        return output.getvalue()

    @patch(
        "masterdata.management.commands.import_masterdata.read_workbook"
    )
    def test_dry_run_does_not_create_records(self, mock_read):
        mock_read.return_value = self.sheets

        output = self.run_command()

        self.assertIn("DRY-RUN COMPLETE", output)
        self.assertIn("Database writes: NONE", output)
        self.assertEqual(Supplier.objects.count(), 0)
        self.assertEqual(Outlet.objects.count(), 0)
        self.assertEqual(TransportProvider.objects.count(), 0)

    @patch(
        "masterdata.management.commands.import_masterdata.read_workbook"
    )
    def test_existing_different_record_is_conflict(self, mock_read):
        mock_read.return_value = self.sheets
        Supplier.objects.create(
            supplier_code="SUP-TEST-IMPORT",
            supplier_name="Existing Supplier",
        )

        output = self.run_command()

        self.assertIn("CONFLICT", output)
        self.assertEqual(Supplier.objects.count(), 1)
        self.assertEqual(
            Supplier.objects.get(
                supplier_code="SUP-TEST-IMPORT"
            ).supplier_name,
            "Existing Supplier",
        )

    @patch(
        "masterdata.management.commands.import_masterdata.read_workbook"
    )
    def test_invalid_data_blocks_apply(self, mock_read):
        invalid_sheets = valid_sheets()
        invalid_sheets["04_Suppliers"][1]["G"] = "not-a-boolean"
        mock_read.return_value = invalid_sheets

        with patch(
            "masterdata.management.commands.import_masterdata.sys.stdin.isatty",
            return_value=True,
        ):
            with self.assertRaises(CommandError):
                self.run_command("--apply")

        self.assertEqual(Supplier.objects.count(), 0)
        self.assertEqual(Outlet.objects.count(), 0)
        self.assertEqual(TransportProvider.objects.count(), 0)

    @patch(
        "masterdata.management.commands.import_masterdata.read_workbook"
    )
    def test_cancelled_confirmation_does_not_write(self, mock_read):
        mock_read.return_value = self.sheets

        with patch(
            "masterdata.management.commands.import_masterdata.sys.stdin.isatty",
            return_value=True,
        ):
            with patch(
                "builtins.input",
                return_value="NO",
            ):
                with self.assertRaises(CommandError):
                    self.run_command("--apply")

        self.assertEqual(Supplier.objects.count(), 0)
        self.assertEqual(Outlet.objects.count(), 0)
        self.assertEqual(TransportProvider.objects.count(), 0)

    @patch(
        "masterdata.management.commands.import_masterdata.read_workbook"
    )
    def test_integrity_error_rolls_back_all_inserts(self, mock_read):
        mock_read.return_value = self.sheets

        with patch(
            "masterdata.management.commands.import_masterdata.sys.stdin.isatty",
            return_value=True,
        ):
            with patch("builtins.input", return_value="IMPORT"):
                with patch.object(
                    Outlet,
                    "save",
                    side_effect=IntegrityError("simulated failure"),
                ):
                    with self.assertRaises(CommandError):
                        self.run_command("--apply")

        self.assertEqual(Supplier.objects.count(), 0)
        self.assertEqual(Outlet.objects.count(), 0)
        self.assertEqual(TransportProvider.objects.count(), 0)
