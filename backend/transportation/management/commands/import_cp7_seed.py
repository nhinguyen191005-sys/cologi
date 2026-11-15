import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from masterdata.management.commands.import_masterdata import read_workbook
from masterdata.models import Supplier, TransportProvider, VehicleType
from transportation.models import (
    ProviderAvailability,
    ProviderSupplierCoverage,
    ProviderVehicleOffer,
)


SYNTHETIC_SOURCES = {
    "SYNTHETIC_NOVEMBER_DEMO",
    "SYNTHETIC_HISTORICAL_FIXTURE",
}


def find_records(sheets, sheet_name, required_headers):
    if sheet_name not in sheets:
        raise ValueError(f"Missing worksheet: {sheet_name}")

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
            f"{sheet_name}: missing headers {', '.join(required_headers)}"
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
        if all(
            value is None or str(value).strip() == ""
            for value in record.values()
        ):
            continue
        record["_row_number"] = row_number
        records.append(record)

    return records


def text_value(value, *, required=False, default=None):
    if value is None or str(value).strip() == "":
        if required:
            raise ValueError("Required value is missing")
        return default
    return str(value).strip()


def integer_value(value, *, required=True):
    raw = text_value(value, required=required)
    if raw is None:
        return None

    try:
        number = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid integer: {raw}") from exc

    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"Invalid integer: {raw}")

    return int(number)


def decimal_value(value, *, required=False):
    raw = text_value(value, required=required)
    if raw is None:
        return None

    try:
        number = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal: {raw}") from exc

    if not number.is_finite():
        raise ValueError(f"Invalid decimal: {raw}")

    return number


def boolean_value(value):
    raw = text_value(value, required=True).lower()
    if raw in {"true", "1", "yes", "y"}:
        return True
    if raw in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Invalid boolean: {raw}")


def date_value(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = text_value(value, required=True)
    try:
        number = Decimal(raw)
        if not number.is_finite():
            raise ValueError(f"Invalid date serial: {raw}")
        return (
            datetime(1899, 12, 30) + timedelta(days=float(number))
        ).date()
    except (InvalidOperation, ValueError, OverflowError):
        return date.fromisoformat(raw[:10])


def time_value(value, *, required=False):
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value

    raw = text_value(value, required=required)
    if raw is None:
        return None

    try:
        number = Decimal(raw)
        if not number.is_finite():
            raise ValueError(f"Invalid time serial: {raw}")
        seconds = int(round(float(number) * 86400)) % 86400
        return (datetime.min + timedelta(seconds=seconds)).time()
    except (InvalidOperation, ValueError, OverflowError):
        return time.fromisoformat(raw)


def excel_id_map(sheets, sheet_name, id_header, code_header):
    rows = find_records(sheets, sheet_name, (id_header, code_header))
    result = {}

    for row in rows:
        excel_id = integer_value(row[id_header])
        code = text_value(row[code_header], required=True)

        if excel_id in result:
            raise ValueError(f"{sheet_name}: duplicate Excel ID {excel_id}")

        result[excel_id] = code

    return result


def compare_existing(model, key_filter, values, label):
    existing = model.objects.filter(**key_filter).first()
    if existing is None:
        return "INSERT", None, None

    changed = []
    for field, expected in values.items():
        actual = getattr(existing, field)

        if hasattr(expected, "pk"):
            actual = getattr(existing, f"{field}_id")
            expected = expected.pk

        if actual != expected:
            changed.append(field)

    if changed:
        return (
            "CONFLICT",
            existing,
            f"{label}: existing record differs in {', '.join(changed)}",
        )

    return "UNCHANGED", existing, None


def build_plan(sheets):
    plan = []
    errors = []
    conflicts = []
    summaries = {}

    # Resolve the single supported Provider: TP001.
    provider_rows = find_records(
        sheets,
        "45_Transport_Providers",
        (
            "id", "provider_code", "provider_name", "provider_type",
            "service_region", "contact_email", "is_active",
        ),
    )

    provider_ids = {}
    for row in provider_rows:
        try:
            excel_id = integer_value(row["id"])
            code = text_value(row["provider_code"], required=True)

            if excel_id in provider_ids:
                raise ValueError(f"Duplicate provider Excel ID {excel_id}")

            provider_ids[excel_id] = code
            provider = TransportProvider.objects.filter(
                provider_code=code
            ).first()

            if provider is None:
                errors.append(
                    f"45_Transport_Providers row {row['_row_number']}: "
                    f"Provider {code} must already exist; CP7 seed "
                    "does not create providers"
                )
                continue

            expected = {
                "provider_name": text_value(
                    row["provider_name"], required=True
                ),
                "provider_type": text_value(
                    row["provider_type"], required=True
                ),
                "service_region": text_value(
                    row["service_region"], default=""
                ),
                "contact_email": text_value(
                    row["contact_email"], default=""
                ),
                "is_active": boolean_value(row["is_active"]),
            }

            changed = [
                field
                for field, value in expected.items()
                if getattr(provider, field) != value
            ]

            if changed:
                conflicts.append(
                    f"45_Transport_Providers / {code}: TP001 differs in "
                    f"{', '.join(changed)}"
                )

        except Exception as exc:
            errors.append(
                f"45_Transport_Providers row {row['_row_number']}: {exc}"
            )

    if len(provider_ids) != 1 or set(provider_ids.values()) != {"TP001"}:
        errors.append(
            "45_Transport_Providers: CP7 supports exactly one "
            "workbook Provider, TP001"
        )

    supplier_ids = excel_id_map(
        sheets, "04_Suppliers", "id", "supplier_code"
    )
    vehicle_ids = excel_id_map(
        sheets, "09_Vehicle_Types", "id", "vehicle_code"
    )

    providers = {
        code: TransportProvider.objects.filter(
            provider_code=code
        ).first()
        for code in set(provider_ids.values())
    }
    suppliers = {
        code: Supplier.objects.filter(supplier_code=code).first()
        for code in set(supplier_ids.values())
    }
    vehicles = {
        code: VehicleType.objects.filter(vehicle_code=code).first()
        for code in set(vehicle_ids.values())
    }

    # Sheet 46: Provider-Supplier coverage.
    coverage_rows = find_records(
        sheets,
        "46_Provider_Suppliers",
        (
            "id", "provider_id", "supplier_id", "coverage_status",
            "can_pickup", "service_note",
        ),
    )

    coverage_keys = set()
    counts = {"INSERT": 0, "UNCHANGED": 0, "CONFLICT": 0}

    for row in coverage_rows:
        try:
            provider_code = provider_ids.get(
                integer_value(row["provider_id"])
            )
            supplier_code = supplier_ids.get(
                integer_value(row["supplier_id"])
            )

            if not provider_code or not supplier_code:
                raise ValueError(
                    "Cannot resolve Provider/Supplier Excel ID"
                )

            provider = providers.get(provider_code)
            supplier = suppliers.get(supplier_code)

            if provider is None or supplier is None:
                raise ValueError(
                    f"Provider {provider_code} or Supplier {supplier_code} "
                    "does not exist in DB"
                )

            key = (provider_code, supplier_code)
            if key in coverage_keys:
                raise ValueError(
                    f"Duplicate Provider-Supplier pair {key}"
                )
            coverage_keys.add(key)

            status = text_value(
                row["coverage_status"], required=True
            ).upper()

            if status not in {"ACTIVE", "INACTIVE"}:
                raise ValueError(
                    f"Invalid coverage_status: {status}"
                )
            if status == "ACTIVE" and not supplier.is_active:
                raise ValueError(
                    f"Supplier {supplier_code} is inactive"
                )

            values = {
                "provider": provider,
                "supplier": supplier,
                "coverage_status": status,
                "can_pickup": boolean_value(row["can_pickup"]),
                "service_note": text_value(
                    row["service_note"], default=""
                ) or "",
            }

            state, existing, conflict = compare_existing(
                ProviderSupplierCoverage,
                {"provider": provider, "supplier": supplier},
                values,
                f"46_Provider_Suppliers row {row['_row_number']} / {key}",
            )

            counts[state] += 1
            if conflict:
                conflicts.append(conflict)

            plan.append({
                "kind": "coverage",
                "model": ProviderSupplierCoverage,
                "values": values,
                "state": state,
                "label": key,
            })

        except Exception as exc:
            errors.append(
                f"46_Provider_Suppliers row {row['_row_number']}: {exc}"
            )

    summaries["46_Provider_Suppliers"] = counts

    # Sheet 47: one Offer per Provider-VehicleType.
    offer_rows = find_records(
        sheets,
        "47_Provider_Vehicles",
        (
            "id", "provider_id", "vehicle_type_id",
            "available_vehicle_count", "fuel_type",
            "operating_start_time", "operating_end_time",
            "fixed_quote_vnd", "estimated_cost_per_km_vnd",
            "is_active", "vehicle_note",
        ),
    )

    offer_keys = set()
    offer_by_excel_id = {}
    offer_specs = {}
    counts = {"INSERT": 0, "UNCHANGED": 0, "CONFLICT": 0}

    for row in offer_rows:
        try:
            excel_offer_id = integer_value(row["id"])
            if excel_offer_id in offer_by_excel_id:
                raise ValueError(
                    f"Duplicate Offer Excel ID {excel_offer_id}"
                )

            provider_code = provider_ids.get(
                integer_value(row["provider_id"])
            )
            vehicle_code = vehicle_ids.get(
                integer_value(row["vehicle_type_id"])
            )

            if not provider_code or not vehicle_code:
                raise ValueError(
                    "Cannot resolve Provider/VehicleType Excel ID"
                )

            provider = providers.get(provider_code)
            vehicle = vehicles.get(vehicle_code)

            if provider is None or vehicle is None:
                raise ValueError(
                    f"Provider {provider_code} or VehicleType "
                    f"{vehicle_code} does not exist in DB"
                )
            if not vehicle.is_active:
                raise ValueError(
                    f"VehicleType {vehicle_code} is inactive"
                )

            offer_key = (provider_code, vehicle_code)
            if offer_key in offer_keys:
                raise ValueError(
                    f"Duplicate Provider-VehicleType pair {offer_key}"
                )
            offer_keys.add(offer_key)

            capacity = integer_value(row["available_vehicle_count"])
            fuel = text_value(row["fuel_type"], required=True).upper()
            start = time_value(row["operating_start_time"])
            end = time_value(row["operating_end_time"])
            fixed = decimal_value(row["fixed_quote_vnd"])
            per_km = decimal_value(row["estimated_cost_per_km_vnd"])
            active = boolean_value(row["is_active"])

            if capacity < 0 or (active and capacity <= 0):
                raise ValueError(
                    "Active Offer must have positive capacity"
                )
            if fuel not in {"ELECTRIC", "GASOLINE", "DIESEL"}:
                raise ValueError(f"Invalid fuel_type: {fuel}")
            if (start is None) != (end is None):
                raise ValueError(
                    "Operating hours must both be NULL or both populated"
                )
            if start is not None and start >= end:
                raise ValueError(
                    "Offer operating_start_time must be earlier "
                    "than operating_end_time"
                )
            if fixed is not None and fixed < 0:
                raise ValueError("fixed_quote_vnd cannot be negative")
            if per_km is not None and per_km < 0:
                raise ValueError(
                    "estimated_cost_per_km_vnd cannot be negative"
                )

            values = {
                "provider": provider,
                "vehicle_type": vehicle,
                "available_vehicle_count": capacity,
                "fuel_type": fuel,
                "operating_start_time": start,
                "operating_end_time": end,
                "fixed_quote_vnd": fixed,
                "estimated_cost_per_km_vnd": per_km,
                "is_active": active,
                "vehicle_note": text_value(
                    row["vehicle_note"], default=""
                ) or "",
            }

            state, existing, conflict = compare_existing(
                ProviderVehicleOffer,
                {"provider": provider, "vehicle_type": vehicle},
                values,
                f"47_Provider_Vehicles row {row['_row_number']} / "
                f"{offer_key}",
            )

            counts[state] += 1
            if conflict:
                conflicts.append(conflict)

            offer_specs[offer_key] = {
                "provider": provider,
                "vehicle_type": vehicle,
                "values": values,
                "state": state,
                "existing": existing,
            }
            offer_by_excel_id[excel_offer_id] = offer_key

            plan.append({
                "kind": "offer",
                "model": ProviderVehicleOffer,
                "offer_key": offer_key,
                "values": values,
                "state": state,
                "label": offer_key,
            })

        except Exception as exc:
            errors.append(
                f"47_Provider_Vehicles row {row['_row_number']}: {exc}"
            )

    summaries["47_Provider_Vehicles"] = counts

    # Sheet 48: synthetic Availability only.
    availability_rows = find_records(
        sheets,
        "48_Provider_Availability",
        (
            "id", "provider_vehicle_id", "service_date",
            "available_vehicle_count", "start_time", "end_time",
            "availability_status", "source_mode",
        ),
    )

    availability_keys = set()
    planned_windows = {}
    counts = {"INSERT": 0, "UNCHANGED": 0, "CONFLICT": 0}

    for row in availability_rows:
        try:
            excel_offer_id = integer_value(
                row["provider_vehicle_id"]
            )
            offer_key = offer_by_excel_id.get(excel_offer_id)

            if offer_key is None:
                raise ValueError(
                    "Cannot resolve provider_vehicle_id Excel ID "
                    f"{excel_offer_id}"
                )

            offer_spec = offer_specs[offer_key]
            provider = offer_spec["provider"]
            vehicle = offer_spec["vehicle_type"]
            offer = offer_spec["existing"]
            offer_values = offer_spec["values"]

            service_date = date_value(row["service_date"])
            start = time_value(row["start_time"], required=True)
            end = time_value(row["end_time"], required=True)
            capacity = integer_value(
                row["available_vehicle_count"]
            )
            status = text_value(
                row["availability_status"], required=True
            ).upper()
            source = text_value(
                row["source_mode"], required=True
            ).upper()

            if source not in SYNTHETIC_SOURCES:
                raise ValueError(
                    f"Seed source_mode must be synthetic; got {source}"
                )
            if start >= end:
                raise ValueError(
                    "Availability end_time must be later than start_time"
                )
            if capacity < 0:
                raise ValueError(
                    "Availability count cannot be negative"
                )
            if status == "AVAILABLE" and capacity <= 0:
                raise ValueError(
                    "AVAILABLE requires a positive vehicle count"
                )
            if status == "UNAVAILABLE" and capacity != 0:
                raise ValueError(
                    "UNAVAILABLE requires a vehicle count of zero"
                )
            if status not in {"AVAILABLE", "UNAVAILABLE"}:
                raise ValueError(
                    f"Invalid availability_status: {status}"
                )

            offer_active = (
                offer.is_active if offer is not None
                else offer_values["is_active"]
            )
            offer_capacity = (
                offer.available_vehicle_count if offer is not None
                else offer_values["available_vehicle_count"]
            )
            operating_start = (
                offer.operating_start_time if offer is not None
                else offer_values["operating_start_time"]
            )
            operating_end = (
                offer.operating_end_time if offer is not None
                else offer_values["operating_end_time"]
            )

            if not offer_active:
                raise ValueError(
                    "Synthetic Availability requires an active Offer "
                    "at import time"
                )
            if not vehicle.is_active:
                raise ValueError(
                    "Synthetic Availability requires an active VehicleType"
                )
            if capacity > offer_capacity:
                raise ValueError(
                    "Availability count cannot exceed Offer capacity"
                )
            if operating_start is None or operating_end is None:
                raise ValueError(
                    "Offer operating hours must be configured "
                    "before Availability"
                )
            if start < operating_start or end > operating_end:
                raise ValueError(
                    "Availability must fit entirely within "
                    "Offer operating hours"
                )

            natural_key = (
                offer_key,
                service_date,
                start,
                end,
                source,
            )
            if natural_key in availability_keys:
                raise ValueError(
                    f"Duplicate Availability natural key {natural_key}"
                )
            availability_keys.add(natural_key)

            values = {
                "service_date": service_date,
                "available_vehicle_count": capacity,
                "start_time": start,
                "end_time": end,
                "availability_status": status,
                "source_mode": source,
            }

            if offer is not None:
                state, existing, conflict = compare_existing(
                    ProviderAvailability,
                    {
                        "provider_vehicle_offer": offer,
                        "service_date": service_date,
                        "start_time": start,
                        "end_time": end,
                        "source_mode": source,
                    },
                    {
                        **values,
                        "provider_vehicle_offer": offer,
                    },
                    (
                        f"48_Provider_Availability row "
                        f"{row['_row_number']} / {natural_key}"
                    ),
                )
            else:
                state, existing, conflict = "INSERT", None, None

            if conflict:
                conflicts.append(conflict)

            # Check persisted windows for new rows when the Offer
            # already exists. Synthetic sources are checked separately.
            if state == "INSERT" and offer is not None:
                overlap = ProviderAvailability.objects.filter(
                    provider_vehicle_offer=offer,
                    service_date=service_date,
                    source_mode=source,
                    start_time__lt=end,
                    end_time__gt=start,
                ).exists()

                if overlap:
                    conflicts.append(
                        f"48_Provider_Availability row "
                        f"{row['_row_number']}: overlaps an existing "
                        f"{source} window"
                    )
                    state = "CONFLICT"

            # Always group by the business Offer key, never by a
            # possibly-null database PK.
            group = (offer_key, service_date, source)
            windows = planned_windows.setdefault(group, [])

            for other_start, other_end, other_row in windows:
                if start < other_end and end > other_start:
                    errors.append(
                        f"48_Provider_Availability row "
                        f"{row['_row_number']}: overlaps row "
                        f"{other_row} within source_mode {source}"
                    )

            windows.append((start, end, row["_row_number"]))

            counts[state] += 1
            plan.append({
                "kind": "availability",
                "model": ProviderAvailability,
                "offer_key": offer_key,
                "values": values,
                "state": state,
                "label": natural_key,
            })

        except Exception as exc:
            errors.append(
                f"48_Provider_Availability row {row['_row_number']}: {exc}"
            )

    summaries["48_Provider_Availability"] = counts

    return plan, errors, conflicts, summaries


def apply_plan(plan):
    created = 0
    offer_instances = {}

    # Phase 1: Provider-Supplier Coverage.
    for item in plan:
        if item["kind"] != "coverage":
            continue
        if item["state"] != "INSERT":
            continue

        instance = ProviderSupplierCoverage(**item["values"])
        instance.full_clean()
        instance.save(force_insert=True)
        created += 1

    # Phase 2: Provider Vehicle Offers.
    for item in plan:
        if item["kind"] != "offer":
            continue

        offer_key = item["offer_key"]

        if item["state"] == "INSERT":
            instance = ProviderVehicleOffer(**item["values"])
            instance.full_clean()
            instance.save(force_insert=True)
            created += 1
        else:
            instance = item["model"].objects.get(
                provider=item["values"]["provider"],
                vehicle_type=item["values"]["vehicle_type"],
            )

        offer_instances[offer_key] = instance

    # Phase 3: Availability, after every referenced Offer exists.
    for item in plan:
        if item["kind"] != "availability":
            continue
        if item["state"] != "INSERT":
            continue

        offer = offer_instances.get(item["offer_key"])
        if offer is None:
            raise ValueError(
                f"Cannot resolve inserted Offer {item['offer_key']}"
            )

        values = {
            **item["values"],
            "provider_vehicle_offer": offer,
        }
        instance = ProviderAvailability(**values)
        instance.full_clean()
        instance.save(force_insert=True)
        created += 1

    return created


class Command(BaseCommand):
    help = (
        "Safe CP7 seed importer for Sheets 45-48. "
        "Dry-run by default; only INSERTs after explicit confirmation."
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
            help='Insert missing records after typing "IMPORT".',
        )

    def handle(self, *args, **options):
        workbook = Path(options["workbook"])
        if not workbook.is_file():
            raise CommandError(f"Workbook not found: {workbook}")

        try:
            sheets = read_workbook(workbook)
            plan, errors, conflicts, summaries = build_plan(sheets)
        except Exception as exc:
            raise CommandError(
                f"Cannot build CP7 seed plan: {exc}"
            ) from exc

        self.stdout.write(f"Workbook: {workbook}")
        self.stdout.write(
            "Scope: CP7 Sheets 45-48 (Sheet 49 excluded)"
        )
        self.stdout.write("\n=== CP7 SEED PLAN ===")

        for sheet, counts in summaries.items():
            self.stdout.write(f"{sheet}: {counts}")

        insert_count = sum(
            item["state"] == "INSERT" for item in plan
        )
        unchanged_count = sum(
            item["state"] == "UNCHANGED" for item in plan
        )
        conflict_count = sum(
            item["state"] == "CONFLICT" for item in plan
        )

        self.stdout.write(f"INSERT: {insert_count}")
        self.stdout.write(f"UNCHANGED: {unchanged_count}")
        self.stdout.write(f"CONFLICT: {conflict_count}")
        self.stdout.write(f"ERROR: {len(errors)}")

        for error in errors:
            self.stderr.write(f"ERROR: {error}")
        for conflict in conflicts:
            self.stderr.write(f"CONFLICT: {conflict}")

        if not options["apply"]:
            self.stdout.write(self.style.SUCCESS(
                "CP7 DRY-RUN COMPLETE — Database writes: NONE"
            ))
            return

        if errors or conflicts:
            raise CommandError(
                "CP7 seed import blocked because ERROR or CONFLICT exists."
            )
        if not sys.stdin.isatty():
            raise CommandError(
                "--apply requires an interactive terminal."
            )

        confirmation = input(
            'Only INSERT missing CP7 seed rows. Type exactly "IMPORT": '
        )
        if confirmation != "IMPORT":
            raise CommandError("Cancelled. Database unchanged.")

        try:
            with transaction.atomic():
                TransportProvider.objects.select_for_update().get(
                    provider_code="TP001"
                )

                fresh_sheets = read_workbook(workbook)
                (
                    fresh_plan,
                    fresh_errors,
                    fresh_conflicts,
                    _,
                ) = build_plan(fresh_sheets)

                if fresh_errors or fresh_conflicts:
                    raise CommandError(
                        "CP7 data changed or conflicts appeared; "
                        "transaction rolled back."
                    )

                created = apply_plan(fresh_plan)

        except Exception as exc:
            raise CommandError(
                f"CP7 seed import failed; transaction rolled back: {exc}"
            ) from exc

        self.stdout.write(self.style.SUCCESS(
            f"CP7 seed import completed: {created} record(s) inserted."
        ))
