from .base import *

DEBUG = False

if not SECRET_KEY or SECRET_KEY.startswith("django-insecure-"):
    raise RuntimeError("A secure DJANGO_SECRET_KEY must be configured in production.")

if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must contain explicit production hosts.")
