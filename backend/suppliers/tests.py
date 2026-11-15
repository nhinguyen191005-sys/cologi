from decimal import Decimal

from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import (
    AuditLog,
    ExternalUserAccess,
    Role,
    RoleCode,
    UserRole,
)
from demands.models import (
    DeliveryDemand,
    DemandStatus,
    SupplierConfirmation,
    SupplierItemPromise,
    SupplierRequest,
)
from demands.services import submit_demand
from demands.tests import DemandServiceTestBase
from masterdata.models import Item, Supplier, SupplierItem


class SupplierRequestAPITests(DemandServiceTestBase):
    """CP6 supplier inbox, access scope, and item-level response tests."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        self.supplier_user = self.User.objects.create_user(
            email="cp6-supplier@example.test",
            full_name="CP6 Supplier User",
        )
        role = Role.objects.create(
            code=RoleCode.SUPPLIER,
            name="Supplier",
        )
        UserRole.objects.create(user=self.supplier_user, role=role)
        ExternalUserAccess.objects.create(
            user=self.supplier_user,
            actor_type="SUPPLIER",
            supplier=self.supplier,
        )

        self.demand = self.create_demand(demand_code="DD-CP6-API-001")
        self.create_offer(capacity="100.000")
        self.supplier_request = submit_demand(
            demand_id=self.demand.pk,
            submitted_by=self.user,
        )
        self.promise = self.supplier_request.item_promises.get()
        self.client.force_authenticate(user=self.supplier_user)

    def response_payload(self, quantity="10.000", reason=""):
        item = {
            "promise_id": self.promise.pk,
            "confirmed_weight_kg": quantity,
        }
        if reason:
            item["decline_reason"] = reason

        return {
            "items": [item],
            "ready_date": "2026-11-16",
            "ready_start_time": "08:00:00",
            "ready_end_time": "10:00:00",
            "pickup_address": "Supplier warehouse, Da Nang",
            "confirmation_note": "CP6 API test response",
        }

    def create_foreign_request(self):
        other_supplier = Supplier.objects.create(
            supplier_code="SUP-CP6-OTHER",
            supplier_name="Other CP6 Supplier",
        )
        foreign_demand = self.create_demand(
            demand_code="DD-CP6-API-FOREIGN",
            supplier_id=other_supplier.pk,
        )
        SupplierItem.objects.create(
            supplier=other_supplier,
            item=self.item,
            unit_price_vnd_per_kg=Decimal("25000.00"),
            max_daily_supply_kg=Decimal("100.000"),
            lead_time_hours=8,
            minimum_order_kg=Decimal("0.000"),
            offer_status=SupplierItem.OfferStatus.ACTIVE,
        )
        return submit_demand(
            demand_id=foreign_demand.pk,
            submitted_by=self.user,
        )

    def test_inbox_lists_only_requests_of_authenticated_supplier(self):
        foreign_request = self.create_foreign_request()

        response = self.client.get("/api/suppliers/me/requests")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.supplier_request.pk)
        self.assertNotEqual(response.data[0]["id"], foreign_request.pk)
        self.assertEqual(
            response.data[0]["confirmation_status"],
            SupplierConfirmation.ConfirmationStatus.PENDING,
        )
        self.assertEqual(response.data[0]["items"][0]["id"], self.promise.pk)

    def test_catalog_lists_only_items_of_authenticated_supplier(self):
        self.create_foreign_request()

        response = self.client.get("/api/suppliers/me/items")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["supplier_id"], self.supplier.pk)
        self.assertEqual(response.data[0]["item_code"], self.item.item_code)
        for field in (
            "unit_price_vnd_per_kg",
            "max_daily_supply_kg",
            "lead_time_hours",
            "minimum_order_kg",
            "offer_status",
        ):
            self.assertIn(field, response.data[0])

    def test_supplier_cannot_respond_to_another_supplier_request(self):
        foreign_request = self.create_foreign_request()

        response = self.client.post(
            f"/api/supply-requests/{foreign_request.pk}/confirm",
            data=self.response_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        foreign_request.refresh_from_db()
        self.assertEqual(
            foreign_request.request_status,
            SupplierRequest.RequestStatus.WAITING,
        )

    def test_supplier_can_confirm_all_items_and_audit_response(self):
        response = self.client.post(
            f"/api/supply-requests/{self.supplier_request.pk}/confirm",
            data=self.response_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            response.data["confirmation_status"],
            SupplierConfirmation.ConfirmationStatus.CONFIRMED,
        )
        self.assertEqual(Decimal(response.data["missing_qty"]), Decimal("0"))

        self.supplier_request.refresh_from_db()
        self.promise.refresh_from_db()
        confirmation = self.supplier_request.supplier_confirmation
        confirmation.refresh_from_db()

        self.assertEqual(
            self.supplier_request.request_status,
            SupplierRequest.RequestStatus.RESPONDED,
        )
        self.assertEqual(
            self.promise.line_status,
            SupplierItemPromise.LineStatus.CONFIRMED,
        )
        self.assertEqual(self.promise.confirmed_weight_kg, Decimal("10.000"))
        self.assertEqual(confirmation.ready_start_time.isoformat(), "08:00:00")
        self.assertEqual(
            confirmation.pickup_address,
            "Supplier warehouse, Da Nang",
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action="SUPPLIER_REQUEST_RESPONDED",
                entity_type="SUPPLIER_REQUEST",
                entity_id=str(self.supplier_request.pk),
                actor_user=self.supplier_user,
            ).exists()
        )

    def test_partial_confirmation_reports_missing_quantity(self):
        response = self.client.post(
            f"/api/supply-requests/{self.supplier_request.pk}/confirm",
            data=self.response_payload(quantity="6.000"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            response.data["confirmation_status"],
            SupplierConfirmation.ConfirmationStatus.PARTIAL,
        )
        self.assertEqual(Decimal(response.data["missing_qty"]), Decimal("4.000"))

        self.promise.refresh_from_db()
        self.assertEqual(
            self.promise.line_status,
            SupplierItemPromise.LineStatus.PARTIAL,
        )
        self.assertEqual(self.promise.confirmed_weight_kg, Decimal("6.000"))

    def test_decline_requires_reason_and_records_declined_status(self):
        response = self.client.post(
            f"/api/supply-requests/{self.supplier_request.pk}/confirm",
            data=self.response_payload(
                quantity="0.000",
                reason="Temporarily unavailable.",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            response.data["confirmation_status"],
            SupplierConfirmation.ConfirmationStatus.DECLINED,
        )
        self.assertEqual(Decimal(response.data["missing_qty"]), Decimal("10.000"))

        self.promise.refresh_from_db()
        self.assertEqual(
            self.promise.line_status,
            SupplierItemPromise.LineStatus.DECLINED,
        )
        self.assertEqual(
            self.promise.decline_reason,
            "Temporarily unavailable.",
        )

    def test_over_confirmation_is_rejected_without_database_writes(self):
        response = self.client.post(
            f"/api/supply-requests/{self.supplier_request.pk}/confirm",
            data=self.response_payload(quantity="10.001"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.promise.refresh_from_db()
        self.supplier_request.refresh_from_db()
        self.assertEqual(self.promise.confirmed_weight_kg, Decimal("0.000"))
        self.assertEqual(
            self.promise.line_status,
            SupplierItemPromise.LineStatus.PENDING,
        )
        self.assertEqual(
            self.supplier_request.request_status,
            SupplierRequest.RequestStatus.WAITING,
        )
        self.assertFalse(
            AuditLog.objects.filter(
                action="SUPPLIER_REQUEST_RESPONDED",
                entity_id=str(self.supplier_request.pk),
            ).exists()
        )

    def test_every_promise_must_be_submitted_exactly_once(self):
        payload = self.response_payload()
        payload["items"] = []

        response = self.client.post(
            f"/api/supply-requests/{self.supplier_request.pk}/confirm",
            data=payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.supplier_request.refresh_from_db()
        self.assertEqual(
            self.supplier_request.request_status,
            SupplierRequest.RequestStatus.WAITING,
        )

    def test_positive_confirmation_requires_ready_window_and_pickup_location(self):
        payload = self.response_payload()
        payload.pop("ready_start_time")
        payload.pop("ready_end_time")
        payload.pop("pickup_address")

        response = self.client.post(
            f"/api/supply-requests/{self.supplier_request.pk}/confirm",
            data=payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.promise.refresh_from_db()
        self.supplier_request.refresh_from_db()
        self.assertEqual(self.promise.confirmed_weight_kg, Decimal("0.000"))
        self.assertEqual(
            self.supplier_request.request_status,
            SupplierRequest.RequestStatus.WAITING,
        )

    def test_supplier_response_rejected_when_demand_is_not_submitted(self):
        invalid_statuses = (
            DemandStatus.DRAFT,
            DemandStatus.PLANNING,
            DemandStatus.PLANNED,
            DemandStatus.CANCELLED,
        )

        for demand_status in invalid_statuses:
            with self.subTest(demand_status=demand_status):
                DeliveryDemand.objects.filter(pk=self.demand.pk).update(
                    status=demand_status
                )

                response = self.client.post(
                    f"/api/supply-requests/{self.supplier_request.pk}/confirm",
                    data=self.response_payload(),
                    format="json",
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_409_CONFLICT,
                    response.data,
                )

                self.supplier_request.refresh_from_db()
                self.promise.refresh_from_db()
                confirmation = self.supplier_request.supplier_confirmation
                confirmation.refresh_from_db()

                self.assertEqual(
                    self.supplier_request.request_status,
                    SupplierRequest.RequestStatus.WAITING,
                )
                self.assertEqual(
                    confirmation.confirmation_status,
                    SupplierConfirmation.ConfirmationStatus.PENDING,
                )
                self.assertEqual(
                    self.promise.line_status,
                    SupplierItemPromise.LineStatus.PENDING,
                )
                self.assertEqual(
                    self.promise.confirmed_weight_kg,
                    Decimal("0.000"),
                )
                self.assertFalse(
                    AuditLog.objects.filter(
                        action="SUPPLIER_REQUEST_RESPONDED",
                        entity_id=str(self.supplier_request.pk),
                    ).exists()
                )

    def test_supplier_response_rejected_when_confirmation_is_not_pending(self):
        SupplierConfirmation.objects.filter(
            pk=self.supplier_request.supplier_confirmation_id
        ).update(
            confirmation_status=SupplierConfirmation.ConfirmationStatus.CONFIRMED
        )

        response = self.client.post(
            f"/api/supply-requests/{self.supplier_request.pk}/confirm",
            data=self.response_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
            response.data,
        )

        self.supplier_request.refresh_from_db()
        self.promise.refresh_from_db()
        self.assertEqual(
            self.supplier_request.request_status,
            SupplierRequest.RequestStatus.WAITING,
        )
        self.assertEqual(
            self.promise.line_status,
            SupplierItemPromise.LineStatus.PENDING,
        )
        self.assertEqual(self.promise.confirmed_weight_kg, Decimal("0.000"))
        self.assertFalse(
            AuditLog.objects.filter(
                action="SUPPLIER_REQUEST_RESPONDED",
                entity_id=str(self.supplier_request.pk),
            ).exists()
        )

    def test_supplier_cannot_respond_to_same_request_twice(self):
        first = self.client.post(
            f"/api/supply-requests/{self.supplier_request.pk}/confirm",
            data=self.response_payload(),
            format="json",
        )
        second = self.client.post(
            f"/api/supply-requests/{self.supplier_request.pk}/confirm",
            data=self.response_payload(),
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            AuditLog.objects.filter(
                action="SUPPLIER_REQUEST_RESPONDED",
                entity_id=str(self.supplier_request.pk),
            ).count(),
            1,
        )


class SupplierCatalogCRUDAPITests(DemandServiceTestBase):
    """CRUD and ownership tests for supplier catalogue offers."""

    def setUp(self):
        super().setUp()
        from accounts.models import (
            ExternalUserAccess,
            Role,
            RoleCode,
            UserRole,
        )

        self.client = APIClient()
        self.supplier_user = self.User.objects.create_user(
            email="catalog-crud@example.test",
            full_name="Catalog CRUD Supplier",
        )
        role = Role.objects.create(
            code=RoleCode.SUPPLIER,
            name="Supplier",
        )
        UserRole.objects.create(user=self.supplier_user, role=role)
        ExternalUserAccess.objects.create(
            user=self.supplier_user,
            actor_type="SUPPLIER",
            supplier=self.supplier,
        )
        self.offer = self.create_offer()
        self.client.force_authenticate(user=self.supplier_user)

    def offer_payload(self, **overrides):
        payload = {
            "unit_price_vnd_per_kg": "26000.00",
            "max_daily_supply_kg": "500.000",
            "lead_time_hours": 12,
            "minimum_order_kg": "5.000",
        }
        payload.update(overrides)
        return payload

    def test_available_items_and_categories_list_active_records(self):
        response_items = self.client.get(
            "/api/suppliers/me/available-items"
        )
        response_categories = self.client.get(
            "/api/suppliers/me/cargo-categories"
        )

        self.assertEqual(response_items.status_code, status.HTTP_200_OK)
        self.assertEqual(response_categories.status_code, status.HTTP_200_OK)
        self.assertIn(self.item.pk, [row["id"] for row in response_items.data])
        self.assertIn(
            self.category.pk,
            [row["id"] for row in response_categories.data],
        )

    def test_supplier_can_register_existing_shared_item(self):
        item = self.create_item("ITM-CRUD-EXISTING")

        response = self.client.post(
            "/api/suppliers/me/items",
            data=self.offer_payload(item_id=item.pk),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["item_id"], item.pk)
        self.assertEqual(response.data["supplier_id"], self.supplier.pk)
        self.assertTrue(
            SupplierItem.objects.filter(
                supplier=self.supplier,
                item=item,
            ).exists()
        )

    def test_supplier_can_create_shared_item_and_own_offer(self):
        response = self.client.post(
            "/api/suppliers/me/items",
            data=self.offer_payload(
                item_name="New shared catalog item",
                cargo_category_id=self.category.pk,
                weight_unit="KG",
                item_description="Created by supplier test",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item = Item.objects.get(pk=response.data["item_id"])
        self.assertTrue(item.item_code.startswith("ITM"))
        self.assertEqual(item.item_name, "New shared catalog item")
        self.assertEqual(response.data["supplier_id"], self.supplier.pk)
        self.assertTrue(
            SupplierItem.objects.filter(
                supplier=self.supplier,
                item=item,
            ).exists()
        )

    def test_supplier_cannot_register_same_item_twice(self):
        response = self.client.post(
            "/api/suppliers/me/items",
            data=self.offer_payload(item_id=self.item.pk),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            SupplierItem.objects.filter(
                supplier=self.supplier,
                item=self.item,
            ).count(),
            1,
        )

    def test_supplier_can_update_own_offer_and_deactivate_it(self):
        offer = SupplierItem.objects.get(
            supplier=self.supplier,
            item=self.item,
        )

        response = self.client.patch(
            f"/api/suppliers/me/items/{offer.pk}",
            data={
                "unit_price_vnd_per_kg": "27500.00",
                "offer_status": SupplierItem.OfferStatus.INACTIVE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        offer.refresh_from_db()
        self.assertEqual(
            offer.unit_price_vnd_per_kg,
            Decimal("27500.00"),
        )
        self.assertEqual(
            offer.offer_status,
            SupplierItem.OfferStatus.INACTIVE,
        )

    def test_supplier_cannot_update_another_suppliers_offer(self):
        other_supplier = Supplier.objects.create(
            supplier_code="SUP-CRUD-OTHER",
            supplier_name="Other CRUD Supplier",
        )
        foreign_offer = self.create_offer(
            supplier=other_supplier,
            item=self.create_item("ITM-CRUD-FOREIGN"),
        )

        response = self.client.patch(
            f"/api/suppliers/me/items/{foreign_offer.pk}",
            data={"unit_price_vnd_per_kg": "30000.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        foreign_offer.refresh_from_db()
        self.assertEqual(
            foreign_offer.unit_price_vnd_per_kg,
            Decimal("25000.00"),
        )

    def test_supplier_cannot_change_shared_item_or_supplier_identity(self):
        offer = SupplierItem.objects.get(
            supplier=self.supplier,
            item=self.item,
        )

        response = self.client.patch(
            f"/api/suppliers/me/items/{offer.pk}",
            data={"item_name": "Tampered item name"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            "/api/suppliers/me/items",
            data=self.offer_payload(
                item_id=self.item.pk,
                supplier_id=self.supplier.pk,
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.item.refresh_from_db()
        self.assertEqual(self.item.item_name, "Test item ITM-DEM-001")
