from collections.abc import Mapping

from rest_framework import serializers


class StrictInputMixin:
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = set(data.keys()) - set(self.fields.keys())
            if unknown:
                raise serializers.ValidationError({
                    "non_field_errors": [
                        "Unsupported fields: "
                        + ", ".join(sorted(str(x) for x in unknown))
                    ]
                })
        return super().to_internal_value(data)


class F1PreviewRequestSerializer(
    StrictInputMixin,
    serializers.Serializer,
):
    demand_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        min_length=1,
    )
    rule_set_id = serializers.IntegerField(min_value=1)
    cost_profile_id = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
    )

    def validate_demand_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Duplicate Demand IDs are not allowed."
            )
        return value


class DemandRunPreviewSerializer(serializers.Serializer):
    demand_id = serializers.IntegerField()
    eligibility_status = serializers.CharField()
    blockers = serializers.ListField(
        child=serializers.CharField()
    )
    diagnostics = serializers.ListField(
        child=serializers.CharField()
    )
    primary_reason_code = serializers.CharField(
        allow_null=True
    )
    plan_guard_status = serializers.CharField()
    matching_status = serializers.CharField()
    detail = serializers.CharField()


class CandidateGroupPreviewSerializer(serializers.Serializer):
    demand_ids = serializers.ListField(
        child=serializers.IntegerField()
    )
    requested_date = serializers.DateField()
    cargo_category_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    common_start_time = serializers.TimeField()
    common_end_time = serializers.TimeField()


class F1PreviewResponseSerializer(serializers.Serializer):
    captured_at = serializers.CharField(
        help_text="ISO 8601 timestamp with timezone (date-time).",
    )
    rule_set_id = serializers.IntegerField()
    rule_set_code = serializers.CharField()
    rule_set_version = serializers.IntegerField()
    business_rule_codes = serializers.ListField(
        child=serializers.CharField()
    )
    demand_results = DemandRunPreviewSerializer(many=True)
    candidate_groups = CandidateGroupPreviewSerializer(many=True)
    business_rules_execution = serializers.CharField()
    plan_guard_status = serializers.CharField()
    matching_status = serializers.CharField()
    ready_to_finalize = serializers.BooleanField()
    all_demands_eligible = serializers.BooleanField(read_only=True)
