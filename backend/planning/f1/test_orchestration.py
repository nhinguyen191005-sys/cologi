from datetime import date, time
from types import SimpleNamespace as NS
from decimal import Decimal

from planning.f1.cargo_compatibility import (
    dataset_v7_cargo_compatibility_rows,
)


from planning.f1.eligibility import (
    EligibilityBlocker,
    EligibilityStatus,
)
import planning.f1.orchestration as orchestration


def make_demand(demand_id):
    return NS(
        pk=demand_id,
        outlet_id=demand_id,
        requested_date=date(2026, 11, 20),
        cargo_category_id=7,
        requested_start_time=time(8, 0),
        requested_end_time=time(12, 0),
    )


def make_request(demand_id, attempt_no, pk):
    return NS(
        demand_id=demand_id,
        attempt_no=attempt_no,
        pk=pk,
    )


def test_orchestration_uses_latest_request_and_groups_eligible_demands(
    monkeypatch,
):
    demands = (make_demand(1), make_demand(2))
    old_request = make_request(1, 1, 100)
    latest_request = make_request(1, 2, 101)
    second_request = make_request(2, 1, 200)

    orm_data = NS(
        selected_demands=demands,
        capacity_requests=(old_request, latest_request, second_request),
        supplier_items=(),
    )

    seen_confirmations = []

    monkeypatch.setattr(
        orchestration,
        "build_capacity_requests",
        lambda requests: ("capacity-snapshot",),
    )

    def fake_confirmation(demand, request):
        seen_confirmations.append((demand.pk, request))
        return "confirmation"

    monkeypatch.setattr(
        orchestration,
        "build_confirmation_result",
        fake_confirmation,
    )
    monkeypatch.setattr(
        orchestration,
        "build_eligibility_input",
        lambda **kwargs: kwargs["demand"].pk,
    )

    def fake_evaluate(demand_id):
        status = (
            EligibilityStatus.ELIGIBLE
            if demand_id in {1, 2}
            else EligibilityStatus.EXCLUDED
        )
        return NS(
            demand_id=demand_id,
            eligibility_status=status,
        )

    monkeypatch.setattr(
        orchestration,
        "evaluate_demand_eligibility",
        fake_evaluate,
    )

    result = orchestration.evaluate_f1_orm_data(
        orm_data,
        cargo_compatibility_rows=dataset_v7_cargo_compatibility_rows(),
    )

    assert seen_confirmations == [
        (1, latest_request),
        (2, second_request),
    ]
    assert tuple(row.demand_id for row in result.demand_evaluations) == (1, 2)
    assert len(result.candidate_groups) == 1
    assert result.candidate_groups[0].demand_ids == (1, 2)


def test_orchestration_does_not_group_excluded_demands(monkeypatch):
    demands = (make_demand(1), make_demand(2))
    orm_data = NS(
        selected_demands=demands,
        capacity_requests=(),
        supplier_items=(),
    )

    monkeypatch.setattr(
        orchestration,
        "build_capacity_requests",
        lambda requests: (),
    )
    monkeypatch.setattr(
        orchestration,
        "build_confirmation_result",
        lambda demand, request: None,
    )
    monkeypatch.setattr(
        orchestration,
        "build_eligibility_input",
        lambda **kwargs: kwargs["demand"].pk,
    )
    monkeypatch.setattr(
        orchestration,
        "evaluate_demand_eligibility",
        lambda demand_id: NS(
            demand_id=demand_id,
            eligibility_status=EligibilityStatus.EXCLUDED,
        ),
    )

    result = orchestration.evaluate_f1_orm_data(
        orm_data,
        cargo_compatibility_rows=dataset_v7_cargo_compatibility_rows(),
    )

    assert len(result.demand_evaluations) == 2
    assert result.candidate_groups == ()


def test_orchestration_handles_empty_selected_demands(monkeypatch):
    called = []

    monkeypatch.setattr(
        orchestration,
        "build_capacity_requests",
        lambda requests: called.append("capacity") or (),
    )

    result = orchestration.evaluate_f1_orm_data(
        NS(
            selected_demands=(),
            capacity_requests=(),
            supplier_items=(),
        ),
        cargo_compatibility_rows=dataset_v7_cargo_compatibility_rows(),
    )

    assert result.demand_evaluations == ()
    assert result.candidate_groups == ()
    assert called == ["capacity"]

def related(items):
    return NS(all=lambda: items)



def make_integrated_demand(
    demand_id,
    item_id,
    quantity,
):
    quantity = Decimal(str(quantity))

    item = NS(
        is_active=True,
        cargo_category_id=7,
        weight_unit="KG",
    )

    demand_item = NS(
        pk=demand_id * 10,
        demand_id=demand_id,
        item_id=item_id,
        required_weight_kg=quantity,
        unit_of_measure="KG",
        item=item,
    )

    return NS(
        pk=demand_id,
        outlet_id=demand_id,
        supplier_id=10,
        quantity_kg=quantity,
        requested_date=date(2026, 11, 20),
        status="SUBMITTED",
        cargo_category_id=7,
        requested_start_time=time(8, 0),
        requested_end_time=time(12, 0),
        supplier=NS(is_active=True),
        cargo_category=NS(is_active=True),
        items=related([demand_item]),
    )



def make_integrated_request(demand, supplier_item):
    demand_item = demand.items.all()[0]

    request_id = 1000 + demand.pk

    confirmation = NS(
        demand_id=demand.pk,
        supplier_id=demand.supplier_id,
        confirmation_status="CONFIRMED",
        commitment_released_at=None,
    )

    promise = NS(
        pk=2000 + demand.pk,
        supplier_request_id=request_id,
        supplier_item_id=supplier_item.pk,
        demand_item_id=demand_item.pk,
        promised_weight_kg=demand_item.required_weight_kg,
        confirmed_weight_kg=demand_item.required_weight_kg,
        line_status="CONFIRMED",
        demand_item=demand_item,
        supplier_item=supplier_item,
    )

    return NS(
        pk=request_id,
        demand_id=demand.pk,
        supplier_id=demand.supplier_id,
        attempt_no=1,
        request_status="RESPONDED",
        supplier_confirmation=confirmation,
        demand=NS(
            requested_date=demand.requested_date,
            status=demand.status,
        ),
        item_promises=related([promise]),
    )

def test_capacity_overflow_excludes_entire_bucket_and_preserves_other_bucket():
    # Supplier 10 có hai SupplierItem độc lập.
    supplier_item_a = NS(
        pk=501,
        supplier_id=10,
        item_id=7,
        max_daily_supply_kg=Decimal("100"),
        offer_status="ACTIVE",
    )

    supplier_item_b = NS(
        pk=502,
        supplier_id=10,
        item_id=8,
        max_daily_supply_kg=Decimal("100"),
        offer_status="ACTIVE",
    )

    # Bucket A: 60 + 50 = 110 kg, vượt capacity 100 kg.
    demand_1 = make_integrated_demand(1, 7, "60")
    demand_2 = make_integrated_demand(2, 7, "50")

    # Bucket B: 40 + 30 = 70 kg, vẫn trong capacity 100 kg.
    demand_3 = make_integrated_demand(3, 8, "40")
    demand_4 = make_integrated_demand(4, 8, "30")

    demands = (demand_1, demand_2, demand_3, demand_4)

    requests = (
        make_integrated_request(demand_1, supplier_item_a),
        make_integrated_request(demand_2, supplier_item_a),
        make_integrated_request(demand_3, supplier_item_b),
        make_integrated_request(demand_4, supplier_item_b),
    )

    orm_data = NS(
        selected_demands=demands,
        capacity_requests=requests,
        supplier_items=(
            supplier_item_a,
            supplier_item_b,
        ),
    )

    # Không mock adapter, Capacity Engine, Eligibility hoặc Candidate Generation.
    result = orchestration.evaluate_f1_orm_data(
        orm_data,
        cargo_compatibility_rows=dataset_v7_cargo_compatibility_rows(),
    )

    evaluations = {
        row.demand_id: row.eligibility
        for row in result.demand_evaluations
    }

    # Cả hai Demand trong bucket A phải bị loại.
    for demand_id in (1, 2):
        evaluation = evaluations[demand_id]

        assert evaluation.eligibility_status == EligibilityStatus.EXCLUDED
        assert (
            EligibilityBlocker.CAPACITY_EXCEEDED
            in evaluation.blockers
        )

    # Bucket B được đánh giá độc lập và vẫn đủ điều kiện.
    for demand_id in (3, 4):
        evaluation = evaluations[demand_id]

        assert evaluation.eligibility_status == EligibilityStatus.ELIGIBLE
        assert evaluation.blockers == ()

    # Không có Demand thuộc bucket A đi vào Candidate Group.
    # Hai Demand thuộc bucket B được tạo thành một Candidate Group.
    assert [
        group.demand_ids
        for group in result.candidate_groups
    ] == [(3, 4)]

