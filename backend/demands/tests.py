import re
from datetime import date, datetime, time, timezone as datetime_timezone
from unittest.mock import patch
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from masterdata.models import (
    CargoCategory,
    Item,
    Outlet,
    Supplier,
    SupplierItem,
)

from .models import DeliveryDemand, DemandItem, DemandStatus
from .services import (
    create_draft_demand,
    update_draft_demand,
    validate_supplier_offers_for_demand,
)


class DemandServiceTestBase(TestCase):
    def setUp(self):
        self.User = get_user_model()

        self.user = self.User.objects.create_user(
            email="buyer-demand-test@example.test",
            full_name="Demand Test Buyer",
        )

        self.supplier = Supplier.objects.create(
            supplier_code="SUP-DEM-001",
            supplier_name="Demand Test Supplier",
        )

        self.outlet = Outlet.objects.create(
            outlet_code="OUT-DEM-001",
            outlet_name="Demand Test Outlet",
            address="Da Nang",
        )

        self.category = CargoCategory.objects.create(
            category_code="CAT-DEM-001",
            category_name="Test Dry Cargo",
        )

        self.item = self.create_item("ITM-DEM-001")

    def create_item(self, code, category=None, active=True):
        return Item.objects.create(
            item_code=code,
            item_name=f"Test item {code}",
            cargo_category=category or self.category,
            weight_unit="KG",
            is_active=active,
        )

    def make_line(self, item=None, weight="10.000", uom=None, note=None):
        item = item or self.item

        row = {
            "item_id": item.pk,
            "required_weight_kg": weight,
            "item_note": note,
        }

        if uom is not None:
            row["unit_of_measure"] = uom

        return row

    def create_demand(self, items=None, **overrides):
        values = {
            "demand_code": "DD-DEM-TEST-001",
            "supplier_id": self.supplier.pk,
            "outlet_id": self.outlet.pk,
            "created_by": self.user,
            "requested_date": date(2026, 11, 16),
            "requested_start_time": time(8, 0),
            "requested_end_time": time(10, 0),
            "notes": None,
        }
        values.update(overrides)

        if items is None:
            items = [self.make_line()]

        return create_draft_demand(
            items=items,
            **values,
        )

    def create_offer(
        self,
        item=None,
        supplier=None,
        capacity="1000.000",
        status=SupplierItem.OfferStatus.ACTIVE,
    ):
        return SupplierItem.objects.create(
            supplier=supplier or self.supplier,
            item=item or self.item,
            unit_price_vnd_per_kg="25000.00",
            max_daily_supply_kg=capacity,
            lead_time_hours=8,
            minimum_order_kg="0.000",
            offer_status=status,
        )


class DemandCreationTests(DemandServiceTestBase):
    def test_create_draft_with_one_item(self):
        demand = self.create_demand()

        self.assertEqual(demand.status, DemandStatus.DRAFT)
        self.assertEqual(demand.items.count(), 1)
        self.assertEqual(demand.quantity_kg, Decimal("10.000"))
        self.assertEqual(
            demand.cargo_category_id,
            self.category.pk,
        )

    def test_header_quantity_is_calculated_from_items(self):
        item2 = self.create_item("ITM-DEM-002")
        item3 = self.create_item("ITM-DEM-003")

        demand = self.create_demand(items=[
            self.make_line(self.item, "10.250"),
            self.make_line(item2, "20.125"),
            self.make_line(item3, "30.500"),
        ])

        self.assertEqual(
            demand.quantity_kg,
            Decimal("60.875"),
        )

    def test_demand_supports_more_than_three_items(self):
        extra_items = [
            self.create_item(f"ITM-DEM-{number:03d}")
            for number in range(2, 6)
        ]

        all_items = [self.item] + extra_items

        demand = self.create_demand(items=[
            self.make_line(item, "5.000")
            for item in all_items
        ])

        self.assertEqual(demand.items.count(), 5)
        self.assertEqual(
            demand.quantity_kg,
            Decimal("25.000"),
        )

    def test_uom_is_derived_from_item_when_omitted(self):
        demand = self.create_demand()

        line = demand.items.get()

        self.assertEqual(line.unit_of_measure, "KG")

    def test_create_draft_does_not_require_supplier_offer(self):
        demand = self.create_demand()

        self.assertEqual(demand.status, DemandStatus.DRAFT)
        self.assertFalse(
            SupplierItem.objects.filter(
                supplier=self.supplier,
                item=self.item,
            ).exists()
        )

    def test_empty_item_list_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.create_demand(items=[])

        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_duplicate_item_in_same_demand_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.create_demand(items=[
                self.make_line(self.item, "5.000"),
                self.make_line(self.item, "10.000"),
            ])

        self.assertEqual(DeliveryDemand.objects.count(), 0)
        self.assertEqual(DemandItem.objects.count(), 0)

    def test_unknown_item_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.create_demand(items=[{
                "item_id": 999999,
                "required_weight_kg": "10.000",
            }])

        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_inactive_item_is_rejected(self):
        inactive_item = self.create_item(
            "ITM-DEM-INACTIVE",
            active=False,
        )

        with self.assertRaises(ValidationError):
            self.create_demand(items=[
                self.make_line(inactive_item)
            ])

        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_mixed_cargo_categories_are_rejected(self):
        other_category = CargoCategory.objects.create(
            category_code="CAT-DEM-002",
            category_name="Other Test Cargo",
        )
        other_item = self.create_item(
            "ITM-DEM-OTHER",
            category=other_category,
        )

        with self.assertRaises(ValidationError):
            self.create_demand(items=[
                self.make_line(self.item),
                self.make_line(other_item),
            ])

        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_inactive_cargo_category_is_rejected(self):
        inactive_category = CargoCategory.objects.create(
            category_code="CAT-DEM-INACTIVE",
            category_name="Inactive Cargo",
            is_active=False,
        )
        inactive_category_item = self.create_item(
            "ITM-DEM-INACTIVE-CAT",
            category=inactive_category,
        )

        with self.assertRaises(ValidationError):
            self.create_demand(items=[
                self.make_line(inactive_category_item)
            ])

        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_wrong_uom_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.create_demand(items=[
                self.make_line(self.item, uom="PCS")
            ])

        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_non_positive_weight_is_rejected(self):
        for weight in ("0", "-1"):
            with self.subTest(weight=weight):
                with self.assertRaises(ValidationError):
                    self.create_demand(items=[
                        self.make_line(self.item, weight)
                    ])

        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_invalid_or_non_finite_weight_is_rejected(self):
        for weight in ("invalid", "NaN", "Infinity"):
            with self.subTest(weight=weight):
                with self.assertRaises(ValidationError):
                    self.create_demand(items=[
                        self.make_line(self.item, weight)
                    ])

        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_inactive_supplier_is_rejected(self):
        self.supplier.is_active = False
        self.supplier.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            self.create_demand()

        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_inactive_outlet_is_rejected(self):
        self.outlet.is_active = False
        self.outlet.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            self.create_demand()

        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_reversed_requested_time_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.create_demand(
                requested_start_time=time(10, 0),
                requested_end_time=time(8, 0),
            )

        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_equal_requested_times_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.create_demand(
                requested_start_time=time(9, 0),
                requested_end_time=time(9, 0),
            )

        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_one_sided_requested_time_is_allowed(self):
        demand = self.create_demand(
            requested_start_time=time(8, 0),
            requested_end_time=None,
        )

        self.assertEqual(
            demand.requested_start_time,
            time(8, 0),
        )
        self.assertIsNone(demand.requested_end_time)

    def test_duplicate_demand_code_is_rejected(self):
        self.create_demand()

        with self.assertRaises(ValidationError):
            self.create_demand()

        self.assertEqual(DeliveryDemand.objects.count(), 1)
        self.assertEqual(DemandItem.objects.count(), 1)


class SupplierOfferGateTests(DemandServiceTestBase):
    def test_all_active_supplier_offers_pass(self):
        item2 = self.create_item("ITM-DEM-002")

        demand = self.create_demand(items=[
            self.make_line(self.item, "100.000"),
            self.make_line(item2, "200.000"),
        ])

        self.create_offer(self.item, capacity="500.000")
        self.create_offer(item2, capacity="500.000")

        self.assertTrue(
            validate_supplier_offers_for_demand(demand)
        )

    def test_missing_supplier_offer_blocks_validation(self):
        demand = self.create_demand()

        with self.assertRaises(ValidationError):
            validate_supplier_offers_for_demand(demand)

    def test_inactive_supplier_offer_blocks_validation(self):
        demand = self.create_demand()

        self.create_offer(
            status=SupplierItem.OfferStatus.INACTIVE,
        )

        with self.assertRaises(ValidationError):
            validate_supplier_offers_for_demand(demand)

    def test_null_supplier_capacity_blocks_validation(self):
        demand = self.create_demand()

        self.create_offer(capacity=None)

        with self.assertRaises(ValidationError):
            validate_supplier_offers_for_demand(demand)

    def test_insufficient_supplier_capacity_blocks_validation(self):
        demand = self.create_demand()

        self.create_offer(capacity="9.000")

        with self.assertRaises(ValidationError):
            validate_supplier_offers_for_demand(demand)

    def test_other_supplier_offer_does_not_replace_selected_supplier(self):
        other_supplier = Supplier.objects.create(
            supplier_code="SUP-DEM-002",
            supplier_name="Alternative Supplier",
        )

        demand = self.create_demand()

        self.create_offer(
            supplier=other_supplier,
            capacity="1000.000",
        )

        with self.assertRaises(ValidationError):
            validate_supplier_offers_for_demand(demand)

        self.assertEqual(demand.supplier_id, self.supplier.pk)

    def test_inactive_supplier_blocks_validation(self):
        demand = self.create_demand()

        self.create_offer()

        self.supplier.is_active = False
        self.supplier.save(update_fields=["is_active"])

        demand.refresh_from_db()

        with self.assertRaises(ValidationError):
            validate_supplier_offers_for_demand(demand)

    def test_missing_offer_for_one_of_multiple_items_blocks_validation(self):
        item2 = self.create_item("ITM-DEM-002")

        demand = self.create_demand(items=[
            self.make_line(self.item, "100.000"),
            self.make_line(item2, "100.000"),
        ])

        self.create_offer(self.item, capacity="500.000")

        with self.assertRaises(ValidationError):
            validate_supplier_offers_for_demand(demand)

    def test_capacity_is_checked_per_item(self):
        item2 = self.create_item("ITM-DEM-002")

        demand = self.create_demand(items=[
            self.make_line(self.item, "100.000"),
            self.make_line(item2, "200.000"),
        ])

        self.create_offer(self.item, capacity="150.000")
        self.create_offer(item2, capacity="150.000")

        with self.assertRaises(ValidationError):
            validate_supplier_offers_for_demand(demand)

    def test_demand_without_items_cannot_pass_supplier_gate(self):
        demand = self.create_demand()

        DemandItem.objects.filter(demand=demand).delete()

        with self.assertRaises(ValidationError):
            validate_supplier_offers_for_demand(demand)


class DemandUpdateTests(DemandServiceTestBase):
    @patch("demands.services.timezone.now")
    def test_backend_generates_demand_code_when_omitted(self, mocked_now):
        # 21:30 UTC on Nov 12 is 04:30 on Nov 13 in Ho Chi Minh City.
        mocked_now.return_value = datetime(
            2026, 11, 12, 21, 30,
            tzinfo=datetime_timezone.utc,
        )

        demand = create_draft_demand(
            supplier_id=self.supplier.pk,
            outlet_id=self.outlet.pk,
            created_by=self.user,
            requested_date=date(2026, 11, 16),
            items=[self.make_line()],
        )

        self.assertRegex(
            demand.demand_code,
            r"^DD-\d{8}-[0-9A-F]{8}$",
        )
        self.assertTrue(demand.demand_code.startswith("DD-20261113-"))

    def test_update_replaces_items_and_recalculates_header(self):
        item2 = self.create_item("ITM-DEM-UPD-002")
        demand = self.create_demand()

        updated = update_draft_demand(
            demand_id=demand.pk,
            updated_by=self.user,
            changes={
                "requested_date": date(2026, 11, 17),
                "notes": "Updated through demand service",
                "items": [
                    self.make_line(item2, "25.500", note="Replacement line"),
                ],
            },
        )

        updated.refresh_from_db()

        self.assertEqual(updated.requested_date, date(2026, 11, 17))
        self.assertEqual(updated.notes, "Updated through demand service")
        self.assertEqual(updated.quantity_kg, Decimal("25.500"))
        self.assertEqual(updated.cargo_category_id, self.category.pk)
        self.assertEqual(updated.items.count(), 1)

        line = updated.items.get()
        self.assertEqual(line.item_id, item2.pk)
        self.assertEqual(line.required_weight_kg, Decimal("25.500"))
        self.assertEqual(line.item_note, "Replacement line")

        self.assertEqual(updated.demand_code, "DD-DEM-TEST-001")
        self.assertEqual(updated.outlet_id, self.outlet.pk)
        self.assertEqual(updated.status, DemandStatus.DRAFT)

    def test_omitting_items_preserves_existing_lines(self):
        demand = self.create_demand()
        original_line = demand.items.get()

        updated = update_draft_demand(
            demand_id=demand.pk,
            updated_by=self.user,
            changes={"notes": "Notes only"},
        )

        self.assertEqual(updated.notes, "Notes only")
        self.assertEqual(updated.items.count(), 1)

        preserved_line = updated.items.get()
        self.assertEqual(preserved_line.pk, original_line.pk)
        self.assertEqual(preserved_line.item_id, original_line.item_id)

    def test_only_creator_can_update_draft(self):
        demand = self.create_demand()
        other_user = self.User.objects.create_user(
            email="other-demand-user@example.test",
            full_name="Other Demand User",
        )

        with self.assertRaises(ValidationError):
            update_draft_demand(
                demand_id=demand.pk,
                updated_by=other_user,
                changes={"notes": "Unauthorized update"},
            )

        demand.refresh_from_db()
        self.assertIsNone(demand.notes)
        self.assertEqual(demand.status, DemandStatus.DRAFT)

    def test_non_draft_demand_cannot_be_updated(self):
        demand = self.create_demand()
        demand.status = DemandStatus.SUBMITTED
        demand.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            update_draft_demand(
                demand_id=demand.pk,
                updated_by=self.user,
                changes={"notes": "Must not update"},
            )

        demand.refresh_from_db()
        self.assertIsNone(demand.notes)
        self.assertEqual(demand.status, DemandStatus.SUBMITTED)

    def test_immutable_fields_are_rejected(self):
        demand = self.create_demand()

        with self.assertRaises(ValidationError):
            update_draft_demand(
                demand_id=demand.pk,
                updated_by=self.user,
                changes={"status": DemandStatus.SUBMITTED},
            )

        demand.refresh_from_db()
        self.assertEqual(demand.status, DemandStatus.DRAFT)

    def test_invalid_header_and_item_replacement_leave_demand_unchanged(self):
        item2 = self.create_item("ITM-DEM-UPD-003")
        demand = self.create_demand()
        original_line_id = demand.items.get().pk

        with self.assertRaises(ValidationError):
            update_draft_demand(
                demand_id=demand.pk,
                updated_by=self.user,
                changes={
                    "requested_start_time": time(11, 0),
                    "requested_end_time": time(9, 0),
                    "items": [self.make_line(item2, "50.000")],
                },
            )

        demand.refresh_from_db()
        self.assertEqual(demand.quantity_kg, Decimal("10.000"))
        self.assertEqual(demand.items.count(), 1)
        self.assertEqual(demand.items.get().pk, original_line_id)
        self.assertEqual(demand.items.get().item_id, self.item.pk)


from rest_framework import status as http_status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode, UserRole, UserOutletAccess


class DemandAPITests(APITestCase):
    def setUp(self):
        self.User = get_user_model()

        self.buyer = self.User.objects.create_user(
            email="api-buyer@example.test",
            full_name="API Buyer",
        )
        self.buyer_role = Role.objects.create(
            code=RoleCode.PURCHASING_STAFF,
            name="Purchasing Staff",
        )
        UserRole.objects.create(
            user=self.buyer,
            role=self.buyer_role,
        )

        self.outlet = Outlet.objects.create(
            outlet_code="OUT-API-001",
            outlet_name="API Test Outlet",
            address="Da Nang",
        )
        self.other_outlet = Outlet.objects.create(
            outlet_code="OUT-API-002",
            outlet_name="Other API Outlet",
            address="Da Nang",
        )
        UserOutletAccess.objects.create(
            user=self.buyer,
            outlet=self.outlet,
        )

        self.supplier = Supplier.objects.create(
            supplier_code="SUP-API-001",
            supplier_name="API Test Supplier",
        )
        self.category = CargoCategory.objects.create(
            category_code="CAT-API-001",
            category_name="API Dry Cargo",
        )
        self.item = Item.objects.create(
            item_code="ITM-API-001",
            item_name="API Test Item",
            cargo_category=self.category,
            weight_unit="KG",
            is_active=True,
        )

        self.list_url = "/api/demands/"

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.buyer)

    def payload(self, outlet=None):
        return {
            "supplier_id": self.supplier.pk,
            "outlet_id": (outlet or self.outlet).pk,
            "requested_date": "2026-11-16",
            "requested_start_time": "08:00:00",
            "requested_end_time": "10:00:00",
            "notes": "Created by API test",
            "items": [
                {
                    "item_id": self.item.pk,
                    "required_weight_kg": "25.500",
                    "unit_of_measure": "KG",
                    "item_note": "API test line",
                }
            ],
        }

    def create_db_demand(
        self,
        *,
        outlet=None,
        created_by=None,
        demand_code="DD-API-TEST-001",
    ):
        return create_draft_demand(
            demand_code=demand_code,
            supplier_id=self.supplier.pk,
            outlet_id=(outlet or self.outlet).pk,
            created_by=created_by or self.buyer,
            requested_date=date(2026, 11, 16),
            items=[
                {
                    "item_id": self.item.pk,
                    "required_weight_kg": "10.000",
                }
            ],
        )

    def test_demand_api_requires_authentication(self):
        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            http_status.HTTP_401_UNAUTHORIZED,
        )

    def test_create_generates_code_and_derives_header(self):
        self.authenticate()

        response = self.client.post(
            self.list_url,
            self.payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_201_CREATED,
            response.data,
        )
        self.assertRegex(
            response.data["demand_code"],
            r"^DD-\d{8}-[0-9A-F]{8}$",
        )
        self.assertEqual(response.data["status"], DemandStatus.DRAFT)
        self.assertEqual(
            response.data["created_by_id"],
            self.buyer.pk,
        )
        self.assertEqual(
            response.data["quantity_kg"],
            "25.500",
        )
        self.assertEqual(
            response.data["cargo_category_id"],
            self.category.pk,
        )
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(DeliveryDemand.objects.count(), 1)

    def test_create_rejects_outlet_outside_user_scope(self):
        self.authenticate()

        response = self.client.post(
            self.list_url,
            self.payload(outlet=self.other_outlet),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_create_rejects_server_managed_fields(self):
        self.authenticate()
        data = self.payload()
        data["status"] = DemandStatus.SUBMITTED
        data["quantity_kg"] = "999.000"

        response = self.client.post(
            self.list_url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(DeliveryDemand.objects.count(), 0)

    def test_list_and_detail_are_scoped_to_assigned_outlets(self):
        in_scope = self.create_db_demand(
            demand_code="DD-API-IN-SCOPE-001",
        )
        outside_scope = self.create_db_demand(
            outlet=self.other_outlet,
            demand_code="DD-API-OUTSIDE-001",
        )
        self.authenticate()

        list_response = self.client.get(self.list_url)

        self.assertEqual(
            list_response.status_code,
            http_status.HTTP_200_OK,
        )
        returned_ids = {
            row["id"] for row in list_response.data
        }
        self.assertIn(in_scope.pk, returned_ids)
        self.assertNotIn(outside_scope.pk, returned_ids)

        detail_response = self.client.get(
            f"{self.list_url}{outside_scope.pk}/"
        )
        self.assertEqual(
            detail_response.status_code,
            http_status.HTTP_404_NOT_FOUND,
        )

    def test_creator_can_patch_own_draft(self):
        self.authenticate()

        create_response = self.client.post(
            self.list_url,
            self.payload(),
            format="json",
        )
        self.assertEqual(
            create_response.status_code,
            http_status.HTTP_201_CREATED,
            create_response.data,
        )

        demand_id = create_response.data["id"]
        patch_response = self.client.patch(
            f"{self.list_url}{demand_id}/",
            {"notes": "Updated by creator"},
            format="json",
        )

        self.assertEqual(
            patch_response.status_code,
            http_status.HTTP_200_OK,
            patch_response.data,
        )
        self.assertEqual(
            patch_response.data["notes"],
            "Updated by creator",
        )

    def test_non_creator_cannot_patch_draft(self):
        demand = self.create_db_demand()

        other_buyer = self.User.objects.create_user(
            email="api-other-buyer@example.test",
            full_name="Other API Buyer",
        )
        UserRole.objects.create(
            user=other_buyer,
            role=self.buyer_role,
        )
        UserOutletAccess.objects.create(
            user=other_buyer,
            outlet=self.outlet,
        )

        self.authenticate(other_buyer)
        response = self.client.patch(
            f"{self.list_url}{demand.pk}/",
            {"notes": "Unauthorized update"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_403_FORBIDDEN,
        )

        demand.refresh_from_db()
        self.assertIsNone(demand.notes)

    def test_non_draft_patch_returns_conflict(self):
        demand = self.create_db_demand()
        demand.status = DemandStatus.SUBMITTED
        demand.save(update_fields=["status"])

        self.authenticate()
        response = self.client.patch(
            f"{self.list_url}{demand.pk}/",
            {"notes": "Must not update"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_409_CONFLICT,
        )

        demand.refresh_from_db()
        self.assertIsNone(demand.notes)

    def test_manager_can_read_all_demands_but_cannot_write(self):
        own_demand = self.create_db_demand(
            demand_code="DD-API-MANAGER-001",
        )
        other_demand = self.create_db_demand(
            outlet=self.other_outlet,
            demand_code="DD-API-MANAGER-002",
        )

        manager = self.User.objects.create_user(
            email="api-manager@example.test",
            full_name="API Manager",
        )
        manager_role = Role.objects.create(
            code=RoleCode.MANAGER,
            name="Manager",
        )
        UserRole.objects.create(
            user=manager,
            role=manager_role,
        )

        self.authenticate(manager)

        list_response = self.client.get(self.list_url)
        self.assertEqual(
            list_response.status_code,
            http_status.HTTP_200_OK,
        )
        returned_ids = {
            row["id"] for row in list_response.data
        }
        self.assertIn(own_demand.pk, returned_ids)
        self.assertIn(other_demand.pk, returned_ids)

        create_response = self.client.post(
            self.list_url,
            self.payload(),
            format="json",
        )
        self.assertEqual(
            create_response.status_code,
            http_status.HTTP_403_FORBIDDEN,
        )

        patch_response = self.client.patch(
            f"{self.list_url}{own_demand.pk}/",
            {"notes": "Manager write attempt"},
            format="json",
        )
        self.assertEqual(
            patch_response.status_code,
            http_status.HTTP_403_FORBIDDEN,
        )

    def test_manager_and_purchasing_dual_role_remains_read_only(self):
        demand = self.create_db_demand()

        dual_role_user = self.User.objects.create_user(
            email="api-dual-role@example.test",
            full_name="Dual Role User",
        )
        UserRole.objects.create(
            user=dual_role_user,
            role=self.buyer_role,
        )
        manager_role = Role.objects.create(
            code=RoleCode.MANAGER,
            name="Manager",
        )
        UserRole.objects.create(
            user=dual_role_user,
            role=manager_role,
        )
        UserOutletAccess.objects.create(
            user=dual_role_user,
            outlet=self.outlet,
        )

        self.authenticate(dual_role_user)

        create_response = self.client.post(
            self.list_url,
            self.payload(),
            format="json",
        )
        patch_response = self.client.patch(
            f"{self.list_url}{demand.pk}/",
            {"notes": "Dual role write attempt"},
            format="json",
        )

        self.assertEqual(
            create_response.status_code,
            http_status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            patch_response.status_code,
            http_status.HTTP_403_FORBIDDEN,
        )

    def test_supplier_and_transport_provider_cannot_access_demands(self):
        for index, role_code in enumerate(
            (
                RoleCode.SUPPLIER,
                RoleCode.TRANSPORT_PROVIDER,
            ),
            start=1,
        ):
            user = self.User.objects.create_user(
                email=f"api-external-{index}@example.test",
                full_name=f"External Actor {index}",
            )
            role = Role.objects.create(
                code=role_code,
                name=role_code,
            )
            UserRole.objects.create(user=user, role=role)

            self.authenticate(user)
            response = self.client.get(self.list_url)

            self.assertEqual(
                response.status_code,
                http_status.HTTP_403_FORBIDDEN,
                f"{role_code} unexpectedly accessed Demand API.",
            )

    def test_status_endpoint_returns_current_demand_status(self):
        demand = self.create_db_demand()
        self.authenticate()

        response = self.client.get(
            f"{self.list_url}{demand.pk}/status/"
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_200_OK,
        )
        self.assertEqual(response.data["id"], demand.pk)
        self.assertEqual(
            response.data["demand_code"],
            demand.demand_code,
        )
        self.assertEqual(
            response.data["status"],
            DemandStatus.DRAFT,
        )
