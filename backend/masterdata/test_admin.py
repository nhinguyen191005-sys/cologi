from django.contrib import admin
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from decimal import Decimal

from accounts.models import Role, RoleCode, User, UserRole

from .admin import ManagerOnlyMasterdataAdminMixin
from .models import (
    CargoCategory,
    Item,
    Outlet,
    Supplier,
    SupplierItem,
    TransportProvider,
    Hub,
    VehicleType,
    VehicleCargoCompatibility,
)


MASTERDATA_MODELS = (
    Supplier,
    TransportProvider,
    Outlet,
    CargoCategory,
    Item,
    SupplierItem,
    Hub,
    VehicleType,
)


class MasterdataAdminRegistrationTests(TestCase):
    def test_all_masterdata_models_are_registered_with_manager_policy(self):
        for model in MASTERDATA_MODELS:
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]

                self.assertIsInstance(
                    model_admin,
                    ManagerOnlyMasterdataAdminMixin,
                )
                self.assertIsNone(model_admin.actions)

    def test_masterdata_models_cannot_be_hard_deleted_in_admin(self):
        role = Role.objects.create(
            code=RoleCode.MANAGER,
            name="Manager",
            is_active=True,
        )
        manager = User.objects.create_user(
            email="manager-admin@example.test",
            full_name="Masterdata Manager",
            password="Strong-test-password-123",
            is_staff=True,
        )
        UserRole.objects.create(user=manager, role=role)

        request = RequestFactory().get("/admin/")
        request.user = manager

        for model in MASTERDATA_MODELS:
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertFalse(
                    model_admin.has_delete_permission(request)
                )


class MasterdataAdminPermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.manager_role = Role.objects.create(
            code=RoleCode.MANAGER,
            name="Manager",
            is_active=True,
        )

    def make_request(self, user):
        request = self.factory.get("/admin/")
        request.user = user
        return request

    def make_user(
        self,
        email,
        *,
        is_staff=True,
        is_superuser=False,
        role=None,
    ):
        user = User.objects.create_user(
            email=email,
            full_name=email,
            password="Strong-test-password-123",
            is_staff=is_staff,
        )
        if is_superuser:
            user.is_superuser = True
            user.save(update_fields=("is_superuser",))

        if role is not None:
            UserRole.objects.create(user=user, role=role)

        return user

    def test_active_manager_with_staff_access_can_manage_masterdata(self):
        manager = self.make_user(
            "manager@example.test",
            role=self.manager_role,
        )
        request = self.make_request(manager)

        for model in MASTERDATA_MODELS:
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]

                self.assertTrue(model_admin.has_module_permission(request))
                self.assertTrue(model_admin.has_view_permission(request))
                self.assertTrue(model_admin.has_add_permission(request))
                self.assertTrue(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))

    def test_staff_without_manager_role_cannot_access_masterdata(self):
        staff_user = self.make_user("staff@example.test")
        request = self.make_request(staff_user)

        for model in MASTERDATA_MODELS:
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]

                self.assertFalse(model_admin.has_module_permission(request))
                self.assertFalse(model_admin.has_view_permission(request))
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))

    def test_superuser_without_manager_role_is_not_business_manager(self):
        superuser = self.make_user(
            "superuser@example.test",
            is_superuser=True,
        )
        request = self.make_request(superuser)

        model_admin = admin.site._registry[Supplier]

        self.assertFalse(model_admin.has_module_permission(request))
        self.assertFalse(model_admin.has_view_permission(request))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))

    def test_manager_role_without_staff_access_cannot_use_django_admin(self):
        manager_without_staff = self.make_user(
            "manager-no-staff@example.test",
            is_staff=False,
            role=self.manager_role,
        )
        request = self.make_request(manager_without_staff)

        model_admin = admin.site._registry[Supplier]

        self.assertFalse(model_admin.has_module_permission(request))
        self.assertFalse(model_admin.has_view_permission(request))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))

    def test_inactive_manager_role_does_not_grant_admin_access(self):
        user = self.make_user(
            "inactive-manager@example.test",
            role=self.manager_role,
        )
        self.manager_role.is_active = False
        self.manager_role.save(update_fields=("is_active",))
        request = self.make_request(user)

        model_admin = admin.site._registry[Supplier]

        self.assertFalse(model_admin.has_module_permission(request))
        self.assertFalse(model_admin.has_view_permission(request))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))


class VehicleCargoCompatibilityAdminTests(TestCase):
    def setUp(self):
        self.manager_role = Role.objects.create(
            code=RoleCode.MANAGER,
            name="Manager",
            is_active=True,
        )

        self.manager = User.objects.create_user(
            email="compat-manager@example.test",
            full_name="Compatibility Manager",
            password="Strong-test-password-123",
            is_staff=True,
        )
        UserRole.objects.create(
            user=self.manager,
            role=self.manager_role,
        )

        self.vehicle = VehicleType.objects.create(
            vehicle_code="TEST_TRUCK",
            vehicle_name="Test Truck",
            capacity_kg=Decimal("1000.000"),
        )
        self.cargo = CargoCategory.objects.create(
            category_code="TEST_FOOD",
            category_name="Test Food",
        )

        self.compatibility = VehicleCargoCompatibility.objects.create(
            vehicle_type=self.vehicle,
            cargo_category=self.cargo,
            is_supported=False,
            source="CONFIG_MATRIX",
        )

        self.list_url = reverse("masterdata_vehiclecargo_list")
        self.update_url = reverse(
            "masterdata_vehiclecargo_update",
            kwargs={
                "vehicle_id": self.vehicle.pk,
                "cargo_id": self.cargo.pk,
            },
        )

        self.client.force_login(self.manager)

    def make_user(self, email, *, is_staff=True, is_superuser=False):
        user = User.objects.create_user(
            email=email,
            full_name=email,
            password="Strong-test-password-123",
            is_staff=is_staff,
        )
        if is_superuser:
            user.is_superuser = True
            user.save(update_fields=("is_superuser",))
        return user

    def test_manager_can_view_compatibility_matrix(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TEST_TRUCK")
        self.assertContains(response, "TEST_FOOD")
        self.assertContains(response, "CONFIG_MATRIX")
        self.assertContains(response, "Not supported")

    def test_manager_can_filter_unsupported_pairs(self):
        response = self.client.get(
            self.list_url,
            {"is_supported": "false"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["compatibilities"]),
            [self.compatibility],
        )

    def test_manager_can_open_update_page(self):
        response = self.client.get(self.update_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TEST_TRUCK")
        self.assertContains(response, "TEST_FOOD")
        self.assertContains(response, "CONFIG_MATRIX")

        self.assertEqual(
            list(response.context["form"].fields),
            ["is_supported"],
        )

    def test_manager_can_update_supported_flag(self):
        original_pk = self.compatibility.pk
        original_source = self.compatibility.source

        response = self.client.post(
            self.update_url,
            {"is_supported": "true"},
        )

        self.assertRedirects(response, self.list_url)

        self.compatibility.refresh_from_db()

        self.assertTrue(self.compatibility.is_supported)
        self.assertEqual(self.compatibility.source, original_source)
        self.assertEqual(self.compatibility.pk, original_pk)

    def test_post_cannot_modify_source_or_composite_key(self):
        original_pk = self.compatibility.pk

        another_vehicle = VehicleType.objects.create(
            vehicle_code="OTHER_TRUCK",
            vehicle_name="Other Truck",
            capacity_kg=Decimal("1500.000"),
        )
        another_cargo = CargoCategory.objects.create(
            category_code="OTHER_FOOD",
            category_name="Other Food",
        )

        response = self.client.post(
            self.update_url,
            {
                "is_supported": "true",
                "source": "TAMPERED_SOURCE",
                "vehicle_type": str(another_vehicle.pk),
                "cargo_category": str(another_cargo.pk),
            },
        )

        self.assertRedirects(response, self.list_url)

        self.compatibility.refresh_from_db()

        self.assertTrue(self.compatibility.is_supported)
        self.assertEqual(self.compatibility.source, "CONFIG_MATRIX")
        self.assertEqual(self.compatibility.pk, original_pk)
        self.assertEqual(
            VehicleCargoCompatibility.objects.count(),
            1,
        )

    def test_unsupported_pair_is_retained_not_deleted(self):
        response = self.client.post(
            self.update_url,
            {"is_supported": "false"},
        )

        self.assertRedirects(response, self.list_url)

        self.assertTrue(
            VehicleCargoCompatibility.objects.filter(
                vehicle_type=self.vehicle,
                cargo_category=self.cargo,
                is_supported=False,
            ).exists()
        )

    def test_unknown_composite_pair_returns_404(self):
        response = self.client.get(
            reverse(
                "masterdata_vehiclecargo_update",
                kwargs={
                    "vehicle_id": 999999,
                    "cargo_id": 999999,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_staff_without_manager_role_is_forbidden(self):
        staff_user = self.make_user("compat-staff@example.test")
        self.client.force_login(staff_user)

        self.assertEqual(
            self.client.get(self.list_url).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(self.update_url).status_code,
            403,
        )

    def test_superuser_without_manager_role_is_forbidden(self):
        superuser = self.make_user(
            "compat-superuser@example.test",
            is_superuser=True,
        )
        self.client.force_login(superuser)

        self.assertEqual(
            self.client.get(self.list_url).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(self.update_url).status_code,
            403,
        )

    def test_inactive_manager_role_is_forbidden(self):
        self.manager_role.is_active = False
        self.manager_role.save(update_fields=("is_active",))

        self.assertEqual(
            self.client.get(self.list_url).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(self.update_url).status_code,
            403,
        )

    def test_manager_without_staff_access_is_forbidden(self):
        user = self.make_user(
            "compat-no-staff@example.test",
            is_staff=False,
        )
        UserRole.objects.create(
            user=user,
            role=self.manager_role,
        )
        self.client.force_login(user)

        self.assertEqual(
            self.client.get(self.list_url).status_code,
            302,
        )

    def test_update_rejects_delete_put_and_patch(self):
        for method in ("delete", "put", "patch"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self.update_url,
                    data={"is_supported": "true"},
                )
                self.assertEqual(response.status_code, 405)

    def test_list_rejects_post_and_delete(self):
        self.assertEqual(
            self.client.post(self.list_url).status_code,
            405,
        )
        self.assertEqual(
            self.client.delete(self.list_url).status_code,
            405,
        )

    def test_add_and_delete_routes_do_not_exist(self):
        add_response = self.client.get(
            "/admin/masterdata/vehicle-cargo/add/"
        )
        delete_response = self.client.post(
            f"/admin/masterdata/vehicle-cargo/"
            f"{self.vehicle.pk}/{self.cargo.pk}/delete/"
        )

        self.assertEqual(add_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)

    def test_unauthenticated_user_is_redirected_to_admin_login(self):
        self.client.logout()

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_vehicle_type_admin_links_to_compatibility_matrix(self):
        url = reverse("admin:masterdata_vehicletype_changelist")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("masterdata_vehiclecargo_list"),
        )
        self.assertContains(
            response,
            "Manage Vehicle–Cargo Compatibility",
        )