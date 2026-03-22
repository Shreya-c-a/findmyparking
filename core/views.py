from django.shortcuts import render, redirect
from .forms import UserSignupForm, UserLoginForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
import logging
import secrets
import time
import json
from parking.models import (
    User as ParkingUser, Admin as ParkingAdmin,
    ParkingLot, ParkingSlot, Reservation, Payment, Notification, AuditLog, Analytics
)
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth


logger = logging.getLogger(__name__)


def _send_login_otp(user, otp_code):
    """Send one-time login code email."""
    try:
        send_mail(
            subject='Your FindMyParking Login OTP',
            message=(
                f"Hello {user.first_name or user.email},\n\n"
                f"Your one-time login code is: {otp_code}\n"
                "This code will expire in 5 minutes.\n\n"
                "If you did not try to sign in, please reset your password immediately."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@findmyparking.com',
            recipient_list=[user.email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("Login OTP email failed for %s", user.email)
        return False


def home(request):
    # Get featured parking lots for the home page
    featured_lots = ParkingLot.objects.all().order_by('-created_at')[:6]
    return render(request, 'home.html', {'featured_lots': featured_lots})


def help_center_view(request):
    return render(request, 'help/help_center.html')


def logo_showcase_view(request):
    return render(request, 'branding/logo_showcase.html')


def userSignupView(request):
    if request.method == "POST":
        form = UserSignupForm(request.POST or None)
        if form.is_valid():
            user = form.save()
            # Also create a parking.User record linked by email
            parking_user, created = ParkingUser.objects.get_or_create(
                email=user.email,
                defaults={
                    'full_name': f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    'phone_number': user.mobile_number or '',
                    'password_hash': 'django_auth',
                    'role': 'ADMIN' if user.role == 'owner' else 'USER',
                    'status': 'ACTIVE',
                }
            )
            # If the user signed up as owner, create Admin record too
            if user.role == 'owner':
                ParkingAdmin.objects.get_or_create(
                    user=parking_user,
                    defaults={'access_level': 'STANDARD'}
                )
            messages.success(request, 'Account created successfully! Please login.')
            return redirect('login')
        else:
            return render(request, 'auth/signup.html', {'form': form})
    else:
        form = UserSignupForm()
        return render(request, 'auth/signup.html', {'form': form})


def userLoginView(request):
    next_url = request.POST.get('next') or request.GET.get('next', '')

    if request.method == "POST":
        form = UserLoginForm(request.POST or None)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, email=email, password=password)
            if user:
                otp_code = f"{secrets.randbelow(900000) + 100000}"
                request.session['pending_login_user_id'] = user.pk
                request.session['pending_login_next'] = next_url
                request.session['pending_login_is_admin'] = False
                request.session['pending_login_otp'] = otp_code
                request.session['pending_login_otp_ts'] = int(time.time())

                sent = _send_login_otp(user, otp_code)
                if sent:
                    messages.info(request, 'We sent a 6-digit OTP to your email. Please verify to continue.')
                elif settings.DEBUG:
                    messages.warning(request, f'Email not configured. Use OTP: {otp_code}')
                else:
                    messages.error(request, 'Unable to send OTP email at the moment. Please try again.')
                    return render(request, 'auth/login.html', {'form': form, 'next': next_url})

                return redirect('login_verify_otp')
            else:
                messages.error(request, 'Invalid email or password.')
                return render(request, 'auth/login.html', {'form': form, 'next': next_url})
        else:
            return render(request, 'auth/login.html', {'form': form, 'next': next_url})
    else:
        form = UserLoginForm()
        return render(request, 'auth/login.html', {'form': form, 'next': next_url})


def adminLoginView(request):
    next_url = request.POST.get('next') or request.GET.get('next', '')
    if not next_url:
        next_url = '/dashboard/admin/'

    if request.user.is_authenticated:
        if request.user.is_admin:
            return redirect('admin_dashboard')
        messages.error(request, 'You are already logged in as a non-admin user.')
        if request.user.role == 'owner':
            return redirect('owner_dashboard')
        return redirect('user_dashboard')

    if request.method == "POST":
        form = UserLoginForm(request.POST or None)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, email=email, password=password)
            if user and user.is_admin:
                otp_code = f"{secrets.randbelow(900000) + 100000}"
                request.session['pending_login_user_id'] = user.pk
                request.session['pending_login_next'] = next_url
                request.session['pending_login_is_admin'] = True
                request.session['pending_login_otp'] = otp_code
                request.session['pending_login_otp_ts'] = int(time.time())

                sent = _send_login_otp(user, otp_code)
                if sent:
                    messages.info(request, 'Admin OTP sent to your email. Verify to continue.')
                elif settings.DEBUG:
                    messages.warning(request, f'Email not configured. Use OTP: {otp_code}')
                else:
                    messages.error(request, 'Unable to send OTP email at the moment. Please try again.')
                    return render(request, 'auth/admin_login.html', {'form': form, 'next': next_url})

                return redirect('login_verify_otp')

            if user and not user.is_admin:
                messages.error(request, 'Admin access required. Please use user login.')
            else:
                messages.error(request, 'Invalid admin credentials.')
            return render(request, 'auth/admin_login.html', {'form': form, 'next': next_url})

        return render(request, 'auth/admin_login.html', {'form': form, 'next': next_url})

    form = UserLoginForm()
    return render(request, 'auth/admin_login.html', {'form': form, 'next': next_url})


def login_verify_otp_view(request):
    pending_user_id = request.session.get('pending_login_user_id')
    pending_otp = request.session.get('pending_login_otp')
    otp_ts = int(request.session.get('pending_login_otp_ts') or 0)
    next_url = request.session.get('pending_login_next', '')

    if not pending_user_id or not pending_otp or not otp_ts:
        messages.error(request, 'Your login session has expired. Please login again.')
        return redirect('login')

    if int(time.time()) - otp_ts > 300:
        for key in ['pending_login_user_id', 'pending_login_next', 'pending_login_is_admin', 'pending_login_otp', 'pending_login_otp_ts']:
            request.session.pop(key, None)
        messages.error(request, 'OTP expired. Please login again.')
        return redirect('login')

    if request.method == 'POST':
        entered_otp = (request.POST.get('otp') or '').strip()
        if entered_otp != pending_otp:
            messages.error(request, 'Invalid OTP. Please try again.')
            return render(request, 'auth/login_otp.html')

        UserModel = get_user_model()
        user = UserModel.objects.filter(pk=pending_user_id).first()
        if not user:
            messages.error(request, 'User not found. Please login again.')
            return redirect('login')

        is_admin_login = bool(request.session.get('pending_login_is_admin'))
        for key in ['pending_login_user_id', 'pending_login_next', 'pending_login_is_admin', 'pending_login_otp', 'pending_login_otp_ts']:
            request.session.pop(key, None)

        if is_admin_login and not user.is_admin:
            messages.error(request, 'Admin access required.')
            return redirect('admin_login')

        login(request, user)
        messages.success(request, f'Welcome back, {user.first_name or user.email}!')

        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)

        if user.is_admin:
            return redirect('admin_dashboard')
        if user.role == 'owner':
            return redirect('owner_dashboard')
        return redirect('user_dashboard')

    return render(request, 'auth/login_otp.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return render(request, 'auth/logout.html')


@login_required
def user_dashboard_view(request):
    if request.user.is_admin:
        return redirect('admin_dashboard')
    if request.user.role == 'owner':
        return redirect('owner_analytics_dashboard')

    # Get or create the parking user linked by email
    parking_user = ParkingUser.objects.filter(email=request.user.email).first()

    active_reservations = []
    past_reservations = []
    total_spent = 0

    if parking_user:
        active_reservations = Reservation.objects.filter(
            user=parking_user, status='ACTIVE'
        ).select_related('slot', 'slot__parking_lot').order_by('-start_time')

        past_reservations = Reservation.objects.filter(
            user=parking_user
        ).exclude(status='ACTIVE').select_related('slot', 'slot__parking_lot').order_by('-start_time')[:10]

        total_spent = Payment.objects.filter(
            reservation__user=parking_user, payment_status='SUCCESS'
        ).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'active_reservations': active_reservations,
        'past_reservations': past_reservations,
        'total_spent': total_spent,
        'total_bookings': len(active_reservations) + len(past_reservations),
    }
    return render(request, 'dashboard/user_dashboard.html', context)


def _build_analytics_context(lot_filter=None, scope_label='System', revenue_field='amount', revenue_label='Total Revenue'):
    """Build analytics context for dashboards (consolidated from analytics_views)"""
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
def admin_dashboard_view(request):
    """Consolidated Admin Dashboard with analytics (replaces analytics_dashboard)"""
    if not request.user.is_admin:
        if request.user.role == 'owner':
            messages.error(request, 'Owner account does not have admin access.')
            return redirect('owner_analytics_dashboard')
        messages.error(request, 'Access denied.')
        return redirect('user_dashboard')

    context = _build_analytics_context(
        scope_label='Admin - Full System',
        revenue_field='amount',
        revenue_label='Total Revenue',
    )

    # Add owner summary for admin overview
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
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
def owner_analytics_dashboard(request):
    """Consolidated Owner Dashboard with analytics (replaces owner_analytics_dashboard)"""
    if request.user.is_admin:
        return redirect('admin_dashboard')
    if request.user.role != 'owner':
        messages.error(request, 'Access denied.')
        return redirect('user_dashboard')

    owner_admin = ParkingAdmin.objects.filter(user__email=request.user.email).first()
    if not owner_admin:
        messages.error(request, 'Owner profile not found.')
        return redirect('user_dashboard')

    context = _build_analytics_context(
        lot_filter={'created_by': owner_admin},
        scope_label='Owner - Your Parking Business',
        revenue_field='owner_earning',
        revenue_label='Owner Earnings',
    )
    context['owner_summary'] = []
    context['owner_lots'] = ParkingLot.objects.filter(created_by=owner_admin).order_by('-created_at')
    context['has_analytics'] = True
    return render(request, 'dashboard/admin_dashboard.html', context)