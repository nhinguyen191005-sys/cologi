from rest_framework.permissions import BasePermission

from .models import (
    ExternalActorType,
    ExternalUserAccess,
    UserRole,
    UserOutletAccess,
    RoleCode,
)


def get_active_external_access(user, actor_type):
    """
    Return the user's active external access only when the matching
    business role is also assigned and active.
    """
    if (
        not getattr(user, "is_authenticated", False)
        or actor_type not in ExternalActorType.values
    ):
        return None

    return (
        ExternalUserAccess.objects
        .filter(
            user=user,
            actor_type=actor_type,
            is_active=True,
            user__user_roles__role__code=actor_type,
            user__user_roles__role__is_active=True,
        )
        .select_related("supplier", "provider")
        .distinct()
        .first()
    )


class HasCoLogiRole(BasePermission):
    """
    Allow access only when the user has at least one role declared
    in view.required_roles.

    Views must declare required_roles. Missing/empty configuration
    denies access (fail closed).
    """

    message = "Tài khoản của bạn chưa được cấp vai trò nghiệp vụ CoLogi cần thiết."

    def has_permission(self, request, view):
        user = request.user

        if not getattr(user, "is_authenticated", False):
            return False

        required_roles = getattr(view, "required_roles", ())
        if isinstance(required_roles, str):
            required_roles = (required_roles,)

        required_roles = tuple(required_roles)
        if not required_roles:
            return False

        return UserRole.objects.filter(
            user=user,
            role__code__in=required_roles,
            role__is_active=True,
        ).exists()


class HasExternalActorScope(BasePermission):
    """
    Require an active external actor access declared by
    view.required_actor_type.

    For object-level authorization, the view must also declare
    view.external_scope_field, for example "supplier_id" or
    "provider_id". "pk" / "id" can be used when the protected
    object is the Supplier or TransportProvider itself.
    """

    message = "Bạn không có quyền truy cập vào phạm vi tác nhân bên ngoài này."

    def _get_access(self, request, view):
        actor_type = getattr(view, "required_actor_type", None)
        return get_active_external_access(request.user, actor_type)

    def has_permission(self, request, view):
        return self._get_access(request, view) is not None

    def has_object_permission(self, request, view, obj):
        access = self._get_access(request, view)
        if access is None:
            return False

        actor_type = view.required_actor_type
        scope_field = getattr(view, "external_scope_field", None)

        # Fail closed unless the view explicitly identifies the
        # resource field that carries its external scope.
        if not scope_field:
            return False

        object_scope_id = (
            getattr(obj, "pk", None)
            if scope_field in {"pk", "id"}
            else getattr(obj, scope_field, None)
        )

        if actor_type == ExternalActorType.SUPPLIER:
            expected_scope_id = access.supplier_id
        elif actor_type == ExternalActorType.TRANSPORT_PROVIDER:
            expected_scope_id = access.provider_id
        else:
            return False

        return (
            expected_scope_id is not None
            and object_scope_id == expected_scope_id
        )

    def get_active_user_outlet_accesses(user):
        """
        Return active outlet access records only when:
        - User is authenticated.
        - User has an active PURCHASING_STAFF role.
        - UserOutletAccess is active.
        - Outlet is active.
        """
        if not getattr(user, "is_authenticated", False):
            return UserOutletAccess.objects.none()

        return (
            UserOutletAccess.objects.filter(
                user=user,
                is_active=True,
                outlet__is_active=True,
                user__user_roles__role__code=RoleCode.PURCHASING_STAFF,
                user__user_roles__role__is_active=True,
            )
            .select_related("outlet")
            .distinct()
        )


    def filter_queryset_by_outlet_access(
        queryset,
        user,
        outlet_lookup="outlet_id",
    ):
        """
        Restrict a queryset to the user's active outlet scope.

        For Demand:
            outlet_lookup="outlet_id"

        For Outlet:
            outlet_lookup="pk"
        """
        outlet_ids = get_active_user_outlet_accesses(
            user
        ).values_list("outlet_id", flat=True)

        return queryset.filter(
            **{f"{outlet_lookup}__in": outlet_ids}
        )


    class HasOutletAccess(BasePermission):
        """
        Require active PURCHASING_STAFF role and active Outlet access.

        Optional view configuration:

            outlet_request_field = "outlet_id"
            outlet_scope_field = "outlet_id"

        For Outlet detail resources:

            outlet_scope_field = "pk"

        List endpoints must additionally filter their querysets
        using filter_queryset_by_outlet_access().
        """

        message = "Tài khoản của bạn chưa được cấp quyền truy cập vào điểm bán này."

        def has_permission(self, request, view):
            accesses = get_active_user_outlet_accesses(
                request.user
            )

            if not accesses.exists():
                return False

            request_field = getattr(
                view,
                "outlet_request_field",
                None,
            )

            if not request_field:
                return True

            outlet_id = request.data.get(request_field)

            if outlet_id in (None, ""):
                # Missing required fields are validated by serializer.
                # Existing resource scope is checked at object level.
                return True

            return accesses.filter(
                outlet_id=outlet_id,
            ).exists()

        def has_object_permission(self, request, view, obj):
            scope_field = getattr(
                view,
                "outlet_scope_field",
                None,
            )

            if not scope_field:
                return False

            if scope_field in {"pk", "id"}:
                outlet_id = obj.pk
            else:
                outlet_id = getattr(obj, scope_field, None)

            if outlet_id is None:
                return False

            return get_active_user_outlet_accesses(
                request.user
            ).filter(
                outlet_id=outlet_id,
            ).exists()

def get_active_user_outlet_accesses(user):
    """
    Return active Outlet access records for authenticated users
    with an active PURCHASING_STAFF role.
    """
    if not getattr(user, "is_authenticated", False):
        return UserOutletAccess.objects.none()

    return (
        UserOutletAccess.objects.filter(
            user=user,
            is_active=True,
            outlet__is_active=True,
            user__user_roles__role__code=RoleCode.PURCHASING_STAFF,
            user__user_roles__role__is_active=True,
        )
        .select_related("outlet")
        .distinct()
    )


def filter_queryset_by_outlet_access(
    queryset,
    user,
    outlet_lookup="outlet_id",
):
    """Limit a queryset to the user's active Outlet access."""
    outlet_ids = get_active_user_outlet_accesses(
        user
    ).values_list("outlet_id", flat=True)

    return queryset.filter(
        **{f"{outlet_lookup}__in": outlet_ids}
    )


class HasOutletAccess(BasePermission):
    """
    Require active PURCHASING_STAFF role and active Outlet access.

    Optional view attributes:
        outlet_request_field = "outlet_id"
        outlet_scope_field = "outlet_id"

    For Outlet detail views:
        outlet_scope_field = "pk"

    List views must additionally filter their querysets.
    """

    message = "Tài khoản của bạn chưa được cấp quyền truy cập vào điểm bán này."

    def has_permission(self, request, view):
        accesses = get_active_user_outlet_accesses(request.user)

        if not accesses.exists():
            return False

        request_field = getattr(
            view,
            "outlet_request_field",
            None,
        )

        if not request_field:
            return True

        outlet_id = request.data.get(request_field)

        if outlet_id in (None, ""):
            # Missing fields are handled by serializer validation.
            return True

        try:
            outlet_id = int(outlet_id)
        except (TypeError, ValueError):
            # Malformed input is handled by serializer validation.
            return True

        return accesses.filter(outlet_id=outlet_id).exists()

    def has_object_permission(self, request, view, obj):
        scope_field = getattr(
            view,
            "outlet_scope_field",
            None,
        )

        if not scope_field:
            return False

        if scope_field in {"pk", "id"}:
            outlet_id = obj.pk
        else:
            outlet_id = getattr(obj, scope_field, None)

        if outlet_id is None:
            return False

        return get_active_user_outlet_accesses(
            request.user
        ).filter(outlet_id=outlet_id).exists()
