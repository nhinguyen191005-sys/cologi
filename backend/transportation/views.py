from django.db import IntegrityError
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from masterdata.models import TransportProvider, VehicleType

from .models import (
    ProviderAvailability,
    ProviderSupplierCoverage,
    ProviderVehicleOffer,
)
from .permissions import ProviderScopeMixin
from .serializers import (
    ProviderAvailabilityCreateSerializer,
    ProviderAvailabilityReadSerializer,
    ProviderAvailabilityUpdateSerializer,
    ProviderProfileReadSerializer,
    ProviderProfileUpdateSerializer,
    ProviderSupplierCoverageCreateSerializer,
    ProviderSupplierCoverageReadSerializer,
    ProviderSupplierCoverageUpdateSerializer,
    ProviderVehicleOfferCreateSerializer,
    ProviderVehicleOfferReadSerializer,
    ProviderVehicleOfferUpdateSerializer,
    ProviderVehicleTypeCatalogSerializer,
)
from .services import (
    create_availability,
    create_vehicle_offer,
    set_supplier_coverage,
    update_availability,
    update_provider_profile,
    update_vehicle_offer,
)


def _ip_address(request):
    return request.META.get("REMOTE_ADDR")


def _integrity_error(message):
    return ValidationError({"detail": message})


class ProviderProfileView(
    ProviderScopeMixin,
    generics.GenericAPIView,
):
    def get_object(self):
        try:
            return TransportProvider.objects.get(
                pk=self.get_provider_id(),
                is_active=True,
            )
        except TransportProvider.DoesNotExist as exc:
            raise NotFound("Transport Provider not found.") from exc

    def get(self, request, *args, **kwargs):
        provider = self.get_object()
        return Response(
            ProviderProfileReadSerializer(provider).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, *args, **kwargs):
        provider = self.get_object()
        serializer = ProviderProfileUpdateSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        try:
            provider = update_provider_profile(
                provider_id=provider.pk,
                actor=request.user,
                service_region=serializer.validated_data["service_region"],
                ip_address=_ip_address(request),
            )
        except IntegrityError as exc:
            raise _integrity_error(
                "Could not update Provider profile."
            ) from exc

        return Response(
            ProviderProfileReadSerializer(provider).data,
            status=status.HTTP_200_OK,
        )


class ProviderSupplierCoverageListCreateView(
    ProviderScopeMixin,
    generics.ListCreateAPIView,
):
    def get_queryset(self):
        return (
            ProviderSupplierCoverage.objects
            .filter(provider_id=self.get_provider_id())
            .select_related("supplier")
            .order_by("supplier_id")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProviderSupplierCoverageCreateSerializer
        return ProviderSupplierCoverageReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            coverage = set_supplier_coverage(
                provider_id=self.get_provider_id(),
                supplier_id=data["supplier_id"],
                actor=request.user,
                coverage_status=data["coverage_status"],
                can_pickup=data["can_pickup"],
                service_note=data["service_note"],
                ip_address=_ip_address(request),
            )
        except IntegrityError as exc:
            raise _integrity_error(
                "Coverage already exists or conflicts with another update."
            ) from exc

        return Response(
            ProviderSupplierCoverageReadSerializer(coverage).data,
            status=status.HTTP_201_CREATED,
        )


class ProviderSupplierCoverageDetailView(
    ProviderScopeMixin,
    generics.GenericAPIView,
):
    def get_object(self):
        try:
            return ProviderSupplierCoverage.objects.get(
                pk=self.kwargs["pk"],
                provider_id=self.get_provider_id(),
            )
        except ProviderSupplierCoverage.DoesNotExist as exc:
            raise NotFound("Supplier Coverage not found.") from exc

    def get(self, request, *args, **kwargs):
        coverage = self.get_object()
        return Response(
            ProviderSupplierCoverageReadSerializer(coverage).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, *args, **kwargs):
        coverage = self.get_object()
        serializer = ProviderSupplierCoverageUpdateSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        changes = serializer.validated_data

        try:
            coverage = set_supplier_coverage(
                provider_id=self.get_provider_id(),
                supplier_id=coverage.supplier_id,
                actor=request.user,
                coverage_status=changes.get(
                    "coverage_status",
                    coverage.coverage_status,
                ),
                can_pickup=changes.get(
                    "can_pickup",
                    coverage.can_pickup,
                ),
                service_note=changes.get(
                    "service_note",
                    coverage.service_note,
                ),
                ip_address=_ip_address(request),
            )
        except IntegrityError as exc:
            raise _integrity_error(
                "Could not update Supplier Coverage."
            ) from exc

        return Response(
            ProviderSupplierCoverageReadSerializer(coverage).data,
            status=status.HTTP_200_OK,
        )

class ProviderVehicleTypeListView(
    ProviderScopeMixin,
    generics.ListAPIView,
):
    serializer_class = ProviderVehicleTypeCatalogSerializer

    def get_queryset(self):
        return VehicleType.objects.filter(
            is_active=True,
        ).order_by("vehicle_code")

class ProviderVehicleOfferListCreateView(
    ProviderScopeMixin,
    generics.ListCreateAPIView,
):
    def get_queryset(self):
        return (
            ProviderVehicleOffer.objects
            .filter(provider_id=self.get_provider_id())
            .select_related("vehicle_type")
            .order_by("vehicle_type_id")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProviderVehicleOfferCreateSerializer
        return ProviderVehicleOfferReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            offer = create_vehicle_offer(
                provider_id=self.get_provider_id(),
                actor=request.user,
                ip_address=_ip_address(request),
                **data,
            )
        except IntegrityError as exc:
            raise _integrity_error(
                "Vehicle Offer already exists or conflicts with another update."
            ) from exc

        return Response(
            ProviderVehicleOfferReadSerializer(offer).data,
            status=status.HTTP_201_CREATED,
        )


class ProviderVehicleOfferDetailView(
    ProviderScopeMixin,
    generics.GenericAPIView,
):
    def get_object(self):
        try:
            return (
                ProviderVehicleOffer.objects
                .select_related("vehicle_type")
                .get(
                    pk=self.kwargs["pk"],
                    provider_id=self.get_provider_id(),
                )
            )
        except ProviderVehicleOffer.DoesNotExist as exc:
            raise NotFound("Vehicle Offer not found.") from exc

    def get(self, request, *args, **kwargs):
        offer = self.get_object()
        return Response(
            ProviderVehicleOfferReadSerializer(offer).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, *args, **kwargs):
        offer = self.get_object()
        serializer = ProviderVehicleOfferUpdateSerializer(
            offer,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        try:
            offer = update_vehicle_offer(
                offer_id=offer.pk,
                provider_id=self.get_provider_id(),
                actor=request.user,
                changes=serializer.validated_data,
                ip_address=_ip_address(request),
            )
        except IntegrityError as exc:
            raise _integrity_error(
                "Could not update Vehicle Offer."
            ) from exc

        return Response(
            ProviderVehicleOfferReadSerializer(offer).data,
            status=status.HTTP_200_OK,
        )


class ProviderAvailabilityListCreateView(
    ProviderScopeMixin,
    generics.ListCreateAPIView,
):
    def get_queryset(self):
        return (
            ProviderAvailability.objects
            .filter(
                provider_vehicle_offer__provider_id=self.get_provider_id(),
                source_mode__in=[
                    ProviderAvailability.SourceMode.PROVIDER_PORTAL,
                    ProviderAvailability.SourceMode.PROVIDER_CONFIRMED_IMPORT,
                ],
            )
            .select_related(
                "provider_vehicle_offer",
                "provider_vehicle_offer__vehicle_type",
            )
            .order_by("service_date", "start_time", "id")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProviderAvailabilityCreateSerializer
        return ProviderAvailabilityReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        offer_id = data.pop("provider_vehicle_offer_id")

        try:
            slot = create_availability(
                provider_id=self.get_provider_id(),
                offer_id=offer_id,
                actor=request.user,
                ip_address=_ip_address(request),
                **data,
            )
        except IntegrityError as exc:
            raise _integrity_error(
                "Availability conflicts with an existing record."
            ) from exc

        return Response(
            ProviderAvailabilityReadSerializer(slot).data,
            status=status.HTTP_201_CREATED,
        )


class ProviderAvailabilityDetailView(
    ProviderScopeMixin,
    generics.GenericAPIView,
):
    def get_queryset(self):
        return (
            ProviderAvailability.objects
            .filter(
                provider_vehicle_offer__provider_id=self.get_provider_id(),
                source_mode__in=[
                    ProviderAvailability.SourceMode.PROVIDER_PORTAL,
                    ProviderAvailability.SourceMode.PROVIDER_CONFIRMED_IMPORT,
                ],
            )
            .select_related(
                "provider_vehicle_offer",
                "provider_vehicle_offer__vehicle_type",
            )
        )

    def get_object(self):
        try:
            return self.get_queryset().get(pk=self.kwargs["pk"])
        except ProviderAvailability.DoesNotExist as exc:
            raise NotFound("Availability not found.") from exc

    def get(self, request, *args, **kwargs):
        slot = self.get_object()
        return Response(
            ProviderAvailabilityReadSerializer(slot).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, *args, **kwargs):
        slot = self.get_object()
        serializer = ProviderAvailabilityUpdateSerializer(
            slot,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        try:
            slot = update_availability(
                provider_id=self.get_provider_id(),
                availability_id=slot.pk,
                actor=request.user,
                changes=serializer.validated_data,
                ip_address=_ip_address(request),
            )
        except IntegrityError as exc:
            raise _integrity_error(
                "Could not update Availability."
            ) from exc

        return Response(
            ProviderAvailabilityReadSerializer(slot).data,
            status=status.HTTP_200_OK,
        )
