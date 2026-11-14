from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import RoleCode
from accounts.permissions import get_active_user_outlet_accesses


class DemandRoleOutletPermission(BasePermission):
    """
    Demand access policy.

    PURCHASING_STAFF:
        Read within active Outlet access.
        Create within the specifically assigned Outlet.
        PATCH own DRAFT demands within active Outlet access.

    MANAGER:
        Read all demands; never create or update.

    SUPPLIER and TRANSPORT_PROVIDER:
        No access to Demand APIs.
    """

    message = "You do not have permission to access this demand resource."

    def _active_roles(self, user):
        if not getattr(user, "is_authenticated", False):
            return set()

        return set(
            user.user_roles.filter(
                is_active=True,
                role__is_active=True,
            ).values_list("role__code", flat=True)
        )

    def has_permission(self, request, view):
        if not getattr(request.user, "is_authenticated", False):
            return False

        roles = self._active_roles(request.user)
        is_manager = RoleCode.MANAGER in roles
        is_purchasing = RoleCode.PURCHASING_STAFF in roles

        if request.method in SAFE_METHODS:
            if is_manager:
                return True

            return (
                is_purchasing
                and get_active_user_outlet_accesses(
                    request.user
                ).exists()
            )

        # Manager is read-only, including users who also have
        # PURCHASING_STAFF assigned.
        if is_manager or not is_purchasing:
            return False

        accesses = get_active_user_outlet_accesses(request.user)
        if not accesses.exists():
            return False

        if request.method == "POST":
            outlet_id = request.data.get("outlet_id")

            # Missing or malformed values are validated by the serializer.
            if outlet_id in (None, ""):
                return True

            try:
                outlet_id = int(outlet_id)
            except (TypeError, ValueError):
                return True

            return accesses.filter(outlet_id=outlet_id).exists()

        if request.method == "PATCH":
            return True

        return False

    def has_object_permission(self, request, view, obj):
        roles = self._active_roles(request.user)

        if request.method in SAFE_METHODS:
            if RoleCode.MANAGER in roles:
                return True

        # No write access for Manager, even if the user has multiple roles.
        if RoleCode.MANAGER in roles:
            return False

        if RoleCode.PURCHASING_STAFF not in roles:
            return False

        has_outlet_scope = get_active_user_outlet_accesses(
            request.user
        ).filter(
            outlet_id=obj.outlet_id
        ).exists()

        if not has_outlet_scope:
            return False

        if request.method == "PATCH":
            return obj.created_by_id == request.user.pk

        return request.method in SAFE_METHODS


class DemandSubmitPermission(BasePermission):
    """
    Submit is restricted to the Demand creator, within active Outlet scope.

    MANAGER is always read-only, including dual-role accounts.
    """

    message = "Only the Demand creator with Purchasing Staff Outlet access may submit."

    def has_permission(self, request, view):
        if not getattr(request.user, "is_authenticated", False):
            return False

        roles = set(
            request.user.user_roles.filter(
                is_active=True,
                role__is_active=True,
            ).values_list("role__code", flat=True)
        )

        if (
            RoleCode.MANAGER in roles
            or RoleCode.PURCHASING_STAFF not in roles
        ):
            return False

        return get_active_user_outlet_accesses(request.user).exists()

    def has_object_permission(self, request, view, obj):
        roles = set(
            request.user.user_roles.filter(
                is_active=True,
                role__is_active=True,
            ).values_list("role__code", flat=True)
        )

        if (
            RoleCode.MANAGER in roles
            or RoleCode.PURCHASING_STAFF not in roles
        ):
            return False

        if obj.created_by_id != request.user.pk:
            return False

        return get_active_user_outlet_accesses(
            request.user
        ).filter(
            outlet_id=obj.outlet_id,
        ).exists()

class DemandCancelPermission(BasePermission):
    """
    Cancel is restricted to the Demand creator, within active Outlet scope.

    MANAGER is always read-only, including dual-role accounts.
    """

    message = (
        "Only the Demand creator with Purchasing Staff Outlet "
        "access may cancel."
    )

    def has_permission(self, request, view):
        if not getattr(request.user, "is_authenticated", False):
            return False

        roles = set(
            request.user.user_roles.filter(
                is_active=True,
                role__is_active=True,
            ).values_list("role__code", flat=True)
        )

        if (
            RoleCode.MANAGER in roles
            or RoleCode.PURCHASING_STAFF not in roles
        ):
            return False

        return get_active_user_outlet_accesses(request.user).exists()

    def has_object_permission(self, request, view, obj):
        roles = set(
            request.user.user_roles.filter(
                is_active=True,
                role__is_active=True,
            ).values_list("role__code", flat=True)
        )

        if (
            RoleCode.MANAGER in roles
            or RoleCode.PURCHASING_STAFF not in roles
        ):
            return False

        if obj.created_by_id != request.user.pk:
            return False

        return get_active_user_outlet_accesses(
            request.user
        ).filter(
            outlet_id=obj.outlet_id,
        ).exists()