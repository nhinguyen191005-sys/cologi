from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from accounts.models import (
    ExternalUserAccess,
    UserOutletAccess,
    UserRole,
)
from accounts.role_serializers import (
    ManagedUserSerializer,
    RoleAssignmentSerializer,
    RoleChangeSerializer,
    RoleManagementResultSerializer,
)
from accounts.services.role_management import (
    RoleManagementError,
    assign_role,
    change_role,
    revoke_role,
)

User = get_user_model()


def _ip_address(request):
    return request.META.get("REMOTE_ADDR")


def _error_response(exc):
    return Response(
        {"detail": exc.detail},
        status=exc.status_code,
    )


def _user_role_data(user):
    assignment = (
        UserRole.objects.filter(user=user, is_active=True)
        .select_related("role")
        .first()
    )

    outlet_ids = list(
        UserOutletAccess.objects.filter(
            user=user,
            is_active=True,
            outlet__is_active=True,
        ).values_list("outlet_id", flat=True)
    )

    external_accesses = list(
        ExternalUserAccess.objects.filter(
            user=user,
            is_active=True,
        ).values(
            "actor_type",
            "supplier_id",
            "provider_id",
        )
    )

    return {
        "id": user.pk,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "active_role": (
            {
                "id": assignment.role_id,
                "code": assignment.role.code,
                "name": assignment.role.name,
                "user_role_id": assignment.pk,
            }
            if assignment else None
        ),
        "outlet_ids": outlet_ids,
        "external_accesses": external_accesses,
    }


class RoleManagementUserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ManagedUserSerializer})
    def get(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            # Reuse the same authorization rules as mutation services.
            from accounts.services.role_management import _require_manager
            _require_manager(request.user, user)
        except User.DoesNotExist:
            return Response(
                {"detail": "Target user not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except RoleManagementError as exc:
            return _error_response(exc)

        return Response(_user_role_data(user))


class AssignRoleView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=RoleAssignmentSerializer,
        responses={201: RoleManagementResultSerializer},
    )
    def post(self, request, user_id):
        serializer = RoleAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            assignment = assign_role(
                actor=request.user,
                target_user_id=user_id,
                role_code=serializer.validated_data["role_code"],
                scope=serializer.get_scope(),
                ip_address=_ip_address(request),
            )
        except RoleManagementError as exc:
            return _error_response(exc)

        return Response(
            {
                "detail": "Role assigned successfully.",
                "user_role_id": assignment.pk,
                "user": _user_role_data(assignment.user),
            },
            status=status.HTTP_201_CREATED,
        )


class ChangeRoleView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=RoleChangeSerializer,
        responses={200: RoleManagementResultSerializer},
    )
    def post(self, request, user_id):
        serializer = RoleChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            assignment = change_role(
                actor=request.user,
                target_user_id=user_id,
                new_role_code=serializer.validated_data["role_code"],
                scope=serializer.get_scope(),
                ip_address=_ip_address(request),
            )
        except RoleManagementError as exc:
            return _error_response(exc)

        return Response(
            {
                "detail": "Role changed successfully.",
                "user_role_id": assignment.pk,
                "user": _user_role_data(assignment.user),
            },
            status=status.HTTP_200_OK,
        )


class RevokeRoleView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: RoleManagementResultSerializer},
    )
    def post(self, request, user_id):
        try:
            assignment = revoke_role(
                actor=request.user,
                target_user_id=user_id,
                ip_address=_ip_address(request),
            )
        except RoleManagementError as exc:
            return _error_response(exc)

        return Response(
            {
                "detail": "Role revoked successfully.",
                "user_role_id": assignment.pk,
                "user": _user_role_data(assignment.user),
            },
            status=status.HTTP_200_OK,
        )
