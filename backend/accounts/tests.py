from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, RequestFactory

from .models import (
    Role, 
    RoleCode, 
    User, 
    UserRole, 
    ExternalActorType, 
    ExternalUserAccess, 
    UserOutletAccess,
)
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from types import SimpleNamespace

from masterdata.models import Supplier, TransportProvider, Outlet

from .permissions import (
    HasCoLogiRole, 
    HasExternalActorScope,
    HasOutletAccess,
    filter_queryset_by_outlet_access,
)
class UserManagerTests(TestCase):
    def test_create_user_normalizes_email_and_hashes_password(self):
        user = User.objects.create_user(
            email=" Buyer.One@Example.COM ",
            password="Strong-test-password-123",
            full_name="Buyer One",
        )

        self.assertEqual(user.email, "buyer.one@example.com")
        self.assertTrue(user.check_password("Strong-test-password-123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_natural_key_lookup_is_case_insensitive(self):
        user = User.objects.create_user(
            email="buyer@example.com",
            password="Strong-test-password-123",
            full_name="Buyer",
        )

        found = User.objects.get_by_natural_key("BUYER@EXAMPLE.COM")
        self.assertEqual(found.pk, user.pk)

    def test_duplicate_email_is_rejected_case_insensitively(self):
        User.objects.create_user(
            email="buyer@example.com",
            password="Strong-test-password-123",
            full_name="Buyer One",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    email="BUYER@EXAMPLE.COM",
                    password="Strong-test-password-123",
                    full_name="Buyer Two",
                )

    def test_superuser_requires_both_privilege_flags(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="admin@example.com",
                password="Strong-test-password-123",
                full_name="Technical Admin",
                is_staff=False,
            )

    def test_create_superuser_sets_technical_privileges(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="Strong-test-password-123",
            full_name="Technical Admin",
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class RoleTests(TestCase):
    def test_all_four_business_role_codes_are_defined(self):
        self.assertEqual(
            set(RoleCode.values),
            {
                "PURCHASING_STAFF",
                "SUPPLIER",
                "TRANSPORT_PROVIDER",
                "MANAGER",
            },
        )

    def test_role_code_database_constraint_rejects_unknown_code(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Role.objects.create(
                    code="UNKNOWN_ROLE",
                    name="Unknown",
                )


class UserRoleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="Strong-test-password-123",
            full_name="Buyer",
        )
        self.role = Role.objects.create(
            code=RoleCode.PURCHASING_STAFF,
            name="Purchasing Staff",
        )

    def test_user_role_assignment(self):
        assignment = UserRole.objects.create(
            user=self.user,
            role=self.role,
        )

        self.assertEqual(assignment.user, self.user)
        self.assertEqual(assignment.role, self.role)
        self.assertIsNotNone(assignment.assigned_at)

    def test_duplicate_user_role_is_rejected(self):
        UserRole.objects.create(user=self.user, role=self.role)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserRole.objects.create(user=self.user, role=self.role)

    def test_inactive_role_cannot_be_validated_for_assignment(self):
        self.role.is_active = False
        self.role.save(update_fields=("is_active",))

        assignment = UserRole(user=self.user, role=self.role)

        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_deleting_assigning_actor_preserves_assignment(self):
        actor = User.objects.create_user(
            email="manager@example.com",
            password="Strong-test-password-123",
            full_name="Manager",
        )
        assignment = UserRole.objects.create(
            user=self.user,
            role=self.role,
            assigned_by=actor,
        )

        actor.delete()
        assignment.refresh_from_db()

        self.assertIsNone(assignment.assigned_by_id)


class ModelTableMappingTests(TestCase):
    def test_core_table_names_match_dataset_v7(self):
        self.assertEqual(User._meta.db_table, "users")
        self.assertEqual(Role._meta.db_table, "roles")
        self.assertEqual(UserRole._meta.db_table, "user_roles")


class ExternalUserAccessTests(TestCase):
    def create_user_with_role(self, email, role_code):
        user = User.objects.create_user(
            email=email,
            password="Strong-test-password-123",
            full_name=email.split("@")[0],
        )
        role, _ = Role.objects.get_or_create(
            code=role_code,
            defaults={"name": role_code.replace("_", " ").title()},
        )
        UserRole.objects.create(user=user, role=role)
        return user

    def setUp(self):
        from masterdata.models import Supplier, TransportProvider

        from .models import ExternalUserAccess

        self.ExternalUserAccess = ExternalUserAccess

        self.supplier_user = self.create_user_with_role(
            "supplier@example.test",
            RoleCode.SUPPLIER,
        )
        self.provider_user = self.create_user_with_role(
            "provider@example.test",
            RoleCode.TRANSPORT_PROVIDER,
        )

        self.supplier = Supplier.objects.create(
            supplier_code="SUP-EXT-001",
            supplier_name="External Supplier",
        )
        self.provider = TransportProvider.objects.create(
            provider_code="TP-EXT-001",
            provider_name="External Provider",
            provider_type="EXTERNAL",
            service_region="Test region",
            contact_email="provider@example.test",
        )

    def test_external_access_uses_dataset_table_name(self):
        self.assertEqual(
            self.ExternalUserAccess._meta.db_table,
            "external_user_access",
        )

    def test_supplier_user_can_be_scoped_to_one_supplier(self):
        access = self.ExternalUserAccess.objects.create(
            user=self.supplier_user,
            actor_type="SUPPLIER",
            supplier=self.supplier,
        )

        self.assertEqual(access.supplier_id, self.supplier.pk)
        self.assertIsNone(access.provider_id)
        self.assertTrue(access.is_active)

    def test_provider_user_can_be_scoped_to_one_provider(self):
        access = self.ExternalUserAccess.objects.create(
            user=self.provider_user,
            actor_type="TRANSPORT_PROVIDER",
            provider=self.provider,
        )

        self.assertEqual(access.provider_id, self.provider.pk)
        self.assertIsNone(access.supplier_id)

    def test_actor_type_must_match_assigned_active_role(self):
        from django.core.exceptions import ValidationError

        access = self.ExternalUserAccess(
            user=self.supplier_user,
            actor_type="TRANSPORT_PROVIDER",
            provider=self.provider,
        )

        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_supplier_scope_requires_supplier_fk(self):
        from django.db import IntegrityError, transaction

        # bulk_create intentionally bypasses model.save/full_clean
        # to verify that the database constraint independently rejects it.
        invalid = self.ExternalUserAccess(
            user=self.supplier_user,
            actor_type="SUPPLIER",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.ExternalUserAccess.objects.bulk_create([invalid])

    def test_scope_cannot_contain_both_supplier_and_provider(self):
        from django.db import IntegrityError, transaction

        invalid = self.ExternalUserAccess(
            user=self.supplier_user,
            actor_type="SUPPLIER",
            supplier=self.supplier,
            provider=self.provider,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.ExternalUserAccess.objects.bulk_create([invalid])

    def test_user_actor_type_scope_must_be_unique(self):
        from django.db import IntegrityError, transaction

        self.ExternalUserAccess.objects.create(
            user=self.supplier_user,
            actor_type="SUPPLIER",
            supplier=self.supplier,
        )

        duplicate = self.ExternalUserAccess(
            user=self.supplier_user,
            actor_type="SUPPLIER",
            supplier=self.supplier,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.ExternalUserAccess.objects.bulk_create([duplicate])

class AuthenticationAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="Strong-test-password-123",
            full_name="Buyer",
        )
        self.login_url = "/api/auth/login/"
        self.logout_url = "/api/auth/logout/"
        self.me_url = "/api/auth/me/"

    def login(self, email="buyer@example.com",
               password="Strong-test-password-123"):
        return self.client.post(
            self.login_url,
            {"email": email, "password": password},
            format="json",
        )

    def authenticate_user(self):
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )
        return token

    def test_login_success_returns_token(self):
        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["email"], self.user.email)
        self.assertTrue(
            Token.objects.filter(user=self.user).exists()
        )

    def test_login_wrong_password_returns_401(self):
        response = self.login(password="Wrong-password")

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.login()

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertFalse(
            Token.objects.filter(user=self.user).exists()
        )

    def test_me_requires_authentication(self):
        response = self.client.get(self.me_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_me_returns_active_roles_and_external_scope(self):
        role = Role.objects.create(
            code=RoleCode.PURCHASING_STAFF,
            name="Purchasing Staff",
        )
        UserRole.objects.create(user=self.user, role=role)

        self.authenticate_user()
        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["roles"],
            [RoleCode.PURCHASING_STAFF],
        )
        self.assertEqual(response.data["external_accesses"], [])

    def test_me_excludes_inactive_role(self):
        role = Role.objects.create(
            code=RoleCode.MANAGER,
            name="Manager",
            is_active=False,
        )
        UserRole.objects.create(user=self.user, role=role)

        self.authenticate_user()
        response = self.client.get(self.me_url)

        self.assertEqual(response.data["roles"], [])

    def test_logout_deletes_current_token(self):
        token = self.authenticate_user()

        response = self.client.post(self.logout_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())

    def test_logout_requires_authentication(self):
        response = self.client.post(self.logout_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

class UserOutletAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="outlet-buyer@example.com",
            password="Strong-test-password-123",
            full_name="Outlet Buyer",
        )

        self.role = Role.objects.create(
            code=RoleCode.PURCHASING_STAFF,
            name="Purchasing Staff",
        )
        UserRole.objects.create(
            user=self.user,
            role=self.role,
        )

        self.outlet_1 = Outlet.objects.create(
            outlet_code="OUT-ACCESS-001",
            outlet_name="Outlet One",
            address="Da Nang",
        )
        self.outlet_2 = Outlet.objects.create(
            outlet_code="OUT-ACCESS-002",
            outlet_name="Outlet Two",
            address="Da Nang",
        )

    def test_access_uses_expected_table_name(self):
        self.assertEqual(
            UserOutletAccess._meta.db_table,
            "user_outlet_access",
        )

    def test_user_can_be_assigned_multiple_outlets(self):
        first = UserOutletAccess.objects.create(
            user=self.user,
            outlet=self.outlet_1,
        )
        second = UserOutletAccess.objects.create(
            user=self.user,
            outlet=self.outlet_2,
        )

        self.assertEqual(first.user_id, self.user.pk)
        self.assertEqual(second.user_id, self.user.pk)
        self.assertEqual(
            UserOutletAccess.objects.filter(
                user=self.user,
                is_active=True,
            ).count(),
            2,
        )

    def test_multiple_users_can_access_same_outlet(self):
        other_user = User.objects.create_user(
            email="second-buyer@example.com",
            password="Strong-test-password-123",
            full_name="Second Buyer",
        )
        UserRole.objects.create(
            user=other_user,
            role=self.role,
        )

        UserOutletAccess.objects.create(
            user=self.user,
            outlet=self.outlet_1,
        )
        UserOutletAccess.objects.create(
            user=other_user,
            outlet=self.outlet_1,
        )

        self.assertEqual(
            UserOutletAccess.objects.filter(
                outlet=self.outlet_1,
                is_active=True,
            ).count(),
            2,
        )

    def test_duplicate_user_outlet_pair_is_rejected_by_database(self):
        UserOutletAccess.objects.create(
            user=self.user,
            outlet=self.outlet_1,
        )

        duplicate = UserOutletAccess(
            user=self.user,
            outlet=self.outlet_1,
        )

        # Verify the database constraint independently of save().
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserOutletAccess.objects.bulk_create([duplicate])

    def test_user_without_purchasing_role_cannot_get_active_access(self):
        user_without_role = User.objects.create_user(
            email="no-role@example.com",
            password="Strong-test-password-123",
            full_name="No Role",
        )

        access = UserOutletAccess(
            user=user_without_role,
            outlet=self.outlet_1,
        )

        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_inactive_purchasing_role_cannot_get_active_access(self):
        self.role.is_active = False
        self.role.save(update_fields=["is_active"])

        access = UserOutletAccess(
            user=self.user,
            outlet=self.outlet_1,
        )

        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_access_can_be_revoked_after_role_becomes_inactive(self):
        access = UserOutletAccess.objects.create(
            user=self.user,
            outlet=self.outlet_1,
        )

        self.role.is_active = False
        self.role.save(update_fields=["is_active"])

        access.is_active = False
        access.save(update_fields=["is_active"])
        access.refresh_from_db()

        self.assertFalse(access.is_active)

    def test_deleting_assigning_actor_preserves_access(self):
        manager = User.objects.create_user(
            email="assigner@example.com",
            password="Strong-test-password-123",
            full_name="Assigner",
        )

        access = UserOutletAccess.objects.create(
            user=self.user,
            outlet=self.outlet_1,
            assigned_by=manager,
        )

        manager.delete()
        access.refresh_from_db()

        self.assertIsNone(access.assigned_by_id)

class CoLogiRolePermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="permission-buyer@example.com",
            password="Strong-test-password-123",
            full_name="Permission Buyer",
        )
        self.role = Role.objects.create(
            code=RoleCode.PURCHASING_STAFF,
            name="Purchasing Staff",
        )

    def make_request(self):
        request = self.factory.get("/api/test/")
        request.user = self.user
        return request

    def test_assigned_active_role_is_allowed(self):
        UserRole.objects.create(user=self.user, role=self.role)
        view = SimpleNamespace(
            required_roles=(RoleCode.PURCHASING_STAFF,)
        )

        self.assertTrue(
            HasCoLogiRole().has_permission(self.make_request(), view)
        )

    def test_different_role_is_denied(self):
        manager_role = Role.objects.create(
            code=RoleCode.MANAGER,
            name="Manager",
        )
        UserRole.objects.create(user=self.user, role=manager_role)

        view = SimpleNamespace(
            required_roles=(RoleCode.PURCHASING_STAFF,)
        )

        self.assertFalse(
            HasCoLogiRole().has_permission(self.make_request(), view)
        )

    def test_inactive_role_is_denied(self):
        UserRole.objects.create(user=self.user, role=self.role)
        self.role.is_active = False
        self.role.save(update_fields=["is_active"])

        view = SimpleNamespace(
            required_roles=(RoleCode.PURCHASING_STAFF,)
        )

        self.assertFalse(
            HasCoLogiRole().has_permission(self.make_request(), view)
        )

    def test_missing_required_roles_denies_access(self):
        UserRole.objects.create(user=self.user, role=self.role)

        self.assertFalse(
            HasCoLogiRole().has_permission(
                self.make_request(),
                SimpleNamespace(),
            )
        )

    def test_superuser_without_business_role_is_denied(self):
        superuser = User.objects.create_superuser(
            email="technical-admin@example.com",
            password="Strong-test-password-123",
            full_name="Technical Admin",
        )
        request = self.factory.get("/api/test/")
        request.user = superuser

        view = SimpleNamespace(
            required_roles=(RoleCode.MANAGER,)
        )

        self.assertFalse(
            HasCoLogiRole().has_permission(request, view)
        )


class ExternalActorScopePermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.supplier_user = User.objects.create_user(
            email="supplier-scope@example.com",
            password="Strong-test-password-123",
            full_name="Supplier Scope",
        )
        self.supplier_role = Role.objects.create(
            code=RoleCode.SUPPLIER,
            name="Supplier",
        )
        UserRole.objects.create(
            user=self.supplier_user,
            role=self.supplier_role,
        )

        self.supplier = Supplier.objects.create(
            supplier_code="SUP-SCOPE-001",
            supplier_name="Scoped Supplier",
        )
        self.other_supplier = Supplier.objects.create(
            supplier_code="SUP-SCOPE-002",
            supplier_name="Other Supplier",
        )

        self.access = ExternalUserAccess.objects.create(
            user=self.supplier_user,
            actor_type=ExternalActorType.SUPPLIER,
            supplier=self.supplier,
        )

        self.view = SimpleNamespace(
            required_actor_type=ExternalActorType.SUPPLIER,
            external_scope_field="supplier_id",
        )

    def make_request(self, user=None):
        request = self.factory.get("/api/test/")
        request.user = user or self.supplier_user
        return request

    def test_active_supplier_access_is_allowed(self):
        self.assertTrue(
            HasExternalActorScope().has_permission(
                self.make_request(),
                self.view,
            )
        )

    def test_supplier_can_access_own_scope_object(self):
        obj = SimpleNamespace(supplier_id=self.supplier.pk)

        self.assertTrue(
            HasExternalActorScope().has_object_permission(
                self.make_request(),
                self.view,
                obj,
            )
        )

    def test_supplier_cannot_access_another_supplier_object(self):
        obj = SimpleNamespace(supplier_id=self.other_supplier.pk)

        self.assertFalse(
            HasExternalActorScope().has_object_permission(
                self.make_request(),
                self.view,
                obj,
            )
        )

    def test_inactive_external_access_is_denied(self):
        self.access.is_active = False
        self.access.save(update_fields=["is_active"])

        self.assertFalse(
            HasExternalActorScope().has_permission(
                self.make_request(),
                self.view,
            )
        )

    def test_inactive_business_role_invalidates_external_access(self):
        self.supplier_role.is_active = False
        self.supplier_role.save(update_fields=["is_active"])

        self.assertFalse(
            HasExternalActorScope().has_permission(
                self.make_request(),
                self.view,
            )
        )

    def test_missing_scope_field_denies_object_access(self):
        view = SimpleNamespace(
            required_actor_type=ExternalActorType.SUPPLIER,
        )
        obj = SimpleNamespace(supplier_id=self.supplier.pk)

        self.assertFalse(
            HasExternalActorScope().has_object_permission(
                self.make_request(),
                view,
                obj,
            )
        )

    def test_inactive_supplier_invalidates_external_access(self):
        self.supplier.is_active = False
        self.supplier.save(update_fields=["is_active"])

        self.assertFalse(
            HasExternalActorScope().has_permission(
                self.make_request(),
                self.view,
            )
        )

    def test_inactive_provider_invalidates_external_access(self):
        provider_user = User.objects.create_user(
            email="inactive-provider@example.com",
            password="Strong-test-password-123",
            full_name="Inactive Provider",
        )
        provider_role = Role.objects.create(
            code=RoleCode.TRANSPORT_PROVIDER,
            name="Transport Provider",
        )
        UserRole.objects.create(
            user=provider_user,
            role=provider_role,
        )

        provider = TransportProvider.objects.create(
            provider_code="TP-INACTIVE-001",
            provider_name="Inactive Provider",
            provider_type="EXTERNAL",
            service_region="Test region",
            contact_email="inactive-provider@example.com",
            is_active=True,
        )
        ExternalUserAccess.objects.create(
            user=provider_user,
            actor_type=ExternalActorType.TRANSPORT_PROVIDER,
            provider=provider,
        )

        provider.is_active = False
        provider.save(update_fields=["is_active"])

        provider_view = SimpleNamespace(
            required_actor_type=ExternalActorType.TRANSPORT_PROVIDER,
            external_scope_field="provider_id",
        )

        self.assertFalse(
            HasExternalActorScope().has_permission(
                self.make_request(provider_user),
                provider_view,
            )
        )

    def test_provider_access_cannot_be_used_as_supplier_access(self):
        provider_user = User.objects.create_user(
            email="provider-scope@example.com",
            password="Strong-test-password-123",
            full_name="Provider Scope",
        )
        provider_role = Role.objects.create(
            code=RoleCode.TRANSPORT_PROVIDER,
            name="Transport Provider",
        )
        UserRole.objects.create(
            user=provider_user,
            role=provider_role,
        )

        provider = TransportProvider.objects.create(
            provider_code="TP-SCOPE-001",
            provider_name="Scoped Provider",
            provider_type="EXTERNAL",
            service_region="Test region",
            contact_email="provider-scope@example.com",
        )
        ExternalUserAccess.objects.create(
            user=provider_user,
            actor_type=ExternalActorType.TRANSPORT_PROVIDER,
            provider=provider,
        )

        self.assertFalse(
            HasExternalActorScope().has_permission(
                self.make_request(provider_user),
                self.view,
            )
        )

class OutletAccessPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="outlet-permission@example.com",
            password="Strong-test-password-123",
            full_name="Outlet Permission Buyer",
        )

        self.role = Role.objects.create(
            code=RoleCode.PURCHASING_STAFF,
            name="Purchasing Staff",
        )
        UserRole.objects.create(
            user=self.user,
            role=self.role,
        )

        self.outlet_1 = Outlet.objects.create(
            outlet_code="OUT-PERM-001",
            outlet_name="Authorized Outlet",
            address="Da Nang",
        )
        self.outlet_2 = Outlet.objects.create(
            outlet_code="OUT-PERM-002",
            outlet_name="Unauthorized Outlet",
            address="Da Nang",
        )

        self.access = UserOutletAccess.objects.create(
            user=self.user,
            outlet=self.outlet_1,
        )

        self.view = SimpleNamespace(
            outlet_request_field="outlet_id",
            outlet_scope_field="outlet_id",
        )

    def make_request(self, user=None, outlet_id=None):
        data = {}
        if outlet_id is not None:
            data["outlet_id"] = outlet_id

        return SimpleNamespace(
            user=user or self.user,
            data=data,
            method="POST",
        )

    def test_authorized_outlet_is_allowed(self):
        request = self.make_request(
            outlet_id=self.outlet_1.pk,
        )

        self.assertTrue(
            HasOutletAccess().has_permission(
                request,
                self.view,
            )
        )

    def test_unassigned_outlet_is_denied(self):
        request = self.make_request(
            outlet_id=self.outlet_2.pk,
        )

        self.assertFalse(
            HasOutletAccess().has_permission(
                request,
                self.view,
            )
        )

    def test_inactive_access_is_denied(self):
        self.access.is_active = False
        self.access.save(update_fields=["is_active"])

        request = self.make_request(
            outlet_id=self.outlet_1.pk,
        )

        self.assertFalse(
            HasOutletAccess().has_permission(
                request,
                self.view,
            )
        )

    def test_inactive_outlet_is_denied(self):
        self.outlet_1.is_active = False
        self.outlet_1.save(update_fields=["is_active"])

        request = self.make_request(
            outlet_id=self.outlet_1.pk,
        )

        self.assertFalse(
            HasOutletAccess().has_permission(
                request,
                self.view,
            )
        )

    def test_inactive_purchasing_role_is_denied(self):
        self.role.is_active = False
        self.role.save(update_fields=["is_active"])

        request = self.make_request(
            outlet_id=self.outlet_1.pk,
        )

        self.assertFalse(
            HasOutletAccess().has_permission(
                request,
                self.view,
            )
        )

    def test_superuser_without_purchasing_role_is_denied(self):
        superuser = User.objects.create_superuser(
            email="outlet-admin@example.com",
            password="Strong-test-password-123",
            full_name="Technical Admin",
        )

        request = self.make_request(
            user=superuser,
            outlet_id=self.outlet_1.pk,
        )

        self.assertFalse(
            HasOutletAccess().has_permission(
                request,
                self.view,
            )
        )

    def test_object_in_authorized_outlet_is_allowed(self):
        obj = SimpleNamespace(
            outlet_id=self.outlet_1.pk,
        )

        self.assertTrue(
            HasOutletAccess().has_object_permission(
                self.make_request(),
                self.view,
                obj,
            )
        )

    def test_object_in_unassigned_outlet_is_denied(self):
        obj = SimpleNamespace(
            outlet_id=self.outlet_2.pk,
        )

        self.assertFalse(
            HasOutletAccess().has_object_permission(
                self.make_request(),
                self.view,
                obj,
            )
        )

    def test_missing_object_scope_field_denies_access(self):
        view = SimpleNamespace()

        obj = SimpleNamespace(
            outlet_id=self.outlet_1.pk,
        )

        self.assertFalse(
            HasOutletAccess().has_object_permission(
                self.make_request(),
                view,
                obj,
            )
        )

    def test_queryset_is_filtered_to_authorized_outlets(self):
        visible_outlets = filter_queryset_by_outlet_access(
            Outlet.objects.all(),
            self.user,
            outlet_lookup="pk",
        )

        self.assertEqual(
            list(visible_outlets.values_list("pk", flat=True)),
            [self.outlet_1.pk],
        )