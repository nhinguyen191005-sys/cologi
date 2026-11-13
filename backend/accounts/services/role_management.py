from django.db import transaction
from rest_framework import status

from accounts.models import (
    AuditLog,
    ExternalActorType,
    ExternalUserAccess,
    Role,
    RoleCode,
    User,
    UserOutletAccess,
    UserRole,
)
from masterdata.models import Outlet, Supplier, TransportProvider


class RoleManagementError(Exception):
    def __init__(self, detail, status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _require_manager(actor, target):
    if not actor or not actor.is_authenticated or not actor.is_active:
        raise RoleManagementError(
            "Authentication required.",
            status.HTTP_401_UNAUTHORIZED,
        )

    if actor.pk == target.pk:
        raise RoleManagementError(
            "Manager cannot manage their own business role.",
            status.HTTP_403_FORBIDDEN,
        )

    is_manager = UserRole.objects.filter(
        user=actor,
        user__is_active=True,
        is_active=True,
        role__code=RoleCode.MANAGER,
        role__is_active=True,
    ).exists()

    if not is_manager:
        raise RoleManagementError(
            "An active CoLogi MANAGER role is required.",
            status.HTTP_403_FORBIDDEN,
        )


def _get_target(target_user_id):
    try:
        return User.objects.select_for_update().get(pk=target_user_id)
    except User.DoesNotExist:
        raise RoleManagementError(
            "Target user not found.",
            status.HTTP_404_NOT_FOUND,
        )


def _get_role(role_code):
    if role_code not in RoleCode.values:
        raise RoleManagementError("Invalid business role code.")

    try:
        return Role.objects.get(code=role_code, is_active=True)
    except Role.DoesNotExist:
        raise RoleManagementError(
            "Business role does not exist or is inactive.",
            status.HTTP_400_BAD_REQUEST,
        )


def _active_assignment(user):
    return (
        UserRole.objects.select_for_update()
        .filter(user=user, is_active=True)
        .select_related("role")
        .first()
    )


def _snapshot(user):
    assignment = _active_assignment(user)

    return {
        "role": assignment.role.code if assignment else None,
        "user_role_id": assignment.pk if assignment else None,
        "outlet_ids": list(
            UserOutletAccess.objects.filter(
                user=user,
                is_active=True,
            ).values_list("outlet_id", flat=True)
        ),
        "external_accesses": list(
            ExternalUserAccess.objects.filter(
                user=user,
                is_active=True,
            ).values("actor_type", "supplier_id", "provider_id")
        ),
    }


def _validate_scope(role_code, scope):
    scope = scope or {}

    if not isinstance(scope, dict):
        raise RoleManagementError("Scope must be an object.")

    if role_code == RoleCode.PURCHASING_STAFF:
        if set(scope) != {"outlet_ids"}:
            raise RoleManagementError(
                "PURCHASING_STAFF requires outlet_ids only."
            )

        outlet_ids = scope["outlet_ids"]
        if (
            not isinstance(outlet_ids, list)
            or not outlet_ids
            or any(type(value) is not int for value in outlet_ids)
            or len(outlet_ids) != len(set(outlet_ids))
        ):
            raise RoleManagementError(
                "At least one unique integer outlet_id is required."
            )

        outlets = list(
            Outlet.objects.filter(
                pk__in=outlet_ids,
                is_active=True,
            )
        )
        if len(outlets) != len(outlet_ids):
            raise RoleManagementError(
                "One or more outlets do not exist or are inactive."
            )
        return {"outlets": outlets}

    if role_code == RoleCode.SUPPLIER:
        if set(scope) != {"supplier_id"}:
            raise RoleManagementError(
                "SUPPLIER requires supplier_id only."
            )

        try:
            supplier_id = int(scope["supplier_id"])
        except (TypeError, ValueError):
            raise RoleManagementError("A valid supplier_id is required.")

        try:
            supplier = Supplier.objects.get(
                pk=supplier_id,
                is_active=True,
            )
        except Supplier.DoesNotExist:
            raise RoleManagementError(
                "Supplier does not exist or is inactive."
            )
        return {"supplier": supplier}

    if role_code == RoleCode.TRANSPORT_PROVIDER:
        if set(scope) != {"provider_id"}:
            raise RoleManagementError(
                "TRANSPORT_PROVIDER requires provider_id only."
            )

        try:
            provider_id = int(scope["provider_id"])
        except (TypeError, ValueError):
            raise RoleManagementError("A valid provider_id is required.")

        try:
            provider = TransportProvider.objects.get(
                pk=provider_id,
                provider_code="TP001",
                is_active=True,
            )
        except TransportProvider.DoesNotExist:
            raise RoleManagementError(
                "MVP only permits the active TP001 provider."
            )
        return {"provider": provider}

    if role_code == RoleCode.MANAGER:
        if scope:
            raise RoleManagementError(
                "MANAGER must not have an external scope."
            )
        return {}

    raise RoleManagementError("Unsupported business role.")


def _deactivate_scopes(user):
    UserOutletAccess.objects.filter(
        user=user,
        is_active=True,
    ).update(is_active=False)

    ExternalUserAccess.objects.filter(
        user=user,
        is_active=True,
    ).update(is_active=False)


def _apply_scope(actor, user, role_code, validated_scope):
    if role_code == RoleCode.PURCHASING_STAFF:
        for outlet in validated_scope["outlets"]:
            access, created = UserOutletAccess.objects.get_or_create(
                user=user,
                outlet=outlet,
                defaults={
                    "is_active": True,
                    "assigned_by": actor,
                },
            )
            if not created and (
                not access.is_active or access.assigned_by_id != actor.pk
            ):
                access.is_active = True
                access.assigned_by = actor
                access.save()

    elif role_code == RoleCode.SUPPLIER:
        access, created = ExternalUserAccess.objects.get_or_create(
            user=user,
            actor_type=ExternalActorType.SUPPLIER,
            defaults={
                "supplier": validated_scope["supplier"],
                "is_active": True,
            },
        )
        if not created:
            access.supplier = validated_scope["supplier"]
            access.provider = None
            access.is_active = True
            access.save()

    elif role_code == RoleCode.TRANSPORT_PROVIDER:
        access, created = ExternalUserAccess.objects.get_or_create(
            user=user,
            actor_type=ExternalActorType.TRANSPORT_PROVIDER,
            defaults={
                "provider": validated_scope["provider"],
                "is_active": True,
            },
        )
        if not created:
            access.supplier = None
            access.provider = validated_scope["provider"]
            access.is_active = True
            access.save()


def _write_audit(actor, user, action, old_values, new_values, ip_address):
    AuditLog.objects.create(
        actor_user=actor,
        action=action,
        entity_type="USER_ROLE",
        entity_id=str(user.pk),
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
    )


@transaction.atomic
def assign_role(actor, target_user_id, role_code, scope=None, ip_address=None):
    user = _get_target(target_user_id)
    _require_manager(actor, user)

    if not user.is_active:
        raise RoleManagementError("Cannot assign a role to an inactive user.")

    if _active_assignment(user):
        raise RoleManagementError(
            "User already has an active business role. Use change_role.",
            status.HTTP_409_CONFLICT,
        )

    role = _get_role(role_code)
    validated_scope = _validate_scope(role.code, scope)
    old_values = _snapshot(user)

    # Clean up any stale scopes before establishing the new assignment.
    _deactivate_scopes(user)

    assignment = UserRole.objects.create(
        user=user,
        role=role,
        assigned_by=actor,
    )

    _apply_scope(actor, user, role.code, validated_scope)

    _write_audit(
        actor,
        user,
        "ASSIGN_ROLE",
        old_values,
        {
            "role": role.code,
            "user_role_id": assignment.pk,
            "scope": {
                "outlet_ids": [
                    outlet.pk for outlet in validated_scope.get("outlets", [])
                ],
                "supplier_id": getattr(
                    validated_scope.get("supplier"), "pk", None
                ),
                "provider_id": getattr(
                    validated_scope.get("provider"), "pk", None
                ),
            },
        },
        ip_address,
    )
    return assignment


@transaction.atomic
def change_role(actor, target_user_id, new_role_code, scope=None, ip_address=None):
    user = _get_target(target_user_id)
    _require_manager(actor, user)

    if not user.is_active:
        raise RoleManagementError("Cannot change the role of an inactive user.")

    current = _active_assignment(user)
    if current is None:
        raise RoleManagementError(
            "User has no active business role to change.",
            status.HTTP_409_CONFLICT,
        )

    new_role = _get_role(new_role_code)
    if current.role_id == new_role.pk:
        raise RoleManagementError(
            "The user already has this role.",
            status.HTTP_409_CONFLICT,
        )

    validated_scope = _validate_scope(new_role.code, scope)
    old_values = _snapshot(user)

    # Deactivate scopes while the old role is still active.
    _deactivate_scopes(user)
    current.is_active = False
    current.save(update_fields=("is_active",))

    assignment = UserRole.objects.create(
        user=user,
        role=new_role,
        assigned_by=actor,
    )

    _apply_scope(actor, user, new_role.code, validated_scope)

    _write_audit(
        actor,
        user,
        "CHANGE_ROLE",
        old_values,
        {
            "role": new_role.code,
            "user_role_id": assignment.pk,
            "scope": {
                "outlet_ids": [
                    outlet.pk for outlet in validated_scope.get("outlets", [])
                ],
                "supplier_id": getattr(
                    validated_scope.get("supplier"), "pk", None
                ),
                "provider_id": getattr(
                    validated_scope.get("provider"), "pk", None
                ),
            },
        },
        ip_address,
    )
    return assignment


@transaction.atomic
def revoke_role(actor, target_user_id, ip_address=None):
    user = _get_target(target_user_id)
    _require_manager(actor, user)

    current = _active_assignment(user)
    if current is None:
        raise RoleManagementError(
            "User has no active business role to revoke.",
            status.HTTP_409_CONFLICT,
        )

    old_values = _snapshot(user)

    # Deactivate scopes before deactivating the corresponding role.
    _deactivate_scopes(user)
    current.is_active = False
    current.save(update_fields=("is_active",))

    _write_audit(
        actor,
        user,
        "REVOKE_ROLE",
        old_values,
        {
            "role": None,
            "user_role_id": current.pk,
            "scopes_active": False,
        },
        ip_address,
    )
    return current
