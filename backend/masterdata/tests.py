from django.db import IntegrityError, transaction
from django.test import TestCase
from decimal import Decimal
from django.db.models.deletion import ProtectedError


from .models import (
    CargoCategory,
    Item,
    Outlet,
    Supplier,
    SupplierItem,
    TransportProvider,
    Hub,
    VehicleCargoCompatibility,
    VehicleType,
)


class SupplierTests(TestCase):
    def test_supplier_uses_dataset_table_name(self):
        self.assertEqual(Supplier._meta.db_table, "suppliers")

    def test_supplier_can_have_optional_contact_fields(self):
        supplier = Supplier.objects.create(
            supplier_code="SUP-TEST-001",
            supplier_name="Test Supplier",
        )

        self.assertIsNone(supplier.contact_name)
        self.assertIsNone(supplier.phone)
        self.assertIsNone(supplier.email)
        self.assertIsNone(supplier.address)
        self.assertTrue(supplier.is_active)

    def test_supplier_code_must_be_unique(self):
        Supplier.objects.create(
            supplier_code="SUP-TEST-002",
            supplier_name="Supplier One",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Supplier.objects.create(
                    supplier_code="SUP-TEST-002",
                    supplier_name="Supplier Two",
                )


class TransportProviderTests(TestCase):
    def test_provider_uses_dataset_table_name(self):
        self.assertEqual(
            TransportProvider._meta.db_table,
            "transport_providers",
        )

    def test_provider_can_store_v7_mvp_fields(self):
        provider = TransportProvider.objects.create(
            provider_code="TP-TEST-001",
            provider_name="Test Transport Provider",
            provider_type="EXTERNAL",
            service_region="Test service region",
            contact_email="carrier@example.test",
        )

        self.assertEqual(provider.provider_type, "EXTERNAL")
        self.assertEqual(provider.contact_email, "carrier@example.test")
        self.assertTrue(provider.is_active)

    def test_provider_code_must_be_unique(self):
        TransportProvider.objects.create(
            provider_code="TP-TEST-002",
            provider_name="Provider One",
            provider_type="EXTERNAL",
            service_region="Test region",
            contact_email="one@example.test",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TransportProvider.objects.create(
                    provider_code="TP-TEST-002",
                    provider_name="Provider Two",
                    provider_type="EXTERNAL",
                    service_region="Other region",
                    contact_email="two@example.test",
                )

class OutletTests(TestCase):
    def test_outlet_uses_dataset_table_name(self):
        self.assertEqual(Outlet._meta.db_table, "outlets")

    def test_outlet_optional_fields_and_active_default(self):
        outlet = Outlet.objects.create(
            outlet_code="OUT-TEST-001",
            outlet_name="Test Outlet",
            address="Da Nang",
        )

        self.assertIsNone(outlet.contact_name)
        self.assertIsNone(outlet.phone)
        self.assertTrue(outlet.is_active)

    def test_outlet_code_must_be_unique(self):
        Outlet.objects.create(
            outlet_code="OUT-TEST-002",
            outlet_name="Outlet One",
            address="Da Nang",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Outlet.objects.create(
                    outlet_code="OUT-TEST-002",
                    outlet_name="Outlet Two",
                    address="Da Nang",
                )


class CargoCategoryTests(TestCase):
    def test_cargo_category_uses_dataset_table_name(self):
        self.assertEqual(
            CargoCategory._meta.db_table,
            "cargo_categories",
        )

    def test_cargo_category_code_must_be_unique(self):
        CargoCategory.objects.create(
            category_code="CARGO-TEST-001",
            category_name="Test Category",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CargoCategory.objects.create(
                    category_code="CARGO-TEST-001",
                    category_name="Duplicate Category",
                )

class ItemTests(TestCase):
    def setUp(self):
        self.category = CargoCategory.objects.create(
            category_code="CAT-ITEM-TEST",
            category_name="Item Test Category",
        )

    def test_item_uses_expected_table_name(self):
        self.assertEqual(Item._meta.db_table, "items")

    def test_item_stores_sku_and_category(self):
        item = Item.objects.create(
            item_code="ITM-TEST-001",
            item_name="Test SKU",
            cargo_category=self.category,
            weight_unit="KG",
        )

        self.assertEqual(item.cargo_category_id, self.category.pk)
        self.assertEqual(item.weight_unit, "KG")
        self.assertIsNone(item.item_description)
        self.assertTrue(item.is_active)

    def test_item_code_must_be_unique(self):
        Item.objects.create(
            item_code="ITM-TEST-002",
            item_name="SKU One",
            cargo_category=self.category,
            weight_unit="KG",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Item.objects.create(
                    item_code="ITM-TEST-002",
                    item_name="SKU Duplicate",
                    cargo_category=self.category,
                    weight_unit="KG",
                )

    def test_cargo_category_cannot_be_deleted_while_referenced(self):
        from django.db.models.deletion import ProtectedError

        Item.objects.create(
            item_code="ITM-TEST-003",
            item_name="Protected SKU",
            cargo_category=self.category,
            weight_unit="KG",
        )

        with self.assertRaises(ProtectedError):
            self.category.delete()


class SupplierItemTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            supplier_code="SUP-SITEM-001",
            supplier_name="Supplier Item Test",
        )
        self.category = CargoCategory.objects.create(
            category_code="CAT-SITEM-TEST",
            category_name="Supplier Item Test Category",
        )
        self.item = Item.objects.create(
            item_code="ITM-SITEM-001",
            item_name="Supplier Item Test SKU",
            cargo_category=self.category,
            weight_unit="KG",
        )

    def create_offer(self, supplier=None, item=None, **overrides):
        values = {
            "supplier": supplier or self.supplier,
            "item": item or self.item,
            "unit_price_vnd_per_kg": "24800.00",
            "max_daily_supply_kg": "12800.000",
            "lead_time_hours": 8,
            "minimum_order_kg": "5.000",
        }
        values.update(overrides)
        return SupplierItem.objects.create(**values)

    def test_supplier_item_uses_expected_table_name(self):
        self.assertEqual(
            SupplierItem._meta.db_table,
            "supplier_items",
        )

    def test_supplier_item_stores_source_fields(self):
        offer = self.create_offer()

        self.assertEqual(offer.supplier_id, self.supplier.pk)
        self.assertEqual(offer.item_id, self.item.pk)
        self.assertEqual(str(offer.unit_price_vnd_per_kg), "24800.00")
        self.assertEqual(str(offer.max_daily_supply_kg), "12800.000")
        self.assertEqual(offer.lead_time_hours, 8)
        self.assertEqual(str(offer.minimum_order_kg), "5.000")
        self.assertEqual(offer.offer_status, "ACTIVE")
        self.assertIsNotNone(offer.updated_at)

    def test_supplier_item_pair_must_be_unique(self):
        self.create_offer()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_offer()

    def test_same_item_can_be_offered_by_multiple_suppliers(self):
        second_supplier = Supplier.objects.create(
            supplier_code="SUP-SITEM-002",
            supplier_name="Second Supplier",
        )

        first_offer = self.create_offer()
        second_offer = self.create_offer(supplier=second_supplier)

        self.assertEqual(first_offer.item_id, second_offer.item_id)
        self.assertNotEqual(
            first_offer.supplier_id,
            second_offer.supplier_id,
        )

    def test_supplier_can_offer_multiple_items(self):
        second_item = Item.objects.create(
            item_code="ITM-SITEM-002",
            item_name="Second SKU",
            cargo_category=self.category,
            weight_unit="KG",
        )

        first_offer = self.create_offer()
        second_offer = self.create_offer(item=second_item)

        self.assertEqual(
            first_offer.supplier_id,
            second_offer.supplier_id,
        )
        self.assertNotEqual(
            first_offer.item_id,
            second_offer.item_id,
        )

    def test_zero_unit_price_is_allowed(self):
            offer = self.create_offer(unit_price_vnd_per_kg="0")
            offer.refresh_from_db()

            self.assertEqual(
                offer.unit_price_vnd_per_kg,
                Decimal("0"),
            )

    def test_negative_unit_price_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_offer(unit_price_vnd_per_kg="-1")

    def test_null_max_daily_supply_is_allowed(self):
        offer = self.create_offer(max_daily_supply_kg=None)
        offer.refresh_from_db()

        self.assertIsNone(offer.max_daily_supply_kg)

    def test_max_daily_supply_must_be_positive_if_set(self):
        for value in ("0", "-1"):
            with self.subTest(value=value):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        self.create_offer(max_daily_supply_kg=value)

    def test_null_lead_time_is_allowed(self):
        offer = self.create_offer(lead_time_hours=None)
        offer.refresh_from_db()

        self.assertIsNone(offer.lead_time_hours)

    def test_zero_lead_time_is_allowed(self):
        offer = self.create_offer(lead_time_hours=0)
        offer.refresh_from_db()

        self.assertEqual(offer.lead_time_hours, 0)

    def test_lead_time_cannot_be_negative(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_offer(lead_time_hours=-1)

    def test_null_minimum_order_is_allowed(self):
        offer = self.create_offer(minimum_order_kg=None)
        offer.refresh_from_db()

        self.assertIsNone(offer.minimum_order_kg)

    def test_zero_minimum_order_is_allowed(self):
        offer = self.create_offer(minimum_order_kg="0")
        offer.refresh_from_db()

        self.assertEqual(
            offer.minimum_order_kg,
            Decimal("0"),
        )

    def test_minimum_order_cannot_be_negative(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_offer(minimum_order_kg="-1")

    def test_active_offer_status_is_allowed(self):
        offer = self.create_offer(offer_status="ACTIVE")
        offer.refresh_from_db()

        self.assertEqual(offer.offer_status, "ACTIVE")

    def test_inactive_offer_status_is_allowed(self):
        offer = self.create_offer(offer_status="INACTIVE")
        offer.refresh_from_db()

        self.assertEqual(offer.offer_status, "INACTIVE")

    def test_unknown_offer_status_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_offer(offer_status="PENDING")


class HubTests(TestCase):
    def test_hub_uses_v7_table_and_fields(self):
        self.assertEqual(Hub._meta.db_table, "hubs")
        self.assertEqual(
            {field.name for field in Hub._meta.fields},
            {
                "id",
                "hub_code",
                "hub_name",
                "address",
                "is_active",
                "created_at",
            },
        )

    def test_hub_defaults_to_active_and_has_created_at(self):
        hub = Hub.objects.create(
            hub_code="HUB-TEST-001",
            hub_name="Test Hub",
            address="Da Nang",
        )

        self.assertTrue(hub.is_active)
        self.assertIsNotNone(hub.created_at)

    def test_hub_code_must_be_unique(self):
        Hub.objects.create(
            hub_code="HUB-TEST-002",
            hub_name="Hub One",
            address="Da Nang",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Hub.objects.create(
                    hub_code="HUB-TEST-002",
                    hub_name="Hub Two",
                    address="Hue",
                )

    def test_hub_can_be_soft_deactivated(self):
        hub = Hub.objects.create(
            hub_code="HUB-TEST-003",
            hub_name="Inactive Hub",
            address="Da Nang",
        )

        hub.is_active = False
        hub.save(update_fields=("is_active",))
        hub.refresh_from_db()

        self.assertFalse(hub.is_active)


class VehicleTypeTests(TestCase):
    def test_vehicle_type_uses_v7_table_and_fields(self):
        self.assertEqual(VehicleType._meta.db_table, "vehicle_types")
        self.assertEqual(
            {field.name for field in VehicleType._meta.fields},
            {
                "id",
                "vehicle_code",
                "vehicle_name",
                "capacity_kg",
                "description",
                "is_active",
            },
        )

    def test_vehicle_type_stores_capacity_and_optional_description(self):
        vehicle = VehicleType.objects.create(
            vehicle_code="VEH-TEST-001",
            vehicle_name="Test Truck",
            capacity_kg=Decimal("2500.000"),
        )

        self.assertEqual(vehicle.capacity_kg, Decimal("2500.000"))
        self.assertIsNone(vehicle.description)
        self.assertTrue(vehicle.is_active)

    def test_vehicle_code_must_be_unique(self):
        VehicleType.objects.create(
            vehicle_code="VEH-TEST-002",
            vehicle_name="Truck One",
            capacity_kg=1000,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VehicleType.objects.create(
                    vehicle_code="VEH-TEST-002",
                    vehicle_name="Truck Two",
                    capacity_kg=2000,
                )

    def test_vehicle_capacity_must_be_positive(self):
        for value in ("0", "-1"):
            with self.subTest(value=value):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        VehicleType.objects.create(
                            vehicle_code=f"VEH-INVALID-{value}",
                            vehicle_name="Invalid Truck",
                            capacity_kg=value,
                        )

    def test_vehicle_type_can_be_soft_deactivated(self):
        vehicle = VehicleType.objects.create(
            vehicle_code="VEH-TEST-003",
            vehicle_name="Inactive Truck",
            capacity_kg=1000,
        )

        vehicle.is_active = False
        vehicle.save(update_fields=("is_active",))
        vehicle.refresh_from_db()

        self.assertFalse(vehicle.is_active)


class VehicleCargoCompatibilityTests(TestCase):
    def setUp(self):
        self.vehicle = VehicleType.objects.create(
            vehicle_code="VEH-COMP-001",
            vehicle_name="Compatibility Truck",
            capacity_kg=2500,
        )
        self.category = CargoCategory.objects.create(
            category_code="CAT-COMP-001",
            category_name="Compatibility Cargo",
        )

    def create_compatibility(self, **overrides):
        values = {
            "vehicle_type": self.vehicle,
            "cargo_category": self.category,
            "is_supported": True,
            "source": "V7",
        }
        values.update(overrides)
        return VehicleCargoCompatibility.objects.create(**values)

    def test_compatibility_uses_v7_table_and_composite_pk(self):
        model = VehicleCargoCompatibility

        self.assertEqual(
            model._meta.db_table,
            "vehicle_cargo_compatibility",
        )
        self.assertEqual(
            tuple(model._meta.pk.field_names),
            ("vehicle_type", "cargo_category"),
        )

    def test_compatibility_stores_supported_and_source(self):
        compatibility = self.create_compatibility()

        self.assertTrue(compatibility.is_supported)
        self.assertEqual(compatibility.source, "V7")
        self.assertEqual(
            compatibility.pk,
            (self.vehicle.pk, self.category.pk),
        )

    def test_compatibility_pair_must_be_unique(self):
        self.create_compatibility()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_compatibility()

    def test_same_vehicle_can_have_multiple_cargo_categories(self):
        second_category = CargoCategory.objects.create(
            category_code="CAT-COMP-002",
            category_name="Second Cargo",
        )

        first = self.create_compatibility()
        second = self.create_compatibility(
            cargo_category=second_category,
        )

        self.assertEqual(first.vehicle_type_id, second.vehicle_type_id)
        self.assertNotEqual(
            first.cargo_category_id,
            second.cargo_category_id,
        )

    def test_same_cargo_can_be_supported_by_multiple_vehicles(self):
        second_vehicle = VehicleType.objects.create(
            vehicle_code="VEH-COMP-002",
            vehicle_name="Second Truck",
            capacity_kg=5000,
        )

        first = self.create_compatibility()
        second = self.create_compatibility(vehicle_type=second_vehicle)

        self.assertEqual(first.cargo_category_id, second.cargo_category_id)
        self.assertNotEqual(
            first.vehicle_type_id,
            second.vehicle_type_id,
        )

    def test_vehicle_type_cannot_be_deleted_while_referenced(self):
        self.create_compatibility()

        with self.assertRaises(ProtectedError):
            self.vehicle.delete()

    def test_cargo_category_cannot_be_deleted_while_compatibility_references_it(self):
        self.create_compatibility()

        with self.assertRaises(ProtectedError):
            self.category.delete()

    def test_source_can_be_null(self):
        compatibility = self.create_compatibility(source=None)

        self.assertIsNone(compatibility.source)

    def test_unsupported_pair_is_stored(self):
        compatibility = self.create_compatibility(is_supported=False)

        self.assertFalse(compatibility.is_supported)
