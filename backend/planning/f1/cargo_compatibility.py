
"""Pure Cargo Category compatibility matrix validation.

The matrix is snapshot input. Missing pairs are always fail-closed.
No Django imports, database access, persistence, or I/O.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations_with_replacement


@dataclass(frozen=True)
class CargoPairCompatibility:
    is_compatible: bool
    reason_code: str


@dataclass(frozen=True)
class CargoCompatibilityResult:
    is_compatible: bool
    reason_codes: tuple[str, ...]


def normalize_cargo_compatibility_matrix(rows):
    """Validate snapshot rows and normalize pairs symmetrically."""
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValueError("CARGO_COMPATIBILITY_MATRIX_MISSING")

    matrix = {}

    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("CARGO_COMPATIBILITY_ROW_INVALID")

        cargo_a_id = row.get("cargo_a_id")
        cargo_b_id = row.get("cargo_b_id")
        compatible = row.get("is_compatible")
        reason_code = row.get("reason_code")

        for value in (cargo_a_id, cargo_b_id):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            ):
                raise ValueError("CARGO_COMPATIBILITY_CATEGORY_ID_INVALID")

        if not isinstance(compatible, bool):
            raise ValueError("CARGO_COMPATIBILITY_VALUE_INVALID")

        if not isinstance(reason_code, str) or not reason_code.strip():
            raise ValueError("CARGO_COMPATIBILITY_REASON_REQUIRED")

        pair = (min(cargo_a_id, cargo_b_id), max(cargo_a_id, cargo_b_id))

        if pair in matrix:
            raise ValueError("CARGO_COMPATIBILITY_PAIR_DUPLICATE")

        matrix[pair] = CargoPairCompatibility(
            is_compatible=compatible,
            reason_code=reason_code,
        )

    return matrix


def evaluate_cargo_categories_compatibility(category_ids, matrix):
    """Require every category pair, including self-pairs, to be configured."""
    if not isinstance(matrix, Mapping) or not matrix:
        raise ValueError("CARGO_COMPATIBILITY_MATRIX_MISSING")

    normalized_ids = set()

    for category_id in category_ids:
        if (
            isinstance(category_id, bool)
            or not isinstance(category_id, int)
            or category_id <= 0
        ):
            raise ValueError("CARGO_COMPATIBILITY_CATEGORY_ID_INVALID")

        normalized_ids.add(category_id)

    if not normalized_ids:
        raise ValueError("CARGO_COMPATIBILITY_CATEGORIES_REQUIRED")

    reason_codes = []

    for category_a, category_b in combinations_with_replacement(
        sorted(normalized_ids), 2
    ):
        pair = (category_a, category_b)
        result = matrix.get(pair)

        if result is None:
            reason_codes.append("CARGO_COMPATIBILITY_UNVERIFIED")
        elif not result.is_compatible:
            reason_codes.append(result.reason_code)

    return CargoCompatibilityResult(
        is_compatible=not reason_codes,
        reason_codes=tuple(sorted(set(reason_codes))),
    )


# Frozen configuration source: CoLogi_Dataset_v7, sheet 08_Cargo_Compat.
# Rows are stored in the source workbook as an upper-triangle matrix.
# normalize_cargo_compatibility_matrix() makes lookups symmetric.

_DATASET_V7_CARGO_COMPATIBILITY_DATA = (
    (1, 1, True, "SAME_COMPATIBILITY_GROUP"),
    (1, 2, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (1, 3, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (1, 4, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (1, 5, True, "SAME_COMPATIBILITY_GROUP"),
    (1, 6, True, "SAME_COMPATIBILITY_GROUP"),
    (1, 7, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (2, 2, True, "SAME_COMPATIBILITY_GROUP"),
    (2, 3, True, "SAME_COMPATIBILITY_GROUP"),
    (2, 4, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (2, 5, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (2, 6, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (2, 7, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (3, 3, True, "SAME_COMPATIBILITY_GROUP"),
    (3, 4, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (3, 5, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (3, 6, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (3, 7, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (4, 4, True, "SAME_COMPATIBILITY_GROUP"),
    (4, 5, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (4, 6, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (4, 7, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (5, 5, True, "SAME_COMPATIBILITY_GROUP"),
    (5, 6, True, "SAME_COMPATIBILITY_GROUP"),
    (5, 7, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (6, 6, True, "SAME_COMPATIBILITY_GROUP"),
    (6, 7, False, "HARD_INCOMPATIBLE_TEMPERATURE_OR_FOOD_SAFETY"),
    (7, 7, True, "SAME_COMPATIBILITY_GROUP"),
)


def dataset_v7_cargo_compatibility_rows():
    """Return fresh JSON-safe rows from the frozen Dataset v7 fixture."""
    return tuple(
        {
            "cargo_a_id": cargo_a_id,
            "cargo_b_id": cargo_b_id,
            "is_compatible": is_compatible,
            "reason_code": reason_code,
        }
        for (
            cargo_a_id,
            cargo_b_id,
            is_compatible,
            reason_code,
        ) in _DATASET_V7_CARGO_COMPATIBILITY_DATA
    )
