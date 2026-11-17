from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
    ValidationError as DjangoValidationError,
)

from rest_framework import status
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiResponse, extend_schema

from planning.serializers import (
    F1PreviewRequestSerializer,
    F1PreviewResponseSerializer,
)
from planning.services.run_orchestration import (
    preview_f1_run_for_actor,
)


def raise_api_validation_error(exc):
    if hasattr(exc, "message_dict"):
        detail = exc.message_dict
    else:
        detail = {"non_field_errors": exc.messages}

    raise ValidationError(detail)


class F1RunPreviewView(APIView):
    """
    Read-only F1 preview.

    No PlanningRun, PlanningRunDemand or CollaborationGroup
    records are created by this endpoint.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="planning_f1_run_preview",
        tags=["Planning F1"],
        request=F1PreviewRequestSerializer,
        responses={
            200: F1PreviewResponseSerializer,
            400: OpenApiResponse(
                description="Invalid request or business validation failed."
            ),
            401: OpenApiResponse(
                description="Authentication required."
            ),
            403: OpenApiResponse(
                description="Purchasing Staff or Outlet access required."
            ),
        },
    )
    def post(self, request):
        request_serializer = F1PreviewRequestSerializer(
            data=request.data
        )
        request_serializer.is_valid(raise_exception=True)

        data = request_serializer.validated_data

        try:
            preview = preview_f1_run_for_actor(
                actor=request.user,
                demand_ids=data["demand_ids"],
                rule_set_id=data["rule_set_id"],
                cost_profile_id=data.get("cost_profile_id"),
            )
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc))
        except DjangoValidationError as exc:
            raise_api_validation_error(exc)

        response_serializer = F1PreviewResponseSerializer(preview)

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )
