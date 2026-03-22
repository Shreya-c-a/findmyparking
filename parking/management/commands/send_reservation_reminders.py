from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail

from parking.models import Reservation, Notification, ReservationReminder


class Command(BaseCommand):
    help = 'Send reminders for reservations starting soon.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=30,
            help='Send reminders for reservations starting within this many minutes (default: 30).',
        )

    def handle(self, *args, **options):
        minutes = max(1, options['minutes'])
        now = timezone.now()
        until = now + timedelta(minutes=minutes)

        reservations = Reservation.objects.select_related('user', 'slot', 'slot__parking_lot').filter(
            status='ACTIVE',
            start_time__gte=now,
            start_time__lte=until,
        )

        sent_count = 0
        for reservation in reservations:
            if ReservationReminder.objects.filter(reservation=reservation).exists():
                continue

            user = reservation.user
            message = (
                f"Reminder: Reservation {reservation.reservation_code} starts at "
                f"{timezone.localtime(reservation.start_time).strftime('%d %b %Y, %I:%M %p')} "
                f"for {reservation.slot.parking_lot.name} (Slot {reservation.slot.slot_number})."
            )

            Notification.objects.create(
                user=user,
                message=message,
                notification_type='APP',
                status='SENT',
            )

            if getattr(settings, 'SEND_RESERVATION_EMAILS', True) and user.email:
                try:
                    send_mail(
                        subject='Reservation Reminder - FindMyParking',
                        message=message,
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@findmyparking.com'),
                        recipient_list=[user.email],
                        fail_silently=True,
                    )
                except Exception:
                    # Non-blocking by design for reminder jobs
                    pass

            ReservationReminder.objects.create(reservation=reservation)
            sent_count += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent_count} reminder(s).'))
