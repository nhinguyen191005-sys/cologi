
"""Read-only ORM loader for F1.

This module performs SELECT queries only. It does not mutate database rows.
"""
from dataclasses import dataclass

from demands.models import DeliveryDemand, SupplierRequest
from masterdata.models import SupplierItem


@dataclass(frozen=True)
class F1ORMData:
    selected_demands: tuple
    supplier_items: tuple
    capacity_requests: tuple


def load_f1_orm_data(demand_ids) -> F1ORMData:
    """Load selected Demands and all capacity-relevant request history.

    Capacity history includes every Supplier's requests for every Demand
    whose requested_date is represented in the selected Demand set.
    Do not add a Supplier filter to the SupplierRequest query.
    """
    ids = tuple(sorted({int(value) for value in demand_ids}))

    if not ids:
        return F1ORMData((), (), ())

    selected = tuple(
        DeliveryDemand.objects
        .filter(pk__in=ids)
        .select_related("supplier", "cargo_category")
        .prefetch_related(
            "items__item",
            "supplier_confirmations",
        )
        .order_by("pk")
    )

    dates = {demand.requested_date for demand in selected}
    if not dates:
        return F1ORMData(selected, (), ())

    capacity_demand_ids = tuple(
        DeliveryDemand.objects
        .filter(requested_date__in=dates)
        .values_list("pk", flat=True)
    )

    requests = tuple(
        SupplierRequest.objects
        .filter(demand_id__in=capacity_demand_ids)
        .select_related(
            "demand",
            "supplier",
            "supplier_confirmation",
            "supplier_confirmation__demand",
            "supplier_confirmation__supplier",
        )
        .prefetch_related(
            "item_promises__demand_item",
            "item_promises__supplier_item",
        )
        .order_by("demand_id", "attempt_no", "pk")
    )

    selected_supplier_ids = {d.supplier_id for d in selected}
    selected_item_ids = {
        item.item_id
        for demand in selected
        for item in demand.items.all()
    }

    offers = ()
    if selected_supplier_ids and selected_item_ids:
        offers = tuple(
            SupplierItem.objects
            .filter(
                supplier_id__in=selected_supplier_ids,
                item_id__in=selected_item_ids,
            )
            .select_related("supplier", "item")
            .order_by("supplier_id", "item_id")
        )

    return F1ORMData(
        selected_demands=selected,
        supplier_items=offers,
        capacity_requests=requests,
    )
