from datetime import date, time, timedelta
from unittest.mock import patch

from rest_framework.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import (
    AuditLog,
    ExternalUserAccess,
    Role,
    RoleCode,
    User,
    UserRole,
)
from masterdata.models import (
    CargoCategory,
    Supplier,
    TransportProvider,
    VehicleCargoCompatibility,
    VehicleType,
)
from .models import (
    ProviderAvailability,
    ProviderSupplierCoverage,
    ProviderVehicleOffer,
)
from .services import is_vehicle_type_compatible


class ProviderAPITestBase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="provider@example.test",
            password="Strong-test-password-123",
            full_name="Test Provider",
        )
        role, _ = Role.objects.get_or_create(
            code=RoleCode.TRANSPORT_PROVIDER,
            defaults={"name": "Transport Provider"},
        )
        UserRole.objects.create(user=self.user, role=role)

        self.provider = TransportProvider.objects.create(
            provider_code="TP-TEST-001",
            provider_name="Test Provider",
            provider_type="EXTERNAL",
            service_region="Ho Chi Minh City",
            contact_email="provider@example.test",
        )
        ExternalUserAccess.objects.create(
            user=self.user,
            actor_type="TRANSPORT_PROVIDER",
            provider=self.provider,
        )
        self.client.force_authenticate(user=self.user)

        self.supplier = Supplier.objects.create(
            supplier_code="SUP-TEST-001",
            supplier_name="Test Supplier",
        )
        self.vehicle_type = VehicleType.objects.create(
            vehicle_code="VAN-TEST",
            vehicle_name="Test Van",
            capacity_kg="1000.000",
        )
        self.cargo_category = CargoCategory.objects.create(
            category_code="CARGO-TEST",
            category_name="Test Cargo",
        )

    def create_offer(self, **overrides):
        payload = {
            "vehicle_type_id": self.vehicle_type.pk,
            "available_vehicle_count": 3,
            "fuel_type": "GASOLINE",
            **overrides,
        }
        response = self.client.post(
            "/api/providers/me/vehicle-offers/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return ProviderVehicleOffer.objects.get(pk=response.data["id"])

    def availability_payload(self, offer, **overrides):
        payload = {
            "provider_vehicle_offer_id": offer.pk,
            "service_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
            "start_time": "09:00:00",
            "end_time": "11:00:00",
            "available_vehicle_count": 2,
            "availability_status": "AVAILABLE",
        }
        payload.update(overrides)
        return payload


class ProviderCoverageAPITests(ProviderAPITestBase):
    def test_create_update_and_reactivate_same_coverage(self):
        before = AuditLog.objects.count()

        response = self.client.post(
            "/api/providers/me/supplier-coverages/",
            {"supplier_id": self.supplier.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        coverage_id = response.data["id"]
        self.assertEqual(
            ProviderSupplierCoverage.objects.filter(
                provider=self.provider,
                supplier=self.supplier,
            ).count(),
            1,
        )

        response = self.client.patch(
            f"/api/providers/me/supplier-coverages/{coverage_id}/",
            {"coverage_status": "INACTIVE"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(
            f"/api/providers/me/supplier-coverages/{coverage_id}/",
            {"coverage_status": "ACTIVE"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            ProviderSupplierCoverage.objects.filter(
                provider=self.provider,
                supplier=self.supplier,
            ).count(),
            1,
        )
        self.assertGreaterEqual(AuditLog.objects.count(), before + 3)

    def test_provider_cannot_access_another_providers_coverage(self):
        other_provider = TransportProvider.objects.create(
            provider_code="TP-TEST-002",
            provider_name="Other Provider",
            provider_type="EXTERNAL",
            service_region="Other region",
            contact_email="other@example.test",
        )
        coverage = ProviderSupplierCoverage.objects.create(
            provider=other_provider,
            supplier=self.supplier,
            coverage_status="ACTIVE",
        )

        response = self.client.get(
            f"/api/providers/me/supplier-coverages/{coverage.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ProviderVehicleOfferAPITests(ProviderAPITestBase):
    @patch(
        "transportation.services._validate_model",
        side_effect=ValidationError("Forced validation failure"),
    )
    def test_new_vehicle_type_is_rolled_back_when_offer_creation_fails(
        self,
        mock_validate,
    ):
        before_vehicle_types = VehicleType.objects.count()
        before_offers = ProviderVehicleOffer.objects.count()
        before_audits = AuditLog.objects.count()

        response = self.client.post(
            "/api/providers/me/vehicle-offers/",
            {
                "new_vehicle_type": {
                    "vehicle_name": "Xe tải rollback",
                    "capacity_kg": "5000.000",
                    "description": "Rollback test",
                },
                "available_vehicle_count": 3,
                "fuel_type": "GASOLINE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(VehicleType.objects.count(), before_vehicle_types)
        self.assertEqual(ProviderVehicleOffer.objects.count(), before_offers)
        self.assertEqual(AuditLog.objects.count(), before_audits)
        mock_validate.assert_called_once()

    @patch(
        "transportation.services._generate_vehicle_type_code",
        side_effect=["VAN-TEST", "VTP-ABCDEF12"],
    )
    def test_retry_vehicle_type_code_when_collision(self, mock_generator):
        response = self.client.post(
            "/api/providers/me/vehicle-offers/",
            {
                "new_vehicle_type": {
                    "vehicle_name": "Xe tải retry",
                    "capacity_kg": "4000.000",
                    "description": "Test retry",
                },
                "available_vehicle_count": 2,
                "fuel_type": "GASOLINE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        vehicle_type = VehicleType.objects.get(
            pk=response.data["vehicle_type_id"]
        )

        self.assertEqual(vehicle_type.vehicle_code, "VTP-ABCDEF12")
        self.assertEqual(mock_generator.call_count, 2)

    def test_reject_new_vehicle_type_with_invalid_capacity(self):
        response = self.client.post(
            "/api/providers/me/vehicle-offers/",
            {
                "new_vehicle_type": {
                    "vehicle_name": "Xe tải không hợp lệ",
                    "capacity_kg": "0.000",
                    "description": "",
                },
                "available_vehicle_count": 3,
                "fuel_type": "GASOLINE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            VehicleType.objects.filter(
                vehicle_name="Xe tải không hợp lệ"
            ).count(),
            0,
        )

    def test_reject_offer_with_both_vehicle_type_choices(self):
        response = self.client.post(
            "/api/providers/me/vehicle-offers/",
            {
                "vehicle_type_id": self.vehicle_type.pk,
                "new_vehicle_type": {
                    "vehicle_name": "Xe tải mới",
                    "capacity_kg": "3000.000",
                    "description": "Test",
                },
                "available_vehicle_count": 3,
                "fuel_type": "GASOLINE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ProviderVehicleOffer.objects.count(), 0)
        self.assertEqual(
            VehicleType.objects.filter(vehicle_name="Xe tải mới").count(),
            0,
        )   

    def test_reject_offer_without_vehicle_type_choice(self):
        response = self.client.post(
            "/api/providers/me/vehicle-offers/",
            {
                "available_vehicle_count": 3,
                "fuel_type": "GASOLINE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ProviderVehicleOffer.objects.count(), 0)

    def test_create_offer_with_new_vehicle_type(self):
        before_vehicle_types = VehicleType.objects.count()
        before_audits = AuditLog.objects.count()

        response = self.client.post(
            "/api/providers/me/vehicle-offers/",
            {
                "new_vehicle_type": {
                    "vehicle_name": "Xe tải đông lạnh 5 tấn",
                    "capacity_kg": "5000.000",
                    "description": "Xe chuyên chở hàng đông lạnh",
                },
                "available_vehicle_count": 3,
                "fuel_type": "GASOLINE",
                "operating_start_time": "06:00:00",
                "operating_end_time": "20:00:00",
                "fixed_quote_vnd": "1500000.00",
                "estimated_cost_per_km_vnd": "12000.00",
                "is_active": True,
                "vehicle_note": "Xe có hệ thống làm lạnh",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        vehicle_type = VehicleType.objects.get(
            pk=response.data["vehicle_type_id"]
        )
        offer = ProviderVehicleOffer.objects.get(pk=response.data["id"])

        self.assertEqual(vehicle_type.vehicle_name, "Xe tải đông lạnh 5 tấn")
        self.assertEqual(str(vehicle_type.capacity_kg), "5000.000")
        self.assertTrue(vehicle_type.is_active)
        self.assertRegex(vehicle_type.vehicle_code, r"^VTP-[A-F0-9]{8}$")

        self.assertEqual(offer.provider_id, self.provider.pk)
        self.assertEqual(offer.vehicle_type_id, vehicle_type.pk)
        self.assertEqual(offer.available_vehicle_count, 3)
        self.assertEqual(offer.operating_start_time, time(6, 0))
        self.assertEqual(offer.operating_end_time, time(20, 0))
        self.assertEqual(str(offer.fixed_quote_vnd), "1500000.00")
        self.assertEqual(
            str(offer.estimated_cost_per_km_vnd),
            "12000.00",
        )

        self.assertEqual(
            VehicleType.objects.count(),
            before_vehicle_types + 1,
        )
        self.assertEqual(AuditLog.objects.count(), before_audits + 2)
        self.assertTrue(
            AuditLog.objects.filter(
                action="PROVIDER_VEHICLE_TYPE_CREATED",
                entity_type="VEHICLE_TYPE",
                entity_id=vehicle_type.pk,
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action="PROVIDER_VEHICLE_OFFER_CREATED",
                entity_type="PROVIDER_VEHICLE_OFFER",
                entity_id=offer.pk,
            ).exists()
        )    
    def test_create_offer_without_operating_hours_and_zero_rates(self):
        offer = self.create_offer(
            fixed_quote_vnd="0.00",
            estimated_cost_per_km_vnd="0.00",
        )

        self.assertIsNone(offer.operating_start_time)
        self.assertIsNone(offer.operating_end_time)
        self.assertEqual(str(offer.fixed_quote_vnd), "0.00")
        self.assertEqual(str(offer.estimated_cost_per_km_vnd), "0.00")

    def test_reject_only_one_operating_time(self):
        response = self.client.post(
            "/api/providers/me/vehicle-offers/",
            {
                "vehicle_type_id": self.vehicle_type.pk,
                "available_vehicle_count": 2,
                "fuel_type": "GASOLINE",
                "operating_start_time": "08:00:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_offer_capacity_cannot_be_reduced_below_effective_slot(self):
        offer = self.create_offer(
            operating_start_time="08:00:00",
            operating_end_time="18:00:00",
        )
        payload = self.availability_payload(offer)
        response = self.client.post(
            "/api/providers/me/availability/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.patch(
            f"/api/providers/me/vehicle-offers/{offer.pk}/",
            {"available_vehicle_count": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ProviderAvailabilityAPITests(ProviderAPITestBase):
    def test_availability_requires_offer_operating_hours(self):
        offer = self.create_offer()

        response = self.client.post(
            "/api/providers/me/availability/",
            self.availability_payload(offer),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_availability_and_reject_overlapping_window(self):
        offer = self.create_offer(
            operating_start_time="08:00:00",
            operating_end_time="18:00:00",
        )

        response = self.client.post(
            "/api/providers/me/availability/",
            self.availability_payload(offer),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.post(
            "/api/providers/me/availability/",
            self.availability_payload(
                offer,
                start_time="10:00:00",
                end_time="12:00:00",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(
            ProviderAvailability.objects.filter(
                provider_vehicle_offer=offer,
                source_mode="PROVIDER_PORTAL",
            ).count(),
            1,
        )

    def test_synthetic_availability_is_hidden_from_provider_portal(self):
        offer = self.create_offer(
            operating_start_time="08:00:00",
            operating_end_time="18:00:00",
        )
        ProviderAvailability.objects.create(
            provider_vehicle_offer=offer,
            service_date=timezone.localdate() - timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(11, 0),
            available_vehicle_count=2,
            availability_status="AVAILABLE",
            source_mode="SYNTHETIC_HISTORICAL_FIXTURE",
        )

        response = self.client.get("/api/providers/me/availability/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_availability_cannot_be_deleted_through_provider_api(self):
        offer = self.create_offer(
            operating_start_time="08:00:00",
            operating_end_time="18:00:00",
        )
        response = self.client.post(
            "/api/providers/me/availability/",
            self.availability_payload(offer),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.delete(
            f"/api/providers/me/availability/{response.data['id']}/"
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class ProviderCargoCompatibilityTests(ProviderAPITestBase):
    def test_missing_compatibility_is_not_treated_as_supported(self):
        self.assertFalse(
            is_vehicle_type_compatible(
                vehicle_type_id=self.vehicle_type.pk,
                cargo_category_id=self.cargo_category.pk,
            )
        )

    def test_explicit_compatibility_is_respected(self):
        VehicleCargoCompatibility.objects.create(
            vehicle_type=self.vehicle_type,
            cargo_category=self.cargo_category,
            is_supported=True,
            source="TEST",
        )

        self.assertTrue(
            is_vehicle_type_compatible(
                vehicle_type_id=self.vehicle_type.pk,
                cargo_category_id=self.cargo_category.pk,
            )
        )


class ProviderAvailabilityBoundaryTests(ProviderAPITestBase):
    def setUp(self):
        super().setUp()
        self.offer = self.create_offer(
            operating_start_time="08:00:00",
            operating_end_time="18:00:00",
        )

    def test_reject_availability_outside_offer_operating_hours(self):
        response = self.client.post(
            "/api/providers/me/availability/",
            self.availability_payload(
                self.offer,
                start_time="07:00:00",
                end_time="09:00:00",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unavailable_zero_count_is_allowed(self):
        response = self.client.post(
            "/api/providers/me/availability/",
            self.availability_payload(
                self.offer,
                available_vehicle_count=0,
                availability_status="UNAVAILABLE",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["available_vehicle_count"], 0)
        self.assertEqual(response.data["availability_status"], "UNAVAILABLE")

    def test_available_zero_count_is_rejected(self):
        response = self.client.post(
            "/api/providers/me/availability/",
            self.availability_payload(
                self.offer,
                available_vehicle_count=0,
                availability_status="AVAILABLE",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_adjacent_availability_windows_are_allowed(self):
        first = self.client.post(
            "/api/providers/me/availability/",
            self.availability_payload(
                self.offer,
                start_time="09:00:00",
                end_time="11:00:00",
            ),
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(
            "/api/providers/me/availability/",
            self.availability_payload(
                self.offer,
                start_time="11:00:00",
                end_time="13:00:00",
            ),
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)

    def test_synthetic_overlap_does_not_block_provider_portal_slot(self):
        service_date = timezone.localdate() + timedelta(days=1)
        ProviderAvailability.objects.create(
            provider_vehicle_offer=self.offer,
            service_date=service_date,
            start_time=time(9, 0),
            end_time=time(11, 0),
            available_vehicle_count=2,
            availability_status="AVAILABLE",
            source_mode="SYNTHETIC_NOVEMBER_DEMO",
        )

        response = self.client.post(
            "/api/providers/me/availability/",
            self.availability_payload(
                self.offer,
                service_date=service_date.isoformat(),
                start_time="09:00:00",
                end_time="11:00:00",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_operational_slot_blocks_offer_hours_reduction(self):
        response = self.client.post(
            "/api/providers/me/availability/",
            self.availability_payload(
                self.offer,
                start_time="09:00:00",
                end_time="11:00:00",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.patch(
            f"/api/providers/me/vehicle-offers/{self.offer.pk}/",
            {"operating_start_time": "10:00:00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_synthetic_slot_does_not_block_offer_hours_reduction(self):
        ProviderAvailability.objects.create(
            provider_vehicle_offer=self.offer,
            service_date=timezone.localdate() + timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(11, 0),
            available_vehicle_count=2,
            availability_status="AVAILABLE",
            source_mode="SYNTHETIC_NOVEMBER_DEMO",
        )

        response = self.client.patch(
            f"/api/providers/me/vehicle-offers/{self.offer.pk}/",
            {
                "operating_start_time": "10:00:00",
                "operating_end_time": "18:00:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def test_confirmed_import_availability_is_visible_to_provider(self):
        confirmed = ProviderAvailability.objects.create(
            provider_vehicle_offer=self.offer,
            service_date=timezone.localdate() + timedelta(days=2),
            start_time=time(9, 0),
            end_time=time(11, 0),
            available_vehicle_count=2,
            availability_status="AVAILABLE",
            source_mode="PROVIDER_CONFIRMED_IMPORT",
        )

        response = self.client.get("/api/providers/me/availability/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(confirmed.pk, [item["id"] for item in response.data])
        item = next(
            item for item in response.data if item["id"] == confirmed.pk
        )
        self.assertEqual(item["source_mode"], "PROVIDER_CONFIRMED_IMPORT")

    def test_confirmed_import_availability_can_be_updated_without_changing_source(self):
        confirmed = ProviderAvailability.objects.create(
            provider_vehicle_offer=self.offer,
            service_date=timezone.localdate() + timedelta(days=2),
            start_time=time(9, 0),
            end_time=time(11, 0),
            available_vehicle_count=2,
            availability_status="AVAILABLE",
            source_mode="PROVIDER_CONFIRMED_IMPORT",
        )

        response = self.client.patch(
            f"/api/providers/me/availability/{confirmed.pk}/",
            {
                "start_time": "10:00:00",
                "end_time": "12:00:00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        confirmed.refresh_from_db()
        self.assertEqual(confirmed.start_time, time(10, 0))
        self.assertEqual(confirmed.end_time, time(12, 0))
        self.assertEqual(
            confirmed.source_mode,
            "PROVIDER_CONFIRMED_IMPORT",
        )

    def test_confirmed_import_slot_blocks_overlapping_portal_creation(self):
        service_date = timezone.localdate() + timedelta(days=2)

        ProviderAvailability.objects.create(
            provider_vehicle_offer=self.offer,
            service_date=service_date,
            start_time=time(9, 0),
            end_time=time(11, 0),
            available_vehicle_count=2,
            availability_status="AVAILABLE",
            source_mode="PROVIDER_CONFIRMED_IMPORT",
        )

        response = self.client.post(
            "/api/providers/me/availability/",
            self.availability_payload(
                self.offer,
                service_date=service_date.isoformat(),
                start_time="10:00:00",
                end_time="12:00:00",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            ProviderAvailability.objects.filter(
                provider_vehicle_offer=self.offer,
                service_date=service_date,
                source_mode="PROVIDER_PORTAL",
            ).count(),
            0,
        )


class ProviderProfileAPITests(ProviderAPITestBase):
    def test_provider_can_update_service_region_and_audit_is_written(self):
        before = AuditLog.objects.count()

        response = self.client.patch(
            "/api/providers/me/",
            {"service_region": "Binh Duong"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.provider.refresh_from_db()
        self.assertEqual(self.provider.service_region, "Binh Duong")
        self.assertEqual(AuditLog.objects.count(), before + 1)

        audit = AuditLog.objects.latest("created_at")
        self.assertEqual(audit.action, "PROVIDER_PROFILE_UPDATED")
        self.assertEqual(audit.entity_type, "TRANSPORT_PROVIDER")

    def test_provider_cannot_update_protected_profile_fields(self):
        response = self.client.patch(
            "/api/providers/me/",
            {"provider_name": "Changed Name"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.provider.refresh_from_db()
        self.assertEqual(self.provider.provider_name, "Test Provider")

class ProviderVehicleTypeAPITests(ProviderAPITestBase):
    def test_provider_can_list_active_vehicle_types(self):
        inactive_type = VehicleType.objects.create(
            vehicle_code="VAN-INACTIVE",
            vehicle_name="Inactive Van",
            capacity_kg="2000.000",
            is_active=False,
        )

        response = self.client.get(
            "/api/providers/vehicle-types/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_ids = [item["id"] for item in response.data]

        self.assertIn(self.vehicle_type.pk, returned_ids)
        self.assertNotIn(inactive_type.pk, returned_ids)

        item = next(
            item for item in response.data
            if item["id"] == self.vehicle_type.pk
        )
        self.assertEqual(item["vehicle_code"], "VAN-TEST")
        self.assertEqual(item["vehicle_name"], "Test Van")

    def test_purchasing_staff_cannot_list_vehicle_types(self):
        user = User.objects.create_user(
            email="buyer-vehicle-type@example.test",
            password="Strong-test-password-123",
            full_name="Test Purchasing Staff",
        )
        role, _ = Role.objects.get_or_create(
            code=RoleCode.PURCHASING_STAFF,
            defaults={"name": "Purchasing Staff"},
        )
        UserRole.objects.create(user=user, role=role)

        self.client.force_authenticate(user=user)

        response = self.client.get(
            "/api/providers/vehicle-types/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_list_vehicle_types(self):
        user = User.objects.create_user(
            email="manager-vehicle-type@example.test",
            password="Strong-test-password-123",
            full_name="Test Manager",
        )
        role, _ = Role.objects.get_or_create(
            code=RoleCode.MANAGER,
            defaults={"name": "Manager"},
        )
        UserRole.objects.create(user=user, role=role)

        self.client.force_authenticate(user=user)

        response = self.client.get(
            "/api/providers/vehicle-types/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_supplier_cannot_list_vehicle_types(self):
        user = User.objects.create_user(
            email="supplier-vehicle-type@example.test",
            password="Strong-test-password-123",
            full_name="Test Supplier",
        )
        role, _ = Role.objects.get_or_create(
            code=RoleCode.SUPPLIER,
            defaults={"name": "Supplier"},
        )
        UserRole.objects.create(user=user, role=role)

        ExternalUserAccess.objects.create(
            user=user,
            actor_type="SUPPLIER",
            supplier=self.supplier,
        )

        self.client.force_authenticate(user=user)

        response = self.client.get(
            "/api/providers/vehicle-types/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)