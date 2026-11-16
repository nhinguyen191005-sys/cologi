
from datetime import date, time
from types import SimpleNamespace as NS

import planning.f1.orchestration as orchestration
from planning.f1.eligibility import EligibilityStatus


def make_demand(demand_id):
    return NS(
        pk=demand_id,
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

    result = orchestration.evaluate_f1_orm_data(orm_data)

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

    result = orchestration.evaluate_f1_orm_data(orm_data)

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
        )
    )

    assert result.demand_evaluations == ()
    assert result.candidate_groups == ()
    assert called == ["capacity"]
