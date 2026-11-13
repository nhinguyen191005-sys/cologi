from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode, User, UserRole
from masterdata.models import Outlet


class RoleManagementAPITests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            email="api-manager@example.test",
            password="Strong-test-password-123",
            full_name="API Manager",
        )
        self.target = User.objects.create_user(
            email="api-target@example.test",
            password="Strong-test-password-123",
            full_name="API Target",
        )
        self.buyer = User.objects.create_user(
            email="api-buyer@example.test",
            password="Strong-test-password-123",
            full_name="API Buyer",
        )

        self.manager_role = Role.objects.create(
            code=RoleCode.MANAGER,
            name="Manager",
        )
        self.buyer_role = Role.objects.create(
            code=RoleCode.PURCHASING_STAFF,
            name="Purchasing Staff",
        )
        UserRole.objects.create(
            user=self.manager,
            role=self.manager_role,
        )
        UserRole.objects.create(
            user=self.buyer,
            role=self.buyer_role,
        )

        self.outlet = Outlet.objects.create(
            outlet_code="RM-API-001",
            outlet_name="API Test Outlet",
            address="Da Nang",
        )

        self.assign_url = reverse(
            "role-management-assign",
            kwargs={"user_id": self.target.pk},
        )
        self.detail_url = reverse(
            "role-management-user-detail",
            kwargs={"user_id": self.target.pk},
        )

    def test_assign_requires_authentication(self):
        response = self.client.post(
            self.assign_url,
            {
                "role_code": RoleCode.PURCHASING_STAFF,
                "outlet_ids": [self.outlet.pk],
            },
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_non_manager_cannot_assign_role(self):
        self.client.force_authenticate(user=self.buyer)
        response = self.client.post(
            self.assign_url,
            {
                "role_code": RoleCode.PURCHASING_STAFF,
                "outlet_ids": [self.outlet.pk],
            },
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_manager_can_assign_role_through_api(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            self.assign_url,
            {
                "role_code": RoleCode.PURCHASING_STAFF,
                "outlet_ids": [self.outlet.pk],
            },
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["user"]["active_role"]["code"],
            RoleCode.PURCHASING_STAFF,
        )

    def test_duplicate_assignment_returns_conflict(self):
        self.client.force_authenticate(user=self.manager)
        payload = {
            "role_code": RoleCode.PURCHASING_STAFF,
            "outlet_ids": [self.outlet.pk],
        }

        first = self.client.post(
            self.assign_url, payload, format="json"
        )
        second = self.client.post(
            self.assign_url, payload, format="json"
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)

    def test_manager_can_read_target_role_details(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.target.pk)
        self.assertIsNone(response.data["active_role"])

    def test_manager_cannot_read_own_role_details(self):
        self.client.force_authenticate(user=self.manager)
        url = reverse(
            "role-management-user-detail",
            kwargs={"user_id": self.manager.pk},
        )
        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
