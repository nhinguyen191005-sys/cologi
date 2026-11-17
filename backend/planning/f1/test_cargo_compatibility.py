
import unittest

from planning.f1.cargo_compatibility import (
    evaluate_cargo_categories_compatibility,
    normalize_cargo_compatibility_matrix,
    dataset_v7_cargo_compatibility_rows,
)


class CargoCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.matrix = normalize_cargo_compatibility_matrix([
            {
                "cargo_a_id": 1,
                "cargo_b_id": 1,
                "is_compatible": True,
                "reason_code": "SAME_GROUP",
            },
            {
                "cargo_a_id": 1,
                "cargo_b_id": 2,
                "is_compatible": False,
                "reason_code": "HARD_INCOMPATIBLE",
            },
            {
                "cargo_a_id": 2,
                "cargo_b_id": 2,
                "is_compatible": True,
                "reason_code": "SAME_GROUP",
            },
        ])

    def test_pair_lookup_is_symmetric(self):
        result = evaluate_cargo_categories_compatibility(
            [1, 2], self.matrix
        )
        self.assertFalse(result.is_compatible)
        self.assertEqual(result.reason_codes, ("HARD_INCOMPATIBLE",))

    def test_same_category_requires_configured_self_pair(self):
        result = evaluate_cargo_categories_compatibility(
            [1, 1], self.matrix
        )
        self.assertTrue(result.is_compatible)

    def test_missing_pair_fails_closed(self):
        result = evaluate_cargo_categories_compatibility(
            [1, 3], self.matrix
        )
        self.assertFalse(result.is_compatible)
        self.assertIn(
            "CARGO_COMPATIBILITY_UNVERIFIED",
            result.reason_codes,
        )

    def test_duplicate_pair_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "PAIR_DUPLICATE"):
            normalize_cargo_compatibility_matrix([
                {
                    "cargo_a_id": 1,
                    "cargo_b_id": 2,
                    "is_compatible": True,
                    "reason_code": "OK",
                },
                {
                    "cargo_a_id": 2,
                    "cargo_b_id": 1,
                    "is_compatible": True,
                    "reason_code": "OK",
                },
            ])

    def test_empty_matrix_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "MATRIX_MISSING"):
            normalize_cargo_compatibility_matrix([])

    def test_dataset_v7_matrix_has_28_configured_pairs(self):
        rows = dataset_v7_cargo_compatibility_rows()
        matrix = normalize_cargo_compatibility_matrix(rows)

        self.assertEqual(len(matrix), 28)
        self.assertEqual(
            sum(1 for item in matrix.values() if item.is_compatible),
            11,
        )
        self.assertEqual(
            sum(1 for item in matrix.values() if not item.is_compatible),
            17,
        )


    def test_dataset_v7_matrix_covers_seven_categories(self):
        rows = dataset_v7_cargo_compatibility_rows()
        category_ids = {
            row["cargo_a_id"] for row in rows
        } | {
            row["cargo_b_id"] for row in rows
        }

        self.assertEqual(category_ids, {1, 2, 3, 4, 5, 6, 7})

    