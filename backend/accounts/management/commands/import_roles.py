import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, IntegrityError

from accounts.models import Role
from masterdata.management.commands.import_masterdata import read_workbook


SHEET_NAME = "01_Roles"

SOURCE_FIELDS = [
    "role_code",
    "role_name",
    "description",
    "is_active",
]

MODEL_FIELDS = {
    "role_code": "code",
    "role_name": "name",
    "description": "description",
    "is_active": "is_active",
}


def normalize(field, value):
    if value is None or str(value).strip() == "":
        if field == "description":
            return ""
        if field == "is_active":
            raise ValueError("Thiếu is_active")
        return None

    if field == "is_active":
        value = str(value).strip().lower()

        if value in ("true", "1", "yes", "y"):
            return True
        if value in ("false", "0", "no", "n"):
            return False

        raise ValueError(f"is_active không hợp lệ: {value}")

    return str(value).strip()


def build_plan(sheets):
    plan = []
    errors = []
    conflicts = []

    if SHEET_NAME not in sheets:
        return plan, [f"Không tìm thấy sheet {SHEET_NAME}"], conflicts

    rows = sheets[SHEET_NAME]
    header_index = None
    headers = {}

    for index, row in enumerate(rows):
        candidate = {
            value.strip(): column
            for column, value in row.items()
            if value and value.strip()
        }

        if all(field in candidate for field in SOURCE_FIELDS):
            header_index = index
            headers = candidate
            break

    if header_index is None:
        return plan, [
            f"{SHEET_NAME}: không tìm thấy header hợp lệ"
        ], conflicts

    seen = set()

    for row_number, row in enumerate(
        rows[header_index + 1:],
        start=header_index + 2,
    ):
        if not any(
            value is not None and str(value).strip()
            for value in row.values()
        ):
            continue

        try:
            source_record = {
                field: normalize(field, row.get(headers[field]))
                for field in SOURCE_FIELDS
            }

            if all(value is None for value in source_record.values()):
                continue

            code = source_record["role_code"]

            if not code:
                raise ValueError("Thiếu role_code")

            if code in seen:
                raise ValueError(f"Trùng role_code trong Excel: {code}")

            seen.add(code)

            record = {
                MODEL_FIELDS[field]: value
                for field, value in source_record.items()
            }

            instance = Role(**record)
            instance.full_clean(validate_unique=False)

            existing = Role.objects.filter(code=code).first()

            if existing is None:
                status = "INSERT"
            else:
                changed = [
                    field
                    for field in record
                    if getattr(existing, field) != record[field]
                ]

                if changed:
                    status = "CONFLICT"
                    conflicts.append(
                        f"{SHEET_NAME} row {row_number}: "
                        f"{code}, fields: {', '.join(changed)}"
                    )
                else:
                    status = "UNCHANGED"

            plan.append((record, status, code))

        except Exception as exc:
            errors.append(
                f"{SHEET_NAME} row {row_number}: {exc}"
            )

    return plan, errors, conflicts


class Command(BaseCommand):
    help = (
        "Import the four business roles from Dataset V7. "
        "Default mode is read-only."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--workbook",
            default=str(
                Path(settings.BASE_DIR).parent
                / "docs" / "source" / "CoLogi_Dataset_v7.xlsx"
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Request actual import after explicit confirmation.",
        )

    def handle(self, *args, **options):
        workbook = Path(options["workbook"])

        if not workbook.is_file():
            raise CommandError(
                f"Không tìm thấy workbook: {workbook}"
            )

        try:
            sheets = read_workbook(workbook)
        except Exception as exc:
            raise CommandError(
                f"Không đọc được workbook: {exc}"
            ) from exc

        self.stdout.write("\n=== ROLE IMPORT PLAN ===")
        self.stdout.write(f"Workbook: {workbook}")
        self.stdout.write(f"Source sheet: {SHEET_NAME}")

        plan, errors, conflicts = build_plan(sheets)

        insert_count = sum(
            status == "INSERT" for _, status, _ in plan
        )
        unchanged_count = sum(
            status == "UNCHANGED" for _, status, _ in plan
        )

        for _, status, code in plan:
            self.stdout.write(f"{status}: {code}")

        self.stdout.write("\n=== TOTAL ===")
        self.stdout.write(f"INSERT: {insert_count}")
        self.stdout.write(f"UNCHANGED: {unchanged_count}")
        self.stdout.write(f"CONFLICT: {len(conflicts)}")
        self.stdout.write(f"ERROR: {len(errors)}")

        if errors:
            self.stdout.write("\nValidation errors:")
            for error in errors:
                self.stdout.write(f"- {error}")

        if conflicts:
            self.stdout.write(
                "\nConflicts; existing records will NOT be overwritten:"
            )
            for conflict in conflicts:
                self.stdout.write(f"- {conflict}")

        if not options["apply"]:
            self.stdout.write("\nDRY-RUN COMPLETE")
            self.stdout.write("Database writes: NONE")
            return

        if errors or conflicts:
            raise CommandError(
                "Import bị chặn: cần xử lý toàn bộ ERROR/CONFLICT trước."
            )

        if not sys.stdin.isatty():
            raise CommandError(
                "Chế độ --apply cần terminal tương tác để xác nhận."
            )

        self.stdout.write(
            "\nChỉ tạo Role chưa tồn tại. Không UPDATE, "
            "không DELETE, không ép ID Excel."
        )

        confirmation = input(
            'Nhập chính xác "IMPORT" để xác nhận ghi database: '
        )

        if confirmation != "IMPORT":
            raise CommandError(
                "Đã hủy import. Database không thay đổi."
            )

        try:
            with transaction.atomic():
                fresh_sheets = read_workbook(workbook)
                fresh_plan, fresh_errors, fresh_conflicts = (
                    build_plan(fresh_sheets)
                )

                if fresh_errors or fresh_conflicts:
                    raise CommandError(
                        "Dữ liệu thay đổi hoặc phát sinh lỗi. "
                        "Rollback toàn bộ."
                    )

                created_count = 0

                for record, status, code in fresh_plan:
                    if status != "INSERT":
                        continue

                    instance = Role(**record)
                    instance.full_clean()
                    instance.save(force_insert=True)
                    created_count += 1

        except IntegrityError as exc:
            raise CommandError(
                "Lỗi ràng buộc database. Đã rollback toàn bộ."
            ) from exc

        self.stdout.write("\nIMPORT SUCCESS")
        self.stdout.write(f"Created roles: {created_count}")
        self.stdout.write("Database transaction: COMMITTED")
