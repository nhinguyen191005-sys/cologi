from django import forms

from .models import VehicleCargoCompatibility


class VehicleCargoCompatibilityUpdateForm(forms.ModelForm):
    class Meta:
        model = VehicleCargoCompatibility
        fields = ("is_supported",)
