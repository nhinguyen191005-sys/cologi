
import os
from types import SimpleNamespace as NS

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings.dev",
)

import django
from django.apps import apps

if not apps.ready:
    django.setup()

import planning.f1.orm_reader as reader


class FakeQuerySet:
    def __init__(self, rows=(), values=None):
        self.rows = tuple(rows)
        self.values = tuple(values or ())
        self.calls = []

    def select_related(self, *fields):
        self.calls.append(("select_related", fields))
        return self

    def prefetch_related(self, *fields):
        self.calls.append(("prefetch_related", fields))
        return self

    def order_by(self, *fields):
        self.calls.append(("order_by", fields))
        return self

    def values_list(self, field, flat=False):
        self.calls.append(("values_list", field, flat))
        return self.values

    def __iter__(self):
        return iter(self.rows)


class FakeManager:
    def __init__(self, querysets=()):
        self.querysets = list(querysets)
        self.filters = []

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        if not self.querysets:
            raise AssertionError("Unexpected manager.filter() call")
        return self.querysets.pop(0)


def make_demand(pk, supplier_id, item_ids, requested_date):
    items = [
        NS(item_id=item_id)
        for item_id in item_ids
    ]
    return NS(
        pk=pk,
        supplier_id=supplier_id,
        requested_date=requested_date,
        items=NS(all=lambda: items),
    )


def test_empty_demand_ids_performs_no_queries(monkeypatch):
    delivery_manager = FakeManager()
    request_manager = FakeManager()
    supplier_item_manager = FakeManager()

    monkeypatch.setattr(
        reader,
        "DeliveryDemand",
        NS(objects=delivery_manager),
    )
    monkeypatch.setattr(
        reader,
        "SupplierRequest",
        NS(objects=request_manager),
    )
    monkeypatch.setattr(
        reader,
        "SupplierItem",
        NS(objects=supplier_item_manager),
    )

    result = reader.load_f1_orm_data([])

    assert result.selected_demands == ()
    assert result.supplier_items == ()
    assert result.capacity_requests == ()
    assert delivery_manager.filters == []
    assert request_manager.filters == []
    assert supplier_item_manager.filters == []


def test_no_selected_demands_stops_after_initial_select(monkeypatch):
    selected_qs = FakeQuerySet()
    delivery_manager = FakeManager([selected_qs])
    request_manager = FakeManager()
    supplier_item_manager = FakeManager()

    monkeypatch.setattr(
        reader,
        "DeliveryDemand",
        NS(objects=delivery_manager),
    )
    monkeypatch.setattr(
        reader,
        "SupplierRequest",
        NS(objects=request_manager),
    )
    monkeypatch.setattr(
        reader,
        "SupplierItem",
        NS(objects=supplier_item_manager),
    )

    result = reader.load_f1_orm_data([5, 2, 5])

    assert result.selected_demands == ()
    assert result.supplier_items == ()
    assert result.capacity_requests == ()
    assert delivery_manager.filters == [{"pk__in": (2, 5)}]
    assert request_manager.filters == []
    assert supplier_item_manager.filters == []
    assert (
        "select_related",
        ("supplier", "cargo_category"),
    ) in selected_qs.calls
    assert (
        "prefetch_related",
        ("items__item",),
    ) in selected_qs.calls
    assert ("order_by", ("pk",)) in selected_qs.calls


def test_reader_loads_all_capacity_requests_for_selected_dates(
    monkeypatch,
):
    from datetime import date

    day = date(2026, 11, 20)
    demand_1 = make_demand(1, 10, [101, 102], day)
    demand_2 = make_demand(2, 20, [103], day)

    selected_qs = FakeQuerySet([demand_1, demand_2])
    capacity_ids_qs = FakeQuerySet(values=[1, 2, 3, 4])

    delivery_manager = FakeManager([
        selected_qs,
        capacity_ids_qs,
    ])

    request_rows = [
        NS(pk=501, supplier_id=10),
        NS(pk=502, supplier_id=20),
        NS(pk=503, supplier_id=30),
    ]
    request_qs = FakeQuerySet(request_rows)
    request_manager = FakeManager([request_qs])

    offer_rows = [
        NS(pk=801, supplier_id=10, item_id=101),
        NS(pk=802, supplier_id=20, item_id=103),
    ]
    offer_qs = FakeQuerySet(offer_rows)
    supplier_item_manager = FakeManager([offer_qs])

    monkeypatch.setattr(
        reader,
        "DeliveryDemand",
        NS(objects=delivery_manager),
    )
    monkeypatch.setattr(
        reader,
        "SupplierRequest",
        NS(objects=request_manager),
    )
    monkeypatch.setattr(
        reader,
        "SupplierItem",
        NS(objects=supplier_item_manager),
    )

    result = reader.load_f1_orm_data([2, 1, 2])

    assert result.selected_demands == (demand_1, demand_2)
    assert result.capacity_requests == tuple(request_rows)
    assert result.supplier_items == tuple(offer_rows)

    assert delivery_manager.filters == [
        {"pk__in": (1, 2)},
        {"requested_date__in": {day}},
    ]

    # Critical: no supplier filter here. Capacity history must include
    # requests from every Supplier for the selected delivery dates.
    assert request_manager.filters == [
        {"demand_id__in": (1, 2, 3, 4)},
    ]

    assert (
        "select_related",
        (
            "demand",
            "supplier",
            "supplier_confirmation",
            "supplier_confirmation__demand",
            "supplier_confirmation__supplier",
        ),
    ) in request_qs.calls

    assert (
        "prefetch_related",
        (
            "item_promises__demand_item",
            "item_promises__supplier_item",
        ),
    ) in request_qs.calls

    assert (
        "order_by",
        ("demand_id", "attempt_no", "pk"),
    ) in request_qs.calls

    assert supplier_item_manager.filters == [
        {
            "supplier_id__in": {10, 20},
            "item_id__in": {101, 102, 103},
        },
    ]

    assert (
        "select_related",
        ("supplier", "item"),
    ) in offer_qs.calls

    assert (
        "order_by",
        ("supplier_id", "item_id"),
    ) in offer_qs.calls
