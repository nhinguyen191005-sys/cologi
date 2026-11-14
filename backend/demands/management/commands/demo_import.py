"""Read-only planning and controlled insertion for V7 demo demand inputs."""

from demands.models import (
    DeliveryDemand,
    DemandStatus,
    DemandItem,
    SupplierConfirmation,
    SupplierRequest,
    SupplierItemPromise,
)
from masterdata.models import (
    CargoCategory,
    Item,
    Outlet,
    Supplier,
    SupplierItem,
)

from .import_v7_demo import (
    clean_text,
    clean_integer,
    clean_decimal,
    excel_date,
    excel_time,
    excel_datetime,
    excel_id_map,
    find_sheet_records,
    get_purchasing_actor,
)


DEMO_IDS = set(range(701, 713))


def _records(sheets, name, headers):
    return find_sheet_records(sheets, name, headers)


def _db_object(model, **filters):
    obj = model.objects.filter(**filters).first()
    if obj is None:
        raise ValueError(
            f"{model.__name__} không tồn tại với điều kiện {filters}"
        )
    return obj


def _status(model, key_filter, label):
    if model.objects.filter(**key_filter).exists():
        return "CONFLICT", f"{label}: business key đã tồn tại trong DB"
    return "INSERT", None


def build_demo_plan(sheets, actor_email=None):
    """Build a strictly scoped plan. This function never writes to the DB."""
    plan = []
    errors = []
    conflicts = []
    summaries = {}

    try:
        actor = get_purchasing_actor(actor_email)

        supplier_ids = excel_id_map(
            sheets, "04_Suppliers", "id", "supplier_code"
        )
        outlet_ids = excel_id_map(
            sheets, "05_Outlets", "id", "outlet_code"
        )
        category_ids = excel_id_map(
            sheets, "07_Cargo_Categories", "id", "category_code"
        )
        item_ids = excel_id_map(
            sheets, "40_Items", "id", "item_code"
        )

        supplier_item_rows = _records(
            sheets, "41_Supplier_Items",
            ("id", "supplier_id", "item_id"),
        )
        supplier_item_ids = {}
        for row in supplier_item_rows:
            excel_id = clean_integer(row["id"])
            supplier_code = supplier_ids.get(
                clean_integer(row["supplier_id"])
            )
            item_code = item_ids.get(clean_integer(row["item_id"]))
            if not supplier_code or not item_code:
                raise ValueError(
                    f"41_Supplier_Items row {row['_row_number']}: "
                    "không ánh xạ được supplier/item"
                )
            supplier_item_ids[excel_id] = (supplier_code, item_code)

        demand_rows_all = _records(
            sheets, "17_Delivery_Demands",
            ("id", "demand_code", "supplier_id", "outlet_id",
             "cargo_category_id", "quantity_kg", "requested_date",
             "requested_start_time", "requested_end_time", "status", "notes",
             "created_by"),
        )
        demand_rows = [
            row for row in demand_rows_all
            if clean_integer(row["id"]) in DEMO_IDS
        ]
        found_ids = {clean_integer(row["id"]) for row in demand_rows}
        if found_ids != DEMO_IDS:
            raise ValueError(
                f"Phạm vi Demand không đủ 701–712; thiếu {sorted(DEMO_IDS - found_ids)}"
            )
        if len(demand_rows) != 12:
            raise ValueError("Có Demand ID trùng trong phạm vi demo")

        demand_codes = {}
        for row in demand_rows:
            excel_id = clean_integer(row["id"])
            expected_code = f"DD{excel_id:04d}"
            code = clean_text(row["demand_code"], required=True)
            if code != expected_code:
                raise ValueError(
                    f"Demand Excel ID {excel_id}: demand_code "
                    f"phải là {expected_code}, nhận {code}"
                )
            if code in demand_codes.values():
                raise ValueError(f"Trùng demand_code {code}")
            demand_codes[excel_id] = code

        demand_item_rows_all = _records(
            sheets, "42_Demand_Items",
            ("id", "demand_id", "item_id", "required_weight_kg",
             "unit_of_measure", "item_note"),
        )
        demand_item_rows = [
            row for row in demand_item_rows_all
            if clean_integer(row["demand_id"]) in DEMO_IDS
        ]

        confirmation_rows_all = _records(
            sheets, "44_Supplier_Confirm",
            ("id", "demand_id", "supplier_id", "confirmation_status",
             "ready_date", "ready_start_time", "ready_end_time",
             "pickup_address", "recorded_at", "source_mode",
             "confirmation_note"),
        )
        confirmation_rows = [
            row for row in confirmation_rows_all
            if clean_integer(row["demand_id"]) in DEMO_IDS
        ]

        request_rows_all = _records(
            sheets, "54_Supplier_Requests",
            ("request_id", "demand_id", "supplier_id", "sent_at",
             "request_status", "response_status", "confirmed_weight_kg",
             "supplier_confirmation_id"),
        )
        request_rows = [
            row for row in request_rows_all
            if clean_integer(row["demand_id"]) in DEMO_IDS
        ]

        request_codes = {
            clean_text(row["request_id"], required=True)
            for row in request_rows
        }
        promise_rows_all = _records(
            sheets, "55_Supplier_Item_Promises",
            ("promise_id", "supplier_request_id", "demand_item_id",
             "supplier_item_id", "promised_weight_kg",
             "confirmed_weight_kg", "line_status",
             "unit_price_vnd_per_kg", "lead_time_hours"),
        )
        promise_rows = [
            row for row in promise_rows_all
            if clean_text(row["supplier_request_id"]) in request_codes
        ]

        if len(demand_item_rows) != 12:
            raise ValueError(
                f"Phải có đúng 12 DemandItem demo, tìm thấy {len(demand_item_rows)}"
            )
        if len(confirmation_rows) != 12:
            raise ValueError(
                f"Phải có đúng 12 SupplierConfirmation demo, "
                f"tìm thấy {len(confirmation_rows)}"
            )
        if len(request_rows) != 11 or len(promise_rows) != 11:
            raise ValueError(
                "Phạm vi sourcing demo phải có 11 SupplierRequest "
                "và 11 SupplierItemPromise"
            )

        item_by_excel_id = {
            excel_id: code for excel_id, code in item_ids.items()
        }
        demand_item_by_excel_id = {}
        demand_totals = {code: 0 for code in demand_codes.values()}

        counts = {
            "DeliveryDemand": {"INSERT": 0, "CONFLICT": 0},
            "DemandItem": {"INSERT": 0, "CONFLICT": 0},
            "SupplierConfirmation": {"INSERT": 0, "CONFLICT": 0},
            "SupplierRequest": {"INSERT": 0, "CONFLICT": 0},
            "SupplierItemPromise": {"INSERT": 0, "CONFLICT": 0},
        }

        # 1. DeliveryDemand
        for row in demand_rows:
            excel_id = clean_integer(row["id"])
            code = demand_codes[excel_id]
            supplier_code = supplier_ids.get(
                clean_integer(row["supplier_id"])
            )
            outlet_code = outlet_ids.get(
                clean_integer(row["outlet_id"])
            )
            category_code = category_ids.get(
                clean_integer(row["cargo_category_id"])
            )
            if not supplier_code or not outlet_code or not category_code:
                raise ValueError(f"{code}: thiếu ánh xạ supplier/outlet/category")

            supplier = _db_object(Supplier, supplier_code=supplier_code)
            outlet = _db_object(Outlet, outlet_code=outlet_code)
            category = _db_object(CargoCategory, category_code=category_code)

            values = {
                "demand_code": code,
                "supplier": supplier,
                "outlet": outlet,
                "cargo_category": category,
                "quantity_kg": clean_decimal(row["quantity_kg"]),
                "requested_date": excel_date(row["requested_date"]),
                "requested_start_time": excel_time(
                    row["requested_start_time"], required=False
                ),
                "requested_end_time": excel_time(
                    row["requested_end_time"], required=False
                ),
                "status": clean_text(row["status"], required=True).upper(),
                "notes": clean_text(row["notes"], default=None),
                "created_by": actor,
            }
            if values["quantity_kg"] <= 0:
                raise ValueError(f"{code}: quantity_kg phải lớn hơn 0")
            if values["status"] not in {
                choice for choice, _ in DemandStatus.choices
            }:
                raise ValueError(f"{code}: status không hợp lệ")
            start, end = (
                values["requested_start_time"],
                values["requested_end_time"],
            )
            if start and end and start >= end:
                raise ValueError(f"{code}: khung giờ yêu cầu không hợp lệ")

            status, conflict = _status(
                DeliveryDemand, {"demand_code": code}, code
            )
            counts["DeliveryDemand"][status] += 1
            if conflict:
                conflicts.append(conflict)
            plan.append(("DeliveryDemand", code, values, status))

        # 2. DemandItem
        seen_demand_items = set()
        for row in demand_item_rows:
            demand_id = clean_integer(row["demand_id"])
            demand_code = demand_codes[demand_id]
            item_code = item_by_excel_id.get(clean_integer(row["item_id"]))
            if not item_code:
                raise ValueError(
                    f"DemandItem row {row['_row_number']}: item không ánh xạ được"
                )
            item = _db_object(Item, item_code=item_code)
            weight = clean_decimal(row["required_weight_kg"])
            unit = clean_text(row["unit_of_measure"], required=True)
            if weight <= 0:
                raise ValueError(f"{demand_code}/{item_code}: weight phải dương")
            if unit != item.weight_unit:
                raise ValueError(
                    f"{demand_code}/{item_code}: unit {unit} "
                    f"khác item.weight_unit {item.weight_unit}"
                )
            if item.cargo_category_id != _db_object(
                CargoCategory,
                category_code=category_ids[
                    clean_integer(next(
                        d["cargo_category_id"] for d in demand_rows
                        if clean_integer(d["id"]) == demand_id
                    ))
                ],
            ).id:
                raise ValueError(
                    f"{demand_code}/{item_code}: item không khớp cargo category"
                )

            key = (demand_code, item_code)
            if key in seen_demand_items:
                raise ValueError(f"DemandItem trùng {key}")
            seen_demand_items.add(key)
            excel_item_id = clean_integer(row["id"])
            demand_item_by_excel_id[excel_item_id] = key
            demand_totals[demand_code] += weight

            status, conflict = _status(
                DemandItem,
                {"demand__demand_code": demand_code,
                 "item__item_code": item_code},
                f"{demand_code}/{item_code}",
            )
            counts["DemandItem"][status] += 1
            if conflict:
                conflicts.append(conflict)
            plan.append((
                "DemandItem", key,
                {
                    "demand_code": demand_code,
                    "item_code": item_code,
                    "required_weight_kg": weight,
                    "unit_of_measure": unit,
                    "item_note": clean_text(row["item_note"], default=None),
                },
                status,
            ))

        for row in demand_rows:
            code = demand_codes[clean_integer(row["id"])]
            if demand_totals[code] != clean_decimal(row["quantity_kg"]):
                raise ValueError(
                    f"{code}: tổng DemandItem {demand_totals[code]} "
                    f"khác quantity_kg {row['quantity_kg']}"
                )

        # 3. SupplierConfirmation
        confirmation_by_demand = {}
        for row in confirmation_rows:
            demand_id = clean_integer(row["demand_id"])
            demand_code = demand_codes[demand_id]
            supplier_code = supplier_ids.get(
                clean_integer(row["supplier_id"])
            )
            if not supplier_code:
                raise ValueError(f"{demand_code}: supplier confirmation không hợp lệ")
            if supplier_code != next(
                value["supplier"].supplier_code
                for kind, key, value, _ in plan
                if kind == "DeliveryDemand" and key == demand_code
            ):
                raise ValueError(f"{demand_code}: supplier confirmation lệch supplier")

            confirmation_status = clean_text(
                row["confirmation_status"], required=True
            ).upper()
            if confirmation_status not in {
                choice for choice, _ in SupplierConfirmation.ConfirmationStatus.choices
            }:
                raise ValueError(
                    f"{demand_code}: confirmation_status không hợp lệ"
                )

            recorded_at = excel_datetime(
                row["recorded_at"], required=False
            )
            ready_date = excel_date(row["ready_date"], required=False)
            ready_start = excel_time(
                row["ready_start_time"], required=False
            )
            ready_end = excel_time(
                row["ready_end_time"], required=False
            )
            if confirmation_status in {"NOT_REQUESTED", "PENDING"} and recorded_at:
                raise ValueError(f"{demand_code}: trạng thái không được có recorded_at")
            if confirmation_status in {"CONFIRMED", "PARTIAL", "DECLINED"} and not recorded_at:
                raise ValueError(f"{demand_code}: thiếu recorded_at")
            if confirmation_status in {"CONFIRMED", "PARTIAL"} and not ready_date:
                raise ValueError(f"{demand_code}: thiếu ready_date")
            if bool(ready_start) != bool(ready_end):
                raise ValueError(f"{demand_code}: ready time phải có đủ cặp")
            if ready_start and ready_end and ready_start >= ready_end:
                raise ValueError(f"{demand_code}: ready time không hợp lệ")

            values = {
                "demand_code": demand_code,
                "supplier_code": supplier_code,
                "confirmation_status": confirmation_status,
                "source_mode": "SYNTHETIC_V7",
                "ready_date": ready_date,
                "ready_start_time": ready_start,
                "ready_end_time": ready_end,
                "pickup_address": clean_text(
                    row["pickup_address"], default=None
                ),
                "recorded_at": recorded_at,
                "confirmation_note": clean_text(
                    row["confirmation_note"], default=""
                ),
            }
            status, conflict = _status(
                SupplierConfirmation,
                {"demand__demand_code": demand_code},
                demand_code,
            )
            counts["SupplierConfirmation"][status] += 1
            if conflict:
                conflicts.append(conflict)
            confirmation_by_demand[demand_code] = values
            plan.append((
                "SupplierConfirmation", demand_code, values, status
            ))

        # 4. SupplierRequest
        request_by_code = {}
        for row in request_rows:
            demand_id = clean_integer(row["demand_id"])
            demand_code = demand_codes[demand_id]
            request_code = clean_text(row["request_id"], required=True)
            supplier_code = supplier_ids.get(
                clean_integer(row["supplier_id"])
            )
            if not supplier_code:
                raise ValueError(f"{request_code}: supplier không ánh xạ được")

            confirmation = confirmation_by_demand.get(demand_code)
            if confirmation is None:
                raise ValueError(f"{request_code}: thiếu confirmation")
            if confirmation["supplier_code"] != supplier_code:
                raise ValueError(f"{request_code}: supplier không khớp confirmation")

            request_status = clean_text(
                row["request_status"], required=True
            ).upper()
            response_status = clean_text(
                row["response_status"], required=True
            ).upper()
            expected = confirmation["confirmation_status"]
            if response_status != expected:
                raise ValueError(
                    f"{request_code}: response_status {response_status} "
                    f"khác confirmation {expected}"
                )
            if request_status == "WAITING" and expected != "PENDING":
                raise ValueError(f"{request_code}: WAITING phải có PENDING confirmation")
            if request_status == "RESPONDED" and expected not in {
                "CONFIRMED", "PARTIAL", "DECLINED"
            }:
                raise ValueError(f"{request_code}: RESPONDED có confirmation chưa hoàn tất")
            if request_status not in {"WAITING", "RESPONDED", "EXPIRED"}:
                raise ValueError(f"{request_code}: request_status không hợp lệ")

            values = {
                "demand_code": demand_code,
                "supplier_code": supplier_code,
                "request_code": request_code,
                "attempt_no": 1,
                "request_status": request_status,
                "created_by": actor,
                "sent_at": excel_datetime(row["sent_at"]),
                "responded_at": (
                    confirmation["recorded_at"]
                    if request_status == "RESPONDED" else None
                ),
            }
            status, conflict = _status(
                SupplierRequest, {"request_code": request_code}, request_code
            )
            counts["SupplierRequest"][status] += 1
            if conflict:
                conflicts.append(conflict)
            request_by_code[request_code] = values
            plan.append(("SupplierRequest", request_code, values, status))

        # 5. SupplierItemPromise
        seen_promises = set()
        for row in promise_rows:
            request_code = clean_text(
                row["supplier_request_id"], required=True
            )
            request = request_by_code.get(request_code)
            if request is None:
                raise ValueError(f"Promise: không tìm thấy request {request_code}")

            demand_item_excel_id = clean_integer(row["demand_item_id"])
            demand_item_key = demand_item_by_excel_id.get(
                demand_item_excel_id
            )
            if demand_item_key is None:
                raise ValueError(
                    f"{request_code}: DemandItem Excel ID "
                    f"{demand_item_excel_id} không thuộc demo"
                )

            supplier_item_excel_id = clean_integer(row["supplier_item_id"])
            supplier_item_key = supplier_item_ids.get(
                supplier_item_excel_id
            )
            if supplier_item_key is None:
                raise ValueError(
                    f"{request_code}: SupplierItem Excel ID "
                    f"{supplier_item_excel_id} không ánh xạ được"
                )
            if supplier_item_key[0] != request["supplier_code"]:
                raise ValueError(f"{request_code}: SupplierItem sai supplier")
            if supplier_item_key[1] != demand_item_key[1]:
                raise ValueError(f"{request_code}: SupplierItem sai item")

            promised = clean_decimal(row["promised_weight_kg"])
            confirmed = clean_decimal(row["confirmed_weight_kg"])
            line_status = clean_text(row["line_status"], required=True).upper()
            price = clean_decimal(row["unit_price_vnd_per_kg"])
            lead_time = clean_integer(
                row["lead_time_hours"], required=False
            )
            if promised <= 0 or confirmed < 0 or confirmed > promised:
                raise ValueError(f"{request_code}: khối lượng promise không hợp lệ")
            if price < 0 or (lead_time is not None and lead_time < 0):
                raise ValueError(f"{request_code}: snapshot giá/lead time không hợp lệ")

            expected_status = (
                "PENDING" if confirmed == 0 and line_status == "PENDING"
                else "DECLINED" if confirmed == 0 and line_status == "DECLINED"
                else "CONFIRMED" if confirmed == promised
                else "PARTIAL" if 0 < confirmed < promised
                else None
            )
            if line_status != expected_status:
                raise ValueError(
                    f"{request_code}: line_status {line_status} "
                    f"không khớp confirmed weight"
                )

            key = (request_code, demand_item_key)
            if key in seen_promises:
                raise ValueError(f"Promise trùng {key}")
            seen_promises.add(key)

            values = {
                "request_code": request_code,
                "demand_code": demand_item_key[0],
                "item_code": demand_item_key[1],
                "supplier_code": supplier_item_key[0],
                "promised_weight_kg": promised,
                "confirmed_weight_kg": confirmed,
                "line_status": line_status,
                "unit_price_vnd_per_kg_snapshot": price,
                "lead_time_hours_snapshot": lead_time,
            }
            status, conflict = _status(
                SupplierItemPromise,
                {
                    "supplier_request__request_code": request_code,
                    "demand_item__demand__demand_code": demand_item_key[0],
                    "demand_item__item__item_code": demand_item_key[1],
                },
                f"{request_code}/{demand_item_key}",
            )
            counts["SupplierItemPromise"][status] += 1
            if conflict:
                conflicts.append(conflict)
            plan.append(("SupplierItemPromise", key, values, status))

        expected_counts = {
            "DeliveryDemand": 12,
            "DemandItem": 12,
            "SupplierConfirmation": 12,
            "SupplierRequest": 11,
            "SupplierItemPromise": 11,
        }
        for name, expected in expected_counts.items():
            actual = counts[name]["INSERT"] + counts[name]["CONFLICT"]
            if actual != expected:
                raise ValueError(
                    f"{name}: dự kiến {expected}, lập được {actual}"
                )

        summaries = counts

    except Exception as exc:
        errors.append(str(exc))

    return plan, errors, conflicts, summaries


def apply_demo_plan(plan):
    """Insert in FK order. Caller must wrap this in transaction.atomic()."""
    demands = {}
    demand_items = {}
    confirmations = {}
    requests = {}
    created = 0

    for kind, key, values, status in plan:
        if status != "INSERT":
            continue

        data = dict(values)

        if kind == "DeliveryDemand":
            obj = DeliveryDemand(**data)
            obj.full_clean()
            obj.save()
            demands[key] = obj

        elif kind == "DemandItem":
            demand_code, item_code = key
            obj = DemandItem(
                demand=demands[demand_code],
                item=Item.objects.get(item_code=item_code),
                required_weight_kg=data["required_weight_kg"],
                unit_of_measure=data["unit_of_measure"],
                item_note=data["item_note"],
            )
            obj.full_clean()
            obj.save()
            demand_items[key] = obj

        elif kind == "SupplierConfirmation":
            obj = SupplierConfirmation(
                demand=demands[key],
                supplier=Supplier.objects.get(
                    supplier_code=data["supplier_code"]
                ),
                confirmation_status=data["confirmation_status"],
                source_mode=data["source_mode"],
                ready_date=data["ready_date"],
                ready_start_time=data["ready_start_time"],
                ready_end_time=data["ready_end_time"],
                pickup_address=data["pickup_address"],
                recorded_at=data["recorded_at"],
                confirmation_note=data["confirmation_note"],
            )
            obj.full_clean()
            obj.save()
            confirmations[key] = obj

        elif kind == "SupplierRequest":
            obj = SupplierRequest(
                demand=demands[data["demand_code"]],
                supplier=Supplier.objects.get(
                    supplier_code=data["supplier_code"]
                ),
                supplier_confirmation=confirmations[data["demand_code"]],
                request_code=data["request_code"],
                attempt_no=data["attempt_no"],
                request_status=data["request_status"],
                created_by=data["created_by"],
                sent_at=data["sent_at"],
                responded_at=data["responded_at"],
            )
            obj.full_clean()
            obj.save()
            requests[key] = obj

        elif kind == "SupplierItemPromise":
            request_code = data["request_code"]
            demand_item_key = (data["demand_code"], data["item_code"])
            supplier_item = SupplierItem.objects.get(
                supplier__supplier_code=data["supplier_code"],
                item__item_code=data["item_code"],
            )
            obj = SupplierItemPromise(
                supplier_request=requests[request_code],
                demand_item=demand_items[demand_item_key],
                supplier_item=supplier_item,
                promised_weight_kg=data["promised_weight_kg"],
                confirmed_weight_kg=data["confirmed_weight_kg"],
                line_status=data["line_status"],
                unit_price_vnd_per_kg_snapshot=data[
                    "unit_price_vnd_per_kg_snapshot"
                ],
                lead_time_hours_snapshot=data["lead_time_hours_snapshot"],
            )
            obj.full_clean()
            obj.save()

        created += 1

    return created
