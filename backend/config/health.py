from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def live_health(request):
    """Confirm that the Django application process can serve requests."""
    return JsonResponse({"status": "ok"})


@require_GET
@never_cache
def ready_health(request):
    """Confirm that the application can execute a query against its database."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse(
            {
                "status": "error",
                "checks": {"database": "error"},
            },
            status=503,
        )

    return JsonResponse(
        {
            "status": "ok",
            "checks": {"database": "ok"},
        }
    )
