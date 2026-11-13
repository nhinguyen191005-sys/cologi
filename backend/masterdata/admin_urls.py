from django.urls import path

from . import admin_views


urlpatterns = [
    path(
        "vehicle-cargo/",
        admin_views.vehicle_cargo_compatibility_list,
        name="masterdata_vehiclecargo_list",
    ),
    path(
        "vehicle-cargo/<int:vehicle_id>/<int:cargo_id>/",
        admin_views.vehicle_cargo_compatibility_update,
        name="masterdata_vehiclecargo_update",
    ),
]
