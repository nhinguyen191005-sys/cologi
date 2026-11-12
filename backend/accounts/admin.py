from django.contrib import admin

from .models import (
    ExternalUserAccess,
    Role,
    User,
    UserRole,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "full_name",
        "is_active",
        "is_staff",
        "is_superuser",
    )
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "full_name")
    ordering = ("email",)
    readonly_fields = ("last_login", "created_at", "updated_at")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("code",)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "assigned_at", "assigned_by")
    list_filter = ("role",)
    search_fields = ("user__email", "user__full_name", "role__code")
    autocomplete_fields = ("user", "role", "assigned_by")


@admin.register(ExternalUserAccess)
class ExternalUserAccessAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "actor_type",
        "supplier",
        "provider",
        "is_active",
    )
    list_filter = ("actor_type", "is_active")
    search_fields = (
        "user__email",
        "supplier__supplier_code",
        "provider__provider_code",
    )
    autocomplete_fields = ("user", "supplier", "provider")
