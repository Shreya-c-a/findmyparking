from django.urls import path
from . import payment_views

urlpatterns = [
    path('<int:reservation_id>/', payment_views.payment_page, name='payment_page'),
    path('success/<int:payment_id>/', payment_views.payment_success, name='payment_success'),
    path('failed/', payment_views.payment_failed, name='payment_failed'),
]
