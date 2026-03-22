from django.urls import path
from . import reservation_views

urlpatterns = [
    path('reserve/<int:slot_id>/', reservation_views.reserve_slot, name='reserve_slot'),
    path('my/', reservation_views.my_reservations, name='my_reservations'),
    path('success/<int:reservation_id>/', reservation_views.reservation_success, name='reservation_success'),
    path('cancel/<int:reservation_id>/', reservation_views.cancel_reservation, name='cancel_reservation'),
    path('scan/', reservation_views.qr_gate_scanner, name='qr_gate_scanner'),
]
