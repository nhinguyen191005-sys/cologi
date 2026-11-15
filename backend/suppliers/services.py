from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from accounts.models import AuditLog
from demands.models import (
    DeliveryDemand,
    DemandStatus,
    SupplierConfirmation,
    SupplierItemPromise,
    SupplierRequest,
)


class SupplierRequestConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The supplier request or its Demand is no longer eligible for a response."
    default_code = "supplier_request_conflict"


@transaction.atomic
def respond_to_supplier_request(
    *,
    request_id,
    supplier_id,
    actor,
    response_data,
    ip_address=None,
):
    """
    Record one complete, item-level response for a SupplierRequest.

    Lock order matches Demand cancellation:
    DeliveryDemand -> SupplierRequest -> SupplierConfirmation -> promises.
    """
    try:
        request_scope = SupplierRequest.objects.values(
            "demand_id", "supplier_id"
        ).get(pk=request_id)
    except SupplierRequest.DoesNotExist:
        raise ValidationError({"detail": "Supplier request not found."})

    if request_scope["supplier_id"] != supplier_id:
        raise ValidationError({"detail": "Supplier request not found."})

    try:
        demand = DeliveryDemand.objects.select_for_update().get(
            pk=request_scope["demand_id"]
        )
    except DeliveryDemand.DoesNotExist:
        raise ValidationError({"detail": "Supplier request not found."})

    if demand.status != DemandStatus.SUBMITTED:
        raise SupplierRequestConflict(
            "The Demand must be SUBMITTED to receive a Supplier response."
        )

    try:
        supplier_request = (
            SupplierRequest.objects
            .select_for_update()
            .get(pk=request_id)
        )
    except SupplierRequest.DoesNotExist:
        raise ValidationError({"detail": "Supplier request not found."})

    # Recheck the supplier boundary after acquiring the row lock.
    if (
        supplier_request.supplier_id != supplier_id
        or supplier_request.demand_id != demand.pk
    ):
        raise ValidationError({"detail": "Supplier request not found."})

    if supplier_request.request_status != SupplierRequest.RequestStatus.WAITING:
        raise SupplierRequestConflict(
            "This supplier request has already been closed or answered."
        )

    confirmation = (
        SupplierConfirmation.objects
        .select_for_update()
        .get(pk=supplier_request.supplier_confirmation_id)
    )

    if confirmation.confirmation_status != SupplierConfirmation.ConfirmationStatus.PENDING:
        raise SupplierRequestConflict(
            "Supplier confirmation is not awaiting a response."
        )

    promises = list(
        SupplierItemPromise.objects
        .select_for_update()
        .filter(supplier_request_id=supplier_request.pk)
        .order_by("id")
    )

    submitted_items = response_data["items"]
    submitted_by_id = {
        row["promise_id"]: row
        for row in submitted_items
    }
    if not promises:
        raise ValidationError({"items": "This request has no item promises."})
    if len(submitted_by_id) != len(submitted_items):
        raise ValidationError({"items": "Duplicate promise_id values are not allowed."})
    expected_ids = {promise.pk for promise in promises}
    submitted_ids = set(submitted_by_id)

    if submitted_ids != expected_ids:
        raise ValidationError({
            "items": (
                "The response must include every item in this request "
                "exactly once, using its valid promise_id."
            )
        })

    line_statuses = []
    audit_items = []

    for promise in promises:
        row = submitted_by_id[promise.pk]
        confirmed_weight = row["confirmed_weight_kg"]
        decline_reason = row.get("decline_reason", "").strip()

        if confirmed_weight > promise.promised_weight_kg:
            raise ValidationError({
                "items": (
                    f"Confirmed quantity for promise {promise.pk} "
                    "cannot exceed the promised quantity."
                )
            })

        if confirmed_weight == 0:
            if not decline_reason:
                raise ValidationError({
                    "items": (
                        f"A decline reason is required for promise {promise.pk}."
                    )
                })
            line_status = SupplierItemPromise.LineStatus.DECLINED
        else:
            if decline_reason:
                raise ValidationError({
                    "items": (
                        f"Decline reason is not allowed for promise {promise.pk} "
                        "when a positive quantity is confirmed."
                    )
                })

            if confirmed_weight == promise.promised_weight_kg:
                line_status = SupplierItemPromise.LineStatus.CONFIRMED
            else:
                line_status = SupplierItemPromise.LineStatus.PARTIAL

        promise.confirmed_weight_kg = confirmed_weight
        promise.line_status = line_status
        promise.decline_reason = decline_reason

        try:
            promise.full_clean()
        except DjangoValidationError as exc:
            raise ValidationError({
                "items": exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            })

        promise.save(update_fields=[
            "confirmed_weight_kg",
            "line_status",
            "decline_reason",
            "updated_at",
        ])

        line_statuses.append(line_status)
        audit_items.append({
            "promise_id": promise.pk,
            "confirmed_weight_kg": str(confirmed_weight),
            "line_status": line_status,
            "decline_reason": decline_reason,
        })

    if all(
        status == SupplierItemPromise.LineStatus.CONFIRMED
        for status in line_statuses
    ):
        aggregate_status = SupplierConfirmation.ConfirmationStatus.CONFIRMED
    elif all(
        status == SupplierItemPromise.LineStatus.DECLINED
        for status in line_statuses
    ):
        aggregate_status = SupplierConfirmation.ConfirmationStatus.DECLINED
    else:
        aggregate_status = SupplierConfirmation.ConfirmationStatus.PARTIAL

    ready_date = response_data.get("ready_date")
    if aggregate_status in {
        SupplierConfirmation.ConfirmationStatus.CONFIRMED,
        SupplierConfirmation.ConfirmationStatus.PARTIAL,
    }:
        if ready_date is None:
            raise ValidationError({
                "ready_date": "A ready date is required for confirmed or partial responses."
            })

        ready_start_time = response_data.get("ready_start_time")
        ready_end_time = response_data.get("ready_end_time")
        if ready_start_time is None or ready_end_time is None:
            raise ValidationError({
                "ready_start_time": (
                    "Both ready start and end times are required "
                    "for confirmed or partial responses."
                )
            })

        pickup_address = (response_data.get("pickup_address") or "").strip()
        if not pickup_address:
            raise ValidationError({
                "pickup_address": (
                    "A pickup address is required for confirmed or partial responses."
                )
            })

    now = timezone.now()

    confirmation.confirmation_status = aggregate_status
    confirmation.ready_date = ready_date
    confirmation.ready_start_time = response_data.get("ready_start_time")
    confirmation.ready_end_time = response_data.get("ready_end_time")
    confirmation.pickup_address = response_data.get("pickup_address")
    confirmation.confirmation_note = response_data.get("confirmation_note", "")
    confirmation.recorded_at = now

    try:
        confirmation.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError({
            "confirmation": (
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            )
        })

    confirmation.save(update_fields=[
        "confirmation_status",
        "ready_date",
        "ready_start_time",
        "ready_end_time",
        "pickup_address",
        "confirmation_note",
        "recorded_at",
        "updated_at",
    ])

    old_request_status = supplier_request.request_status
    old_confirmation_status = SupplierConfirmation.ConfirmationStatus.PENDING

    supplier_request.supplier_confirmation = confirmation
    supplier_request.request_status = SupplierRequest.RequestStatus.RESPONDED
    supplier_request.responded_at = now

    try:
        supplier_request.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError({
            "request": (
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            )
        })

    supplier_request.save(update_fields=[
        "request_status",
        "responded_at",
        "updated_at",
    ])

    AuditLog.objects.create(
        actor_user=actor,
        action="SUPPLIER_REQUEST_RESPONDED",
        entity_type="SUPPLIER_REQUEST",
        entity_id=str(supplier_request.pk),
        old_values={
            "request_status": old_request_status,
            "confirmation_status": old_confirmation_status,
        },
        new_values={
            "request_status": supplier_request.request_status,
            "confirmation_status": aggregate_status,
            "items": audit_items,
        },
        ip_address=ip_address,
    )

    return supplier_request
