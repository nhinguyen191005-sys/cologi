from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiResponse, extend_schema

from accounts.models import RoleCode
from accounts.permissions import filter_queryset_by_outlet_access

from .models import DeliveryDemand
from .permissions import (
    DemandRoleOutletPermission,
    DemandSubmitPermission,
)
from .serializers import (
    DeliveryDemandReadSerializer,
    DemandCreateSerializer,
    DemandPatchSerializer,
    DemandSupplierSelectionSerializer,
    DemandStatusResponseSerializer,
    DemandSubmitResponseSerializer,
    DemandSupplierSelectionResponseSerializer,
)
from .services import (
    create_draft_demand,
    select_supplier_for_submitted_demand,
    submit_demand,
    update_draft_demand,
)


class DemandConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The demand cannot be changed in its current state."
    default_code = "demand_conflict"


def raise_api_validation_error(exc):
    if hasattr(exc, "message_dict"):
        detail = exc.message_dict
    else:
        detail = {"non_field_errors": exc.messages}

    raise ValidationError(detail)


def normalize_item_rows(rows):
    """
    Convert PrimaryKeyRelatedField Item objects into the integer IDs
    expected by the demand service.
    """
    normalized = []

    for row in rows:
        item_data = dict(row)
        item_data["item_id"] = item_data["item_id"].pk
        normalized.append(item_data)

    return normalized


def demand_queryset_for_user(user):
    queryset = (
        DeliveryDemand.objects
        .select_related(
            "supplier",
            "outlet",
            "cargo_category",
            "created_by",
        )
        .prefetch_related("items__item")
    )

    is_manager = user.user_roles.filter(
        role__code=RoleCode.MANAGER,
        role__is_active=True,
    ).exists()

    if is_manager:
        return queryset

    return filter_queryset_by_outlet_access(queryset, user)


class DemandObjectMixin:
    permission_classes = [
        IsAuthenticated,
        DemandRoleOutletPermission,
    ]

    def get_demand_object(self, request, pk):
        demand = get_object_or_404(
            demand_queryset_for_user(request.user),
            pk=pk,
        )
        self.check_object_permissions(request, demand)
        return demand


class DemandListCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        DemandRoleOutletPermission,
    ]

    @extend_schema(
        operation_id="demands_list",
        tags=["Demands"],
        responses={
            200: DeliveryDemandReadSerializer(many=True),
            401: OpenApiResponse(description="Authentication required."),
            403: OpenApiResponse(description="The actor is not allowed to list demands."),
        },
    )
    def get(self, request):
        queryset = demand_queryset_for_user(request.user)

        serializer = DeliveryDemandReadSerializer(
            queryset,
            many=True,
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="demands_create",
        tags=["Demands"],
        request=DemandCreateSerializer,
        responses={
            201: DeliveryDemandReadSerializer,
            400: OpenApiResponse(description="Request validation or business validation failed."),
            401: OpenApiResponse(description="Authentication required."),
            403: OpenApiResponse(description="The actor is not allowed to create this demand."),
        },
    )
    def post(self, request):
        serializer = DemandCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = dict(serializer.validated_data)
        supplier = data.pop("supplier_id")
        outlet = data.pop("outlet_id")
        item_rows = normalize_item_rows(data.pop("items"))

        try:
            demand = create_draft_demand(
                supplier_id=supplier.pk,
                outlet_id=outlet.pk,
                created_by=request.user,
                items=item_rows,
                **data,
            )
        except DjangoValidationError as exc:
            raise_api_validation_error(exc)

        demand = demand_queryset_for_user(request.user).get(
            pk=demand.pk
        )
        response_serializer = DeliveryDemandReadSerializer(demand)

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class DemandDetailView(DemandObjectMixin, APIView):
    @extend_schema(
        operation_id="demands_retrieve",
        tags=["Demands"],
        responses={
            200: DeliveryDemandReadSerializer,
            401: OpenApiResponse(description="Authentication required."),
            403: OpenApiResponse(description="The actor is not allowed to access this demand."),
            404: OpenApiResponse(description="Demand not found in the actor's accessible scope."),
        },
    )
    def get(self, request, pk):
        demand = self.get_demand_object(request, pk)
        serializer = DeliveryDemandReadSerializer(demand)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="demands_update",
        tags=["Demands"],
        request=DemandPatchSerializer,
        responses={
            200: DeliveryDemandReadSerializer,
            400: OpenApiResponse(description="Request or business validation failed."),
            401: OpenApiResponse(description="Authentication required."),
            403: OpenApiResponse(description="The actor is not allowed to update this demand."),
            404: OpenApiResponse(description="Demand not found in the actor's accessible scope."),
            409: OpenApiResponse(description="Demand cannot be edited in its current state."),
        },
    )
    def patch(self, request, pk):
        demand = self.get_demand_object(request, pk)

        if demand.status != "DRAFT":
            raise DemandConflict(
                "Only DRAFT demands can be edited."
            )

        serializer = DemandPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        changes = dict(serializer.validated_data)

        if "supplier_id" in changes:
            changes["supplier_id"] = changes["supplier_id"].pk

        if "items" in changes:
            changes["items"] = normalize_item_rows(changes["items"])

        try:
            updated = update_draft_demand(
                demand_id=demand.pk,
                updated_by=request.user,
                changes=changes,
            )
        except DjangoValidationError as exc:
            raise_api_validation_error(exc)

        updated = demand_queryset_for_user(request.user).get(
            pk=updated.pk
        )
        response_serializer = DeliveryDemandReadSerializer(updated)

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )


class DemandStatusView(DemandObjectMixin, APIView):
    @extend_schema(
        operation_id="demands_status_retrieve",
        tags=["Demands"],
        responses={
            200: DemandStatusResponseSerializer,
            401: OpenApiResponse(description="Authentication required."),
            403: OpenApiResponse(description="The actor is not allowed to access this demand."),
            404: OpenApiResponse(description="Demand not found in the actor's accessible scope."),
        },
    )
    def get(self, request, pk):
        demand = self.get_demand_object(request, pk)

        return Response(
            {
                "id": demand.pk,
                "demand_code": demand.demand_code,
                "status": demand.status,
                "updated_at": demand.updated_at,
            },
            status=status.HTTP_200_OK,
        )


class DemandSubmitView(DemandObjectMixin, APIView):
    permission_classes = [
        IsAuthenticated,
        DemandSubmitPermission,
    ]

    @extend_schema(
        operation_id="demands_submit",
        tags=["Demands"],
        request=None,
        responses={
            200: DemandSubmitResponseSerializer,
            400: OpenApiResponse(description="Supplier offer or submission business validation failed."),
            401: OpenApiResponse(description="Authentication required."),
            403: OpenApiResponse(description="The actor is not allowed to submit this demand."),
            404: OpenApiResponse(description="Demand not found in the actor's accessible scope."),
            409: OpenApiResponse(description="Demand or supplier request is in a conflicting state."),
        },
    )
    def post(self, request, pk):
        demand = self.get_demand_object(request, pk)

        try:
            supplier_request = submit_demand(
                demand_id=demand.pk,
                submitted_by=request.user,
            )
        except DjangoValidationError as exc:
            # A state conflict is distinct from a failed business gate.
            if hasattr(exc, "message_dict") and (
                "status" in exc.message_dict
                or "supplier_request" in exc.message_dict
            ):
                raise DemandConflict(exc.message_dict)

            raise_api_validation_error(exc)

        return Response(
            {
                "submission_status": "SUBMITTED",
                "supplier_request_id": supplier_request.pk,
            },
            status=status.HTTP_200_OK,
        )


class DemandSelectSupplierView(DemandObjectMixin, APIView):
    permission_classes = [
        IsAuthenticated,
        DemandSubmitPermission,
    ]

    @extend_schema(
        operation_id="demands_select_supplier",
        tags=["Demands"],
        request=DemandSupplierSelectionSerializer,
        responses={
            200: DemandSupplierSelectionResponseSerializer,
            400: OpenApiResponse(description="Supplier selection validation failed."),
            401: OpenApiResponse(description="Authentication required."),
            403: OpenApiResponse(description="The actor is not allowed to select a supplier."),
            404: OpenApiResponse(description="Demand not found in the actor's accessible scope."),
            409: OpenApiResponse(description="Supplier selection conflicts with the current demand or commitment state."),
        },
    )
    def post(self, request, pk):
        demand = self.get_demand_object(request, pk)

        serializer = DemandSupplierSelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        selected_supplier = serializer.validated_data["selected_supplier_id"]

        try:
            selection = select_supplier_for_submitted_demand(
                demand_id=demand.pk,
                selected_by=request.user,
                selected_supplier_id=selected_supplier.pk,
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict") and any(
                key in exc.message_dict
                for key in (
                    "status",
                    "supplier_request",
                    "commitment",
                    "supplier_selection",
                )
            ):
                raise DemandConflict(exc.message_dict)

            raise_api_validation_error(exc)

        return Response(
            {
                "selection_id": selection.pk,
                "demand_id": selection.demand_id,
                "selected_supplier_id": selection.selected_supplier_id,
                "selection_reason": selection.selection_reason,
                "demand_status": "SUBMITTED",
            },
            status=status.HTTP_200_OK,
        )
