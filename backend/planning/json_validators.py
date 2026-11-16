from django.core.exceptions import ValidationError


def validate_json_object(value):
    if not isinstance(value, dict):
        raise ValidationError("Value must be a JSON object.")


def validate_diagnostics_array(value):
    if not isinstance(value, list):
        raise ValidationError("Diagnostics must be a JSON array.")
