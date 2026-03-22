from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Notification, User as ParkingUser


@login_required
def notifications_list(request):
    parking_user = ParkingUser.objects.filter(email=request.user.email).first()
    notifications = []
    if parking_user:
        notifications = Notification.objects.filter(
            user=parking_user
        ).order_by('-created_at')

    return render(request, 'notifications/notifications.html', {'notifications': notifications})
