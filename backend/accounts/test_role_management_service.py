from unittest.mock import patch

from django.test import TestCase
from rest_framework import status

from accounts.models import (
    AuditLog,
    ExternalActorType,
    ExternalUserAccess,
    Role,
    RoleCode,
    User,
    UserOutletAccess,
    UserRole,
)
from accounts.services.role_management import (
    RoleManagementError,
    assign_role,
    change_role,
    revoke_role,
)
from masterdata.models import Outlet, Supplier, TransportProvider


class RoleManagementServiceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            email="role-manager@example.test",
            password="Strong-test-password-123",
            full_name="Role Manager",
        )
        self.target = User.objects.create_user(
            email="role-target@example.test",
            password="Strong-test-password-123",
            full_name="Role Target",
        )

        self.roles = {
            code: Role.objects.create(code=code, name=code)
            for code in RoleCode.values
        }
        UserRole.objects.create(
            user=self.manager,
            role=self.roles[RoleCode.MANAGER],
        )

        self.outlet = Outlet.objects.create(
            outlet_code="RM-OUT-001",
            outlet_name="Role Management Outlet",
            address="Da Nang",
        )
        self.supplier = Supplier.objects.create(
            supplier_code="RM-SUP-001",
            supplier_name="Role Management Supplier",
        )
        self.provider = TransportProvider.objects.create(
            provider_code="TP001",
            provider_name="CoLogi Transport Provider",
            provider_type="MVP",
            service_region="Vietnam",
            contact_email="tp001@example.test",
        )

    def test_assign_purchasing_staff_creates_role_scope_and_audit(self):
        assignment = assign_role(
            self.manager,
            self.target.pk,
            RoleCode.PURCHASING_STAFF,
            {"outlet_ids": [self.outlet.pk]},
            "127.0.0.1",
        )

        self.assertTrue(assignment.is_active)
        self.assertEqual(assignment.assigned_by, self.manager)
        self.assertTrue(
            UserOutletAccess.objects.filter(
                user=self.target,
                outlet=self.outlet,
                is_active=True,
            ).exists()
        )
        audit = AuditLog.objects.get(action="ASSIGN_ROLE")
        self.assertEqual(audit.actor_user, self.manager)
        self.assertEqual(audit.entity_id, str(self.target.pk))
        self.assertEqual(audit.ip_address, "127.0.0.1")

    def test_assign_supplier_creates_supplier_scope(self):
        assign_role(
            self.manager,
            self.target.pk,
            RoleCode.SUPPLIER,
            {"supplier_id": self.supplier.pk},
        )

        access = ExternalUserAccess.objects.get(
            user=self.target,
            actor_type=ExternalActorType.SUPPLIER,
        )
        self.assertTrue(access.is_active)
        self.assertEqual(access.supplier, self.supplier)
        self.assertIsNone(access.provider_id)

    def test_assign_provider_only_accepts_tp001(self):
        other_provider = TransportProvider.objects.create(
            provider_code="TP002",
            provider_name="Other Provider",
            provider_type="MVP",
            service_region="Vietnam",
            contact_email="tp002@example.test",
        )

        with self.assertRaises(RoleManagementError):
            assign_role(
                self.manager,
                self.target.pk,
                RoleCode.TRANSPORT_PROVIDER,
                {"provider_id": other_provider.pk},
            )

        self.assertFalse(
            UserRole.objects.filter(
                user=self.target,
                is_active=True,
            ).exists()
        )

    def test_assign_role_rejects_user_with_existing_active_role(self):
        assign_role(
            self.manager,
            self.target.pk,
            RoleCode.MANAGER,
            {},
        )

        with self.assertRaises(RoleManagementError) as context:
            assign_role(
                self.manager,
                self.target.pk,
                RoleCode.SUPPLIER,
                {"supplier_id": self.supplier.pk},
            )

        self.assertEqual(
            context.exception.status_code,
            status.HTTP_409_CONFLICT,
        )
        self.assertEqual(
            UserRole.objects.filter(
                user=self.target,
                is_active=True,
            ).count(),
            1,
        )

    def test_change_role_deactivates_old_scope_and_creates_new_scope(self):
        assign_role(
            self.manager,
            self.target.pk,
            RoleCode.PURCHASING_STAFF,
            {"outlet_ids": [self.outlet.pk]},
        )

        assignment = change_role(
            self.manager,
            self.target.pk,
            RoleCode.SUPPLIER,
            {"supplier_id": self.supplier.pk},
        )

        self.assertEqual(assignment.role.code, RoleCode.SUPPLIER)
        self.assertFalse(
            UserOutletAccess.objects.get(
                user=self.target,
                outlet=self.outlet,
            ).is_active
        )
        self.assertTrue(
            ExternalUserAccess.objects.get(
                user=self.target,
                actor_type=ExternalActorType.SUPPLIER,
            ).is_active
        )
        self.assertEqual(AuditLog.objects.filter(action="CHANGE_ROLE").count(), 1)

    def test_revoke_role_deactivates_role_and_scope(self):
        assign_role(
            self.manager,
            self.target.pk,
            RoleCode.SUPPLIER,
            {"supplier_id": self.supplier.pk},
        )

        revoke_role(self.manager, self.target.pk)

        self.assertFalse(
            UserRole.objects.filter(
                user=self.target,
                is_active=True,
            ).exists()
        )
        self.assertFalse(
            ExternalUserAccess.objects.get(
                user=self.target,
                actor_type=ExternalActorType.SUPPLIER,
            ).is_active
        )
        self.assertEqual(AuditLog.objects.filter(action="REVOKE_ROLE").count(), 1)

    def test_manager_cannot_manage_own_account(self):
        with self.assertRaises(RoleManagementError) as context:
            assign_role(
                self.manager,
                self.manager.pk,
                RoleCode.MANAGER,
                {},
            )

        self.assertEqual(
            context.exception.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_audit_failure_rolls_back_role_and_scope_changes(self):
        with patch(
            "accounts.services.role_management._write_audit",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                assign_role(
                    self.manager,
                    self.target.pk,
                    RoleCode.PURCHASING_STAFF,
                    {"outlet_ids": [self.outlet.pk]},
                )

        self.assertFalse(
            UserRole.objects.filter(
                user=self.target,
                is_active=True,
            ).exists()
        )
        self.assertFalse(
            UserOutletAccess.objects.filter(
                user=self.target,
                is_active=True,
            ).exists()
        )
        self.assertFalse(
            AuditLog.objects.filter(entity_id=str(self.target.pk)).exists()
        )
