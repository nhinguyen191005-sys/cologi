from django.conf import settings
from django.test import SimpleTestCase


class LoggingConfigurationTests(SimpleTestCase):
    def test_console_handler_writes_to_stdout(self):
        handler = settings.LOGGING["handlers"]["console"]

        self.assertEqual(
            handler["class"],
            "logging.StreamHandler",
        )
        self.assertEqual(
            handler["stream"],
            "ext://sys.stdout",
        )

    def test_console_handler_uses_configured_level(self):
        self.assertEqual(
            settings.LOGGING["handlers"]["console"]["level"],
            settings.LOG_LEVEL,
        )

    def test_cologi_logger_uses_configured_level(self):
        logger = settings.LOGGING["loggers"]["cologi"]

        self.assertEqual(logger["level"], settings.LOG_LEVEL)
        self.assertFalse(logger["propagate"])

    def test_django_and_root_loggers_default_to_warning(self):
        self.assertEqual(
            settings.LOGGING["loggers"]["django"]["level"],
            "WARNING",
        )
        self.assertEqual(settings.LOGGING["root"]["level"], "WARNING")

    def test_sql_debug_logger_is_not_enabled(self):
        self.assertNotIn(
            "django.db.backends",
            settings.LOGGING["loggers"],
        )
