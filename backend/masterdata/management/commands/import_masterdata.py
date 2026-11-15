import sys
import zipfile
import re
import xml.etree.ElementTree as ET

from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, IntegrityError

from masterdata.models import (
    Supplier,
    Outlet,
    TransportProvider,
    CargoCategory,
    VehicleType,
    VehicleCargoCompatibility,
)


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
    {
        "sheet": "07_Cargo_Categories",
        "model": CargoCategory,
        "key": "category_code",
        "fields": [
            "category_code", "category_name",
            "description", "is_active",
        ],
    },
    {
        "sheet": "09_Vehicle_Types",
        "model": VehicleType,
        "key": "vehicle_code",
        "fields": [
            "vehicle_code", "vehicle_name",
            "capacity_kg", "description", "is_active",
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

    if field in ("is_active", "is_supported"):
        value = str(value).strip().lower()

        if value in ("true", "1", "yes", "y"):
            return True

        if value in ("false", "0", "no", "n"):
            return False

        raise ValueError(f"{field} không hợp lệ: {value}")

    return str(value).strip()


def extract_records(sheets, sheet_name, fields):
    if sheet_name not in sheets:
        raise ValueError(f"Không tìm thấy sheet {sheet_name}")

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
        raise ValueError(
            f"{sheet_name}: không tìm thấy header hợp lệ"
        )

    records = []

    for row_number, row in enumerate(
        rows[header_index + 1:],
        start=header_index + 2,
    ):
        record = {
            field: normalize(field, row.get(headers[field]))
            for field in fields
        }

        if all(value is None for value in record.values()):
            continue

        records.append((row_number, record))

    return records


def build_masterdata_plan(sheets):
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

        try:
            rows = extract_records(sheets, sheet_name, fields)
        except Exception as exc:
            errors.append(str(exc))
            continue

        seen = set()
        counts = {
            "INSERT": 0,
            "UNCHANGED": 0,
            "CONFLICT": 0,
            "ERROR": 0,
        }

        for row_number, record in rows:
            try:
                key = record[key_field]

                if not key:
                    raise ValueError("Thiếu khóa tự nhiên")

                if key in seen:
                    raise ValueError(
                        f"Trùng mã trong Excel: {key}"
                    )

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
                    changed = [
                        field for field in fields
                        if getattr(existing, field) != record[field]
                    ]

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


def workbook_id(value):
    if value is None or str(value).strip() == "":
        raise ValueError("Thiếu Excel ID")

    try:
        number = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError(f"Excel ID không hợp lệ: {value}") from exc

    if number != number.to_integral_value():
        raise ValueError(f"Excel ID phải là số nguyên: {value}")

    return int(number)


def build_vehicle_compatibility_plan(sheets, master_plan):
    sheet_name = "10_Vehicle_Cargo"
    fields = [
        "vehicle_type_id",
        "cargo_category_id",
        "is_supported",
        "source",
    ]

    plan = []
    errors = []
    conflicts = []
    counts = {
        "INSERT": 0,
        "UNCHANGED": 0,
        "CONFLICT": 0,
        "ERROR": 0,
    }

    print(f"\n=== {sheet_name} ===")

    try:
        vehicle_rows = extract_records(
            sheets,
            "09_Vehicle_Types",
            ["id", "vehicle_code"],
        )
        cargo_rows = extract_records(
            sheets,
            "07_Cargo_Categories",
            ["id", "category_code"],
        )
        compatibility_rows = extract_records(
            sheets,
            sheet_name,
            fields,
        )

        vehicle_map = {}
        cargo_map = {}

        for row_number, record in vehicle_rows:
            excel_id = workbook_id(record["id"])
            code = record["vehicle_code"]

            if not code or excel_id in vehicle_map:
                raise ValueError(
                    f"09_Vehicle_Types row {row_number}: "
                    "ID hoặc vehicle_code bị thiếu/trùng"
                )

            vehicle_map[excel_id] = code

        for row_number, record in cargo_rows:
            excel_id = workbook_id(record["id"])
            code = record["category_code"]

            if not code or excel_id in cargo_map:
                raise ValueError(
                    f"07_Cargo_Categories row {row_number}: "
                    "ID hoặc category_code bị thiếu/trùng"
                )

            cargo_map[excel_id] = code

        planned_vehicles = {
            record["vehicle_code"]
            for model, record, status, key in master_plan
            if model is VehicleType and status == "INSERT"
        }

        planned_categories = {
            record["category_code"]
            for model, record, status, key in master_plan
            if model is CargoCategory and status == "INSERT"
        }

        seen = set()

        for row_number, record in compatibility_rows:
            try:
                vehicle_excel_id = workbook_id(
                    record["vehicle_type_id"]
                )
                cargo_excel_id = workbook_id(
                    record["cargo_category_id"]
                )

                if vehicle_excel_id not in vehicle_map:
                    raise ValueError(
                        f"Không tìm thấy VehicleType Excel ID "
                        f"{vehicle_excel_id}"
                    )

                if cargo_excel_id not in cargo_map:
                    raise ValueError(
                        f"Không tìm thấy CargoCategory Excel ID "
                        f"{cargo_excel_id}"
                    )

                vehicle_code = vehicle_map[vehicle_excel_id]
                category_code = cargo_map[cargo_excel_id]

                key = f"{vehicle_code}|{category_code}"

                if key in seen:
                    raise ValueError(
                        f"Trùng cặp Vehicle-Cargo: {key}"
                    )

                seen.add(key)

                if record["is_supported"] is None:
                    raise ValueError("Thiếu is_supported")

                if not record["source"]:
                    raise ValueError("Thiếu source")

                vehicle = VehicleType.objects.filter(
                    vehicle_code=vehicle_code
                ).first()

                category = CargoCategory.objects.filter(
                    category_code=category_code
                ).first()

                if vehicle is None and vehicle_code not in planned_vehicles:
                    raise ValueError(
                        f"VehicleType chưa tồn tại hoặc chưa được lập kế hoạch: "
                        f"{vehicle_code}"
                    )

                if category is None and category_code not in planned_categories:
                    raise ValueError(
                        f"CargoCategory chưa tồn tại hoặc chưa được lập kế hoạch: "
                        f"{category_code}"
                    )

                existing = None

                if vehicle is not None and category is not None:
                    existing = VehicleCargoCompatibility.objects.filter(
                        vehicle_type=vehicle,
                        cargo_category=category,
                    ).first()

                compatibility_record = {
                    "vehicle_type_code": vehicle_code,
                    "cargo_category_code": category_code,
                    "is_supported": record["is_supported"],
                    "source": record["source"],
                }

                if existing is None:
                    status = "INSERT"
                else:
                    changed = []

                    if existing.is_supported != record["is_supported"]:
                        changed.append("is_supported")

                    if existing.source != record["source"]:
                        changed.append("source")

                    if changed:
                        status = "CONFLICT"
                        conflicts.append(
                            f"{sheet_name} row {row_number}: "
                            f"{key}, fields: {', '.join(changed)}"
                        )
                    else:
                        status = "UNCHANGED"

                counts[status] += 1
                plan.append((
                    VehicleCargoCompatibility,
                    compatibility_record,
                    status,
                    key,
                ))
                print(f"{status}: {key}")

            except Exception as exc:
                counts["ERROR"] += 1
                errors.append(
                    f"{sheet_name} row {row_number}: {exc}"
                )
                print(f"ERROR row {row_number}: {exc}")

    except Exception as exc:
        errors.append(f"{sheet_name}: {exc}")

    print("Summary:", counts)

    return plan, errors, conflicts, counts


def build_plan(sheets):
    master_plan, errors, conflicts, summaries = (
        build_masterdata_plan(sheets)
    )

    compatibility_plan, compatibility_errors, compatibility_conflicts, compatibility_summary = (
        build_vehicle_compatibility_plan(sheets, master_plan)
    )

    plan = master_plan + compatibility_plan
    errors.extend(compatibility_errors)
    conflicts.extend(compatibility_conflicts)
    summaries["10_Vehicle_Cargo"] = compatibility_summary

    return plan, errors, conflicts, summaries


class Command(BaseCommand):
    help = (
        "Import master data and vehicle-cargo configuration "
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
            raise CommandError(
                "Đã hủy import. Database không thay đổi."
            )

        try:
            with transaction.atomic():
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

                    if model is VehicleCargoCompatibility:
                        vehicle = VehicleType.objects.get(
                            vehicle_code=record["vehicle_type_code"]
                        )
                        category = CargoCategory.objects.get(
                            category_code=record["cargo_category_code"]
                        )

                        instance = VehicleCargoCompatibility(
                            vehicle_type=vehicle,
                            cargo_category=category,
                            is_supported=record["is_supported"],
                            source=record["source"],
                        )
                    else:
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