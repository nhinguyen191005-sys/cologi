"""Build immutable, JSON-safe CP8 Demand snapshots from F1 ORM data."""

from datetime import date, datetime, time
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from planning.json_validators import validate_demand_snapshot
from planning.services.plan_guard import build_plan_guard_snapshots

def _iso(value):
    if value is None:
        return None
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return value


def _decimal(value):
    return None if value is None else str(Decimal(value))


def _confirmation_snapshot(request):
    confirmation = request.supplier_confirmation

    return {
        "id": confirmation.pk,
        "demand_id": confirmation.demand_id,
        "supplier_id": confirmation.supplier_id,
        "confirmation_status": confirmation.confirmation_status,
        "source_mode": confirmation.source_mode,
        "ready_date": _iso(confirmation.ready_date),
        "ready_start_time": _iso(confirmation.ready_start_time),
        "ready_end_time": _iso(confirmation.ready_end_time),
        "commitment_released": (
            confirmation.commitment_released_at is not None
        ),
        "recorded_at": _iso(confirmation.recorded_at),
    }


def _promise_snapshot(promise):
    return {
        "id": promise.pk,
        "supplier_request_id": promise.supplier_request_id,
        "demand_item_id": promise.demand_item_id,
        "demand_item_demand_id": promise.demand_item.demand_id,
        "supplier_item_id": promise.supplier_item_id,
        "item_id": promise.demand_item.item_id,
        "promised_weight_kg": _decimal(promise.promised_weight_kg),
        "confirmed_weight_kg": _decimal(promise.confirmed_weight_kg),
        "line_status": promise.line_status,
        "supplier_item_supplier_id": promise.supplier_item.supplier_id,
        "supplier_item_item_id": promise.supplier_item.item_id,
    }


def _request_snapshot(request):
    return {
        "id": request.pk,
        "demand_id": request.demand_id,
        "requested_date": _iso(request.demand.requested_date),
        "demand_status": request.demand.status,
        "supplier_id": request.supplier_id,
        "attempt_no": request.attempt_no,
        "request_status": request.request_status,
        "confirmation": _confirmation_snapshot(request),
        "promises": [
            _promise_snapshot(promise)
            for promise in request.item_promises.all()
        ],
    }


def _demand_item_snapshot(demand_item):
    item = demand_item.item

    return {
        "id": demand_item.pk,
        "item_id": demand_item.item_id,
        "required_weight_kg": _decimal(
            demand_item.required_weight_kg
        ),
        "unit_of_measure": demand_item.unit_of_measure,
        "item": {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "cargo_category_id": item.cargo_category_id,
            "weight_unit": item.weight_unit,
            "is_active": item.is_active,
        },
    }


def _supplier_item_snapshot(supplier_item):
    return {
        "id": supplier_item.pk,
        "supplier_id": supplier_item.supplier_id,
        "item_id": supplier_item.item_id,
        "unit_price_vnd_per_kg": _decimal(
            supplier_item.unit_price_vnd_per_kg
        ),
        "max_daily_supply_kg": _decimal(
            supplier_item.max_daily_supply_kg
        ),
        "lead_time_hours": supplier_item.lead_time_hours,
        "minimum_order_kg": _decimal(
            supplier_item.minimum_order_kg
        ),
        "offer_status": supplier_item.offer_status,
    }


def build_demand_snapshots(
    orm_data,
    captured_at=None,
    *,
    plan_guard_source=None,
):
    """Return {demand_id: snapshot_dict}; does not write to the database."""
    captured_at = captured_at or timezone.now()

    if timezone.is_naive(captured_at):
        raise ValidationError("captured_at must be timezone-aware.")

    capacity_requests = [
        _request_snapshot(request)
        for request in orm_data.capacity_requests
    ]

    selected_demands = tuple(orm_data.selected_demands)

    plan_guard_snapshots = build_plan_guard_snapshots(
        source=plan_guard_source,
        demand_ids=tuple(demand.pk for demand in selected_demands),
        captured_at=captured_at.isoformat(),
    )

    snapshots = {}

    for demand in selected_demands:
        demand_items = tuple(demand.items.all())
        item_ids = {item.item_id for item in demand_items}

        supplier_items = [
            _supplier_item_snapshot(offer)
            for offer in orm_data.supplier_items
            if (
                offer.supplier_id == demand.supplier_id
                and offer.item_id in item_ids
            )
        ]

        category = demand.cargo_category

        snapshot = {
            "schema_version": "1.0",
            "captured_at": captured_at.isoformat(),
            "demand_ref": {
                "demand_id": demand.pk,
                "demand_code": demand.demand_code,
            },
            "demand_values": {
                "supplier_id": demand.supplier_id,
                "outlet_id": demand.outlet_id,
                "cargo_category_id": demand.cargo_category_id,
                "cargo_category_active": category.is_active,
                "supplier_active": demand.supplier.is_active,
                "quantity_kg": _decimal(demand.quantity_kg),
                "requested_date": _iso(demand.requested_date),
                "requested_start_time": _iso(
                    demand.requested_start_time
                ),
                "requested_end_time": _iso(demand.requested_end_time),
                "status": demand.status,
            },
            "related_records": {
                "demand_items": [
                    _demand_item_snapshot(item)
                    for item in demand_items
                ],
                "supplier_items": supplier_items,
                "capacity_requests": capacity_requests,
                "supplier_confirmations": [
                    _standalone_confirmation_snapshot(confirmation)
                    for confirmation in demand.supplier_confirmations.all()
                ],
                "plan_guard": {
                    "schema_version": "1.0",
                    "demand_id": demand.pk,
                    "captured_at": captured_at.isoformat(),
                    "source": "UNAVAILABLE",
                    "query_complete": False,
                    "has_finalized_plan": None,
                    "finalized_plan_ids": [],
                    "status": "NOT_EVALUATED",
                    "reason_code": "PLAN_GUARD_QUERY_INCOMPLETE",
                }
            },
            
        }

        validate_demand_snapshot(snapshot)
        snapshots[demand.pk] = snapshot

    return snapshots

def _standalone_confirmation_snapshot(confirmation):
    return {
        "id": confirmation.pk,
        "demand_id": confirmation.demand_id,
        "supplier_id": confirmation.supplier_id,
        "confirmation_status": confirmation.confirmation_status,
        "source_mode": confirmation.source_mode,
        "ready_date": _iso(confirmation.ready_date),
        "ready_start_time": _iso(confirmation.ready_start_time),
        "ready_end_time": _iso(confirmation.ready_end_time),
        "commitment_released": (
            confirmation.commitment_released_at is not None
        ),
        "recorded_at": _iso(confirmation.recorded_at),
    }