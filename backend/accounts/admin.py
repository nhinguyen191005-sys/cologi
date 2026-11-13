from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import (
    ExternalUserAccess,
    Role,
    User,
    UserOutletAccess,
    UserRole,
)


class CoLogiUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "full_name", "is_active")


class CoLogiUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = ("email", "full_name", "is_active", "groups", "user_permissions")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = CoLogiUserChangeForm
    add_form = CoLogiUserCreationForm

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
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (
            "Account",
            {"fields": ("email", "password", "full_name")},
        ),
        (
            "Status & Technical Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser")},
        ),
        (
            "Django Permissions",
            {"fields": ("groups", "user_permissions")},
        ),
        (
            "Dates",
            {"fields": ("last_login", "created_at", "updated_at")},
        ),
    )

    add_fieldsets = (
        (
            "Create User",
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "is_active",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    readonly_fields = (
        "last_login",
        "created_at",
        "updated_at",
        "is_staff",
        "is_superuser",
    )


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


@admin.register(UserOutletAccess)
class UserOutletAccessAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "outlet",
        "is_active",
        "assigned_at",
        "assigned_by",
    )
    list_filter = ("is_active", "outlet")
    search_fields = (
        "user__email",
        "user__full_name",
        "outlet__outlet_code",
        "outlet__outlet_name",
    )
    autocomplete_fields = ("user", "assigned_by")
    readonly_fields = ("assigned_at",)
