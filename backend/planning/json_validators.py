import json
from django.core.exceptions import ValidationError
MAX_DEMAND_SNAPSHOT_BYTES = 256 * 1024
MAX_FAILURE_DIAGNOSTICS_BYTES = 16 * 1024

def validate_json_object(value):
    if not isinstance(value, dict):
        raise ValidationError("Value must be a JSON object.")


def validate_diagnostics_array(value):
    if not isinstance(value, list):
        raise ValidationError("Diagnostics must be a JSON array.")

def validate_demand_snapshot(value):
    if not isinstance(value, dict):
        raise ValidationError("Demand snapshot must be a JSON object.")

    if value.get("schema_version") != "1.0":
        raise ValidationError("Unsupported demand snapshot schema version.")

    required_keys = {
        "schema_version",
        "captured_at",
        "demand_ref",
        "demand_values",
        "related_records",
    }
    if not required_keys.issubset(value):
        raise ValidationError("Demand snapshot is missing required fields.")

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise ValidationError("Demand snapshot must contain valid JSON data.")

    if len(encoded) > MAX_DEMAND_SNAPSHOT_BYTES:
        raise ValidationError(
            "Demand snapshot exceeds the 256 KiB limit."
        )
