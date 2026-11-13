import os

from .base import *

DEBUG = False

if not SECRET_KEY or SECRET_KEY.startswith("django-insecure-"):
    raise RuntimeError(
        "A secure DJANGO_SECRET_KEY must be configured in production."
    )

if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise RuntimeError(
        "DJANGO_ALLOWED_HOSTS must contain explicit production hosts."
    )

# Production defaults to WARNING; DJANGO_LOG_LEVEL can override it.
LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "WARNING").upper()
LOGGING["handlers"]["console"]["level"] = LOG_LEVEL
LOGGING["loggers"]["cologi"]["level"] = LOG_LEVEL
