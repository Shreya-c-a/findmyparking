from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from django.db import IntegrityError
from .decorators import role_required
from .models import ParkingLot, ParkingSlot, Reservation, Admin as ParkingAdmin, User as ParkingUser, AuditLog
from .forms import ParkingLotForm, ParkingSlotForm


LOCATION_COORDS = {
    'sg highway': (23.0300, 72.5070),
    'satellite': (23.0296, 72.5079),
    'manek chowk': (23.0258, 72.5873),
    'cg road': (23.0326, 72.5606),
    'navrangpura': (23.0326, 72.5606),
    'iscon': (23.0296, 72.5079),
    'kalupur': (23.0245, 72.6009),
    'railway': (23.0245, 72.6009),
    'airport': (23.0735, 72.6266),
    'vastrapur': (23.0383, 72.5230),
    'sabarmati': (23.0465, 72.5780),
    'riverfront': (23.0465, 72.5780),
    'prahlad nagar': (23.0120, 72.5120),
    'science city': (23.0700, 72.5110),
    'sola': (23.0700, 72.5110),
    'law garden': (23.0310, 72.5566),
    'ellis bridge': (23.0320, 72.5600),
    'bopal': (22.9880, 72.4750),
    'paldi': (23.0130, 72.5620),
    'thaltej': (23.0500, 72.5000),
    'memnagar': (23.0450, 72.5350),
    'gota': (23.1000, 72.5400),
    'sarkhej': (22.9892, 72.4990),
    'chandkheda': (23.1100, 72.5900),
    'drive in': (23.0400, 72.5350),
    'ashram road': (23.0360, 72.5700),
    'bodakdev': (23.0356, 72.5066),
    'gandhinagar': (23.2156, 72.6369),
    'sanand': (22.9900, 72.3800),
    'dholera': (22.2500, 72.1900),
    'ahmedabad': (23.0225, 72.5714),
    'naroda': (23.0709, 72.6777),
    'ambawadi': (23.0230, 72.5530),
    'vejalpur': (23.0092, 72.5266),
}

DETAIL_IMAGE_POOL = [
    'images/car.jpg',
    'images/car2.jpg',
    'images/car3.jpg',
    'images/car4.jpg',
    'images/car5.jpg',
    'images/car6.jpg',
    'images/car7.jpg',
    'images/car8.jpg',
    'images/car9.jpg',
    'images/car10.jpg',
    'images/car11.jpg',
    'images/car12.jpg',
    'images/car13.jpg',
    'images/car14.jpg',
    'images/car15.jpg',
    'images/car16.jpg',
    'images/car17.jpg',
    'images/car18.png',
    'images/car19.jpg',
    'images/car20.jpg',
    'images/car21.jpg',
    'images/car22.jpg',
]


def _resolve_lot_coords(location_text, seed=0):
    loc = (location_text or '').lower()
    for key, value in LOCATION_COORDS.items():
        if key in loc:
            return value

    # Fallback near city center with deterministic spread.
    offset = seed * 0.004
    return (23.0225 + offset, 72.5714 - offset)


def _default_slot_type(index):
    # Keep mostly regular slots while ensuring EV and handicap options exist.
    if index % 10 == 0:
        return 'EV'
    if index % 15 == 0:
        return 'HANDICAP'
    return 'REGULAR'


def _get_request_owner_admin(request):
    parking_user = ParkingUser.objects.filter(email=request.user.email).first()
    if not parking_user:
        return None
    return ParkingAdmin.objects.filter(user=parking_user).first()


def _is_platform_admin(request):
    return bool(getattr(request.user, 'is_admin', False))


def _record_audit(request, action, entity, entity_id='', details=''):
    actor_email = getattr(request.user, 'email', 'system@local')
    AuditLog.objects.create(
        actor_email=actor_email,
        action=action,
        entity=entity,
        entity_id=str(entity_id or ''),
        details=details or '',
    )


def _sync_lot_counts(lot):
    lot.total_slots = ParkingSlot.objects.filter(parking_lot=lot).count()
    lot.available_slots = ParkingSlot.objects.filter(
        parking_lot=lot,
        status='AVAILABLE'
    ).count()
    lot.save(update_fields=['total_slots', 'available_slots'])


def _can_manage_lot(request, lot):
    owner_admin = _get_request_owner_admin(request)
    if _is_platform_admin(request):
        return True
    if not owner_admin:
        return False
    if lot.created_by and lot.created_by != owner_admin:
        return False
    return True


def _next_slot_sequence_number(lot):
    max_num = 0
    for slot_number in ParkingSlot.objects.filter(parking_lot=lot).values_list('slot_number', flat=True):
        digits = ''.join(ch for ch in slot_number if ch.isdigit())
        if digits:
            max_num = max(max_num, int(digits))
    return max_num + 1


def check_expired_reservations(lot):
    """Expire reservations that have passed their end time"""
    now = timezone.now()
    expired = Reservation.objects.filter(
        slot__parking_lot=lot,
        status='ACTIVE',
        end_time__lt=now
    )
    
    if expired.exists():
        for reservation in expired:
            reservation.status = 'EXPIRED'
            reservation.save()
            
            slot = reservation.slot
            slot.status = 'AVAILABLE'
            slot.save()
            
        # Recalculate available slots for the lot
        lot.available_slots = ParkingSlot.objects.filter(
            parking_lot=lot, 
            status='AVAILABLE'
        ).count()
        lot.save()


def parking_list(request):
    """View all parking lots with optional search"""
    query = request.GET.get('q', '')
    sort = request.GET.get('sort', '')
    lots = ParkingLot.objects.all().order_by('-created_at')

    if query:
        lots = lots.filter(Q(name__icontains=query) | Q(location__icontains=query))

    if sort == 'availability':
        lots = lots.order_by('-available_slots', 'name')
    elif sort == 'name':
        lots = lots.order_by('name')

    lots = list(lots)
    for idx, lot in enumerate(lots, start=1):
        if lot.latitude is not None and lot.longitude is not None:
            lot.map_lat, lot.map_lng = float(lot.latitude), float(lot.longitude)
        else:
            lot.map_lat, lot.map_lng = _resolve_lot_coords(lot.location, seed=idx)

    context = {
        'parking_lots': lots,
        'query': query,
        'sort': sort,
        'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
    }
    return render(request, 'parking/parking_list.html', context)


@login_required
def quick_book(request):
    """Open a parking lot detail page where user can view and choose slots."""
    preferred_lot = ParkingLot.objects.filter(
        available_slots__gt=0
    ).order_by('-available_slots', 'id').first()

    if not preferred_lot:
        messages.error(request, 'No parking slots are currently available. Please try again later.')
        return redirect('parking_list')

    return redirect('parking_detail', pk=preferred_lot.pk)


@login_required
def parking_detail(request, pk):
    """View parking lot details and its slots"""
    lot = get_object_or_404(ParkingLot, pk=pk)
    
    # Check for expired reservations
    check_expired_reservations(lot)
    lot.refresh_from_db()
    
    slots = ParkingSlot.objects.filter(parking_lot=lot)
    available_count = slots.filter(status='AVAILABLE').count()
    reserved_count = slots.filter(status='RESERVED').count()
    occupied_count = slots.filter(status='OCCUPIED').count()
    if lot.latitude is not None and lot.longitude is not None:
        lot_map_lat, lot_map_lng = float(lot.latitude), float(lot.longitude)
    else:
        lot_map_lat, lot_map_lng = _resolve_lot_coords(lot.location, seed=lot.pk)

    pool_size = len(DETAIL_IMAGE_POOL)
    base_index = lot.pk % pool_size
    detail_gallery_images = [
        DETAIL_IMAGE_POOL[base_index],
        DETAIL_IMAGE_POOL[(base_index + 4) % pool_size],
        DETAIL_IMAGE_POOL[(base_index + 8) % pool_size],
    ]

    context = {
        'parking_lot': lot,
        'slots': slots,
        'available_count': available_count,
        'reserved_count': reserved_count,
        'occupied': occupied_count,
        'lot_map_lat': lot_map_lat,
        'lot_map_lng': lot_map_lng,
        'detail_gallery_images': detail_gallery_images,
        'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
    }
    return render(request, 'parking/parking_detail.html', context)


@login_required
def slot_list(request, pk):
    """View available slots for a parking lot"""
    lot = get_object_or_404(ParkingLot, pk=pk)
    
    # Check for expired reservations
    check_expired_reservations(lot)
    lot.refresh_from_db()

    slot_type = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    slots = ParkingSlot.objects.filter(parking_lot=lot)

    if slot_type:
        slots = slots.filter(slot_type=slot_type)

    if status_filter:
        slots = slots.filter(status=status_filter)

    context = {
        'lot': lot,
        'slots': slots,
        'slot_type': slot_type,
        'status_filter': status_filter,
    }
    return render(request, 'parking/slot_list.html', context)


@login_required
def book_parking(request, pk):
    """Booking flow: show lot details so user can choose any slot."""
    lot = get_object_or_404(ParkingLot, pk=pk)

    # Keep availability fresh before selecting a slot.
    check_expired_reservations(lot)

    lot.refresh_from_db()
    if lot.available_slots <= 0:
        messages.error(request, f'No slots are currently available at {lot.name}.')
        return redirect('parking_detail', pk=lot.pk)

    return redirect('parking_detail', pk=lot.pk)


@login_required
@role_required(allowed_roles=["owner"])
def add_parking(request):
    """Admin: Add new parking lot"""
    if request.method == 'POST':
        form = ParkingLotForm(request.POST)
        if form.is_valid():
            lot = form.save(commit=False)
            lot.available_slots = lot.total_slots
            # Link to parking Admin
            parking_user = ParkingUser.objects.filter(email=request.user.email).first()
            if parking_user:
                admin = ParkingAdmin.objects.filter(user=parking_user).first()
                lot.created_by = admin
            lot.save()

            # Auto-create slots
            for i in range(1, lot.total_slots + 1):
                ParkingSlot.objects.create(
                    parking_lot=lot,
                    slot_number=f"S-{i:03d}",
                    slot_type=_default_slot_type(i),
                    status='AVAILABLE'
                )

            # Keep summary fields in sync with actual slot rows.
            lot.available_slots = lot.total_slots
            lot.save(update_fields=['available_slots'])
            _record_audit(
                request,
                action='PARKING_LOT_CREATED',
                entity='ParkingLot',
                entity_id=lot.pk,
                details=f'name={lot.name}',
            )

            messages.success(request, f'Parking lot "{lot.name}" created with {lot.total_slots} slots!')
            return redirect('parking_detail', pk=lot.pk)
    else:
        form = ParkingLotForm()

    return render(request, 'parking/add_parking.html', {'form': form})


@login_required
@role_required(allowed_roles=["owner"])
def edit_parking(request, pk):
    """Admin: Edit parking lot"""
    lot = get_object_or_404(ParkingLot, pk=pk)
    owner_admin = _get_request_owner_admin(request)

    if not _is_platform_admin(request) and not owner_admin:
        messages.error(request, 'Owner profile is missing. Please contact support.')
        return redirect('parking_list')

    if not _is_platform_admin(request) and lot.created_by and lot.created_by != owner_admin:
        messages.error(request, 'You can only edit parking lots created by you.')
        return redirect('parking_detail', pk=lot.pk)

    if request.method == 'POST':
        form = ParkingLotForm(request.POST, instance=lot)
        if form.is_valid():
            lot = form.save()

            # If owner increases total slots, create missing slot rows.
            existing_count = ParkingSlot.objects.filter(parking_lot=lot).count()
            if lot.total_slots > existing_count:
                for i in range(existing_count + 1, lot.total_slots + 1):
                    ParkingSlot.objects.create(
                        parking_lot=lot,
                        slot_number=f"S-{i:03d}",
                        slot_type=_default_slot_type(i),
                        status='AVAILABLE',
                    )

            # Recalculate available slots from real slot status.
            lot.available_slots = ParkingSlot.objects.filter(
                parking_lot=lot,
                status='AVAILABLE'
            ).count()
            lot.save(update_fields=['available_slots'])
            _record_audit(
                request,
                action='PARKING_LOT_UPDATED',
                entity='ParkingLot',
                entity_id=lot.pk,
                details=f'name={lot.name}',
            )

            messages.success(request, f'Parking lot "{lot.name}" updated!')
            return redirect('parking_detail', pk=lot.pk)
    else:
        form = ParkingLotForm(instance=lot)

    return render(request, 'parking/edit_parking.html', {'form': form, 'lot': lot})


@login_required
@role_required(allowed_roles=["owner"])
def add_slot(request, pk):
    """Admin: Add a new slot to a parking lot"""
    lot = get_object_or_404(ParkingLot, pk=pk)
    if not _is_platform_admin(request) and not _get_request_owner_admin(request):
        messages.error(request, 'Owner profile is missing. Please contact support.')
        return redirect('parking_list')

    if not _can_manage_lot(request, lot):
        messages.error(request, 'You can only manage slots for parking lots created by you.')
        return redirect('parking_detail', pk=lot.pk)

    if request.method == 'POST':
        bulk_count_raw = request.POST.get('bulk_count', '1')
        slot_prefix = (request.POST.get('slot_prefix') or 'S').strip().upper()
        try:
            bulk_count = int(bulk_count_raw)
        except (TypeError, ValueError):
            bulk_count = 1

        if bulk_count < 1 or bulk_count > 200:
            messages.error(request, 'Bulk count must be between 1 and 200.')
            return redirect('add_slot', pk=lot.pk)

        post_data = request.POST.copy()
        post_data['parking_lot'] = str(lot.pk)
        form = ParkingSlotForm(post_data)
        if form.is_valid():
            base_slot = form.save(commit=False)
            base_slot.parking_lot = lot

            if bulk_count == 1:
                try:
                    base_slot.save()
                except IntegrityError:
                    messages.error(request, 'Slot number already exists for this parking lot.')
                    return redirect('add_slot', pk=lot.pk)

                _sync_lot_counts(lot)
                _record_audit(
                    request,
                    action='PARKING_SLOT_ADDED',
                    entity='ParkingSlot',
                    entity_id=base_slot.pk,
                    details=f'lot_id={lot.pk}, slot={base_slot.slot_number}',
                )
                messages.success(request, f'Slot "{base_slot.slot_number}" added!')
            else:
                start_seq = _next_slot_sequence_number(lot)
                created = 0
                for i in range(bulk_count):
                    slot_no = f"{slot_prefix}-{start_seq + i:03d}"
                    try:
                        ParkingSlot.objects.create(
                            parking_lot=lot,
                            slot_number=slot_no,
                            slot_type=base_slot.slot_type,
                            status=base_slot.status,
                        )
                        created += 1
                    except IntegrityError:
                        continue

                _sync_lot_counts(lot)
                _record_audit(
                    request,
                    action='PARKING_SLOT_BULK_ADDED',
                    entity='ParkingLot',
                    entity_id=lot.pk,
                    details=f'created={created}, prefix={slot_prefix}',
                )
                messages.success(request, f'{created} slots added successfully.')

            return redirect('parking_detail', pk=lot.pk)
    else:
        form = ParkingSlotForm(initial={'parking_lot': lot})

    return render(request, 'parking/add_slot.html', {'form': form, 'lot': lot})


@login_required
@role_required(allowed_roles=["owner"])
def toggle_slot_status(request, pk, slot_id):
    if request.method != 'POST':
        return redirect('slot_list', pk=pk)

    lot = get_object_or_404(ParkingLot, pk=pk)
    slot = get_object_or_404(ParkingSlot, pk=slot_id, parking_lot=lot)

    if not _can_manage_lot(request, lot):
        messages.error(request, 'You can only manage slots for parking lots created by you.')
        return redirect('slot_list', pk=lot.pk)

    if slot.status in {'RESERVED', 'OCCUPIED'}:
        messages.error(request, 'Reserved or occupied slots cannot be disabled right now.')
        return redirect('slot_list', pk=lot.pk)

    previous_status = slot.status
    slot.status = 'DISABLED' if slot.status == 'AVAILABLE' else 'AVAILABLE'
    slot.save(update_fields=['status'])
    _sync_lot_counts(lot)

    _record_audit(
        request,
        action='PARKING_SLOT_STATUS_CHANGED',
        entity='ParkingSlot',
        entity_id=slot.pk,
        details=f'{previous_status}->{slot.status}',
    )

    messages.success(request, f'Slot {slot.slot_number} is now {slot.get_status_display()}.')
    return redirect('slot_list', pk=lot.pk)


@login_required
@role_required(allowed_roles=["owner"])
def delete_parking(request, pk):
    """Admin: Delete parking lot and related slots/reservations"""
    if request.method != 'POST':
        return redirect('parking_detail', pk=pk)

    lot = get_object_or_404(ParkingLot, pk=pk)
    owner_admin = _get_request_owner_admin(request)

    if not _is_platform_admin(request) and not owner_admin:
        messages.error(request, 'Owner profile is missing. Please contact support.')
        return redirect('parking_list')

    if not _is_platform_admin(request) and lot.created_by and lot.created_by != owner_admin:
        messages.error(request, 'You can only delete parking lots created by you.')
        return redirect('parking_detail', pk=lot.pk)

    lot_name = lot.name
    lot_id = lot.pk
    lot.delete()
    _record_audit(
        request,
        action='PARKING_LOT_DELETED',
        entity='ParkingLot',
        entity_id=lot_id,
        details=f'name={lot_name}',
    )
    messages.success(request, f'Parking lot "{lot_name}" deleted successfully.')
    return redirect('parking_list')


# Keep existing dashboard views for backward compatibility
@role_required(allowed_roles=["owner"])
def ownerDashboardView(request):
    return redirect('owner_analytics_dashboard')


@role_required(allowed_roles=["user"])
def userDashboardView(request):
    return redirect('user_dashboard')