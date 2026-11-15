from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models import AuditLog
from masterdata.models import (
    CargoCategory,
    Supplier,
    TransportProvider,
    VehicleCargoCompatibility,
    VehicleType,
)
from .models import (
    ProviderAvailability,
    ProviderSupplierCoverage,
    ProviderVehicleOffer,
)


BUSINESS_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _audit(actor, action, entity_type, entity_id, old_values, new_values, ip_address):
    AuditLog.objects.create(
        actor_user=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
    )


def _model_values(instance, fields):
    result = {}
    for field in fields:
        value = getattr(instance, field)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = str(value)
        result[field] = value
    return result


def _validate_model(instance):
    try:
        instance.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        ) from exc


def _get_provider(provider_id, *, lock=False):
    queryset = TransportProvider.objects
    if lock:
        queryset = queryset.select_for_update()
    try:
        provider = queryset.get(pk=provider_id)
    except TransportProvider.DoesNotExist as exc:
        raise NotFound("Transport Provider not found.") from exc
    if not provider.is_active:
        raise ValidationError({"provider": "Transport Provider is inactive."})
    return provider


def _get_active_supplier(supplier_id):
    try:
        supplier = Supplier.objects.get(pk=supplier_id)
    except Supplier.DoesNotExist as exc:
        raise NotFound("Supplier not found.") from exc
    if not supplier.is_active:
        raise ValidationError({"supplier": "Supplier is inactive."})
    return supplier


def _get_active_vehicle_type(vehicle_type_id):
    try:
        vehicle_type = VehicleType.objects.get(pk=vehicle_type_id)
    except VehicleType.DoesNotExist as exc:
        raise NotFound("Vehicle type not found.") from exc
    if not vehicle_type.is_active:
        raise ValidationError({"vehicle_type": "Vehicle type is inactive."})
    return vehicle_type


def _coverage_snapshot(coverage):
    return {
        "provider_id": coverage.provider_id,
        "supplier_id": coverage.supplier_id,
        "coverage_status": coverage.coverage_status,
        "can_pickup": coverage.can_pickup,
        "service_note": coverage.service_note,
    }


def _offer_snapshot(offer):
    return _model_values(
        offer,
        (
            "provider_id",
            "vehicle_type_id",
            "available_vehicle_count",
            "fuel_type",
            "operating_start_time",
            "operating_end_time",
            "fixed_quote_vnd",
            "estimated_cost_per_km_vnd",
            "is_active",
            "vehicle_note",
        ),
    )


def _availability_snapshot(slot):
    return _model_values(
        slot,
        (
            "provider_vehicle_offer_id",
            "service_date",
            "available_vehicle_count",
            "start_time",
            "end_time",
            "availability_status",
            "source_mode",
        ),
    )


@transaction.atomic
def set_supplier_coverage(
    *,
    provider_id,
    supplier_id,
    actor,
    coverage_status,
    can_pickup=True,
    service_note="",
    ip_address=None,
):
    provider = _get_provider(provider_id, lock=True)

    if coverage_status not in ProviderSupplierCoverage.CoverageStatus.values:
        raise ValidationError({"coverage_status": "Invalid coverage status."})

    if coverage_status == ProviderSupplierCoverage.CoverageStatus.ACTIVE:
        supplier = _get_active_supplier(supplier_id)
    else:
        try:
            supplier = Supplier.objects.get(pk=supplier_id)
        except Supplier.DoesNotExist as exc:
            raise NotFound("Supplier not found.") from exc

    coverage = (
        ProviderSupplierCoverage.objects.select_for_update()
        .filter(provider=provider, supplier=supplier)
        .first()
    )

    if coverage is None:
        if coverage_status == ProviderSupplierCoverage.CoverageStatus.INACTIVE:
            raise ValidationError({
                "coverage_status": "Coverage does not exist; there is no record to deactivate."
            })
        coverage = ProviderSupplierCoverage(
            provider=provider,
            supplier=supplier,
            coverage_status=coverage_status,
            can_pickup=can_pickup,
            service_note=service_note,
        )
        _validate_model(coverage)
        coverage.save()
        _audit(
            actor,
            "PROVIDER_COVERAGE_CREATED",
            "PROVIDER_SUPPLIER_COVERAGE",
            coverage.pk,
            None,
            _coverage_snapshot(coverage),
            ip_address,
        )
        return coverage

    old_values = _coverage_snapshot(coverage)
    coverage.coverage_status = coverage_status
    coverage.can_pickup = can_pickup
    coverage.service_note = service_note
    _validate_model(coverage)
    coverage.save(
        update_fields=[
            "coverage_status",
            "can_pickup",
            "service_note",
            "updated_at",
        ]
    )
    _audit(
        actor,
        "PROVIDER_COVERAGE_UPDATED",
        "PROVIDER_SUPPLIER_COVERAGE",
        coverage.pk,
        old_values,
        _coverage_snapshot(coverage),
        ip_address,
    )
    return coverage


@transaction.atomic
def create_vehicle_offer(
    *,
    provider_id,
    vehicle_type_id,
    actor,
    available_vehicle_count,
    fuel_type,
    operating_start_time=None,
    operating_end_time=None,
    fixed_quote_vnd=None,
    estimated_cost_per_km_vnd=None,
    is_active=True,
    vehicle_note="",
    ip_address=None,
):
    provider = _get_provider(provider_id, lock=True)
    vehicle_type = _get_active_vehicle_type(vehicle_type_id)

    offer = ProviderVehicleOffer(
        provider=provider,
        vehicle_type=vehicle_type,
        available_vehicle_count=available_vehicle_count,
        fuel_type=fuel_type,
        operating_start_time=operating_start_time,
        operating_end_time=operating_end_time,
        fixed_quote_vnd=fixed_quote_vnd,
        estimated_cost_per_km_vnd=estimated_cost_per_km_vnd,
        is_active=is_active,
        vehicle_note=vehicle_note,
    )
    _validate_model(offer)
    offer.save()
    _audit(
        actor,
        "PROVIDER_VEHICLE_OFFER_CREATED",
        "PROVIDER_VEHICLE_OFFER",
        offer.pk,
        None,
        _offer_snapshot(offer),
        ip_address,
    )
    return offer


def _effective_operational_slots(offer):
    local_now = timezone.now().astimezone(BUSINESS_TZ)
    local_date = local_now.date()
    local_time = local_now.time().replace(tzinfo=None)

    return ProviderAvailability.objects.filter(
        provider_vehicle_offer=offer,
        source_mode=ProviderAvailability.SourceMode.PROVIDER_PORTAL,
    ).filter(
        Q(service_date__gt=local_date)
        | Q(service_date=local_date, end_time__gt=local_time)
    )


def _validate_offer_slot_impact(offer, *, new_capacity, new_start, new_end):
    slots = _effective_operational_slots(offer)

    if slots.filter(available_vehicle_count__gt=new_capacity).exists():
        raise ValidationError({
            "available_vehicle_count": (
                "Capacity cannot be reduced below an effective operational "
                "Availability count. Adjust those slots first."
            )
        })

    if new_start is None or new_end is None:
        if slots.exists():
            raise ValidationError({
                "operating_start_time": (
                    "Operating hours cannot be cleared while effective "
                    "operational Availability slots exist."
                )
            })
        return

    outside_hours = slots.filter(
        Q(start_time__lt=new_start) | Q(end_time__gt=new_end)
    )
    if outside_hours.exists():
        raise ValidationError({
            "operating_start_time": (
                "New operating hours would invalidate an effective "
                "operational Availability slot. Adjust those slots first."
            )
        })


@transaction.atomic
def update_vehicle_offer(
    *,
    offer_id,
    provider_id,
    actor,
    changes,
    ip_address=None,
):
    _get_provider(provider_id, lock=True)

    try:
        offer = (
            ProviderVehicleOffer.objects.select_for_update()
            .get(pk=offer_id, provider_id=provider_id)
        )
    except ProviderVehicleOffer.DoesNotExist as exc:
        raise NotFound("Vehicle offer not found.") from exc

    allowed_fields = {
        "available_vehicle_count",
        "fuel_type",
        "operating_start_time",
        "operating_end_time",
        "fixed_quote_vnd",
        "estimated_cost_per_km_vnd",
        "is_active",
        "vehicle_note",
    }
    unknown_fields = set(changes) - allowed_fields
    if unknown_fields:
        raise ValidationError({
            "detail": f"Unsupported offer fields: {', '.join(sorted(unknown_fields))}"
        })

    if "vehicle_type_id" in changes or "provider_id" in changes:
        raise ValidationError({"detail": "Offer ownership and vehicle type cannot be changed."})

    if changes.get("is_active", offer.is_active) and not offer.vehicle_type.is_active:
        raise ValidationError({"vehicle_type": "Inactive vehicle types cannot have active offers."})

    old_values = _offer_snapshot(offer)

    new_capacity = changes.get(
        "available_vehicle_count",
        offer.available_vehicle_count,
    )
    new_start = changes.get(
        "operating_start_time",
        offer.operating_start_time,
    )
    new_end = changes.get(
        "operating_end_time",
        offer.operating_end_time,
    )

    if offer.is_active and changes.get("is_active", True):
        if new_capacity <= 0:
            raise ValidationError({
                "available_vehicle_count": "An active offer must have positive capacity."
            })

    _validate_offer_slot_impact(
        offer,
        new_capacity=new_capacity,
        new_start=new_start,
        new_end=new_end,
    )

    for field, value in changes.items():
        setattr(offer, field, value)

    _validate_model(offer)
    offer.save(update_fields=[*changes.keys(), "updated_at"])
    _audit(
        actor,
        "PROVIDER_VEHICLE_OFFER_UPDATED",
        "PROVIDER_VEHICLE_OFFER",
        offer.pk,
        old_values,
        _offer_snapshot(offer),
        ip_address,
    )
    return offer


def _validate_portal_availability(
    *,
    offer,
    service_date,
    start_time,
    end_time,
    available_vehicle_count,
    availability_status,
    exclude_id=None,
):
    if not offer.is_active:
        raise ValidationError({"provider_vehicle_offer_id": "Vehicle offer is inactive."})

    if not offer.vehicle_type.is_active:
        raise ValidationError({"provider_vehicle_offer_id": "Vehicle type is inactive."})

    if offer.operating_start_time is None or offer.operating_end_time is None:
        raise ValidationError({
            "provider_vehicle_offer_id": (
                "Operating hours must be configured before Availability can be added."
            )
        })

    if start_time >= end_time:
        raise ValidationError({"end_time": "End time must be later than start time."})

    if (
        start_time < offer.operating_start_time
        or end_time > offer.operating_end_time
    ):
        raise ValidationError({
            "start_time": "Availability must fit entirely within Provider operating hours."
        })

    if available_vehicle_count < 0:
        raise ValidationError({
            "available_vehicle_count": "Vehicle count cannot be negative."
        })

    if available_vehicle_count > offer.available_vehicle_count:
        raise ValidationError({
            "available_vehicle_count": "Availability count cannot exceed offer capacity."
        })

    if availability_status == ProviderAvailability.AvailabilityStatus.AVAILABLE:
        if available_vehicle_count <= 0:
            raise ValidationError({
                "available_vehicle_count": "AVAILABLE requires a positive vehicle count."
            })
    elif availability_status == ProviderAvailability.AvailabilityStatus.UNAVAILABLE:
        if available_vehicle_count != 0:
            raise ValidationError({
                "available_vehicle_count": "UNAVAILABLE requires a vehicle count of zero."
            })
    else:
        raise ValidationError({"availability_status": "Invalid availability status."})

    local_now = timezone.now().astimezone(BUSINESS_TZ)
    if service_date < local_now.date():
        raise ValidationError({"service_date": "Past dates are not allowed."})
    if service_date == local_now.date() and start_time <= local_now.time().replace(tzinfo=None):
        raise ValidationError({
            "start_time": "Today's Availability slot must be entirely in the future."
        })

    overlaps = ProviderAvailability.objects.filter(
        provider_vehicle_offer=offer,
        service_date=service_date,
        source_mode=ProviderAvailability.SourceMode.PROVIDER_PORTAL,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_id is not None:
        overlaps = overlaps.exclude(pk=exclude_id)
    if overlaps.exists():
        raise ValidationError({
            "start_time": "This Availability window overlaps another Provider Portal window."
        })


@transaction.atomic
def create_availability(
    *,
    provider_id,
    offer_id,
    actor,
    service_date,
    start_time,
    end_time,
    available_vehicle_count,
    availability_status,
    ip_address=None,
):
    _get_provider(provider_id, lock=True)

    try:
        offer = (
            ProviderVehicleOffer.objects.select_for_update()
            .select_related("vehicle_type")
            .get(pk=offer_id, provider_id=provider_id)
        )
    except ProviderVehicleOffer.DoesNotExist as exc:
        raise NotFound("Vehicle offer not found.") from exc

    _validate_portal_availability(
        offer=offer,
        service_date=service_date,
        start_time=start_time,
        end_time=end_time,
        available_vehicle_count=available_vehicle_count,
        availability_status=availability_status,
    )

    slot = ProviderAvailability(
        provider_vehicle_offer=offer,
        service_date=service_date,
        start_time=start_time,
        end_time=end_time,
        available_vehicle_count=available_vehicle_count,
        availability_status=availability_status,
        source_mode=ProviderAvailability.SourceMode.PROVIDER_PORTAL,
    )
    _validate_model(slot)
    slot.save()
    _audit(
        actor,
        "PROVIDER_AVAILABILITY_CREATED",
        "PROVIDER_AVAILABILITY",
        slot.pk,
        None,
        _availability_snapshot(slot),
        ip_address,
    )
    return slot


@transaction.atomic
def update_availability(
    *,
    provider_id,
    availability_id,
    actor,
    changes,
    ip_address=None,
):
    _get_provider(provider_id, lock=True)

    try:
        scope = ProviderAvailability.objects.values(
            "provider_vehicle_offer_id",
            "source_mode",
        ).get(pk=availability_id)
    except ProviderAvailability.DoesNotExist as exc:
        raise NotFound("Availability not found.") from exc

    if scope["source_mode"] != ProviderAvailability.SourceMode.PROVIDER_PORTAL:
        raise NotFound("Availability not found.")

    try:
        offer = (
            ProviderVehicleOffer.objects.select_for_update()
            .select_related("vehicle_type")
            .get(
                pk=scope["provider_vehicle_offer_id"],
                provider_id=provider_id,
            )
        )
    except ProviderVehicleOffer.DoesNotExist as exc:
        raise NotFound("Availability not found.") from exc

    try:
        slot = ProviderAvailability.objects.select_for_update().get(
            pk=availability_id,
            provider_vehicle_offer=offer,
            source_mode=ProviderAvailability.SourceMode.PROVIDER_PORTAL,
        )
    except ProviderAvailability.DoesNotExist as exc:
        raise NotFound("Availability not found.") from exc

    allowed_fields = {
        "service_date",
        "start_time",
        "end_time",
        "available_vehicle_count",
        "availability_status",
    }
    unknown_fields = set(changes) - allowed_fields
    if unknown_fields:
        raise ValidationError({
            "detail": f"Unsupported Availability fields: {', '.join(sorted(unknown_fields))}"
        })

    old_values = _availability_snapshot(slot)
    values = {
        "service_date": changes.get("service_date", slot.service_date),
        "start_time": changes.get("start_time", slot.start_time),
        "end_time": changes.get("end_time", slot.end_time),
        "available_vehicle_count": changes.get(
            "available_vehicle_count",
            slot.available_vehicle_count,
        ),
        "availability_status": changes.get(
            "availability_status",
            slot.availability_status,
        ),
    }

    _validate_portal_availability(
        offer=offer,
        exclude_id=slot.pk,
        **values,
    )

    for field, value in values.items():
        setattr(slot, field, value)

    _validate_model(slot)
    slot.save(update_fields=[*values.keys(), "updated_at"])
    _audit(
        actor,
        "PROVIDER_AVAILABILITY_UPDATED",
        "PROVIDER_AVAILABILITY",
        slot.pk,
        old_values,
        _availability_snapshot(slot),
        ip_address,
    )
    return slot


@transaction.atomic
def update_provider_profile(
    *,
    provider_id,
    actor,
    service_region,
    ip_address=None,
):
    provider = _get_provider(provider_id, lock=True)
    old_values = {"service_region": provider.service_region}
    provider.service_region = service_region
    _validate_model(provider)
    provider.save(update_fields=["service_region"])
    _audit(
        actor,
        "PROVIDER_PROFILE_UPDATED",
        "TRANSPORT_PROVIDER",
        provider.pk,
        old_values,
        {"service_region": provider.service_region},
        ip_address,
    )
    return provider


def is_vehicle_type_compatible(*, vehicle_type_id, cargo_category_id):
    if not VehicleType.objects.filter(
        pk=vehicle_type_id,
        is_active=True,
    ).exists():
        return False

    if not CargoCategory.objects.filter(
        pk=cargo_category_id,
        is_active=True,
    ).exists():
        return False

    return VehicleCargoCompatibility.objects.filter(
        vehicle_type_id=vehicle_type_id,
        cargo_category_id=cargo_category_id,
        is_supported=True,
    ).exists()
