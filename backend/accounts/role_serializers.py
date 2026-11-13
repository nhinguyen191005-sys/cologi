from rest_framework import serializers

from accounts.models import RoleCode


class RoleAssignmentSerializer(serializers.Serializer):
    role_code = serializers.ChoiceField(choices=RoleCode.choices)
    outlet_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=False,
    )
    supplier_id = serializers.IntegerField(min_value=1, required=False)
    provider_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        role_code = attrs["role_code"]
        scope_fields = {
            key for key in ("outlet_ids", "supplier_id", "provider_id")
            if key in attrs
        }

        expected = {
            RoleCode.PURCHASING_STAFF: {"outlet_ids"},
            RoleCode.SUPPLIER: {"supplier_id"},
            RoleCode.TRANSPORT_PROVIDER: {"provider_id"},
            RoleCode.MANAGER: set(),
        }[role_code]

        if scope_fields != expected:
            raise serializers.ValidationError(
                f"Scope fields for {role_code} must be {sorted(expected)}."
            )

        if "outlet_ids" in attrs:
            outlet_ids = attrs["outlet_ids"]
            if len(outlet_ids) != len(set(outlet_ids)):
                raise serializers.ValidationError({
                    "outlet_ids": "Duplicate outlet IDs are not allowed."
                })

        return attrs

    def get_scope(self):
        data = self.validated_data
        return {
            key: data[key]
            for key in ("outlet_ids", "supplier_id", "provider_id")
            if key in data
        }


class RoleChangeSerializer(RoleAssignmentSerializer):
    pass


class RoleSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    user_role_id = serializers.IntegerField()


class ExternalAccessSummarySerializer(serializers.Serializer):
    actor_type = serializers.CharField()
    supplier_id = serializers.IntegerField(allow_null=True)
    provider_id = serializers.IntegerField(allow_null=True)


class ManagedUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    is_active = serializers.BooleanField()
    active_role = RoleSummarySerializer(allow_null=True)
    outlet_ids = serializers.ListField(
        child=serializers.IntegerField()
    )
    external_accesses = ExternalAccessSummarySerializer(many=True)


class RoleManagementResultSerializer(serializers.Serializer):
    detail = serializers.CharField()
    user_role_id = serializers.IntegerField()
    user = ManagedUserSerializer()
