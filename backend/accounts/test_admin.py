from django.contrib import admin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.test import TestCase

from .admin import (
    CoLogiUserChangeForm,
    CoLogiUserCreationForm,
    UserAdmin,
    UserOutletAccessAdmin,
)
from .models import User, UserOutletAccess


class CoLogiUserAdminFormTests(TestCase):
    def test_creation_form_hashes_password_and_does_not_grant_technical_privileges(self):
        form = CoLogiUserCreationForm(
            data={
                "email": "  purchasing@example.com ",
                "full_name": " Purchasing Staff ",
                "password1": "Strong-test-password-123",
                "password2": "Strong-test-password-123",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        self.assertEqual(user.email, "purchasing@example.com")
        self.assertEqual(user.full_name, "Purchasing Staff")
        self.assertTrue(user.check_password("Strong-test-password-123"))
        self.assertNotEqual(user.password, "Strong-test-password-123")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_creation_form_rejects_password_mismatch(self):
        form = CoLogiUserCreationForm(
            data={
                "email": "purchasing@example.com",
                "full_name": "Purchasing Staff",
                "password1": "Strong-test-password-123",
                "password2": "Different-password-123",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_change_form_uses_read_only_password_hash_and_excludes_technical_flags(self):
        user = User(
            email="purchasing@example.com",
            full_name="Purchasing Staff",
        )
        user.set_password("Strong-test-password-123")

        form = CoLogiUserChangeForm(instance=user)

        self.assertIsInstance(form.fields["password"], ReadOnlyPasswordHashField)
        self.assertNotIn("is_staff", form.fields)
        self.assertNotIn("is_superuser", form.fields)

    def test_user_admin_is_registered_and_technical_flags_are_readonly(self):
        registered_admin = admin.site._registry[User]

        self.assertIsInstance(registered_admin, UserAdmin)
        self.assertIn("is_staff", registered_admin.readonly_fields)
        self.assertIn("is_superuser", registered_admin.readonly_fields)
        self.assertIn("password", registered_admin.fieldsets[0][1]["fields"])

    def test_user_outlet_access_admin_is_registered(self):
        registered_admin = admin.site._registry[UserOutletAccess]

        self.assertIsInstance(registered_admin, UserOutletAccessAdmin)
        self.assertIn("user", registered_admin.list_display)
        self.assertIn("outlet", registered_admin.list_display)
        self.assertIn("is_active", registered_admin.list_display)
