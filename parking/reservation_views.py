import uuid
import os
import logging
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.core.mail import send_mail
from django.db import transaction
from .models import ParkingSlot, Reservation, Payment, Notification, User as ParkingUser, AuditLog
from .pricing import RATE_MAP, calculate_reservation_amount

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


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


def _sync_lot_available_slots(lot):
    lot.available_slots = ParkingSlot.objects.filter(
        parking_lot=lot,
        status='AVAILABLE'
    ).count()
    lot.save(update_fields=['available_slots'])


def _can_manage_gate(request):
    return bool(getattr(request.user, 'is_admin', False) or getattr(request.user, 'role', '') == 'owner')


@login_required
def reserve_slot(request, slot_id):
    slot = get_object_or_404(ParkingSlot, pk=slot_id)
    lot = slot.parking_lot

    # Check if slot is expired
    if slot.status == 'RESERVED':
        active_res = Reservation.objects.filter(slot=slot, status='ACTIVE').first()
        if active_res and active_res.end_time < timezone.now():
            active_res.status = 'EXPIRED'
            active_res.save()
            slot.status = 'AVAILABLE'
            slot.save()
            
            # Recalculate available slots for the lot
            _sync_lot_available_slots(slot.parking_lot)

    if slot.status != 'AVAILABLE':
        messages.error(request, 'This slot is no longer available.')
        return redirect('parking_detail', pk=slot.parking_lot.pk)

    rate_map = RATE_MAP
    min_end_time = timezone.localtime(timezone.now() + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
    available_slot_types = list(
        ParkingSlot.objects.filter(parking_lot=lot, status='AVAILABLE')
        .values_list('slot_type', 'slot_type')
        .distinct()
        .order_by('slot_type')
    )

    slot_type_labels = dict(ParkingSlot.SLOT_TYPE_CHOICES)
    available_slot_types = [
        (code, slot_type_labels.get(code, code))
        for code, _ in available_slot_types
    ]

    def _render_reserve_form(selected_slot_type=None, selected_reservation_type='HOURLY'):
        selected_type_code = selected_slot_type or slot.slot_type
        return render(request, 'reservation/reserve_slot.html', {
            'slot': slot,
            'rate_map': rate_map,
            'min_end_time': min_end_time,
            'available_slot_types': available_slot_types,
            'selected_slot_type': selected_type_code,
            'slot_type_labels': slot_type_labels,
            'selected_slot_type_label': slot_type_labels.get(selected_type_code, selected_type_code),
            'selected_reservation_type': selected_reservation_type,
        })

    if request.method == 'POST':
        start_time_raw = request.POST.get('start_time')
        end_time_raw = request.POST.get('end_time')
        reservation_type = request.POST.get('reservation_type', 'HOURLY')
        selected_slot_type = request.POST.get('slot_type', slot.slot_type)

        if selected_slot_type and selected_slot_type not in {s[0] for s in available_slot_types}:
            messages.error(request, 'Selected slot type is not currently available in this parking lot.')
            return _render_reserve_form(selected_slot_type=slot.slot_type, selected_reservation_type=reservation_type)

        if not start_time_raw or not end_time_raw:
            messages.error(request, 'Please select start and end times.')
            return _render_reserve_form(selected_slot_type=selected_slot_type, selected_reservation_type=reservation_type)

        start_time = parse_datetime(start_time_raw)
        end_time = parse_datetime(end_time_raw)
        if not start_time or not end_time:
            messages.error(request, 'Invalid date/time selected. Please try again.')
            return _render_reserve_form(selected_slot_type=selected_slot_type, selected_reservation_type=reservation_type)

        if timezone.is_naive(start_time):
            start_time = timezone.make_aware(start_time, timezone.get_current_timezone())
        if timezone.is_naive(end_time):
            end_time = timezone.make_aware(end_time, timezone.get_current_timezone())

        now = timezone.now()
        if start_time < now:
            messages.error(request, 'Start time cannot be in the past.')
            return _render_reserve_form(selected_slot_type=selected_slot_type, selected_reservation_type=reservation_type)

        if end_time <= start_time:
            messages.error(request, 'End time must be after start time.')
            return _render_reserve_form(selected_slot_type=selected_slot_type, selected_reservation_type=reservation_type)

        with transaction.atomic():
            selected_slot = ParkingSlot.objects.select_for_update().filter(
                parking_lot=lot,
                status='AVAILABLE',
                slot_type=selected_slot_type,
            ).order_by('id').first()

            if not selected_slot:
                messages.error(request, f'No {slot_type_labels.get(selected_slot_type, selected_slot_type)} slots are currently available.')
                return _render_reserve_form(selected_slot_type=selected_slot_type, selected_reservation_type=reservation_type)

            # Get or create parking user
            parking_user, _ = ParkingUser.objects.get_or_create(
                email=request.user.email,
                defaults={
                    'full_name': f"{request.user.first_name or ''} {request.user.last_name or ''}".strip() or request.user.email,
                    'phone_number': request.user.mobile_number or '',
                    'password_hash': 'django_auth',
                    'role': 'USER',
                    'status': 'ACTIVE',
                }
            )

            # Generate unique reservation code
            reservation_code = f"FMP-{uuid.uuid4().hex[:8].upper()}"

            reservation = Reservation.objects.create(
                user=parking_user,
                slot=selected_slot,
                start_time=start_time,
                end_time=end_time,
                reservation_type=reservation_type,
                reservation_code=reservation_code,
                status='ACTIVE',
            )

            # Mark slot as reserved
            selected_slot.status = 'RESERVED'
            selected_slot.save(update_fields=['status'])

            # Update available slots count
            _sync_lot_available_slots(selected_slot.parking_lot)

        # Generate QR Code
        qr_path = ''
        if HAS_QRCODE:
            qr_dir = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
            os.makedirs(qr_dir, exist_ok=True)

            qr_data = f"FindMyParking | Code: {reservation_code} | Slot: {slot.slot_number} | Lot: {slot.parking_lot.name}"
            qr = qrcode.make(qr_data)
            qr_filename = f"{reservation_code}.png"
            qr_full_path = os.path.join(qr_dir, qr_filename)
            qr.save(qr_full_path)
            qr_path = f"qr_codes/{qr_filename}"

        # Create notification
        Notification.objects.create(
            user=parking_user,
            message=f"Your reservation {reservation_code} for slot {selected_slot.slot_number} at {selected_slot.parking_lot.name} has been confirmed.",
            notification_type='APP',
            status='SENT',
        )
        _record_audit(
            request,
            action='RESERVATION_CREATED',
            entity='Reservation',
            entity_id=reservation.pk,
            details=f'code={reservation.reservation_code}',
        )

        # Send email notification
        send_notification_email(
            parking_user,
            'Reservation Confirmed - FindMyParking',
            f"Dear {parking_user.full_name},\n\nYour reservation {reservation_code} for slot {selected_slot.slot_number} at {selected_slot.parking_lot.name} has been confirmed.\n\nStart Time: {reservation.start_time}\nEnd Time: {reservation.end_time}\n\nThank you for using FindMyParking!"
        )

        return redirect('payment_page', reservation_id=reservation.pk)

    return _render_reserve_form()


@login_required
def my_reservations(request):
    parking_user = ParkingUser.objects.filter(email=request.user.email).first()
    reservations = []
    paid_reservation_ids = set()
    if parking_user:
        reservations = Reservation.objects.filter(
            user=parking_user
        ).select_related('slot', 'slot__parking_lot').order_by('-start_time')
        paid_reservation_ids = set(
            Payment.objects.filter(
                reservation__in=reservations,
                payment_status='SUCCESS',
            ).values_list('reservation_id', flat=True)
        )

    return render(request, 'reservation/my_reservations.html', {
        'reservations': reservations,
        'paid_reservation_ids': paid_reservation_ids,
    })


@login_required
def reservation_success(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id)
    parking_user = ParkingUser.objects.filter(email=request.user.email).first()
    if not parking_user or reservation.user != parking_user:
        messages.error(request, 'You cannot view this reservation.')
        return redirect('my_reservations')

    qr_path = f"qr_codes/{reservation.reservation_code}.png"

    # Check if QR exists
    full_qr_path = os.path.join(settings.MEDIA_ROOT, qr_path)
    qr_exists = os.path.exists(full_qr_path)
    successful_payment = reservation.payment_set.filter(payment_status='SUCCESS').order_by('-transaction_date').first()
    estimated_amount = calculate_reservation_amount(
        reservation.reservation_type,
        reservation.start_time,
        reservation.end_time,
    )

    return render(request, 'reservation/reservation_success.html', {
        'reservation': reservation,
        'qr_path': qr_path if qr_exists else '',
        'successful_payment': successful_payment,
        'estimated_amount': estimated_amount,
    })


@login_required
def cancel_reservation(request, reservation_id):
    if request.method != 'POST':
        messages.error(request, 'Invalid cancellation request.')
        return redirect('my_reservations')

    reservation = get_object_or_404(Reservation, pk=reservation_id)
    parking_user = ParkingUser.objects.filter(email=request.user.email).first()

    if not parking_user or reservation.user != parking_user:
        messages.error(request, 'You cannot cancel this reservation.')
        return redirect('my_reservations')

    if reservation.status != 'ACTIVE':
        messages.error(request, 'Only active reservations can be cancelled.')
        return redirect('my_reservations')

    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().select_related('slot', 'slot__parking_lot').get(pk=reservation_id)
        if reservation.status != 'ACTIVE':
            messages.error(request, 'This reservation is already processed.')
            return redirect('my_reservations')

        reservation.status = 'CANCELLED'
        reservation.save(update_fields=['status'])

        slot = reservation.slot
        slot.status = 'AVAILABLE'
        slot.save(update_fields=['status'])

        _sync_lot_available_slots(slot.parking_lot)

    Notification.objects.create(
        user=parking_user,
        message=f"Your reservation {reservation.reservation_code} has been cancelled.",
        notification_type='APP',
        status='SENT',
    )
    _record_audit(
        request,
        action='RESERVATION_CANCELLED',
        entity='Reservation',
        entity_id=reservation.pk,
        details=f'code={reservation.reservation_code}',
    )

    send_notification_email(
        parking_user,
        'Reservation Cancelled - FindMyParking',
        f"Dear {parking_user.full_name},\n\nYour reservation {reservation.reservation_code} has been cancelled.\n\nThank you for using FindMyParking!"
    )

    messages.success(request, 'Reservation cancelled successfully.')

    return redirect('my_reservations')


@login_required
def qr_gate_scanner(request):
    if not _can_manage_gate(request):
        messages.error(request, 'You are not authorized to access QR gate scanner.')
        return redirect('home')

    scanned_reservation = None

    if request.method == 'POST':
        reservation_code = (request.POST.get('reservation_code') or '').strip().upper()
        scan_action = (request.POST.get('scan_action') or 'entry').strip().lower()

        if not reservation_code:
            messages.error(request, 'Please enter a reservation QR code.')
            return render(request, 'reservation/qr_gate_scanner.html', {'scanned_reservation': None})

        if scan_action not in {'entry', 'exit'}:
            messages.error(request, 'Invalid scan action selected.')
            return render(request, 'reservation/qr_gate_scanner.html', {'scanned_reservation': None})

        with transaction.atomic():
            reservation = Reservation.objects.select_for_update().select_related('slot', 'slot__parking_lot', 'user').filter(
                reservation_code=reservation_code
            ).first()

            if not reservation:
                messages.error(request, 'Reservation not found for this QR code.')
                return render(request, 'reservation/qr_gate_scanner.html', {'scanned_reservation': None})

            scanned_reservation = reservation

            has_successful_payment = Payment.objects.filter(
                reservation=reservation,
                payment_status='SUCCESS',
            ).exists()
            if not has_successful_payment:
                messages.error(request, 'Entry/exit blocked: payment is not completed for this reservation.')
                return render(request, 'reservation/qr_gate_scanner.html', {'scanned_reservation': scanned_reservation})

            now = timezone.now()
            slot = reservation.slot

            if scan_action == 'entry':
                if reservation.status != 'ACTIVE':
                    messages.error(request, f'Cannot allow entry for reservation status: {reservation.get_status_display()}.')
                    return render(request, 'reservation/qr_gate_scanner.html', {'scanned_reservation': scanned_reservation})

                if reservation.checked_in_at and not reservation.checked_out_at:
                    messages.warning(request, 'Vehicle already checked in for this reservation.')
                    return render(request, 'reservation/qr_gate_scanner.html', {'scanned_reservation': scanned_reservation})

                if now < reservation.start_time - timedelta(minutes=30):
                    messages.error(request, 'Too early for entry. Entry is allowed up to 30 minutes before start time.')
                    return render(request, 'reservation/qr_gate_scanner.html', {'scanned_reservation': scanned_reservation})

                reservation.checked_in_at = now
                reservation.scanned_by_email = getattr(request.user, 'email', '')
                reservation.save(update_fields=['checked_in_at', 'scanned_by_email'])

                slot.status = 'OCCUPIED'
                slot.save(update_fields=['status'])

                Notification.objects.create(
                    user=reservation.user,
                    message=f'Entry confirmed for reservation {reservation.reservation_code} at {reservation.slot.parking_lot.name}.',
                    notification_type='APP',
                    status='SENT',
                )

                _record_audit(
                    request,
                    action='RESERVATION_ENTRY_SCANNED',
                    entity='Reservation',
                    entity_id=reservation.pk,
                    details=f'code={reservation.reservation_code}',
                )

                messages.success(request, f'Entry successful for {reservation.reservation_code}.')

            else:
                if reservation.checked_in_at is None:
                    messages.error(request, 'Exit denied: this reservation has no check-in record.')
                    return render(request, 'reservation/qr_gate_scanner.html', {'scanned_reservation': scanned_reservation})

                if reservation.checked_out_at is not None:
                    messages.warning(request, 'Vehicle already checked out for this reservation.')
                    return render(request, 'reservation/qr_gate_scanner.html', {'scanned_reservation': scanned_reservation})

                reservation.checked_out_at = now
                reservation.status = 'COMPLETED'
                reservation.scanned_by_email = getattr(request.user, 'email', '')
                reservation.save(update_fields=['checked_out_at', 'status', 'scanned_by_email'])

                slot.status = 'AVAILABLE'
                slot.save(update_fields=['status'])
                _sync_lot_available_slots(slot.parking_lot)

                Notification.objects.create(
                    user=reservation.user,
                    message=f'Exit confirmed for reservation {reservation.reservation_code}. Thanks for parking with us.',
                    notification_type='APP',
                    status='SENT',
                )

                _record_audit(
                    request,
                    action='RESERVATION_EXIT_SCANNED',
                    entity='Reservation',
                    entity_id=reservation.pk,
                    details=f'code={reservation.reservation_code}',
                )

                messages.success(request, f'Exit successful for {reservation.reservation_code}.')

            scanned_reservation.refresh_from_db()

    return render(request, 'reservation/qr_gate_scanner.html', {
        'scanned_reservation': scanned_reservation,
    })
