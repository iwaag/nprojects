"""URL patterns for the Nautobot Service Catalog App."""

from django.urls import path

from . import views

urlpatterns = [
    path("repositories/", views.repository_list, name="repository_list"),
]
