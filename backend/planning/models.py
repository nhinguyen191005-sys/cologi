from django.db.models import F, Func, Value, Q
from django.db.models.lookups import Exact

from .json_validators import (
    validate_diagnostics_array,
    validate_json_object,
    validate_demand_snapshot,
)
from django.conf import settings
from django.db import models
from .fields import Char3Field


class RuleSetStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    RETIRED = "RETIRED", "Retired"


class PlanningModuleCode(models.TextChoices):
    F1 = "F1", "F1"
    F2 = "F2", "F2"
    F3 = "F3", "F3"
    F4 = "F4", "F4"
    F5 = "F5", "F5"


class PlanningRunStatus(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class PlanningRunSourceMode(models.TextChoices):
    SYNTHETIC = "SYNTHETIC", "Synthetic"
    MANUAL = "MANUAL", "Manual"
    BATCH = "BATCH", "Batch"
    API = "API", "API"


class EligibilityStatus(models.TextChoices):
    ELIGIBLE = "ELIGIBLE", "Eligible"
    EXCLUDED = "EXCLUDED", "Excluded"


class PlanGuardStatus(models.TextChoices):
    PASS = "PASS", "Pass"
    CONFLICT = "CONFLICT", "Conflict"
    NOT_EVALUATED = "NOT_EVALUATED", "Not evaluated"


class MatchingStatus(models.TextChoices):
    NOT_EVALUATED = "NOT_EVALUATED", "Not evaluated"
    UNMATCHED = "UNMATCHED", "Unmatched"
    INCLUDED = "INCLUDED", "Included"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES", "Multiple candidates"


class CollaborationGroupStatus(models.TextChoices):
    CANDIDATE = "CANDIDATE", "Candidate"
    ACCEPTED = "ACCEPTED", "Accepted"
    MODIFIED = "MODIFIED", "Modified"
    REJECTED = "REJECTED", "Rejected"


class GroupDemandEligibilityStatus(models.TextChoices):
    INCLUDED = "INCLUDED", "Included"
    EXCLUDED = "EXCLUDED", "Excluded"


class PlanningRuleSet(models.Model):
    rule_set_code = models.CharField(max_length=40, unique=True)
    rule_set_name = models.CharField(max_length=150)
    version_no = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=RuleSetStatus.choices,
    )
    effective_from = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_planning_rule_sets",
    )

    class Meta:
        db_table = "rule_sets"
        constraints = [
            models.CheckConstraint(
                condition=Q(version_no__gt=0),
                name="ck_rule_sets_version_positive",
            ),
            models.CheckConstraint(
                condition=Q(status__in=RuleSetStatus.values),
                name="ck_rule_sets_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.rule_set_code} v{self.version_no}"


class PlanningBusinessRule(models.Model):
    rule_set = models.ForeignKey(
        PlanningRuleSet,
        on_delete=models.PROTECT,
        related_name="business_rules",
        db_index=False,
    )
    rule_code = models.CharField(max_length=50)
    module_code = models.CharField(
        max_length=5,
        choices=PlanningModuleCode.choices,
    )
    rule_name = models.CharField(max_length=150)
    description = models.TextField(null=True, blank=True)
    rule_definition = models.JSONField()
    priority = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "business_rules"
        constraints = [
            models.UniqueConstraint(
                fields=("rule_set", "rule_code"),
                name="uq_business_rules_set_code",
            ),
            models.CheckConstraint(
                condition=Q(module_code__in=PlanningModuleCode.values),
                name="ck_business_rules_module_valid",
            ),
            models.CheckConstraint(
                condition=Q(priority__gte=0),
                name="ck_business_rules_priority_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.rule_set.rule_set_code}:{self.rule_code}"


class PlanningParameters(models.Model):
    parameter_key = models.CharField(max_length=100, unique=True)
    parameter_value = models.JSONField()
    data_type = models.CharField(max_length=20)
    description = models.TextField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_planning_parameters",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "planning_parameters"

    def __str__(self):
        return self.parameter_key


class CostProfile(models.Model):
    profile_code = models.CharField(max_length=40, unique=True)
    profile_name = models.CharField(max_length=150)
    currency_code = Char3Field(max_length=3)
    fixed_transport_cost = models.DecimalField(
        max_digits=14, decimal_places=2
    )
    cost_per_km = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    additional_handling_cost = models.DecimalField(
        max_digits=14, decimal_places=2
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "cost_profiles"
        constraints = [
            models.CheckConstraint(
                condition=Q(fixed_transport_cost__gte=0),
                name="ck_cost_profiles_fixed_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    Q(cost_per_km__isnull=True)
                    | Q(cost_per_km__gte=0)
                ),
                name="ck_cost_profiles_per_km_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(additional_handling_cost__gte=0),
                name="ck_cost_profiles_handling_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(currency_code="VND"),
                name="ck_cost_profiles_currency_vnd",
            ),
        ]

    def __str__(self):
        return f"{self.profile_code} - {self.profile_name}"


class PlanningRun(models.Model):
    run_code = models.UUIDField(unique=True)
    rule_set = models.ForeignKey(
        PlanningRuleSet,
        on_delete=models.PROTECT,
        related_name="planning_runs",
    )
    cost_profile = models.ForeignKey(
        CostProfile,
        on_delete=models.PROTECT,
        related_name="planning_runs",
        null=True,
        blank=True,
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="initiated_planning_runs",
        db_index=False,
    )
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PlanningRunStatus.choices,
    )
    source_mode = models.CharField(
        max_length=30,
        choices=PlanningRunSourceMode.choices,
    )
    scenario_tag = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    source_reference = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    parameters_snapshot = models.JSONField(
        validators=[validate_json_object],
    )


    class Meta:
        db_table = "planning_runs"
        indexes = [
            models.Index(
                fields=("status", "started_at"),
                name="ix_planning_runs_status_time",
            ),
            models.Index(
                fields=("initiated_by", "started_at"),
                name="ix_planning_runs_actor_time",
            ),
        ]
        constraints = [
            # PlanningRun.Meta.constraints
            models.CheckConstraint(
                condition=Exact(
                    Func(F("parameters_snapshot"), function="jsonb_typeof"),
                    Value("object"),
                ),
                name="ck_planning_runs_snapshot_object",
            ),
            models.CheckConstraint(
                condition=Q(status__in=PlanningRunStatus.values),
                name="ck_planning_runs_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(source_mode__in=PlanningRunSourceMode.values),
                name="ck_planning_runs_source_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=PlanningRunStatus.IN_PROGRESS,
                      completed_at__isnull=True)
                    | Q(
                        status__in=[
                            PlanningRunStatus.COMPLETED,
                            PlanningRunStatus.FAILED,
                        ],
                        completed_at__isnull=False,
                    )
                ),
                name="ck_planning_runs_completion_time",
            ),
        ]

    def __str__(self):
        return str(self.run_code)


class PlanningRunDemand(models.Model):
    planning_run = models.ForeignKey(
        PlanningRun,
        on_delete=models.PROTECT,
        related_name="run_demands",
        db_index=False,
    )
    demand = models.ForeignKey(
        "demands.DeliveryDemand",
        on_delete=models.PROTECT,
        related_name="planning_run_records",
    )
    demand_snapshot = models.JSONField(
        validators=[validate_demand_snapshot],
    )
    eligibility_status = models.CharField(
        max_length=20,
        choices=EligibilityStatus.choices,
    )
    primary_reason_code = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    plan_guard_status = models.CharField(
        max_length=20,
        choices=PlanGuardStatus.choices,
        default=PlanGuardStatus.NOT_EVALUATED,
    )
    matching_status = models.CharField(
        max_length=30,
        choices=MatchingStatus.choices,
        default=MatchingStatus.NOT_EVALUATED,
    )
    diagnostics = models.JSONField(
        default=list,
        validators=[validate_diagnostics_array],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "planning_run_demands"
        constraints = [
            # PlanningRunDemand.Meta.constraints
            models.CheckConstraint(
                condition=Exact(
                    Func(F("diagnostics"), function="jsonb_typeof"),
                    Value("array"),
                ),
                name="ck_run_demands_diagnostics_array",
            ),
            models.UniqueConstraint(
                fields=("planning_run", "demand"),
                name="uq_planning_run_demands_run_demand",
            ),
            models.CheckConstraint(
                condition=Q(
                    eligibility_status__in=EligibilityStatus.values
                ),
                name="ck_planning_run_demands_eligibility",
            ),
            models.CheckConstraint(
                condition=Q(
                    plan_guard_status__in=PlanGuardStatus.values
                ),
                name="ck_planning_run_demands_plan_guard",
            ),
            models.CheckConstraint(
                condition=Q(matching_status__in=MatchingStatus.values),
                name="ck_planning_run_demands_matching",
            ),
        ]
        indexes = [
            models.Index(
                fields=("planning_run", "eligibility_status"),
                name="ix_run_demands_eligibility",
            ),
            models.Index(
                fields=("planning_run", "matching_status"),
                name="ix_run_demands_matching",
            ),
        ]


class CollaborationGroup(models.Model):
    group_code = models.CharField(max_length=40, unique=True)
    run_code = models.UUIDField()
    status = models.CharField(
        max_length=20,
        choices=CollaborationGroupStatus.choices,
    )
    matching_reason = models.JSONField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_collaboration_groups",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "collaboration_groups"
        indexes = [
            models.Index(
                fields=("run_code", "status"),
                name="ix_collab_groups_run_status",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=CollaborationGroupStatus.values),
                name="ck_collaboration_groups_status",
            ),
        ]

    def __str__(self):
        return self.group_code



class GroupDemand(models.Model):
    pk = models.CompositePrimaryKey("group_id", "demand_id")

    group = models.ForeignKey(
        CollaborationGroup,
        on_delete=models.PROTECT,
        related_name="group_demands",
        db_index=False,
    )
    demand = models.ForeignKey(
        "demands.DeliveryDemand",
        on_delete=models.PROTECT,
        related_name="collaboration_group_links",
    )
    eligibility_status = models.CharField(
        max_length=20,
        choices=GroupDemandEligibilityStatus.choices,
    )
    matching_reason = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "group_demands"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    eligibility_status__in=GroupDemandEligibilityStatus.values
                ),
                name="ck_group_demands_eligibility",
            ),
        ]
