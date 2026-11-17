from django.urls import path

from planning.views import F1RunPreviewView


urlpatterns = [
    path(
        "f1/preview/",
        F1RunPreviewView.as_view(),
        name="planning-f1-preview",
    ),
]
