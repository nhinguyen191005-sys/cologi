
"""Read-only F1 orchestration over preloaded Django ORM records."""

from dataclasses import dataclass

from planning.f1.adapter import (
    build_capacity_requests,
    build_confirmation_result,
    build_eligibility_input,
    latest_request_by_demand,
)
from planning.f1.candidate_groups import (
    CandidateDemandInput,
    CandidateGroup,
    generate_candidate_groups,
)
from planning.f1.eligibility import (
    DemandEligibilityResult,
    evaluate_demand_eligibility,
)


@dataclass(frozen=True)
class F1DemandEvaluation:
    demand_id: int
    eligibility: DemandEligibilityResult
    candidate_input: CandidateDemandInput


@dataclass(frozen=True)
class F1Evaluation:
    demand_evaluations: tuple[F1DemandEvaluation, ...]
    candidate_groups: tuple[CandidateGroup, ...]


def evaluate_f1_orm_data(orm_data) -> F1Evaluation:
    """Evaluate selected Demands and produce all valid Candidate Groups.

    This function is read-only. It does not create PlanningRun records,
    PlanningRunDemand rows, CollaborationGroups or GroupDemand rows.
    """
    selected_demands = tuple(orm_data.selected_demands)
    all_requests = tuple(orm_data.capacity_requests)
    offers = tuple(orm_data.supplier_items)

    latest_by_demand = latest_request_by_demand(all_requests)
    capacity_requests = build_capacity_requests(all_requests)

    evaluations = []
    candidate_inputs = []

    for demand in selected_demands:
        latest_request = latest_by_demand.get(demand.pk)
        confirmation = build_confirmation_result(
            demand,
            latest_request,
        )

        eligibility_input = build_eligibility_input(
            demand=demand,
            supplier_items=offers,
            confirmation_result=confirmation,
            capacity_requests=capacity_requests,
        )
        eligibility = evaluate_demand_eligibility(eligibility_input)

        candidate_input = CandidateDemandInput(
            demand_id=demand.pk,
            eligibility_status=eligibility.eligibility_status.value,
            requested_date=demand.requested_date,
            cargo_category_id=demand.cargo_category_id,
            requested_start_time=demand.requested_start_time,
            requested_end_time=demand.requested_end_time,
        )

        evaluations.append(
            F1DemandEvaluation(
                demand_id=demand.pk,
                eligibility=eligibility,
                candidate_input=candidate_input,
            )
        )

        candidate_inputs.append(candidate_input)

    groups = generate_candidate_groups(tuple(candidate_inputs))

    return F1Evaluation(
        demand_evaluations=tuple(evaluations),
        candidate_groups=tuple(groups),
    )
