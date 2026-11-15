from django.db import migrations
from django.utils import timezone


PROVIDER_CODE = "TP001"
TARGET_SOURCE = "PROVIDER_CONFIRMED_IMPORT"

SOURCE_COUNTS = {
    "SYNTHETIC_NOVEMBER_DEMO": 126,
    "SYNTHETIC_HISTORICAL_FIXTURE": 14,
}

EXPECTED_TOTAL = 140
FORWARD_ACTION = "PROVIDER_AVAILABILITY_MIGRATED"
REVERSE_ACTION = "PROVIDER_AVAILABILITY_MIGRATION_REVERSED"
ENTITY_TYPE = "PROVIDER_AVAILABILITY_BATCH"
BATCH_ID = "TP001_CP7_140_AVAILABILITY_20261116"


def fail(message):
    raise RuntimeError(
        f"CP7 availability migration aborted: {message}"
    )

def forward(apps, schema_editor):
    db = schema_editor.connection.alias

    Provider = apps.get_model("masterdata", "TransportProvider")
    Offer = apps.get_model("transportation", "ProviderVehicleOffer")
    Availability = apps.get_model(
        "transportation",
        "ProviderAvailability",
    )
    AuditLog = apps.get_model("accounts", "AuditLog")
    if AuditLog.objects.using(db).filter(
        action=FORWARD_ACTION,
        entity_type=ENTITY_TYPE,
        entity_id=BATCH_ID,
    ).exists():
        fail("Forward audit batch already exists.")

    provider = (
        Provider.objects.using(db)
        .filter(provider_code=PROVIDER_CODE)
        .first()
    )

    if provider is None:
        return

    offers = list(
        Offer.objects.using(db)
        .filter(provider_id=provider.pk)
        .order_by("pk")
    )
    offers_by_id = {offer.pk: offer for offer in offers}
    offer_ids = list(offers_by_id.keys())

    if not offer_ids:
        fail("TP001 has no vehicle offers.")

    if any(not offer.is_active for offer in offers):
        fail("TP001 has an inactive vehicle offer.")

    rows = list(
        Availability.objects.using(db)
        .filter(
            provider_vehicle_offer_id__in=offer_ids,
            source_mode__in=list(SOURCE_COUNTS),
        )
        .order_by("pk")
    )

    actual_counts = {}
    for row in rows:
        actual_counts[row.source_mode] = (
            actual_counts.get(row.source_mode, 0) + 1
        )

    if len(rows) != EXPECTED_TOTAL:
        fail(
            f"Expected {EXPECTED_TOTAL} synthetic rows; "
            f"found {len(rows)}."
        )

    if actual_counts != SOURCE_COUNTS:
        fail(
            f"Unexpected source distribution: {actual_counts!r}; "
            f"expected {SOURCE_COUNTS!r}."
        )

    synthetic_total = (
        Availability.objects.using(db)
        .filter(
            provider_vehicle_offer_id__in=offer_ids,
            source_mode__in=[
                "SYNTHETIC_NOVEMBER_DEMO",
                "SYNTHETIC_HISTORICAL_FIXTURE",
            ],
        )
        .count()
    )

    if synthetic_total != EXPECTED_TOTAL:
        fail("Unexpected additional synthetic availability rows.")

    # Validate each row against its offer.
    for row in rows:
        offer = offers_by_id.get(row.provider_vehicle_offer_id)

        if offer is None:
            fail(f"Availability {row.pk} references an unknown offer.")

        if not offer.is_active:
            fail(f"Availability {row.pk} references an inactive offer.")

        if (
            offer.operating_start_time is None
            or offer.operating_end_time is None
        ):
            fail(f"Offer {offer.pk} has no complete operating hours.")

        if (
            row.start_time < offer.operating_start_time
            or row.end_time > offer.operating_end_time
        ):
            fail(f"Availability {row.pk} is outside offer operating hours.")

        if row.start_time >= row.end_time:
            fail(f"Availability {row.pk} has an invalid time window.")

        if row.availability_status == "AVAILABLE":
            if (
                row.available_vehicle_count <= 0
                or row.available_vehicle_count
                > offer.available_vehicle_count
            ):
                fail(f"Availability {row.pk} has invalid capacity.")
        elif row.availability_status == "UNAVAILABLE":
            if row.available_vehicle_count != 0:
                fail(f"Availability {row.pk} has invalid unavailable count.")
        else:
            fail(f"Availability {row.pk} has an unknown status.")

    # Check overlaps across all operational sources, including Portal.
    operational_rows = list(
        Availability.objects.using(db)
        .filter(
            provider_vehicle_offer_id__in=offer_ids,
            source_mode__in=[
                "PROVIDER_PORTAL",
                TARGET_SOURCE,
                "SYNTHETIC_NOVEMBER_DEMO",
                "SYNTHETIC_HISTORICAL_FIXTURE",
            ],
        )
        .order_by("provider_vehicle_offer_id", "service_date", "start_time")
    )

    grouped = {}
    for row in operational_rows:
        key = (row.provider_vehicle_offer_id, row.service_date)
        grouped.setdefault(key, []).append(row)

    for key, day_rows in grouped.items():
        day_rows.sort(key=lambda item: (item.start_time, item.end_time))

        for previous, current in zip(day_rows, day_rows[1:]):
            if current.start_time < previous.end_time:
                fail(
                    "Overlapping operational availability: "
                    f"offer={key[0]}, date={key[1]}, "
                    f"rows={previous.pk},{current.pk}."
                )

    # Keep exact original provenance for rollback.
    original_sources = [
        {
            "id": row.pk,
            "source_mode": row.source_mode,
        }
        for row in rows
    ]

    ids = [row.pk for row in rows]

    updated = (
        Availability.objects.using(db)
        .filter(
            pk__in=ids,
            source_mode__in=list(SOURCE_COUNTS),
        )
        .update(source_mode=TARGET_SOURCE)
    )

    if updated != EXPECTED_TOTAL:
        fail(
            f"Expected to update {EXPECTED_TOTAL} rows; "
            f"updated {updated}."
        )

    AuditLog.objects.using(db).create(
        actor_user_id=None,
        action=FORWARD_ACTION,
        entity_type=ENTITY_TYPE,
        entity_id=BATCH_ID,
        old_values={
            "provider_code": PROVIDER_CODE,
            "source_counts": SOURCE_COUNTS,
            "original_sources": original_sources,
        },
        new_values={
            "provider_code": PROVIDER_CODE,
            "target_source": TARGET_SOURCE,
            "row_count": EXPECTED_TOTAL,
            "availability_ids": ids,
            "workbook": "CoLogi_Dataset_v7.xlsx",
            "sheets": [
                "48_Provider_Availability",
            ],
            "conversion_time": timezone.now().isoformat(),
            "note": (
                "Converted according to user-confirmed TP001 "
                "operational commitments. Original source modes "
                "are retained in old_values for rollback."
            ),
        },
    )


def reverse(apps, schema_editor):
    db = schema_editor.connection.alias

    Availability = apps.get_model(
        "transportation",
        "ProviderAvailability",
    )
    AuditLog = apps.get_model("accounts", "AuditLog")

    audit = (
        AuditLog.objects.using(db)
        .filter(
            action=FORWARD_ACTION,
            entity_type=ENTITY_TYPE,
            entity_id=BATCH_ID,
        )
        .order_by("-pk")
        .first()
    )

    if audit is None or not audit.old_values:
        fail("Cannot reverse: original audit record is missing.")

    original_sources = audit.old_values.get("original_sources")

    if not isinstance(original_sources, list):
        fail("Cannot reverse: original source mapping is invalid.")

    if len(original_sources) != EXPECTED_TOTAL:
        fail("Cannot reverse: expected exactly 140 original records.")

    original_ids = [entry.get("id") for entry in original_sources]

    if (
        any(row_id is None for row_id in original_ids)
        or len(set(original_ids)) != EXPECTED_TOTAL
    ):
        fail("Cannot reverse: original IDs are missing or duplicated.")

    reverse_counts = {}
    for entry in original_sources:
        source = entry.get("source_mode")

        if source not in SOURCE_COUNTS:
            fail(
                f"Invalid original source for row {entry.get('id')}."
            )

        reverse_counts[source] = reverse_counts.get(source, 0) + 1

    if reverse_counts != SOURCE_COUNTS:
        fail(
            f"Cannot reverse: unexpected original source distribution "
            f"{reverse_counts!r}."
        )

    restored = []

    for entry in original_sources:
        row_id = entry.get("id")
        original_source = entry.get("source_mode")

        if original_source not in SOURCE_COUNTS:
            fail(f"Invalid original source for row {row_id}.")

        row = (
            Availability.objects.using(db)
            .filter(pk=row_id)
            .first()
        )

        if row is None:
            fail(f"Cannot reverse: availability {row_id} is missing.")

        if row.source_mode != TARGET_SOURCE:
            fail(
                f"Cannot reverse: availability {row_id} "
                "has been changed since conversion."
            )

        restored.append(
            {
                "id": row_id,
                "source_mode": original_source,
            }
        )

    for entry in restored:
        Availability.objects.using(db).filter(
            pk=entry["id"],
            source_mode=TARGET_SOURCE,
        ).update(source_mode=entry["source_mode"])

    AuditLog.objects.using(db).create(
        actor_user_id=None,
        action=REVERSE_ACTION,
        entity_type=ENTITY_TYPE,
        entity_id=BATCH_ID,
        old_values={
            "target_source": TARGET_SOURCE,
            "row_count": len(restored),
        },
        new_values={
            "restored_sources": restored,
            "rollback_time": timezone.now().isoformat(),
            "note": "Original source modes restored.",
        },
    )


class Migration(migrations.Migration):
    atomic = True
    dependencies = [
        ("accounts", "0006_alter_auditlog_entity_id"),
        ("transportation", "0002_alter_provideravailability_source_mode"),
    ]

    operations = [
        migrations.RunPython(
            forward,
            reverse,
        ),
    ]
