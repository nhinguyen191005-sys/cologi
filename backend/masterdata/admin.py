from django.contrib import admin

from .models import Supplier, TransportProvider


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        "supplier_code",
        "supplier_name",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = (
        "supplier_code",
        "supplier_name",
        "contact_name",
    )
    ordering = ("supplier_code",)


@admin.register(TransportProvider)
class TransportProviderAdmin(admin.ModelAdmin):
    list_display = (
        "provider_code",
        "provider_name",
        "provider_type",
        "is_active",
    )
    list_filter = ("provider_type", "is_active")
    search_fields = (
        "provider_code",
        "provider_name",
    )
    ordering = ("provider_code",)
