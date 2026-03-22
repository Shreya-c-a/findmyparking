from django.urls import path
from . import notification_views

urlpatterns = [
    path('', notification_views.notifications_list, name='notifications_list'),
]
