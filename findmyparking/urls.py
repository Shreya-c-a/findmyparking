"""
URL configuration for findmyparking project.
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('parking/', include('parking.urls')),
    path('reservations/', include('parking.reservation_urls')),
    path('payments/', include('parking.payment_urls')),
    path('notifications/', include('parking.notification_urls')),
    path('analytics/', include('parking.analytics_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
