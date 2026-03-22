from django.urls import path
from . import views

urlpatterns = [
    # Legacy analytics routes now redirect to consolidated dashboards in core/urls.py
    # These are handled by core.urls: path('analytics/', ...) and path('analytics/owner/', ...)
    # Keeping this file for backwards compatibility
]
