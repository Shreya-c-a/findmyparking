import os
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.db import transaction
from .models import Reservation, Payment, Notification, User as ParkingUser, AuditLog
from .pricing import RATE_MAP, calculate_reservation_amount, get_rate_label, calculate_commission_split


logger = logging.getLogger(__name__)


def send_notification_email(user, subject, message):
    """Send email notification to user"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@findmyparking.com',
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Email sending failed for %s", user.email)


def _record_audit(request, action, entity, entity_id='', details=''):
    actor_email = getattr(request.user, 'email', 'system@local')
    AuditLog.objects.create(
        actor_email=actor_email,
        action=action,
        entity=entity,
        entity_id=str(entity_id or ''),
        details=details or '',
    )


def send_payment_success_email_with_qr(user, reservation, amount, payment_method):
    """Send payment confirmation email and attach QR ticket if available."""
    subject = 'Payment Successful - FindMyParking'
    message = (
        f"Dear {user.full_name},\n\n"
        f"Your payment of Rs.{amount} for reservation {reservation.reservation_code} was successful.\n\n"
        f"Payment Method: {payment_method}\n"
        f"Parking: {reservation.slot.parking_lot.name}\n"
        f"Slot: {reservation.slot.slot_number}\n\n"
        "Your QR ticket is attached with this email.\n"
        "Please show it at the parking entrance.\n\n"
        "Thank you for using FindMyParking!"
    )

    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@findmyparking.com',
        to=[user.email],
    )

    qr_file = os.path.join(settings.MEDIA_ROOT, 'qr_codes', f'{reservation.reservation_code}.png')
    if os.path.exists(qr_file):
        with open(qr_file, 'rb') as file_obj:
            email.attach(f'{reservation.reservation_code}.png', file_obj.read(), 'image/png')

    try:
        email.send(fail_silently=False)
        return True
    except Exception as exc:
        print(f"Payment email sending failed: {exc}")
        return False


@login_required
def payment_page(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id)
    parking_user = ParkingUser.objects.filter(email=request.user.email).first()

    if not parking_user or reservation.user != parking_user:
        messages.error(request, 'You cannot pay for this reservation.')
        return redirect('my_reservations')

    if reservation.status != 'ACTIVE':
        messages.error(request, 'Only active reservations can be paid.')
        return redirect('my_reservations')

    existing_payment = Payment.objects.filter(
        reservation=reservation,
        payment_status='SUCCESS',
    ).order_by('-transaction_date').first()
    if existing_payment:
        messages.info(request, 'Payment already completed for this reservation.')
        return redirect('payment_success', payment_id=existing_payment.pk)

    amount = calculate_reservation_amount(
        reservation.reservation_type,
        reservation.start_time,
        reservation.end_time,
    )
    unit_rate = RATE_MAP.get(reservation.reservation_type, RATE_MAP['HOURLY'])
    rate_label = get_rate_label(reservation.reservation_type)

    selected_payment_method = 'CARD'
    upi_id_value = ''

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'CARD')
        selected_payment_method = payment_method
        upi_id_value = (request.POST.get('upi_id') or '').strip()

        if payment_method not in {'CARD', 'UPI', 'WALLET'}:
            messages.error(request, 'Invalid payment method selected.')
            return redirect('payment_failed')

        if payment_method == 'UPI' and not upi_id_value:
            messages.error(request, 'Please enter your UPI ID before proceeding.')
            context = {
                'reservation': reservation,
                'amount': amount,
                'unit_rate': unit_rate,
                'rate_label': rate_label,
                'selected_payment_method': selected_payment_method,
                'upi_id_value': upi_id_value,
            }
            return render(request, 'payment/payment_page.html', context)

        with transaction.atomic():
            locked_reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
            existing_payment = Payment.objects.select_for_update().filter(
                reservation=locked_reservation,
                payment_status='SUCCESS',
            ).order_by('-transaction_date').first()

            if existing_payment:
                messages.info(request, 'Payment already completed for this reservation.')
                return redirect('payment_success', payment_id=existing_payment.pk)

            owner_percent = getattr(settings, 'OWNER_COMMISSION_PERCENT', 90)
            owner_earning, platform_fee = calculate_commission_split(amount, owner_percent)

            payment = Payment.objects.create(
                reservation=locked_reservation,
                amount=amount,
                owner_earning=owner_earning,
                platform_fee=platform_fee,
                payment_method=payment_method,
                payment_status='SUCCESS',
            )

        Notification.objects.create(
            user=parking_user,
            message=(
                f"Payment of ₹{amount} for reservation {reservation.reservation_code} "
                f"was successful via {payment_method}. Owner earning: ₹{owner_earning}, platform fee: ₹{platform_fee}."
                + (f" UPI ID: {upi_id_value}" if payment_method == 'UPI' else '')
            ),
            notification_type='APP',
            status='SENT',
        )
        _record_audit(
            request,
            action='PAYMENT_SUCCESS',
            entity='Payment',
            entity_id=payment.pk,
            details=f'reservation={reservation.reservation_code}, method={payment_method}',
        )

        email_sent = send_payment_success_email_with_qr(
            user=parking_user,
            reservation=reservation,
            amount=amount,
            payment_method=payment_method,
        )

        Notification.objects.create(
            user=parking_user,
            message=(
                f"Payment email for reservation {reservation.reservation_code} "
                f"{'sent successfully' if email_sent else 'failed to send'}."
            ),
            notification_type='EMAIL',
            status='SENT' if email_sent else 'FAILED',
        )

        return redirect('payment_success', payment_id=payment.pk)

    context = {
        'reservation': reservation,
        'amount': amount,
        'unit_rate': unit_rate,
        'rate_label': rate_label,
        'selected_payment_method': selected_payment_method,
        'upi_id_value': upi_id_value,
    }
    return render(request, 'payment/payment_page.html', context)


@login_required
def payment_success(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)
    parking_user = ParkingUser.objects.filter(email=request.user.email).first()
    if not parking_user or payment.reservation.user != parking_user:
        messages.error(request, 'You cannot view this payment.')
        return redirect('my_reservations')
    return render(request, 'payment/payment_success.html', {'payment': payment})


@login_required
def payment_failed(request):
    return render(request, 'payment/payment_failed.html')
