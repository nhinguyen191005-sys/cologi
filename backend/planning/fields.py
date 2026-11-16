from django.db import models


class Char3Field(models.CharField):
    """Fixed-width CHAR(3), matching the PostgreSQL schema contract."""

    def db_type(self, connection):
        if connection.vendor == "postgresql":
            return "char(3)"
        return super().db_type(connection)
