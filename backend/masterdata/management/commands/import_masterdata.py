import sys
import zipfile
import re
import xml.etree.ElementTree as ET

from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, IntegrityError

from masterdata.models import Supplier, Outlet, TransportProvider


NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}

CONFIG = [
    {
        "sheet": "04_Suppliers",
        "model": Supplier,
        "key": "supplier_code",
        "fields": [
            "supplier_code", "supplier_name", "contact_name",
            "phone", "email", "address", "is_active",
        ],
    },
    {
        "sheet": "05_Outlets",
        "model": Outlet,
        "key": "outlet_code",
        "fields": [
            "outlet_code", "outlet_name", "address",
            "contact_name", "phone", "is_active",
        ],
    },
    {
        "sheet": "45_Transport_Providers",
        "model": TransportProvider,
        "key": "provider_code",
        "fields": [
            "provider_code", "provider_name", "provider_type",
            "service_region", "contact_email", "is_active",
        ],
    },
]


def read_workbook(path):
    with zipfile.ZipFile(path) as workbook_file:
        workbook = ET.fromstring(
            workbook_file.read("xl/workbook.xml")
        )
        relationships = ET.fromstring(
            workbook_file.read("xl/_rels/workbook.xml.rels")
        )

        targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in relationships.findall("p:Relationship", NS)
        }

        shared = []
        if "xl/sharedStrings.xml" in workbook_file.namelist():
            root = ET.fromstring(
                workbook_file.read("xl/sharedStrings.xml")
            )
            for item in root.findall("m:si", NS):
                shared.append(
                    "".join(
                        node.text or ""
                        for node in item.iter(f"{{{NS['m']}}}t")
                    )
                )

        sheets = {}

        for sheet in workbook.find("m:sheets", NS):
            name = sheet.attrib["name"]
            rel_id = sheet.attrib[f"{{{NS['r']}}}id"]
            target = targets[rel_id].lstrip("/")

            if not target.startswith("xl/"):
                target = str(PurePosixPath("xl") / target)

            root = ET.fromstring(workbook_file.read(target))
            rows = []

            for row in root.findall(".//m:sheetData/m:row", NS):
                values = {}

                for cell in row.findall("m:c", NS):
                    match = re.match(
                        r"[A-Z]+", cell.attrib.get("r", "")
                    )
                    if not match:
                        continue

                    cell_type = cell.attrib.get("t")
                    value_node = cell.find("m:v", NS)

                    if cell_type == "inlineStr":
                        value = "".join(
                            node.text or ""
                            for node in cell.iter(f"{{{NS['m']}}}t")
                        )
                    elif value_node is None:
                        value = None
                    else:
                        value = value_node.text
                        if cell_type == "s":
                            value = shared[int(value)]

                    values[match.group()] = value

                rows.append(values)

            sheets[name] = rows

        return sheets


def normalize(field, value):
    if value is None or str(value).strip() == "":
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
    summaries = {}

    for config in CONFIG:
        sheet_name = config["sheet"]
        model = config["model"]
        key_field = config["key"]
        fields = config["fields"]

        print(f"\n=== {sheet_name} ===")

        if sheet_name not in sheets:
            errors.append(f"Không tìm thấy sheet {sheet_name}")
            continue

        rows = sheets[sheet_name]
        header_index = None
        headers = {}

        for index, row in enumerate(rows):
            candidate = {
                value.strip(): col
                for col, value in row.items()
                if value and value.strip()
            }

            if all(field in candidate for field in fields):
                header_index = index
                headers = candidate
                break

        if header_index is None:
            errors.append(
                f"{sheet_name}: không tìm thấy header hợp lệ"
            )
            continue

        seen = set()
        counts = {
            "INSERT": 0,
            "UNCHANGED": 0,
            "CONFLICT": 0,
            "ERROR": 0,
        }

        for row_number, row in enumerate(
            rows[header_index + 1:],
            start=header_index + 2,
        ):
            record = {}

            try:
                for field in fields:
                    record[field] = normalize(
                        field, row.get(headers[field])
                    )

                if all(value is None for value in record.values()):
                    continue

                key = record[key_field]

                if not key:
                    raise ValueError("Thiếu khóa tự nhiên")

                if key in seen:
                    raise ValueError(f"Trùng mã trong Excel: {key}")

                seen.add(key)

                for field in fields:
                    model_field = model._meta.get_field(field)
                    value = record[field]

                    if (
                        value is None
                        and model_field.blank
                        and not model_field.null
                    ):
                        value = ""

                    record[field] = model_field.clean(value, None)

                existing = model.objects.filter(
                    **{key_field: key}
                ).first()

                if existing is None:
                    status = "INSERT"
                else:
                    changed = []

                    for field in fields:
                        current = getattr(existing, field)
                        if current != record[field]:
                            changed.append(field)

                    if changed:
                        status = "CONFLICT"
                        conflicts.append(
                            f"{sheet_name} row {row_number}: "
                            f"{key}, fields: {', '.join(changed)}"
                        )
                    else:
                        status = "UNCHANGED"

                counts[status] += 1
                plan.append((model, record, status, key))

                print(f"{status}: {key}")

            except Exception as exc:
                counts["ERROR"] += 1
                errors.append(
                    f"{sheet_name} row {row_number}: {exc}"
                )
                print(f"ERROR row {row_number}: {exc}")

        summaries[sheet_name] = counts
        print("Summary:", counts)

    return plan, errors, conflicts, summaries


class Command(BaseCommand):
    help = (
        "Import Suppliers, Outlets and Transport Providers "
        "from Dataset V7. Default mode is read-only."
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

        print("\n=== MASTER DATA IMPORT PLAN ===")
        print("Workbook:", workbook)

        plan, errors, conflicts, summaries = build_plan(sheets)

        insert_count = sum(
            1 for _, _, status, _ in plan if status == "INSERT"
        )
        unchanged_count = sum(
            1 for _, _, status, _ in plan if status == "UNCHANGED"
        )

        print("\n=== TOTAL ===")
        print("INSERT:", insert_count)
        print("UNCHANGED:", unchanged_count)
        print("CONFLICT:", len(conflicts))
        print("ERROR:", len(errors))

        if errors:
            print("\nValidation errors:")
            for error in errors:
                print("-", error)

        if conflicts:
            print("\nConflicts; existing records will NOT be overwritten:")
            for conflict in conflicts:
                print("-", conflict)

        if not options["apply"]:
            print("\nDRY-RUN COMPLETE")
            print("Database writes: NONE")
            return

        if errors or conflicts:
            raise CommandError(
                "Import bị chặn: cần xử lý toàn bộ ERROR/CONFLICT trước."
            )

        if not sys.stdin.isatty():
            raise CommandError(
                "Chế độ --apply cần terminal tương tác để xác nhận."
            )

        print("\nChỉ các bản ghi INSERT mới được tạo.")
        print("Không UPDATE, không DELETE, không ép ID Excel.")
        confirmation = input(
            'Nhập chính xác "IMPORT" để xác nhận ghi database: '
        )

        if confirmation != "IMPORT":
            raise CommandError("Đã hủy import. Database không thay đổi.")

        try:
            with transaction.atomic():
                # Re-check the plan inside the transaction.
                fresh_sheets = read_workbook(workbook)
                fresh_plan, fresh_errors, fresh_conflicts, _ = (
                    build_plan(fresh_sheets)
                )

                if fresh_errors or fresh_conflicts:
                    raise CommandError(
                        "Dữ liệu thay đổi hoặc phát sinh lỗi. "
                        "Rollback toàn bộ."
                    )

                created_count = 0

                for model, record, status, key in fresh_plan:
                    if status != "INSERT":
                        continue

                    instance = model(**record)
                    instance.save(force_insert=True)
                    created_count += 1

        except IntegrityError as exc:
            raise CommandError(
                "Lỗi ràng buộc database. Đã rollback toàn bộ."
            ) from exc

        print("\nIMPORT SUCCESS")
        print("Created records:", created_count)
        print("Database transaction: COMMITTED")
