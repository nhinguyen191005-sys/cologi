from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from accounts.models import ExternalActorType
from accounts.permissions import (
    HasExternalActorScope,
    get_active_external_access,
)


class ProviderScopeMixin:
    permission_classes = [IsAuthenticated, HasExternalActorScope]
    required_actor_type = ExternalActorType.TRANSPORT_PROVIDER
    external_scope_field = "provider_id"

    def get_provider_access(self):
        access = get_active_external_access(
            self.request.user,
            ExternalActorType.TRANSPORT_PROVIDER,
        )
        if access is None or access.provider_id is None:
            raise PermissionDenied(
                "Active transport provider access is required."
            )
        return access

    def get_provider_id(self):
        return self.get_provider_access().provider_id
