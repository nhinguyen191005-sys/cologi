import re
from datetime import date, datetime, time, timezone as datetime_timezone
from unittest.mock import patch
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone as django_timezone
from django.test import TestCase

from masterdata.models import (
    CargoCategory,
    Item,
    Outlet,
    Supplier,
    SupplierItem,
)

from .models import (
    DeliveryDemand,
    DemandItem,
    DemandStatus,
    DemandSourcingOption,
    DemandSupplierSelection,
    SupplierConfirmation,
    SupplierItemPromise,
    SupplierRequest,
)
from .services import (
    create_draft_demand,
    select_supplier_for_submitted_demand,
    submit_demand,
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


    def create_submit_offer(self, capacity="100.000"):
        return SupplierItem.objects.create(
            supplier=self.supplier,
            item=self.item,
            unit_price_vnd_per_kg=Decimal("25000.00"),
            max_daily_supply_kg=Decimal(capacity),
            lead_time_hours=8,
            minimum_order_kg=Decimal("0.000"),
            offer_status=SupplierItem.OfferStatus.ACTIVE,
        )

    def test_submit_multi_item_via_api_creates_real_request_and_promises(self):
        item2 = Item.objects.create(
            item_code="ITM-API-SUBMIT-002",
            item_name="Second API Submit Item",
            cargo_category=self.category,
            weight_unit="KG",
            is_active=True,
        )

        self.create_submit_offer(capacity="100.000")
        SupplierItem.objects.create(
            supplier=self.supplier,
            item=item2,
            unit_price_vnd_per_kg=Decimal("27000.00"),
            max_daily_supply_kg=Decimal("100.000"),
            lead_time_hours=12,
            minimum_order_kg=Decimal("0.000"),
            offer_status=SupplierItem.OfferStatus.ACTIVE,
        )

        data = self.payload()
        data["items"].append({
            "item_id": item2.pk,
            "required_weight_kg": "35.000",
            "unit_of_measure": "KG",
            "item_note": "Second API test line",
        })

        self.authenticate()
        create_response = self.client.post(
            self.list_url,
            data,
            format="json",
        )
        self.assertEqual(
            create_response.status_code,
            http_status.HTTP_201_CREATED,
            create_response.data,
        )

        demand_id = create_response.data["id"]
        self.assertEqual(len(create_response.data["items"]), 2)
        self.assertEqual(create_response.data["quantity_kg"], "60.500")

        # DRAFT must not create supply-side records.
        self.assertFalse(
            SupplierRequest.objects.filter(demand_id=demand_id).exists()
        )
        self.assertFalse(
            SupplierConfirmation.objects.filter(demand_id=demand_id).exists()
        )
        self.assertFalse(
            SupplierItemPromise.objects.filter(
                supplier_request__demand_id=demand_id,
            ).exists()
        )

        status_before_submit = self.client.get(
            f"{self.list_url}{demand_id}/status/"
        )
        self.assertEqual(
            status_before_submit.status_code,
            http_status.HTTP_200_OK,
            status_before_submit.data,
        )
        self.assertEqual(
            status_before_submit.data["status"],
            DemandStatus.DRAFT,
        )

        submit_response = self.client.post(
            f"{self.list_url}{demand_id}/submit",
            {},
            format="json",
        )
        self.assertEqual(
            submit_response.status_code,
            http_status.HTTP_200_OK,
            submit_response.data,
        )
        self.assertEqual(
            submit_response.data["submission_status"],
            "SUBMITTED",
        )

        supplier_request = SupplierRequest.objects.select_related(
            "demand",
            "supplier",
            "supplier_confirmation",
        ).get(pk=submit_response.data["supplier_request_id"])

        self.assertEqual(supplier_request.demand_id, demand_id)
        self.assertEqual(supplier_request.supplier_id, self.supplier.pk)
        self.assertTrue(supplier_request.request_code)
        self.assertEqual(supplier_request.attempt_no, 1)
        self.assertEqual(
            supplier_request.request_status,
            SupplierRequest.RequestStatus.WAITING,
        )
        self.assertEqual(
            supplier_request.supplier_confirmation.confirmation_status,
            SupplierConfirmation.ConfirmationStatus.PENDING,
        )

        promises = list(
            SupplierItemPromise.objects.filter(
                supplier_request=supplier_request,
            ).select_related("demand_item", "supplier_item")
        )
        self.assertEqual(len(promises), 2)

        actual_weights = {
            row.demand_item.item_id: row.promised_weight_kg
            for row in promises
        }
        self.assertEqual(
            actual_weights,
            {
                self.item.pk: Decimal("25.500"),
                item2.pk: Decimal("35.000"),
            },
        )
        self.assertEqual(
            {row.supplier_item.supplier_id for row in promises},
            {self.supplier.pk},
        )
        self.assertTrue(all(
            row.line_status == SupplierItemPromise.LineStatus.PENDING
            and row.confirmed_weight_kg == Decimal("0.000")
            for row in promises
        ))

        demand = DeliveryDemand.objects.get(pk=demand_id)
        self.assertEqual(demand.status, DemandStatus.SUBMITTED)
        self.assertEqual(
            SupplierRequest.objects.filter(demand_id=demand_id).count(),
            1,
        )
        self.assertEqual(
            SupplierConfirmation.objects.filter(demand_id=demand_id).count(),
            1,
        )

        status_after_submit = self.client.get(
            f"{self.list_url}{demand_id}/status/"
        )
        self.assertEqual(
            status_after_submit.status_code,
            http_status.HTTP_200_OK,
            status_after_submit.data,
        )
        self.assertEqual(
            status_after_submit.data["status"],
            DemandStatus.SUBMITTED,
        )

    def test_creator_can_submit_draft_and_receives_supplier_request_id(self):
        demand = self.create_db_demand()
        self.create_submit_offer()
        self.authenticate()

        response = self.client.post(
            f"{self.list_url}{demand.pk}/submit",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_200_OK,
            response.data,
        )
        self.assertEqual(
            set(response.data.keys()),
            {"submission_status", "supplier_request_id"},
        )
        self.assertEqual(response.data["submission_status"], "SUBMITTED")

        demand.refresh_from_db()
        self.assertEqual(demand.status, DemandStatus.SUBMITTED)

        supplier_request = SupplierRequest.objects.get(
            pk=response.data["supplier_request_id"]
        )
        self.assertEqual(supplier_request.demand_id, demand.pk)
        self.assertEqual(supplier_request.created_by_id, self.buyer.pk)

    def test_non_creator_cannot_submit_demand(self):
        demand = self.create_db_demand()
        self.create_submit_offer()

        other_buyer = self.User.objects.create_user(
            email="submit-noncreator@example.test",
            full_name="Submit Non Creator",
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
        response = self.client.post(
            f"{self.list_url}{demand.pk}/submit",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(SupplierRequest.objects.count(), 0)

        demand.refresh_from_db()
        self.assertEqual(demand.status, DemandStatus.DRAFT)

    def test_manager_cannot_submit_demand(self):
        demand = self.create_db_demand()
        self.create_submit_offer()

        manager = self.User.objects.create_user(
            email="submit-manager@example.test",
            full_name="Submit Manager",
        )
        manager_role = Role.objects.create(
            code=RoleCode.MANAGER,
            name="Manager",
        )
        UserRole.objects.create(user=manager, role=manager_role)

        self.authenticate(manager)
        response = self.client.post(
            f"{self.list_url}{demand.pk}/submit",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(SupplierRequest.objects.count(), 0)

    def test_submit_without_active_supplier_offer_returns_400(self):
        demand = self.create_db_demand()
        self.authenticate()

        response = self.client.post(
            f"{self.list_url}{demand.pk}/submit",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_400_BAD_REQUEST,
            response.data,
        )
        self.assertEqual(SupplierRequest.objects.count(), 0)
        self.assertFalse(
            SupplierConfirmation.objects.filter(demand=demand).exists()
        )
        self.assertFalse(
            SupplierItemPromise.objects.filter(
                supplier_request__demand=demand,
            ).exists()
        )

        demand.refresh_from_db()
        self.assertEqual(demand.status, DemandStatus.DRAFT)

    def test_submit_with_existing_waiting_request_returns_409(self):
        demand = self.create_db_demand()
        self.create_submit_offer()

        confirmation = SupplierConfirmation.objects.create(
            demand=demand,
            supplier=self.supplier,
            confirmation_status=SupplierConfirmation.ConfirmationStatus.PENDING,
            source_mode=SupplierConfirmation.SourceMode.LIVE_API,
        )
        SupplierRequest.objects.create(
            demand=demand,
            supplier=self.supplier,
            supplier_confirmation=confirmation,
            request_code="SR-API-WAITING-001",
            attempt_no=1,
            request_status=SupplierRequest.RequestStatus.WAITING,
            created_by=self.buyer,
        )

        self.authenticate()
        response = self.client.post(
            f"{self.list_url}{demand.pk}/submit",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_409_CONFLICT,
            response.data,
        )
        self.assertEqual(
            SupplierRequest.objects.filter(demand=demand).count(),
            1,
        )

        demand.refresh_from_db()
        self.assertEqual(demand.status, DemandStatus.DRAFT)

    def test_submit_non_draft_demand_returns_409(self):
        demand = self.create_db_demand()
        self.create_submit_offer()
        demand.status = DemandStatus.SUBMITTED
        demand.save(update_fields=["status"])

        self.authenticate()
        response = self.client.post(
            f"{self.list_url}{demand.pk}/submit",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_409_CONFLICT,
            response.data,
        )
        self.assertEqual(SupplierRequest.objects.count(), 0)


    def make_selection_attempt(
        self,
        confirmation_status,
        request_status,
    ):
        demand = self.create_db_demand()
        demand.status = DemandStatus.SUBMITTED
        demand.save(update_fields=["status"])

        now = django_timezone.now()
        confirmation = SupplierConfirmation.objects.create(
            demand=demand,
            supplier=self.supplier,
            confirmation_status=confirmation_status,
            source_mode=SupplierConfirmation.SourceMode.LIVE_API,
            recorded_at=(
                now
                if confirmation_status
                in {
                    SupplierConfirmation.ConfirmationStatus.CONFIRMED,
                    SupplierConfirmation.ConfirmationStatus.PARTIAL,
                    SupplierConfirmation.ConfirmationStatus.DECLINED,
                }
                else None
            ),
            ready_date=(
                demand.requested_date
                if confirmation_status
                in {
                    SupplierConfirmation.ConfirmationStatus.CONFIRMED,
                    SupplierConfirmation.ConfirmationStatus.PARTIAL,
                }
                else None
            ),
        )

        request = SupplierRequest.objects.create(
            demand=demand,
            supplier=self.supplier,
            supplier_confirmation=confirmation,
            request_code=f"SR-API-SELECT-{demand.pk}",
            attempt_no=1,
            request_status=request_status,
            created_by=self.buyer,
            responded_at=(
                now
                if request_status == SupplierRequest.RequestStatus.RESPONDED
                else None
            ),
        )
        return demand, request, confirmation

    def create_selection_offer(self, supplier, capacity="100.000"):
        return SupplierItem.objects.create(
            supplier=supplier,
            item=self.item,
            unit_price_vnd_per_kg=Decimal("25000.00"),
            max_daily_supply_kg=Decimal(capacity),
            lead_time_hours=8,
            minimum_order_kg=Decimal("0.000"),
            offer_status=SupplierItem.OfferStatus.ACTIVE,
        )

    def test_creator_can_select_same_supplier_after_expired_request(self):
        demand, previous, _ = self.make_selection_attempt(
            SupplierConfirmation.ConfirmationStatus.PENDING,
            SupplierRequest.RequestStatus.EXPIRED,
        )
        self.create_selection_offer(self.supplier)
        self.authenticate()

        response = self.client.post(
            f"{self.list_url}{demand.pk}/select-supplier",
            {"selected_supplier_id": self.supplier.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_200_OK,
            response.data,
        )
        self.assertEqual(response.data["demand_id"], demand.pk)
        self.assertEqual(response.data["selected_supplier_id"], self.supplier.pk)
        self.assertEqual(response.data["demand_status"], "SUBMITTED")
        self.assertEqual(
            response.data["selection_reason"],
            DemandSupplierSelection.SelectionReason.RETRY_AFTER_EXPIRED,
        )

        demand.refresh_from_db()
        self.assertEqual(demand.status, DemandStatus.SUBMITTED)
        self.assertEqual(demand.supplier_id, self.supplier.pk)
        self.assertEqual(SupplierRequest.objects.filter(demand=demand).count(), 1)
        self.assertEqual(
            DemandSupplierSelection.objects.filter(
                demand=demand,
                previous_request=previous,
            ).count(),
            1,
        )

    def test_creator_can_select_alternative_supplier_after_declined(self):
        demand, previous, _ = self.make_selection_attempt(
            SupplierConfirmation.ConfirmationStatus.DECLINED,
            SupplierRequest.RequestStatus.RESPONDED,
        )
        alternative = Supplier.objects.create(
            supplier_code="SUP-API-SELECT-ALT",
            supplier_name="API Selection Alternative",
        )
        self.create_selection_offer(alternative)
        self.authenticate()

        response = self.client.post(
            f"{self.list_url}{demand.pk}/select-supplier",
            {"selected_supplier_id": alternative.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_200_OK,
            response.data,
        )
        self.assertEqual(
            response.data["selection_reason"],
            DemandSupplierSelection.SelectionReason.REPLACE_AFTER_DECLINED,
        )

        demand.refresh_from_db()
        self.assertEqual(demand.status, DemandStatus.SUBMITTED)
        self.assertEqual(demand.supplier_id, alternative.pk)
        self.assertEqual(
            SupplierRequest.objects.filter(demand=demand).count(),
            1,
        )
        self.assertTrue(
            DemandSupplierSelection.objects.filter(
                demand=demand,
                previous_request=previous,
                selected_supplier=alternative,
            ).exists()
        )

    def test_non_creator_cannot_select_supplier(self):
        demand, _, _ = self.make_selection_attempt(
            SupplierConfirmation.ConfirmationStatus.PENDING,
            SupplierRequest.RequestStatus.EXPIRED,
        )
        self.create_selection_offer(self.supplier)

        other_buyer = self.User.objects.create_user(
            email="select-other-buyer@example.test",
            full_name="Other Selection Buyer",
        )
        UserRole.objects.create(user=other_buyer, role=self.buyer_role)
        UserOutletAccess.objects.create(
            user=other_buyer,
            outlet=self.outlet,
        )

        self.authenticate(other_buyer)
        response = self.client.post(
            f"{self.list_url}{demand.pk}/select-supplier",
            {"selected_supplier_id": self.supplier.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(DemandSupplierSelection.objects.count(), 0)

    def test_manager_cannot_select_supplier(self):
        demand, _, _ = self.make_selection_attempt(
            SupplierConfirmation.ConfirmationStatus.PENDING,
            SupplierRequest.RequestStatus.EXPIRED,
        )
        self.create_selection_offer(self.supplier)

        manager = self.User.objects.create_user(
            email="select-manager@example.test",
            full_name="Selection Manager",
        )
        manager_role = Role.objects.create(
            code=RoleCode.MANAGER,
            name="Manager",
        )
        UserRole.objects.create(user=manager, role=manager_role)

        self.authenticate(manager)
        response = self.client.post(
            f"{self.list_url}{demand.pk}/select-supplier",
            {"selected_supplier_id": self.supplier.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(DemandSupplierSelection.objects.count(), 0)

    def test_select_supplier_does_not_issue_request_when_offer_is_missing(self):
        demand, _, _ = self.make_selection_attempt(
            SupplierConfirmation.ConfirmationStatus.PENDING,
            SupplierRequest.RequestStatus.EXPIRED,
        )
        alternative = Supplier.objects.create(
            supplier_code="SUP-API-SELECT-MISSING",
            supplier_name="Missing Offer Supplier",
        )
        self.authenticate()

        response = self.client.post(
            f"{self.list_url}{demand.pk}/select-supplier",
            {"selected_supplier_id": alternative.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            http_status.HTTP_400_BAD_REQUEST,
            response.data,
        )
        demand.refresh_from_db()
        self.assertEqual(demand.supplier_id, self.supplier.pk)
        self.assertEqual(demand.status, DemandStatus.SUBMITTED)
        self.assertEqual(SupplierRequest.objects.filter(demand=demand).count(), 1)
        self.assertEqual(DemandSupplierSelection.objects.filter(demand=demand).count(), 0)


class SupplierRequestLifecycleTests(DemandServiceTestBase):
    """Regression tests for SupplierRequest attempts and response consistency."""

    def setUp(self):
        super().setUp()
        self.demand = self.create_demand()

    def make_confirmation(self, status=None, **overrides):
        values = {
            "demand": self.demand,
            "supplier": self.supplier,
            "confirmation_status": (
                status or SupplierConfirmation.ConfirmationStatus.PENDING
            ),
            "source_mode": SupplierConfirmation.SourceMode.LIVE_API,
        }
        values.update(overrides)

        confirmation = SupplierConfirmation(**values)
        confirmation.full_clean()
        confirmation.save()
        return confirmation

    def make_request(
        self,
        confirmation,
        attempt_no=1,
        status=None,
        responded_at=None,
    ):
        request_status = status or SupplierRequest.RequestStatus.WAITING

        request = SupplierRequest(
            demand=self.demand,
            supplier=self.supplier,
            supplier_confirmation=confirmation,
            request_code=(
                f"SR-TEST-{self.demand.pk}-{attempt_no}-{request_status}"
            ),
            attempt_no=attempt_no,
            request_status=request_status,
            created_by=self.user,
            responded_at=responded_at,
        )
        request.full_clean()
        request.save()
        return request

    def test_waiting_request_requires_pending_confirmation(self):
        confirmation = self.make_confirmation()

        request = self.make_request(
            confirmation,
            status=SupplierRequest.RequestStatus.WAITING,
        )

        self.assertEqual(
            request.supplier_confirmation.confirmation_status,
            SupplierConfirmation.ConfirmationStatus.PENDING,
        )
        self.assertIsNone(request.responded_at)

    def test_expired_request_can_retain_pending_confirmation_without_response(self):
        confirmation = self.make_confirmation()

        request = self.make_request(
            confirmation,
            status=SupplierRequest.RequestStatus.EXPIRED,
        )

        self.assertEqual(
            request.request_status,
            SupplierRequest.RequestStatus.EXPIRED,
        )
        self.assertEqual(
            request.supplier_confirmation.confirmation_status,
            SupplierConfirmation.ConfirmationStatus.PENDING,
        )
        self.assertIsNone(request.responded_at)

    def test_expired_request_rejects_completed_confirmation(self):
        confirmation = self.make_confirmation(
            status=SupplierConfirmation.ConfirmationStatus.CONFIRMED,
            ready_date=self.demand.requested_date,
            recorded_at=django_timezone.now(),
        )

        request = SupplierRequest(
            demand=self.demand,
            supplier=self.supplier,
            supplier_confirmation=confirmation,
            request_code=f"SR-TEST-{self.demand.pk}-1-INVALID-EXPIRED",
            attempt_no=1,
            request_status=SupplierRequest.RequestStatus.EXPIRED,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            request.full_clean()

    def test_responded_request_rejects_pending_confirmation(self):
        confirmation = self.make_confirmation()

        request = SupplierRequest(
            demand=self.demand,
            supplier=self.supplier,
            supplier_confirmation=confirmation,
            request_code=f"SR-TEST-{self.demand.pk}-1-INVALID-RESPONDED",
            attempt_no=1,
            request_status=SupplierRequest.RequestStatus.RESPONDED,
            created_by=self.user,
            responded_at=django_timezone.now(),
        )

        with self.assertRaises(ValidationError):
            request.full_clean()

    def test_responded_request_accepts_completed_confirmation(self):
        confirmation = self.make_confirmation(
            status=SupplierConfirmation.ConfirmationStatus.CONFIRMED,
            ready_date=self.demand.requested_date,
            recorded_at=django_timezone.now(),
        )

        request = self.make_request(
            confirmation,
            status=SupplierRequest.RequestStatus.RESPONDED,
            responded_at=django_timezone.now(),
        )

        self.assertEqual(
            request.supplier_confirmation.confirmation_status,
            SupplierConfirmation.ConfirmationStatus.CONFIRMED,
        )
        self.assertIsNotNone(request.responded_at)

    def test_database_rejects_second_waiting_request_for_same_demand(self):
        first_confirmation = self.make_confirmation()
        self.make_request(first_confirmation, attempt_no=1)

        second_confirmation = self.make_confirmation()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SupplierRequest.objects.create(
                    demand=self.demand,
                    supplier=self.supplier,
                    supplier_confirmation=second_confirmation,
                    request_code=(
                        f"SR-TEST-{self.demand.pk}-2-DUPLICATE-WAITING"
                    ),
                    attempt_no=2,
                    request_status=SupplierRequest.RequestStatus.WAITING,
                    created_by=self.user,
                )

    def test_new_attempt_is_allowed_after_previous_attempt_expires(self):
        first_confirmation = self.make_confirmation()
        first_request = self.make_request(
            first_confirmation,
            attempt_no=1,
            status=SupplierRequest.RequestStatus.EXPIRED,
        )

        second_confirmation = self.make_confirmation()
        second_request = self.make_request(
            second_confirmation,
            attempt_no=2,
            status=SupplierRequest.RequestStatus.WAITING,
        )

        self.assertEqual(
            SupplierRequest.objects.filter(demand=self.demand).count(),
            2,
        )
        self.assertEqual(
            first_request.request_status,
            SupplierRequest.RequestStatus.EXPIRED,
        )
        self.assertEqual(
            second_request.request_status,
            SupplierRequest.RequestStatus.WAITING,
        )
        self.assertEqual(
            list(
                SupplierRequest.objects.filter(demand=self.demand)
                .order_by("attempt_no")
                .values_list("attempt_no", flat=True)
            ),
            [1, 2],
        )

    def test_database_rejects_expired_request_with_response_timestamp(self):
        confirmation = self.make_confirmation()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SupplierRequest.objects.create(
                    demand=self.demand,
                    supplier=self.supplier,
                    supplier_confirmation=confirmation,
                    request_code=(
                        f"SR-TEST-{self.demand.pk}-1-INVALID-TIMESTAMP"
                    ),
                    attempt_no=1,
                    request_status=SupplierRequest.RequestStatus.EXPIRED,
                    created_by=self.user,
                    responded_at=django_timezone.now(),
                )


class DemandSubmissionServiceTests(DemandServiceTestBase):
    """Atomic Submit service regression tests."""

    def make_existing_request(self, *, attempt_no=1, request_status=None):
        confirmation = SupplierConfirmation(
            demand=self.demand,
            supplier=self.supplier,
            confirmation_status=SupplierConfirmation.ConfirmationStatus.PENDING,
            source_mode=SupplierConfirmation.SourceMode.LIVE_API,
        )
        confirmation.full_clean()
        confirmation.save()

        request = SupplierRequest(
            demand=self.demand,
            supplier=self.supplier,
            supplier_confirmation=confirmation,
            request_code=f"SR-SUBMIT-TEST-{self.demand.pk}-{attempt_no}",
            attempt_no=attempt_no,
            request_status=(
                request_status or SupplierRequest.RequestStatus.WAITING
            ),
            created_by=self.user,
        )
        request.full_clean()
        request.save()
        return request

    def setUp(self):
        super().setUp()
        self.demand = self.create_demand()

    def test_submit_creates_request_confirmation_and_promise_snapshots(self):
        self.create_offer(capacity="100.000")

        request = submit_demand(
            demand_id=self.demand.pk,
            submitted_by=self.user,
        )

        self.demand.refresh_from_db()
        request.refresh_from_db()

        self.assertEqual(self.demand.status, DemandStatus.SUBMITTED)
        self.assertEqual(request.demand_id, self.demand.pk)
        self.assertEqual(request.supplier_id, self.supplier.pk)
        self.assertEqual(request.created_by_id, self.user.pk)
        self.assertEqual(request.attempt_no, 1)
        self.assertEqual(
            request.request_status,
            SupplierRequest.RequestStatus.WAITING,
        )
        self.assertEqual(
            request.supplier_confirmation.confirmation_status,
            SupplierConfirmation.ConfirmationStatus.PENDING,
        )
        self.assertEqual(
            request.supplier_confirmation.source_mode,
            SupplierConfirmation.SourceMode.LIVE_API,
        )

        promises = list(
            SupplierItemPromise.objects.filter(
                supplier_request=request
            ).select_related("demand_item", "supplier_item")
        )
        self.assertEqual(len(promises), 1)
        self.assertEqual(
            promises[0].promised_weight_kg,
            self.demand.items.get().required_weight_kg,
        )
        self.assertEqual(
            promises[0].confirmed_weight_kg,
            Decimal("0.000"),
        )
        self.assertEqual(
            promises[0].line_status,
            SupplierItemPromise.LineStatus.PENDING,
        )
        self.assertEqual(
            promises[0].supplier_item.supplier_id,
            self.supplier.pk,
        )

    def test_submit_supports_multiple_items_with_one_selected_supplier(self):
        item2 = self.create_item("ITM-SUBMIT-002")
        self.demand.items.create(
            item=item2,
            required_weight_kg=Decimal("25.000"),
            unit_of_measure="KG",
        )
        self.demand.quantity_kg = Decimal("35.000")
        self.demand.save(update_fields=["quantity_kg"])

        self.create_offer(self.item, capacity="100.000")
        self.create_offer(item2, capacity="100.000")

        request = submit_demand(
            demand_id=self.demand.pk,
            submitted_by=self.user,
        )

        promises = list(
            SupplierItemPromise.objects.filter(
                supplier_request=request
            ).select_related("supplier_item", "demand_item")
        )

        self.assertEqual(len(promises), 2)
        self.assertEqual(
            {row.demand_item.item_id for row in promises},
            {self.item.pk, item2.pk},
        )
        self.assertEqual(
            {row.supplier_item.supplier_id for row in promises},
            {self.supplier.pk},
        )
    def test_submit_rejects_missing_offer_without_partial_writes(self):
        item2 = self.create_item("ITM-SUBMIT-MISSING-002")
        self.demand.items.create(
            item=item2,
            required_weight_kg=Decimal("20.000"),
            unit_of_measure="KG",
        )

        self.create_offer(self.item, capacity="100.000")

        with self.assertRaises(ValidationError):
            submit_demand(
                demand_id=self.demand.pk,
                submitted_by=self.user,
            )

        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, DemandStatus.DRAFT)
        self.assertEqual(
            SupplierConfirmation.objects.filter(demand=self.demand).count(),
            0,
        )
        self.assertEqual(
            SupplierRequest.objects.filter(demand=self.demand).count(),
            0,
        )
        self.assertEqual(SupplierItemPromise.objects.count(), 0)
        self.assertEqual(DemandSourcingOption.objects.count(), 0)

    def test_submit_rejects_unknown_capacity(self):
        self.create_offer(capacity=None)

        with self.assertRaises(ValidationError):
            submit_demand(
                demand_id=self.demand.pk,
                submitted_by=self.user,
            )

        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, DemandStatus.DRAFT)
        self.assertEqual(SupplierRequest.objects.count(), 0)

    def test_submit_rejects_insufficient_capacity(self):
        self.create_offer(capacity="9.000")

        with self.assertRaises(ValidationError):
            submit_demand(
                demand_id=self.demand.pk,
                submitted_by=self.user,
            )

        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, DemandStatus.DRAFT)
        self.assertEqual(SupplierRequest.objects.count(), 0)

    def test_submit_blocks_when_previous_request_is_waiting(self):
        self.create_offer(capacity="100.000")
        self.make_existing_request()

        with self.assertRaises(ValidationError):
            submit_demand(
                demand_id=self.demand.pk,
                submitted_by=self.user,
            )

        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, DemandStatus.DRAFT)
        self.assertEqual(
            SupplierRequest.objects.filter(demand=self.demand).count(),
            1,
        )
        self.assertEqual(SupplierItemPromise.objects.count(), 0)

    def test_submit_creates_next_attempt_after_previous_expired(self):
        self.create_offer(capacity="100.000")

        # A real expired attempt belongs to a previously submitted Demand.
        self.demand.status = DemandStatus.SUBMITTED
        self.demand.save(update_fields=["status"])

        previous = self.make_existing_request(
            attempt_no=1,
            request_status=SupplierRequest.RequestStatus.EXPIRED,
        )

        # EXPIRED permits an explicit retry selection of the same Supplier.
        selection = select_supplier_for_submitted_demand(
            demand_id=self.demand.pk,
            selected_by=self.user,
            selected_supplier_id=self.supplier.pk,
        )

        self.assertEqual(selection.previous_request_id, previous.pk)
        self.assertEqual(selection.previous_supplier_id, self.supplier.pk)
        self.assertEqual(selection.selected_supplier_id, self.supplier.pk)
        self.assertEqual(
            selection.selection_reason,
            "RETRY_AFTER_EXPIRED",
        )

        new_request = submit_demand(
            demand_id=self.demand.pk,
            submitted_by=self.user,
        )

        previous.refresh_from_db()
        self.demand.refresh_from_db()

        self.assertEqual(
            previous.request_status,
            SupplierRequest.RequestStatus.EXPIRED,
        )
        self.assertEqual(new_request.attempt_no, 2)
        self.assertEqual(self.demand.status, DemandStatus.SUBMITTED)
        self.assertEqual(
            SupplierRequest.objects.filter(demand=self.demand).count(),
            2,
        )

    def test_submit_rejects_non_creator(self):
        self.create_offer(capacity="100.000")
        other_user = self.User.objects.create_user(
            email="submit-other-user@example.test",
            full_name="Other Submit User",
        )

        with self.assertRaises(ValidationError):
            submit_demand(
                demand_id=self.demand.pk,
                submitted_by=other_user,
            )

        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, DemandStatus.DRAFT)
        self.assertEqual(SupplierRequest.objects.count(), 0)

    def test_submit_rejects_non_draft_demand(self):
        self.create_offer(capacity="100.000")
        self.demand.status = DemandStatus.SUBMITTED
        self.demand.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            submit_demand(
                demand_id=self.demand.pk,
                submitted_by=self.user,
            )

        self.assertEqual(SupplierRequest.objects.count(), 0)

    def test_submit_rolls_back_confirmation_and_request_if_promise_save_fails(self):
        self.create_offer(capacity="100.000")

        with patch(
            "demands.services.SupplierItemPromise.save",
            side_effect=ValidationError("Simulated promise persistence failure."),
        ):
            with self.assertRaises(ValidationError):
                submit_demand(
                    demand_id=self.demand.pk,
                    submitted_by=self.user,
                )

        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, DemandStatus.DRAFT)
        self.assertEqual(
            SupplierConfirmation.objects.filter(demand=self.demand).count(),
            0,
        )
        self.assertEqual(
            SupplierRequest.objects.filter(demand=self.demand).count(),
            0,
        )
        self.assertEqual(SupplierItemPromise.objects.count(), 0)
        self.assertEqual(DemandSourcingOption.objects.count(), 0)


class DemandSupplierSelectionServiceTests(DemandServiceTestBase):
    """Explicit supplier replacement and commitment-release tests."""

    def setUp(self):
        super().setUp()
        self.demand = self.create_demand()
        self.demand.status = DemandStatus.SUBMITTED
        self.demand.save(update_fields=["status"])

    def make_other_supplier(self):
        return Supplier.objects.create(
            supplier_code="SUP-SELECT-002",
            supplier_name="Alternative Selection Supplier",
        )

    def make_closed_attempt(
        self,
        confirmation_status,
        confirmed_weight="0.000",
    ):
        line = self.demand.items.order_by("pk").first()
        if line is None:
            raise AssertionError("Test fixture requires at least one DemandItem.")

        offer = self.create_offer(
            item=line.item,
            capacity="100.000",
        )
        now = django_timezone.now()

        confirmation_values = {
            "demand": self.demand,
            "supplier": self.supplier,
            "confirmation_status": confirmation_status,
            "source_mode": SupplierConfirmation.SourceMode.LIVE_API,
            "recorded_at": now,
        }
        if confirmation_status in {
            SupplierConfirmation.ConfirmationStatus.CONFIRMED,
            SupplierConfirmation.ConfirmationStatus.PARTIAL,
        }:
            confirmation_values["ready_date"] = self.demand.requested_date

        confirmation = SupplierConfirmation(**confirmation_values)
        confirmation.full_clean()
        confirmation.save()

        request = SupplierRequest(
            demand=self.demand,
            supplier=self.supplier,
            supplier_confirmation=confirmation,
            request_code=f"SR-SELECT-{self.demand.pk}-{confirmation_status}",
            attempt_no=1,
            request_status=SupplierRequest.RequestStatus.RESPONDED,
            created_by=self.user,
            responded_at=now,
        )
        request.full_clean()
        request.save()

        confirmed = Decimal(confirmed_weight)
        promised = line.required_weight_kg

        if confirmation_status == SupplierConfirmation.ConfirmationStatus.DECLINED:
            line_status = SupplierItemPromise.LineStatus.DECLINED
        elif confirmed == promised:
            line_status = SupplierItemPromise.LineStatus.CONFIRMED
        elif confirmed > 0:
            line_status = SupplierItemPromise.LineStatus.PARTIAL
        else:
            line_status = SupplierItemPromise.LineStatus.PENDING

        promise = SupplierItemPromise(
            supplier_request=request,
            demand_item=line,
            supplier_item=offer,
            promised_weight_kg=promised,
            confirmed_weight_kg=confirmed,
            line_status=line_status,
            unit_price_vnd_per_kg_snapshot=offer.unit_price_vnd_per_kg,
            lead_time_hours_snapshot=offer.lead_time_hours,
        )
        promise.full_clean()
        promise.save()

        return request, confirmation

    def test_declined_requires_a_different_supplier(self):
        self.make_closed_attempt(
            SupplierConfirmation.ConfirmationStatus.DECLINED,
        )

        with self.assertRaises(ValidationError):
            select_supplier_for_submitted_demand(
                demand_id=self.demand.pk,
                selected_by=self.user,
                selected_supplier_id=self.supplier.pk,
            )

        self.demand.refresh_from_db()
        self.assertEqual(self.demand.supplier_id, self.supplier.pk)
        self.assertEqual(
            DemandSupplierSelection.objects.filter(demand=self.demand).count(),
            0,
        )

    def test_declined_allows_explicit_selection_of_alternative_supplier(self):
        previous, _ = self.make_closed_attempt(
            SupplierConfirmation.ConfirmationStatus.DECLINED,
        )
        alternative = self.make_other_supplier()
        self.create_offer(supplier=alternative, capacity="100.000")

        selection = select_supplier_for_submitted_demand(
            demand_id=self.demand.pk,
            selected_by=self.user,
            selected_supplier_id=alternative.pk,
        )

        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, DemandStatus.SUBMITTED)
        self.assertEqual(self.demand.supplier_id, alternative.pk)
        self.assertEqual(selection.previous_request_id, previous.pk)
        self.assertEqual(selection.previous_supplier_id, self.supplier.pk)
        self.assertEqual(selection.selected_supplier_id, alternative.pk)
        self.assertEqual(
            selection.selection_reason,
            DemandSupplierSelection.SelectionReason.REPLACE_AFTER_DECLINED,
        )
        self.assertEqual(SupplierRequest.objects.filter(demand=self.demand).count(), 1)

    def test_partial_positive_commitment_blocks_replacement_until_released(self):
        self.make_closed_attempt(
            SupplierConfirmation.ConfirmationStatus.PARTIAL,
            confirmed_weight="6.000",
        )
        alternative = self.make_other_supplier()
        self.create_offer(supplier=alternative, capacity="100.000")

        with self.assertRaises(ValidationError):
            select_supplier_for_submitted_demand(
                demand_id=self.demand.pk,
                selected_by=self.user,
                selected_supplier_id=alternative.pk,
            )

        self.demand.refresh_from_db()
        self.assertEqual(self.demand.supplier_id, self.supplier.pk)
        self.assertEqual(
            DemandSupplierSelection.objects.filter(demand=self.demand).count(),
            0,
        )

    def test_partial_allows_replacement_after_explicit_release(self):
        previous, confirmation = self.make_closed_attempt(
            SupplierConfirmation.ConfirmationStatus.PARTIAL,
            confirmed_weight="6.000",
        )
        alternative = self.make_other_supplier()
        self.create_offer(supplier=alternative, capacity="100.000")

        confirmation.commitment_released_at = django_timezone.now()
        confirmation.commitment_release_note = "Supplier confirmed release."
        confirmation.commitment_released_by = self.user
        confirmation.full_clean()
        confirmation.save(
            update_fields=[
                "commitment_released_at",
                "commitment_release_note",
                "commitment_released_by",
                "updated_at",
            ]
        )

        selection = select_supplier_for_submitted_demand(
            demand_id=self.demand.pk,
            selected_by=self.user,
            selected_supplier_id=alternative.pk,
        )

        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, DemandStatus.SUBMITTED)
        self.assertEqual(self.demand.supplier_id, alternative.pk)
        self.assertEqual(selection.previous_request_id, previous.pk)
        self.assertEqual(
            selection.selection_reason,
            DemandSupplierSelection.SelectionReason.REPLACE_AFTER_PARTIAL,
        )

    def test_partial_release_requires_a_note(self):
        _, confirmation = self.make_closed_attempt(
            SupplierConfirmation.ConfirmationStatus.PARTIAL,
            confirmed_weight="6.000",
        )

        confirmation.commitment_released_at = django_timezone.now()
        confirmation.commitment_released_by = self.user
        confirmation.commitment_release_note = ""

        with self.assertRaises(ValidationError):
            confirmation.full_clean()

    def test_alternative_supplier_must_offer_every_demand_item(self):
        item2 = self.create_item("ITM-SELECT-002")
        self.demand.items.create(
            item=item2,
            required_weight_kg=Decimal("20.000"),
            unit_of_measure="KG",
        )
        self.demand.quantity_kg = Decimal("30.000")
        self.demand.save(update_fields=["quantity_kg"])

        self.make_closed_attempt(
            SupplierConfirmation.ConfirmationStatus.DECLINED,
        )
        alternative = self.make_other_supplier()
        self.create_offer(supplier=alternative, item=self.item)

        with self.assertRaises(ValidationError):
            select_supplier_for_submitted_demand(
                demand_id=self.demand.pk,
                selected_by=self.user,
                selected_supplier_id=alternative.pk,
            )

        self.demand.refresh_from_db()
        self.assertEqual(self.demand.supplier_id, self.supplier.pk)
        self.assertEqual(
            DemandSupplierSelection.objects.filter(demand=self.demand).count(),
            0,
        )

    def test_submit_after_declined_requires_explicit_selection(self):
        # make_closed_attempt() already creates the selected Supplier's offer.
        self.make_closed_attempt(
            SupplierConfirmation.ConfirmationStatus.DECLINED,
        )

        with self.assertRaises(ValidationError):
            submit_demand(
                demand_id=self.demand.pk,
                submitted_by=self.user,
            )

        self.assertEqual(
            SupplierRequest.objects.filter(demand=self.demand).count(),
            1,
        )

    def test_declined_replacement_then_submit_creates_new_attempt(self):
        previous, _ = self.make_closed_attempt(
            SupplierConfirmation.ConfirmationStatus.DECLINED,
        )
        alternative = self.make_other_supplier()
        self.create_offer(supplier=alternative, capacity="100.000")

        select_supplier_for_submitted_demand(
            demand_id=self.demand.pk,
            selected_by=self.user,
            selected_supplier_id=alternative.pk,
        )

        new_request = submit_demand(
            demand_id=self.demand.pk,
            submitted_by=self.user,
        )

        self.demand.refresh_from_db()
        previous.refresh_from_db()
        self.assertEqual(self.demand.status, DemandStatus.SUBMITTED)
        self.assertEqual(self.demand.supplier_id, alternative.pk)
        self.assertEqual(
            previous.request_status,
            SupplierRequest.RequestStatus.RESPONDED,
        )
        self.assertEqual(new_request.attempt_no, 2)
        self.assertEqual(new_request.supplier_id, alternative.pk)
        self.assertEqual(
            SupplierRequest.objects.filter(demand=self.demand).count(),
            2,
        )
