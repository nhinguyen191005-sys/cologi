import re
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User, UserRole
from demands.models import (
    DeliveryDemand,
    DemandItem,
    SupplierConfirmation,
    SupplierRequest,
    SupplierItemPromise,
)

from masterdata.management.commands.import_masterdata import read_workbook
from masterdata.models import (
    CargoCategory,
    Item,
    Outlet,
    Supplier,
    SupplierItem,
)


MASTERDATA_CONFIG = (
    {
        "sheet": "07_Cargo_Categories",
        "model": CargoCategory,
        "key": "category_code",
        "fields": (
            "category_code",
            "category_name",
            "description",
            "is_active",
        ),
    },
)


def find_sheet_records(sheets, sheet_name, required_headers):
    """Return normalized dictionaries from a sheet using its actual header row."""
    if sheet_name not in sheets:
        raise ValueError(f"Không tìm thấy sheet {sheet_name}")

    rows = sheets[sheet_name]
    header_index = None
    headers = {}

    for index, row in enumerate(rows):
        candidate = {
            str(value).strip(): column
            for column, value in row.items()
            if value is not None and str(value).strip()
        }
        if all(header in candidate for header in required_headers):
            header_index = index
            headers = candidate
            break

    if header_index is None:
        raise ValueError(
            f"{sheet_name}: không tìm thấy header "
            f"{', '.join(required_headers)}"
        )

    records = []
    for row_number, row in enumerate(
        rows[header_index + 1:],
        start=header_index + 2,
    ):
        record = {
            header: row.get(headers[header])
            for header in required_headers
        }
        if all(value is None or str(value).strip() == "" for value in record.values()):
            continue
        record["_row_number"] = row_number
        records.append(record)

    return records


def clean_text(value, *, required=False, default=None):
    if value is None or str(value).strip() == "":
        if required:
            raise ValueError("Thiếu giá trị bắt buộc")
        return default
    return str(value).strip()


def clean_bool(value):
    value = clean_text(value, required=True).lower()
    if value in ("true", "1", "yes", "y"):
        return True
    if value in ("false", "0", "no", "n"):
        return False
    raise ValueError(f"Giá trị boolean không hợp lệ: {value}")


def clean_decimal(value, *, required=True):
    value = clean_text(value, required=required)
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Số thập phân không hợp lệ: {value}") from exc


def clean_integer(value, *, required=True):
    value = clean_text(value, required=required)
    if value is None:
        return None
    number = Decimal(value)
    if number != number.to_integral_value():
        raise ValueError(f"Số nguyên không hợp lệ: {value}")
    return int(number)


def excel_id_map(sheets, sheet_name, id_header, code_header):
    """Map workbook-local numeric IDs to business codes; never DB primary keys."""
    rows = find_sheet_records(
        sheets,
        sheet_name,
        (id_header, code_header),
    )
    result = {}
    for row in rows:
        excel_id = clean_integer(row[id_header])
        code = clean_text(row[code_header], required=True)
        if excel_id in result:
            raise ValueError(
                f"{sheet_name}: trùng Excel ID {excel_id}"
            )
        result[excel_id] = code
    return result



def classify_record(model, key_filter, record, label, relation_fields=None):
    """Classify INSERT/UNCHANGED/CONFLICT without updating existing rows."""
    relation_fields = relation_fields or {}
    existing = model.objects.filter(**key_filter).first()
    if existing is None:
        return "INSERT", None

    changed = []
    for field, value in record.items():
        if field in relation_fields:
            relation_name, related_code_field = relation_fields[field]
            related = getattr(existing, relation_name)
            actual = getattr(related, related_code_field)
            if actual != value:
                changed.append(field)
        elif getattr(existing, field) != value:
            changed.append(field)

    if changed:
        return "CONFLICT", f"{label}: khác field {', '.join(changed)}"
    return "UNCHANGED", None



def excel_datetime(value, *, required=True):
    """Convert Excel serial or ISO-like value to a timezone-aware datetime."""
    raw = clean_text(value, required=required)
    if raw is None:
        return None

    try:
        number = Decimal(raw)
        if number >= 1:
            total_seconds = round(float(number) * 86400)
            result = datetime(1899, 12, 30) + timedelta(
                seconds=total_seconds
            )
        else:
            raise ValueError
    except (InvalidOperation, ValueError):
        result = datetime.fromisoformat(raw)

    if timezone.is_naive(result):
        result = timezone.make_aware(
            result,
            timezone=ZoneInfo(settings.COLOGI_BUSINESS_TIME_ZONE),
        )
    return result


def excel_date(value, *, required=True):
    raw = clean_text(value, required=required)
    if raw is None:
        return None
    try:
        number = Decimal(raw)
        return (datetime(1899, 12, 30) + timedelta(days=float(number))).date()
    except (InvalidOperation, ValueError):
        return date.fromisoformat(raw[:10])


def excel_time(value, *, required=True):
    raw = clean_text(value, required=required)
    if raw is None:
        return None
    try:
        number = Decimal(raw)
        seconds = int(round(float(number) * 86400))
        seconds %= 86400
        return (datetime.min + timedelta(seconds=seconds)).time()
    except (InvalidOperation, ValueError):
        return time.fromisoformat(raw)


def get_purchasing_actor(email):
    if not email:
        email = "user01@cologi.demo"

    user = User.objects.filter(
        email__iexact=email,
        is_active=True,
    ).first()
    if user is None:
        raise ValueError(
            f"Không tìm thấy User active với email {email}"
        )

    has_role = UserRole.objects.filter(
        user=user,
        is_active=True,
        role__code="PURCHASING_STAFF",
        role__is_active=True,
    ).exists()
    if not has_role:
        raise ValueError(
            f"{email} không có UserRole PURCHASING_STAFF active"
        )
    return user

def build_masterdata_plan(sheets):
    plan, errors, conflicts, summaries = [], [], [], {}

    # Resolve workbook-local IDs to business codes, never database IDs.
    category_ids = excel_id_map(
        sheets, "07_Cargo_Categories", "id", "category_code"
    )
    item_ids = excel_id_map(
        sheets, "40_Items", "id", "item_code"
    )
    supplier_ids = excel_id_map(
        sheets, "04_Suppliers", "id", "supplier_code"
    )

    # 1. Cargo categories.
    category_records = find_sheet_records(
        sheets, "07_Cargo_Categories",
        ("id", "category_code", "category_name", "description", "is_active"),
    )
    category_codes = set()
    category_counts = {"INSERT": 0, "UNCHANGED": 0, "CONFLICT": 0}

    for row in category_records:
        try:
            code = clean_text(row["category_code"], required=True)
            if code in category_codes:
                raise ValueError(f"Trùng category_code: {code}")
            category_codes.add(code)
            record = {
                "category_code": code,
                "category_name": clean_text(row["category_name"], required=True),
                "description": clean_text(row["description"], default=None),
                "is_active": clean_bool(row["is_active"]),
            }
            status, conflict = classify_record(
                CargoCategory, {"category_code": code}, record,
                f"07_Cargo_Categories row {row['_row_number']} / {code}",
            )
            category_counts[status] += 1
            if conflict:
                conflicts.append(conflict)
            plan.append((CargoCategory, record, status, code))
        except Exception as exc:
            errors.append(f"07_Cargo_Categories row {row['_row_number']}: {exc}")

    summaries["07_Cargo_Categories"] = category_counts

    # 2. Items. cargo_category_code is a workbook business-key reference.
    item_records = find_sheet_records(
        sheets, "40_Items",
        ("id", "item_code", "item_name", "cargo_category_id",
         "weight_unit", "item_description", "is_active"),
    )
    item_codes = set()
    item_counts = {"INSERT": 0, "UNCHANGED": 0, "CONFLICT": 0}
    db_category_codes = set(
        CargoCategory.objects.values_list("category_code", flat=True)
    )
    available_category_codes = db_category_codes | category_codes

    for row in item_records:
        try:
            code = clean_text(row["item_code"], required=True)
            if code in item_codes:
                raise ValueError(f"Trùng item_code: {code}")
            item_codes.add(code)

            category_excel_id = clean_integer(row["cargo_category_id"])
            category_code = category_ids.get(category_excel_id)
            if not category_code:
                raise ValueError(
                    f"Không ánh xạ được cargo_category_id={category_excel_id}"
                )
            if category_code not in available_category_codes:
                raise ValueError(
                    f"CargoCategory {category_code} không tồn tại "
                    "trong DB hoặc kế hoạch import"
                )

            record = {
                "item_name": clean_text(row["item_name"], required=True),
                "cargo_category_code": category_code,
                "weight_unit": clean_text(row["weight_unit"], required=True),
                "item_description": clean_text(
                    row["item_description"], default=None
                ),
                "is_active": clean_bool(row["is_active"]),
            }
            status, conflict = classify_record(
                Item, {"item_code": code}, record,
                f"40_Items row {row['_row_number']} / {code}",
                {"cargo_category_code": ("cargo_category", "category_code")},
            )
            item_counts[status] += 1
            if conflict:
                conflicts.append(conflict)
            plan.append((Item, {"item_code": code, **record}, status, code))
        except Exception as exc:
            errors.append(f"40_Items row {row['_row_number']}: {exc}")

    summaries["40_Items"] = item_counts

    # 3. Supplier-item offers. Excel IDs are translated to business codes.
    supplier_item_records = find_sheet_records(
        sheets, "41_Supplier_Items",
        ("id", "supplier_id", "item_id", "unit_price_vnd_per_kg",
         "max_daily_supply_kg", "lead_time_hours", "minimum_order_kg",
         "offer_status"),
    )
    db_supplier_codes = set(
        Supplier.objects.values_list("supplier_code", flat=True)
    )
    available_item_codes = set(
        Item.objects.values_list("item_code", flat=True)
    ) | item_codes
    supplier_item_pairs = set()
    supplier_item_counts = {"INSERT": 0, "UNCHANGED": 0, "CONFLICT": 0}

    for row in supplier_item_records:
        try:
            supplier_excel_id = clean_integer(row["supplier_id"])
            item_excel_id = clean_integer(row["item_id"])
            supplier_code = supplier_ids.get(supplier_excel_id)
            item_code = item_ids.get(item_excel_id)

            if not supplier_code:
                raise ValueError(
                    f"Không ánh xạ được supplier_id={supplier_excel_id}"
                )
            if not item_code:
                raise ValueError(f"Không ánh xạ được item_id={item_excel_id}")
            if supplier_code not in db_supplier_codes:
                raise ValueError(
                    f"Supplier {supplier_code} chưa tồn tại trong DB"
                )
            if item_code not in available_item_codes:
                raise ValueError(
                    f"Item {item_code} không tồn tại trong DB hoặc kế hoạch import"
                )

            pair = (supplier_code, item_code)
            if pair in supplier_item_pairs:
                raise ValueError(f"Trùng cặp supplier/item: {pair}")
            supplier_item_pairs.add(pair)

            price = clean_decimal(row["unit_price_vnd_per_kg"])
            max_daily = clean_decimal(row["max_daily_supply_kg"], required=False)
            lead_time = clean_integer(row["lead_time_hours"], required=False)
            minimum = clean_decimal(row["minimum_order_kg"], required=False)
            offer_status = clean_text(row["offer_status"], required=True).upper()

            if price < 0:
                raise ValueError("unit_price_vnd_per_kg không được âm")
            if max_daily is not None and max_daily <= 0:
                raise ValueError("max_daily_supply_kg phải lớn hơn 0")
            if lead_time is not None and lead_time < 0:
                raise ValueError("lead_time_hours không được âm")
            if minimum is not None and minimum < 0:
                raise ValueError("minimum_order_kg không được âm")
            if offer_status not in {"ACTIVE", "INACTIVE"}:
                raise ValueError(f"offer_status không hợp lệ: {offer_status}")

            record = {
                "supplier_code": supplier_code,
                "item_code": item_code,
                "unit_price_vnd_per_kg": price,
                "max_daily_supply_kg": max_daily,
                "lead_time_hours": lead_time,
                "minimum_order_kg": minimum,
                "offer_status": offer_status,
            }
            status, conflict = classify_record(
                SupplierItem,
                {
                    "supplier__supplier_code": supplier_code,
                    "item__item_code": item_code,
                },
                record,
                f"41_Supplier_Items row {row['_row_number']} / {pair}",
                {
                    "supplier_code": ("supplier", "supplier_code"),
                    "item_code": ("item", "item_code"),
                },
            )
            supplier_item_counts[status] += 1
            if conflict:
                conflicts.append(conflict)
            plan.append((SupplierItem, record, status, pair))
        except Exception as exc:
            errors.append(f"41_Supplier_Items row {row['_row_number']}: {exc}")

    summaries["41_Supplier_Items"] = supplier_item_counts
    return plan, errors, conflicts, summaries


class Command(BaseCommand):
    help = (
        "Safe V7 demo importer. Default mode is read-only; "
        "only new records may be inserted after explicit confirmation."
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
            "--scope",
            choices=("masterdata", "demo", "all"),
            default="masterdata",
            help="Import scope. Demo scope will require a Purchasing Staff actor.",
        )
        parser.add_argument(
            "--actor-email",
            default=None,
            help="Active Purchasing Staff email for demand and sourcing records.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually insert missing records after typing IMPORT.",
        )

    def handle(self, *args, **options):
        workbook = Path(options["workbook"])
        if not workbook.is_file():
            raise CommandError(f"Không tìm thấy workbook: {workbook}")

        if options["scope"] == "demo":
            from .demo_import import build_demo_plan, apply_demo_plan

            try:
                sheets = read_workbook(workbook)
                plan, errors, conflicts, summaries = build_demo_plan(
                    sheets, options["actor_email"]
                )
            except Exception as exc:
                raise CommandError(
                    f"Không thể lập demo import plan: {exc}"
                ) from exc

            self.stdout.write(f"Workbook: {workbook}")
            self.stdout.write("Scope: demo (DD0701–DD0712)")
            self.stdout.write("\\n=== DEMO PLAN ===")
            for model_name, counts in summaries.items():
                self.stdout.write(f"{model_name}: {counts}")

            insert_count = sum(
                1 for _, _, _, status in plan if status == "INSERT"
            )
            self.stdout.write(f"INSERT: {insert_count}")
            self.stdout.write(f"CONFLICT: {len(conflicts)}")
            self.stdout.write(f"ERROR: {len(errors)}")

            for error in errors:
                self.stderr.write(f"ERROR: {error}")
            for conflict in conflicts:
                self.stderr.write(f"CONFLICT: {conflict}")

            if not options["apply"]:
                self.stdout.write(self.style.SUCCESS(
                    "DEMO DRY-RUN COMPLETE — Database writes: NONE"
                ))
                return

            if errors or conflicts:
                raise CommandError(
                    "Demo import bị chặn vì có ERROR hoặc CONFLICT."
                )

            if not sys.stdin.isatty():
                raise CommandError(
                    "--apply yêu cầu terminal tương tác để xác nhận."
                )

            confirmation = input(
                'Chỉ INSERT bản ghi demo mới. Nhập chính xác "IMPORT" '
                "để tiếp tục: "
            )
            if confirmation != "IMPORT":
                raise CommandError("Đã hủy. Database không thay đổi.")

            try:
                with transaction.atomic():
                    fresh_sheets = read_workbook(workbook)
                    fresh_plan, fresh_errors, fresh_conflicts, _ = (
                        build_demo_plan(fresh_sheets, options["actor_email"])
                    )
                    if fresh_errors or fresh_conflicts:
                        raise CommandError(
                            "Demo data thay đổi hoặc phát sinh xung đột; "
                            "transaction đã rollback."
                        )
                    created = apply_demo_plan(fresh_plan)
            except Exception as exc:
                raise CommandError(
                    f"Demo import thất bại, transaction đã rollback: {exc}"
                ) from exc

            self.stdout.write(self.style.SUCCESS(
                f"Đã tạo {created} demo demand/sourcing record(s)."
            ))
            return

        try:
            sheets = read_workbook(workbook)
            plan, errors, conflicts, summaries = build_masterdata_plan(sheets)
        except Exception as exc:
            raise CommandError(f"Không thể lập import plan: {exc}") from exc

        self.stdout.write(f"Workbook: {workbook}")
        self.stdout.write(f"Scope: {options['scope']}")
        self.stdout.write("\n=== MASTERDATA PLAN ===")

        for sheet_name, counts in summaries.items():
            self.stdout.write(f"{sheet_name}: {counts}")

        insert_count = sum(
            1 for _, _, status, _ in plan if status == "INSERT"
        )
        unchanged_count = sum(
            1 for _, _, status, _ in plan if status == "UNCHANGED"
        )

        self.stdout.write(f"INSERT: {insert_count}")
        self.stdout.write(f"UNCHANGED: {unchanged_count}")
        self.stdout.write(f"CONFLICT: {len(conflicts)}")
        self.stdout.write(f"ERROR: {len(errors)}")

        for error in errors:
            self.stderr.write(f"ERROR: {error}")
        for conflict in conflicts:
            self.stderr.write(f"CONFLICT: {conflict}")

        if options["scope"] != "masterdata":
            raise CommandError(
                "Scope demo/all chưa được kích hoạt; "
                "chỉ chạy masterdata sau khi hoàn tất kiểm tra các dependency."
            )

        if not options["apply"]:
            self.stdout.write(self.style.SUCCESS(
                "DRY-RUN COMPLETE — Database writes: NONE"
            ))
            return

        if errors or conflicts:
            raise CommandError(
                "Import bị chặn vì có ERROR hoặc CONFLICT."
            )

        if not sys.stdin.isatty():
            raise CommandError(
                "--apply yêu cầu terminal tương tác để xác nhận."
            )

        confirmation = input(
            'Chỉ INSERT bản ghi mới. Nhập chính xác "IMPORT" để tiếp tục: '
        )
        if confirmation != "IMPORT":
            raise CommandError("Đã hủy. Database không thay đổi.")

        try:
            with transaction.atomic():
                fresh_sheets = read_workbook(workbook)
                fresh_plan, fresh_errors, fresh_conflicts, _ = (
                    build_masterdata_plan(fresh_sheets)
                )
                if fresh_errors or fresh_conflicts:
                    raise CommandError(
                        "Dữ liệu thay đổi hoặc phát sinh xung đột; rollback."
                    )

                created = 0
                for model, record, status, _key in fresh_plan:
                    if status != "INSERT":
                        continue

                    values = dict(record)
                    if model is Item:
                        category_code = values.pop("cargo_category_code")
                        values["cargo_category"] = CargoCategory.objects.get(
                            category_code=category_code
                        )
                    elif model is SupplierItem:
                        supplier_code = values.pop("supplier_code")
                        item_code = values.pop("item_code")
                        values["supplier"] = Supplier.objects.get(
                            supplier_code=supplier_code
                        )
                        values["item"] = Item.objects.get(item_code=item_code)

                    model.objects.create(**values)
                    created += 1
        except Exception as exc:
            raise CommandError(f"Import thất bại, transaction đã rollback: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(
            f"Đã tạo {created} masterdata record(s)."
        ))
