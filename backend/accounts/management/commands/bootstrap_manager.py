import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from accounts.models import AuditLog, Role, RoleCode, User, UserRole


BOOTSTRAP_SOURCE = "approved_initial_manager_bootstrap"


class Command(BaseCommand):
    help = (
        "Bootstrap the first CoLogi Manager. "
        "Default mode is read-only."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            required=True,
            help="Email of the account receiving the initial Manager role.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Create the initial Manager role after explicit confirmation.",
        )

    def _get_plan(self, email):
        user = User.objects.filter(email__iexact=email.strip()).first()

        if user is None:
            raise CommandError(f"Không tìm thấy tài khoản: {email}")

        if not user.is_active:
            raise CommandError("Không thể bootstrap tài khoản đã bị vô hiệu hóa.")

        manager_role = Role.objects.filter(
            code=RoleCode.MANAGER,
            is_active=True,
        ).first()

        if manager_role is None:
            raise CommandError("Không tìm thấy Role MANAGER đang active.")

        active_assignment = (
            UserRole.objects
            .select_related("role")
            .filter(user=user, is_active=True)
            .first()
        )

        if active_assignment:
            if active_assignment.role.code == RoleCode.MANAGER:
                return user, manager_role, "UNCHANGED"

            raise CommandError(
                f"Tài khoản đã có business role "
                f"{active_assignment.role.code}; không tự động thay đổi."
            )

        other_managers = UserRole.objects.filter(
            is_active=True,
            role__code=RoleCode.MANAGER,
            role__is_active=True,
            user__is_active=True,
        ).exclude(user=user)

        if other_managers.exists():
            raise CommandError(
                "Đã tồn tại Manager active khác. "
                "Bootstrap lần đầu bị từ chối."
            )

        return user, manager_role, "CREATE"

    def handle(self, *args, **options):
        email = options["email"]

        user, manager_role, status = self._get_plan(email)

        self.stdout.write("\n=== MANAGER BOOTSTRAP PLAN ===")
        self.stdout.write(f"Target: {user.email}")
        self.stdout.write(f"User ID: {user.pk}")
        self.stdout.write(f"Role: {manager_role.code}")
        self.stdout.write(f"Action: {status}")
        self.stdout.write("assigned_by: NULL")
        self.stdout.write(f"Audit action: BOOTSTRAP_MANAGER")
        self.stdout.write(f"Bootstrap source: {BOOTSTRAP_SOURCE}")

        if status == "UNCHANGED":
            self.stdout.write("\nAccount is already an active Manager.")
            self.stdout.write("Database writes: NONE")
            return

        if not options["apply"]:
            self.stdout.write("\nDRY-RUN COMPLETE")
            self.stdout.write("Database writes: NONE")
            return

        if not sys.stdin.isatty():
            raise CommandError(
                "Chế độ --apply cần terminal tương tác để xác nhận."
            )

        confirmation = input(
            '\nNhập chính xác "BOOTSTRAP MANAGER" để xác nhận: '
        )

        if confirmation != "BOOTSTRAP MANAGER":
            raise CommandError(
                "Đã hủy bootstrap. Database không thay đổi."
            )

        try:
            with transaction.atomic():
                user, manager_role, fresh_status = self._get_plan(email)

                if fresh_status == "UNCHANGED":
                    self.stdout.write(
                        "Tài khoản đã được bootstrap trước đó; không ghi thêm."
                    )
                    return

                assignment = UserRole(
                    user=user,
                    role=manager_role,
                    is_active=True,
                    assigned_by=None,
                )
                assignment.full_clean()
                assignment.save(force_insert=True)

                AuditLog.objects.create(
                    actor_user=None,
                    action="BOOTSTRAP_MANAGER",
                    entity_type="USER_ROLE",
                    entity_id=str(user.pk),
                    old_values={
                        "active_role": None,
                    },
                    new_values={
                        "user_role_id": assignment.pk,
                        "role_id": manager_role.pk,
                        "role_code": manager_role.code,
                        "assigned_by_id": None,
                        "bootstrap_source": BOOTSTRAP_SOURCE,
                    },
                    ip_address=None,
                )

        except IntegrityError as exc:
            raise CommandError(
                "Lỗi ràng buộc database. Đã rollback bootstrap."
            ) from exc

        self.stdout.write("\nBOOTSTRAP SUCCESS")
        self.stdout.write(f"User: {user.email}")
        self.stdout.write(f"UserRole ID: {assignment.pk}")
        self.stdout.write("Audit action: BOOTSTRAP_MANAGER")
        self.stdout.write("Database transaction: COMMITTED")
