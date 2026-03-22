import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from .models import Analytics, Reservation, Payment, ParkingLot, ParkingSlot, Admin as ParkingAdmin


def _build_analytics_context(lot_filter=None, scope_label='System', revenue_field='amount', revenue_label='Total Revenue'):
    lot_queryset = ParkingLot.objects.all()
    reservation_queryset = Reservation.objects.all()
    payment_queryset = Payment.objects.filter(payment_status='SUCCESS')
    analytics_queryset = Analytics.objects.select_related('parking_lot')
    total_slots_queryset = ParkingSlot.objects.all()

    if lot_filter is not None:
        lot_queryset = lot_queryset.filter(**lot_filter)
        reservation_queryset = reservation_queryset.filter(slot__parking_lot__in=lot_queryset)
        payment_queryset = payment_queryset.filter(reservation__slot__parking_lot__in=lot_queryset)
        analytics_queryset = analytics_queryset.filter(parking_lot__in=lot_queryset)
        total_slots_queryset = total_slots_queryset.filter(parking_lot__in=lot_queryset)

    revenue_data = payment_queryset.annotate(
        month=TruncMonth('transaction_date')
    ).values('month').annotate(
        total=Sum(revenue_field)
    ).order_by('month')

    revenue_labels = [item['month'].strftime('%b %Y') for item in revenue_data] if revenue_data else ['No data']
    revenue_values = [float(item['total']) for item in revenue_data] if revenue_data else [0]

    reservation_data = reservation_queryset.annotate(
        month=TruncMonth('start_time')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    res_labels = [item['month'].strftime('%b %Y') for item in reservation_data] if reservation_data else ['No data']
    res_values = [item['count'] for item in reservation_data] if reservation_data else [0]

    status_data = reservation_queryset.values('status').annotate(count=Count('id'))
    status_labels = [item['status'] for item in status_data] if status_data else ['No data']
    status_values = [item['count'] for item in status_data] if status_data else [0]

    return {
        'revenue_labels': json.dumps(revenue_labels),
        'revenue_values': json.dumps(revenue_values),
        'res_labels': json.dumps(res_labels),
        'res_values': json.dumps(res_values),
        'status_labels': json.dumps(status_labels),
        'status_values': json.dumps(status_values),
        'analytics_records': analytics_queryset.order_by('-report_date')[:20],
        'total_revenue': payment_queryset.aggregate(total=Sum(revenue_field))['total'] or 0,
        'total_reservations': reservation_queryset.count(),
        'total_lots': lot_queryset.count(),
        'total_slots': total_slots_queryset.count(),
        'analytics_scope': scope_label,
        'total_revenue_label': revenue_label,
        'platform_revenue': payment_queryset.aggregate(total=Sum('platform_fee'))['total'] or 0,
    }


@login_required
def analytics_dashboard(request):
    if not request.user.is_admin:
        if request.user.role == 'owner':
            return redirect('owner_analytics_dashboard')
        messages.error(request, 'Access denied.')
        return redirect('user_dashboard')

    context = _build_analytics_context(
        scope_label='Admin - Full System',
        revenue_field='amount',
        revenue_label='Total Revenue',
    )

    owner_rows = ParkingAdmin.objects.select_related('user').all()
    owner_summary = []
    for owner in owner_rows:
        owner_lots = ParkingLot.objects.filter(created_by=owner)
        owner_reservations = Reservation.objects.filter(slot__parking_lot__in=owner_lots)
        owner_revenue = Payment.objects.filter(
            payment_status='SUCCESS',
            reservation__slot__parking_lot__in=owner_lots,
        ).aggregate(total=Sum('amount'))['total'] or 0

        owner_summary.append({
            'owner_name': owner.user.full_name,
            'owner_email': owner.user.email,
            'lots': owner_lots.count(),
            'bookings': owner_reservations.count(),
            'revenue': owner_revenue,
        })

    context['owner_summary'] = owner_summary
    return render(request, 'analytics/analytics_dashboard.html', context)


@login_required
def owner_analytics_dashboard(request):
    if request.user.is_admin:
        return redirect('analytics_dashboard')
    if request.user.role != 'owner':
        messages.error(request, 'Access denied.')
        return redirect('user_dashboard')

    owner_admin = ParkingAdmin.objects.filter(user__email=request.user.email).first()
    if not owner_admin:
        messages.error(request, 'Owner profile not found for analytics.')
        return redirect('user_dashboard')

    context = _build_analytics_context(
        lot_filter={'created_by': owner_admin},
        scope_label='Owner - Your Parking Business',
        revenue_field='owner_earning',
        revenue_label='Owner Earnings',
    )
    context['owner_summary'] = []
    context['owner_lots'] = ParkingLot.objects.filter(created_by=owner_admin).order_by('-created_at')
    return render(request, 'analytics/analytics_dashboard.html', context)
