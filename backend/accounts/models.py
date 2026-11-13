from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone


class RoleCode(models.TextChoices):
    PURCHASING_STAFF = "PURCHASING_STAFF", "Purchasing Staff"
    SUPPLIER = "SUPPLIER", "Supplier"
    TRANSPORT_PROVIDER = "TRANSPORT_PROVIDER", "Transport Provider"
    MANAGER = "MANAGER", "Manager"


ROLE_CODE_VALUES = tuple(code.value for code in RoleCode)


class UserManager(BaseUserManager):
    """Create and retrieve users using normalized email addresses."""

    use_in_migrations = True

    def normalize_email_address(self, email):
        if not email:
            raise ValueError("An email address is required.")

        normalized = self.normalize_email(email).strip().lower()
        validate_email(normalized)
        return normalized

    def get_by_natural_key(self, username):
        email = self.normalize_email_address(username)
        return self.get(email=email)

    def _create_user(self, email, password, **extra_fields):
        email = self.normalize_email_address(email)

        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        if password is None:
            raise ValueError("A password is required for a superuser.")

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(max_length=254, unique=True)
    full_name = models.CharField(max_length=255)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Keep Django's authentication field while matching Dataset column naming.
    last_login = models.DateTimeField(
        blank=True,
        null=True,
        db_column="last_login_at",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "users"
        ordering = ("email",)
        constraints = [
            models.CheckConstraint(
                condition=Q(email=Lower("email")),
                name="accounts_user_email_lowercase",
            ),
        ]

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()
        if self.full_name:
            self.full_name = self.full_name.strip()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        if self.full_name:
            self.full_name = self.full_name.strip()
        super().save(*args, **kwargs)

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name

    def __str__(self):
        return f"{self.full_name} <{self.email}>"


class Role(models.Model):
    code = models.CharField(
        max_length=32,
        choices=RoleCode.choices,
        unique=True,
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "roles"
        ordering = ("code",)
        constraints = [
            models.CheckConstraint(
                condition=Q(code__in=ROLE_CODE_VALUES),
                name="accounts_role_valid_code",
            ),
        ]

    def __str__(self):
        return self.code


class UserRole(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="user_roles",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="role_assignments",
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="role_assignments_made",
    )

    class Meta:
        db_table = "user_roles"
        ordering = ("user_id", "role_id")
        constraints = [
            models.UniqueConstraint(
                fields=("user",),
                name="acc_userrole_user_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(assigned_by__isnull=True)
                    | ~models.Q(assigned_by=models.F("user"))
                ),
                name="acc_userrole_no_self_assign",
            ),
        ]
        indexes = [
            models.Index(
                fields=("role", "user"),
                name="acc_userrole_role_user_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.role_id and not self.role.is_active:
            raise ValidationError({
                "role": "Cannot assign an inactive role."
            })
        if (
            self.user_id
            and self.assigned_by_id is not None
            and self.assigned_by_id == self.user_id
        ):
            raise ValidationError({
                "assigned_by": "Users cannot assign a business role to themselves."
            })

    def __str__(self):
        return f"{self.user_id} -> {self.role.code}"

class AuditLog(models.Model):
    """
    Shared audit trail for important business mutations.

    Audit records are append-only. Business services create records;
    normal application flows must not update or delete existing records.
    """

    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_logs",
        db_index=False,
    )
    action = models.CharField(max_length=50)
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=100)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(
        protocol="both",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ("-created_at", "-pk")
        indexes = [
            models.Index(
                fields=("entity_type", "entity_id", "created_at"),
                name="acc_audit_entity_time_idx",
            ),
            models.Index(
                fields=("actor_user", "created_at"),
                name="acc_audit_actor_time_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Audit records cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit records cannot be deleted.")

    def __str__(self):
        return (
            f"{self.action} {self.entity_type}:{self.entity_id} "
            f"by {self.actor_user_id or 'system'}"
        )


class ExternalActorType(models.TextChoices):
    SUPPLIER = "SUPPLIER", "Supplier"
    TRANSPORT_PROVIDER = "TRANSPORT_PROVIDER", "Transport Provider"


class ExternalUserAccess(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="external_accesses",
    )
    actor_type = models.CharField(
        max_length=30,
        choices=ExternalActorType.choices,
    )
    supplier = models.ForeignKey(
        "masterdata.Supplier",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="external_user_accesses",
    )
    provider = models.ForeignKey(
        "masterdata.TransportProvider",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="external_user_accesses",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "external_user_access"
        ordering = ("user_id", "actor_type")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "actor_type"),
                name="acc_ext_access_user_type_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        actor_type=ExternalActorType.SUPPLIER,
                        supplier__isnull=False,
                        provider__isnull=True,
                    )
                    | Q(
                        actor_type=ExternalActorType.TRANSPORT_PROVIDER,
                        supplier__isnull=True,
                        provider__isnull=False,
                    )
                ),
                name="acc_ext_access_valid_scope",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.actor_type == ExternalActorType.SUPPLIER:
            if not self.supplier_id or self.provider_id:
                errors["supplier"] = (
                    "SUPPLIER access requires exactly one supplier "
                    "and no provider."
                )

        elif self.actor_type == ExternalActorType.TRANSPORT_PROVIDER:
            if not self.provider_id or self.supplier_id:
                errors["provider"] = (
                    "TRANSPORT_PROVIDER access requires exactly one "
                    "provider and no supplier."
                )

        if (
            self.user_id
            and self.actor_type in ExternalActorType.values
            and not UserRole.objects.filter(
                user_id=self.user_id,
                role__code=self.actor_type,
                role__is_active=True,
            ).exists()
        ):
            errors["actor_type"] = (
                "External access actor_type must match an active "
                "role assigned to this user."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Enforce cross-table role matching on normal ORM writes.
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        target = self.supplier or self.provider
        return f"{self.user_id} -> {self.actor_type} -> {target}"

class UserOutletAccess(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="outlet_accesses",
    )
    outlet = models.ForeignKey(
        "masterdata.Outlet",
        on_delete=models.PROTECT,
        related_name="user_accesses",
    )
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(default=timezone.now)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outlet_accesses_granted",
    )

    class Meta:
        db_table = "user_outlet_access"
        ordering = ("user_id", "outlet_id")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "outlet"),
                name="acc_user_outlet_access_uniq",
            ),
        ]

    def clean(self):
        super().clean()

        # An active access must belong to a user with an active
        # PURCHASING_STAFF role.
        if self.is_active and self.user_id:
            has_purchasing_role = UserRole.objects.filter(
                user_id=self.user_id,
                role__code=RoleCode.PURCHASING_STAFF,
                role__is_active=True,
            ).exists()

            if not has_purchasing_role:
                raise ValidationError({
                    "user": (
                        "Active outlet access requires an active "
                        "PURCHASING_STAFF role."
                    )
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_id} -> Outlet {self.outlet_id}"