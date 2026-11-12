from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )


class ExternalAccessSerializer(serializers.Serializer):
    actor_type = serializers.CharField()
    supplier_id = serializers.IntegerField(allow_null=True)
    provider_id = serializers.IntegerField(allow_null=True)


class CurrentUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    roles = serializers.ListField(child=serializers.CharField())
    external_accesses = ExternalAccessSerializer(many=True)