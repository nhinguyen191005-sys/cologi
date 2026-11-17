from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from demands.management.commands.import_v7_demo import (
    assert_safe_import_database,
)


@override_settings(
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "cologi_cp08_dev",
        }
    },
    DATABASE_ROUTERS=[],
)
class SafeImportDatabaseGuardTests(SimpleTestCase):
    def setUp(self):
        self.env_patcher = patch.dict(
            "os.environ",
            {"POSTGRES_DB": "cologi_cp08_dev"},
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = ("cologi_cp08_dev",)

        self.connection_patcher = patch(
            "demands.management.commands.import_v7_demo.connections"
        )
        self.connections = self.connection_patcher.start()
        self.addCleanup(self.connection_patcher.stop)
        self.connections.__getitem__.return_value = self.connection

    def test_allows_verified_cp08_dev_database(self):
        result = assert_safe_import_database()

        self.assertEqual(result, "default")
        self.connection.ensure_connection.assert_called_once()
        self.cursor.execute.assert_called_once_with(
            "SELECT current_database()"
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_rejects_missing_explicit_database(self):
        with self.assertRaisesMessage(
            CommandError,
            "phải khai báo POSTGRES_DB",
        ):
            assert_safe_import_database()

    @patch.dict("os.environ", {"POSTGRES_DB": "cologi"}, clear=False)
    def test_rejects_main_database(self):
        with self.assertRaisesMessage(
            CommandError,
            "không nằm trong CP08 allow-list",
        ):
            assert_safe_import_database()

    @patch.dict("os.environ", {"POSTGRES_DB": "unknown_db"}, clear=False)
    def test_rejects_database_outside_allow_list(self):
        with self.assertRaisesMessage(
            CommandError,
            "không nằm trong CP08 allow-list",
        ):
            assert_safe_import_database()

    @patch.dict("os.environ", {"POSTGRES_DB": "cologi_cp08_test"}, clear=False)
    def test_rejects_environment_settings_mismatch(self):
        with self.assertRaisesMessage(
            CommandError,
            "không khớp POSTGRES_DB",
        ):
            assert_safe_import_database()

    def test_rejects_actual_database_mismatch(self):
        self.cursor.fetchone.return_value = ("cologi",)

        with self.assertRaisesMessage(
            CommandError,
            "database thực tế không khớp cấu hình",
        ):
            assert_safe_import_database()

    def test_rejects_connection_verification_failure(self):
        self.connection.ensure_connection.side_effect = RuntimeError(
            "connection unavailable"
        )

        with self.assertRaisesMessage(
            CommandError,
            "không xác minh được database thực tế",
        ):
            assert_safe_import_database()

    def test_rejects_database_routers(self):
        with patch(
            "demands.management.commands.import_v7_demo.settings.DATABASE_ROUTERS",
            ["dummy.router.DatabaseRouter"],
        ):
            with self.assertRaisesMessage(
                CommandError,
                "database router chưa được hỗ trợ an toàn",
            ):
                assert_safe_import_database()

    @override_settings(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "cologi_cp08_dev",
            },
            "other": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "other_db",
            },
        }
    )
    def test_rejects_additional_database_alias(self):
        with self.assertRaisesMessage(
            CommandError,
            "database alias ngoài phạm vi kiểm soát",
        ):
            assert_safe_import_database()
