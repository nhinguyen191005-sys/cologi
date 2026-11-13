from functools import wraps

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from accounts.models import RoleCode, UserRole

from .forms import VehicleCargoCompatibilityUpdateForm
from .models import (
    CargoCategory,
    VehicleCargoCompatibility,
    VehicleType,
)



def has_active_manager_role(user):
    if not (
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "is_staff", False)
    ):
        return False

    return UserRole.objects.filter(
        user=user,
        is_active=True,
        role__code=RoleCode.MANAGER,
        role__is_active=True,
    ).exists()


def manager_required(view_func):
    @wraps(view_func)
    def checked_view(request, *args, **kwargs):
        if not has_active_manager_role(request.user):
            raise PermissionDenied(
                "An active CoLogi MANAGER role is required."
            )

        return view_func(request, *args, **kwargs)

    return staff_member_required(checked_view)


def _get_filter_id(value):
    if value and value.isdecimal() and int(value) > 0:
        return int(value)
    return None


@manager_required
@require_GET
def vehicle_cargo_compatibility_list(request):
    queryset = (
        VehicleCargoCompatibility.objects
        .select_related("vehicle_type", "cargo_category")
        .order_by(
            "vehicle_type__vehicle_code",
            "cargo_category__category_code",
        )
    )

    vehicle_id = _get_filter_id(
        request.GET.get("vehicle_type", "")
    )
    cargo_id = _get_filter_id(
        request.GET.get("cargo_category", "")
    )
    supported = request.GET.get("is_supported", "")

    if vehicle_id:
        queryset = queryset.filter(vehicle_type_id=vehicle_id)

    if cargo_id:
        queryset = queryset.filter(cargo_category_id=cargo_id)

    if supported == "true":
        queryset = queryset.filter(is_supported=True)
    elif supported == "false":
        queryset = queryset.filter(is_supported=False)

    context = {
        "title": "Vehicle–Cargo Compatibility",
        "compatibilities": queryset,
        "vehicle_types": VehicleType.objects.order_by("vehicle_code"),
        "cargo_categories": CargoCategory.objects.order_by(
            "category_code"
        ),
        "selected_vehicle_type": str(vehicle_id or ""),
        "selected_cargo_category": str(cargo_id or ""),
        "selected_is_supported": supported,
    }

    return render(
        request,
        "admin/masterdata/vehicle_cargo_compatibility/list.html",
        context,
    )


@manager_required
@require_http_methods(["GET", "POST"])
def vehicle_cargo_compatibility_update(
    request,
    vehicle_id,
    cargo_id,
):
    compatibility = get_object_or_404(
        VehicleCargoCompatibility.objects.select_related(
            "vehicle_type",
            "cargo_category",
        ),
        vehicle_type_id=vehicle_id,
        cargo_category_id=cargo_id,
    )

    if request.method == "POST":
        form = VehicleCargoCompatibilityUpdateForm(
            request.POST,
            instance=compatibility,
        )

        if form.is_valid():
            with transaction.atomic():
                form.save()

            messages.success(
                request,
                "Vehicle–Cargo compatibility updated successfully.",
            )
            return redirect(
                reverse("masterdata_vehiclecargo_list")
            )
    else:
        form = VehicleCargoCompatibilityUpdateForm(
            instance=compatibility,
        )

    return render(
        request,
        "admin/masterdata/vehicle_cargo_compatibility/update.html",
        {
            "title": "Update Vehicle–Cargo Compatibility",
            "form": form,
            "compatibility": compatibility,
        },
    )
