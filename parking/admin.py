from django.contrib import admin
from .models import User, Admin, ParkingLot, ParkingSlot, Reservation, Payment, Notification, Analytics


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone_number', 'role', 'status', 'created_at')
    list_filter = ('role', 'status')
    search_fields = ('full_name', 'email', 'phone_number')


@admin.register(Admin)
class AdminModelAdmin(admin.ModelAdmin):
    list_display = ('user', 'access_level')
    list_filter = ('access_level',)
    search_fields = ('user__full_name', 'user__email')


@admin.register(ParkingLot)
class ParkingLotAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'total_slots', 'available_slots', 'created_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'location')


@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):
    list_display = ('parking_lot', 'slot_number', 'slot_type', 'status')
    list_filter = ('slot_type', 'status', 'parking_lot')
    search_fields = ('slot_number', 'parking_lot__name')


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('reservation_code', 'user', 'slot', 'reservation_type', 'status', 'start_time', 'end_time')
    list_filter = ('reservation_type', 'status')
    search_fields = ('reservation_code', 'user__full_name', 'user__email')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('reservation', 'amount', 'payment_method', 'payment_status', 'transaction_date')
    list_filter = ('payment_method', 'payment_status')
    search_fields = ('reservation__reservation_code',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'status', 'created_at')
    list_filter = ('notification_type', 'status')
    search_fields = ('user__full_name', 'message')


@admin.register(Analytics)
class AnalyticsAdmin(admin.ModelAdmin):
    list_display = ('parking_lot', 'peak_hours', 'total_revenue', 'usage_rate', 'report_date')
    list_filter = ('report_date', 'parking_lot')
    search_fields = ('parking_lot__name',)
