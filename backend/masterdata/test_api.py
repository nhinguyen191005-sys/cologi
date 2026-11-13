from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import (
    Role,
    RoleCode,
    User,
    UserOutletAccess,
    UserRole,
)
from .models import (
    CargoCategory,
    Item,
    Outlet,
    Supplier,
    SupplierItem,
)


class MasterdataReadAPITests(TestCase):
    endpoints = {
        "suppliers": "/api/masterdata/suppliers/",
        "outlets": "/api/masterdata/outlets/",
        "cargo_categories": "/api/masterdata/cargo-categories/",
        "items": "/api/masterdata/items/",
        "supplier_items": "/api/masterdata/supplier-items/",
    }

    def setUp(self):
        self.client = APIClient()

        self.roles = {
            code: Role.objects.create(
                code=code,
                name=code.replace("_", " ").title(),
            )
            for code in RoleCode.values
        }

        self.purchasing_user = self.create_user(
            "purchasing@example.test",
            RoleCode.PURCHASING_STAFF,
        )
        self.manager_user = self.create_user(
            "manager@example.test",
            RoleCode.MANAGER,
        )
        self.supplier_user = self.create_user(
            "supplier@example.test",
            RoleCode.SUPPLIER,
        )
        self.provider_user = self.create_user(
            "provider@example.test",
            RoleCode.TRANSPORT_PROVIDER,
        )

        self.outlet_a = Outlet.objects.create(
            outlet_code="OUT-API-A",
            outlet_name="API Outlet A",
            address="Da Nang",
        )
        self.outlet_b = Outlet.objects.create(
            outlet_code="OUT-API-B",
            outlet_name="API Outlet B",
            address="Da Nang",
        )
        self.inactive_outlet = Outlet.objects.create(
            outlet_code="OUT-API-INACTIVE",
            outlet_name="Inactive API Outlet",
            address="Da Nang",
            is_active=False,
        )

        UserOutletAccess.objects.create(
            user=self.purchasing_user,
            outlet=self.outlet_a,
        )
        UserOutletAccess.objects.create(
            user=self.purchasing_user,
            outlet=self.inactive_outlet,
            is_active=False,
        )

        self.supplier = Supplier.objects.create(
            supplier_code="SUP-API-A",
            supplier_name="API Supplier A",
        )
        self.inactive_supplier = Supplier.objects.create(
            supplier_code="SUP-API-INACTIVE",
            supplier_name="Inactive API Supplier",
            is_active=False,
        )

        self.category = CargoCategory.objects.create(
            category_code="CAT-API-A",
            category_name="API Category A",
        )
        self.inactive_category = CargoCategory.objects.create(
            category_code="CAT-API-INACTIVE",
            category_name="Inactive API Category",
            is_active=False,
        )

        self.item = Item.objects.create(
            item_code="ITEM-API-A",
            item_name="API Item A",
            cargo_category=self.category,
            weight_unit="KG",
        )
        self.inactive_item = Item.objects.create(
            item_code="ITEM-API-INACTIVE",
            item_name="Inactive API Item",
            cargo_category=self.category,
            weight_unit="KG",
            is_active=False,
        )
        self.item_with_inactive_category = Item.objects.create(
            item_code="ITEM-API-INACTIVE-CAT",
            item_name="Item With Inactive Category",
            cargo_category=self.inactive_category,
            weight_unit="KG",
        )

        self.active_offer = SupplierItem.objects.create(
            supplier=self.supplier,
            item=self.item,
            unit_price_vnd_per_kg="25000.00",
            max_daily_supply_kg="1000.000",
            lead_time_hours=8,
            minimum_order_kg="5.000",
            offer_status=SupplierItem.OfferStatus.ACTIVE,
        )
        self.inactive_offer = SupplierItem.objects.create(
            supplier=self.supplier,
            item=self.inactive_item,
            unit_price_vnd_per_kg="26000.00",
            offer_status=SupplierItem.OfferStatus.ACTIVE,
        )
        self.offer_from_inactive_supplier = SupplierItem.objects.create(
            supplier=self.inactive_supplier,
            item=self.item,
            unit_price_vnd_per_kg="27000.00",
            offer_status=SupplierItem.OfferStatus.ACTIVE,
        )
        self.inactive_status_offer = SupplierItem.objects.create(
            supplier=self.supplier,
            item=self.item_with_inactive_category,
            unit_price_vnd_per_kg="28000.00",
            offer_status=SupplierItem.OfferStatus.INACTIVE,
        )

    def create_user(self, email, role_code):
        user = User.objects.create_user(
            email=email,
            full_name=email,
            password="Strong-test-password-123",
        )
        UserRole.objects.create(
            user=user,
            role=self.roles[role_code],
        )
        return user

    def authenticate_as(self, user):
        self.client.force_authenticate(user=user)

    def test_anonymous_user_cannot_read_masterdata(self):
        for endpoint in self.endpoints.values():
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_401_UNAUTHORIZED,
                )

    def test_external_actors_cannot_read_generic_masterdata(self):
        for user in (self.supplier_user, self.provider_user):
            self.authenticate_as(user)

            for endpoint in self.endpoints.values():
                with self.subTest(
                    role=user.user_roles.get().role.code,
                    endpoint=endpoint,
                ):
                    response = self.client.get(endpoint)
                    self.assertEqual(
                        response.status_code,
                        status.HTTP_403_FORBIDDEN,
                    )

    def test_purchasing_staff_can_read_active_shared_masterdata(self):
        self.authenticate_as(self.purchasing_user)

        expected = {
            "suppliers": ["SUP-API-A"],
            "cargo_categories": ["CAT-API-A"],
            "items": ["ITEM-API-A"],
            "supplier_items": ["SUP-API-A"],
        }

        for resource, codes in expected.items():
            response = self.client.get(self.endpoints[resource])

            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                resource,
            )

            if resource == "supplier_items":
                returned_codes = [
                    row["supplier_code"] for row in response.data
                ]
            else:
                code_field = {
                    "suppliers": "supplier_code",
                    "cargo_categories": "category_code",
                    "items": "item_code",
                }[resource]
                returned_codes = [
                    row[code_field] for row in response.data
                ]

            self.assertEqual(returned_codes, codes, resource)

    def test_purchasing_staff_only_sees_assigned_active_outlets(self):
        self.authenticate_as(self.purchasing_user)

        response = self.client.get(self.endpoints["outlets"])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["outlet_code"] for row in response.data],
            ["OUT-API-A"],
        )

    def test_manager_sees_all_active_outlets(self):
        self.authenticate_as(self.manager_user)

        response = self.client.get(self.endpoints["outlets"])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {row["outlet_code"] for row in response.data},
            {"OUT-API-A", "OUT-API-B"},
        )

    def test_manager_still_only_sees_active_shared_masterdata(self):
        self.authenticate_as(self.manager_user)

        response = self.client.get(self.endpoints["suppliers"])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["supplier_code"] for row in response.data],
            ["SUP-API-A"],
        )

    def test_purchasing_user_without_outlet_access_gets_empty_outlet_list(self):
        user = self.create_user(
            "purchasing-no-outlet@example.test",
            RoleCode.PURCHASING_STAFF,
        )
        self.authenticate_as(user)

        response = self.client.get(self.endpoints["outlets"])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_items_exclude_inactive_category(self):
        self.authenticate_as(self.manager_user)

        response = self.client.get(self.endpoints["items"])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["item_code"] for row in response.data],
            ["ITEM-API-A"],
        )
        self.assertEqual(
            response.data[0]["category_code"],
            "CAT-API-A",
        )

    def test_supplier_items_exclude_inactive_offer_or_related_masterdata(self):
        self.authenticate_as(self.manager_user)

        response = self.client.get(self.endpoints["supplier_items"])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["id"],
            self.active_offer.pk,
        )
        self.assertEqual(
            response.data[0]["item_code"],
            "ITEM-API-A",
        )

    def test_masterdata_list_endpoints_are_read_only(self):
        self.authenticate_as(self.manager_user)

        for endpoint in self.endpoints.values():
            with self.subTest(endpoint=endpoint):
                response = self.client.post(endpoint, data={})
                self.assertEqual(
                    response.status_code,
                    status.HTTP_405_METHOD_NOT_ALLOWED,
                )
