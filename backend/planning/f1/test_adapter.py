
from datetime import date
from decimal import Decimal
from types import SimpleNamespace as NS

from planning.f1.adapter import (
    build_capacity_requests,
    build_confirmation_result,
    demand_data_is_valid,
    latest_request_by_demand,
)
from planning.f1.supplier_confirmation import ConfirmationGateStatus


def related(items):
    return NS(all=lambda: items)


def make_demand():
    item = NS(
        is_active=True,
        cargo_category_id=7,
        weight_unit="KG",
    )
    demand_item = NS(
        pk=31,
        demand_id=1,
        item_id=101,
        required_weight_kg=Decimal("5"),
        unit_of_measure="KG",
        item=item,
    )
    return NS(
        pk=1,
        supplier_id=10,
        quantity_kg=Decimal("5"),
        requested_date=date(2026, 11, 20),
        status="SUBMITTED",
        cargo_category_id=7,
        supplier=NS(is_active=True),
        cargo_category=NS(is_active=True),
        items=related([demand_item]),
    )


def make_request(demand=None, **overrides):
    demand = demand or make_demand()
    confirmation = NS(
        demand_id=demand.pk,
        supplier_id=demand.supplier_id,
        confirmation_status="CONFIRMED",
        commitment_released_at=None,
    )
    values = {
        "pk": 51,
        "demand_id": demand.pk,
        "supplier_id": demand.supplier_id,
        "attempt_no": 1,
        "request_status": "RESPONDED",
        "supplier_confirmation": confirmation,
        "demand": NS(
            requested_date=demand.requested_date,
            status=demand.status,
        ),
        "item_promises": related([]),
    }
    values.update(overrides)
    return NS(**values)


def make_promise(request, demand=None):
    demand = demand or make_demand()
    demand_item = demand.items.all()[0]
    supplier_item = NS(
        pk=81,
        supplier_id=request.supplier_id,
        item_id=demand_item.item_id,
    )
    return NS(
        pk=91,
        supplier_request_id=request.pk,
        supplier_item_id=supplier_item.pk,
        demand_item_id=demand_item.pk,
        promised_weight_kg=Decimal("5"),
        confirmed_weight_kg=Decimal("5"),
        line_status="CONFIRMED",
        demand_item=demand_item,
        supplier_item=supplier_item,
    )


def test_latest_request_is_selected_globally_per_demand():
    old = NS(demand_id=1, attempt_no=1, pk=100, supplier_id=10)
    latest = NS(demand_id=1, attempt_no=2, pk=101, supplier_id=20)
    other = NS(demand_id=2, attempt_no=1, pk=200, supplier_id=10)

    result = latest_request_by_demand([old, other, latest])

    assert result == {1: latest, 2: other}


def test_latest_request_uses_pk_as_tie_breaker():
    first = NS(demand_id=1, attempt_no=2, pk=100)
    second = NS(demand_id=1, attempt_no=2, pk=101)

    assert latest_request_by_demand([first, second])[1] is second


def test_confirmation_result_accepts_complete_valid_promise():
    demand = make_demand()
    request = make_request(demand)
    promise = make_promise(request, demand)
    request.item_promises = related([promise])

    result = build_confirmation_result(demand, request)

    assert result.status == ConfirmationGateStatus.ELIGIBLE
    assert result.confirmed_weight_by_demand_item == (
        (31, Decimal("5")),
    )


def test_confirmation_result_rejects_request_for_another_demand():
    demand = make_demand()
    request = make_request(
        demand,
        demand_id=999,
        item_promises=related([]),
    )
    request.supplier_confirmation.demand_id = 999

    result = build_confirmation_result(demand, request)

    assert result.status == ConfirmationGateStatus.INVALID_INPUT
    assert "INVALID_CONFIRMATION_LINK" in result.diagnostic_codes


def test_confirmation_result_rejects_wrong_confirmation_supplier():
    demand = make_demand()
    request = make_request(demand)
    request.supplier_confirmation.supplier_id = 999

    result = build_confirmation_result(demand, request)

    assert result.status == ConfirmationGateStatus.INVALID_INPUT


def test_confirmation_result_without_request_is_not_responded():
    result = build_confirmation_result(make_demand(), None)

    assert result.status == ConfirmationGateStatus.NOT_RESPONDED


def test_capacity_requests_preserve_attempt_and_release_information():
    demand = make_demand()
    request = make_request(demand)
    promise = make_promise(request, demand)
    request.item_promises = related([promise])

    result = build_capacity_requests([request])

    assert len(result) == 1
    assert result[0].request_id == request.pk
    assert result[0].demand_id == demand.pk
    assert result[0].supplier_id == demand.supplier_id
    assert result[0].attempt_no == request.attempt_no
    assert result[0].promises[0].links_valid is True
    assert result[0].commitment_released is False


def test_capacity_request_marks_invalid_supplier_item_link():
    demand = make_demand()
    request = make_request(demand)
    promise = make_promise(request, demand)
    promise.supplier_item.supplier_id = 999
    request.item_promises = related([promise])

    result = build_capacity_requests([request])

    assert result[0].promises[0].links_valid is False


def test_demand_data_validation_accepts_valid_demand():
    assert demand_data_is_valid(make_demand()) is True


def test_demand_data_validation_rejects_duplicate_item():
    demand = make_demand()
    original = demand.items.all()[0]
    duplicate = NS(**vars(original))
    duplicate.pk = 32
    demand.items = related([original, duplicate])

    assert demand_data_is_valid(demand) is False


def test_demand_data_validation_rejects_inactive_item():
    demand = make_demand()
    demand.items.all()[0].item.is_active = False

    assert demand_data_is_valid(demand) is False

def test_demand_data_validation_rejects_item_total_mismatch():
    demand = make_demand()
    demand.items.all()[0].required_weight_kg = Decimal("4.999")

    assert demand_data_is_valid(demand) is False

def test_capacity_requests_use_confirmed_not_promised_weight():
    demand = make_demand()
    request = make_request(demand)
    promise = make_promise(request, demand)

    promise.promised_weight_kg = Decimal("100")
    promise.confirmed_weight_kg = Decimal("60")
    promise.line_status = "PARTIAL"
    request.supplier_confirmation.confirmation_status = "PARTIAL"
    request.item_promises = related([promise])

    result = build_capacity_requests([request])

    assert result[0].promises[0].confirmed_weight_kg == Decimal("60")