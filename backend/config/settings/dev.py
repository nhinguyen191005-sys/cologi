from .base import *

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in {"1", "true", "yes", "on"}
