from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.db import IntegrityError
from django.test import TestCase

from accounts.models import Role
from accounts.management.commands.import_roles import SOURCE_FIELDS


def valid_sheets():
    headers = {
        "A": "role_code",
        "B": "role_name",
        "C": "description",
        "D": "is_active",
    }

    records = [
        {
            "A": "PURCHASING_STAFF",
            "B": "Nhân viên mua hàng",
            "C": "Tạo và theo dõi nhu cầu mua hàng.",
            "D": "1",
        },
        {
            "A": "SUPPLIER",
            "B": "Nhà cung cấp hàng hóa",
            "C": "Xác nhận khả năng cung ứng.",
            "D": "1",
        },
        {
            "A": "TRANSPORT_PROVIDER",
            "B": "Đơn vị vận chuyển",
            "C": "Cung cấp năng lực vận chuyển.",
            "D": "1",
        },
        {
            "A": "MANAGER",
            "B": "Quản lý",
            "C": "Phê duyệt phương án.",
            "D": "1",
        },
    ]

    return {
        "01_Roles": [headers, *records, {}],
    }


class ImportRolesCommandTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.workbook = Path(self.temp_dir.name) / "test.xlsx"
        self.workbook.write_bytes(b"mock workbook")
        self.sheets = valid_sheets()

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_command(self, *args):
        output = StringIO()
        call_command(
            "import_roles",
            "--workbook",
            str(self.workbook),
            *args,
            stdout=output,
        )
        return output.getvalue()

    @patch(
        "accounts.management.commands.import_roles.read_workbook"
    )
    def test_dry_run_does_not_create_roles(self, mock_read):
        mock_read.return_value = self.sheets

        output = self.run_command()

        self.assertIn("DRY-RUN COMPLETE", output)
        self.assertIn("INSERT: 4", output)
        self.assertIn("ERROR: 0", output)
        self.assertIn("Database writes: NONE", output)
        self.assertEqual(Role.objects.count(), 0)

    @patch(
        "accounts.management.commands.import_roles.read_workbook"
    )
    def test_blank_excel_row_is_ignored(self, mock_read):
        mock_read.return_value = self.sheets

        output = self.run_command()

        self.assertIn("ERROR: 0", output)
        self.assertNotIn("Thiếu is_active", output)
        self.assertEqual(Role.objects.count(), 0)

    @patch(
        "accounts.management.commands.import_roles.read_workbook"
    )
    def test_existing_different_role_is_conflict(self, mock_read):
        mock_read.return_value = self.sheets

        Role.objects.create(
            code="MANAGER",
            name="Existing Manager",
            description="Existing description",
            is_active=True,
        )

        output = self.run_command()

        self.assertIn("CONFLICT: 1", output)
        self.assertEqual(Role.objects.count(), 1)
        self.assertEqual(
            Role.objects.get(code="MANAGER").name,
            "Existing Manager",
        )

    @patch(
        "accounts.management.commands.import_roles.read_workbook"
    )
    def test_invalid_data_blocks_apply(self, mock_read):
        invalid_sheets = valid_sheets()
        invalid_sheets["01_Roles"][1]["D"] = "invalid"
        mock_read.return_value = invalid_sheets

        with patch(
            "accounts.management.commands.import_roles.sys.stdin.isatty",
            return_value=True,
        ):
            with self.assertRaises(CommandError):
                self.run_command("--apply")

        self.assertEqual(Role.objects.count(), 0)

    @patch(
        "accounts.management.commands.import_roles.read_workbook"
    )
    def test_cancelled_confirmation_does_not_write(self, mock_read):
        mock_read.return_value = self.sheets

        with patch(
            "accounts.management.commands.import_roles.sys.stdin.isatty",
            return_value=True,
        ):
            with patch("builtins.input", return_value="NO"):
                with self.assertRaises(CommandError):
                    self.run_command("--apply")

        self.assertEqual(Role.objects.count(), 0)

    @patch(
        "accounts.management.commands.import_roles.read_workbook"
    )
    def test_integrity_error_rolls_back_all_roles(self, mock_read):
        mock_read.return_value = self.sheets

        with patch(
            "accounts.management.commands.import_roles.sys.stdin.isatty",
            return_value=True,
        ):
            with patch("builtins.input", return_value="IMPORT"):
                with patch.object(
                    Role,
                    "save",
                    side_effect=IntegrityError("simulated failure"),
                ):
                    with self.assertRaises(CommandError):
                        self.run_command("--apply")

        self.assertEqual(Role.objects.count(), 0)
