
# Create your models here.
from django.db import models
from django.utils import timezone

# Create your models here.
#user model
class User(models.Model):
    ROLE_CHOICES = [
        ('USER', 'User'),
        ('ADMIN', 'Admin'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    ]

    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='USER')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name
#admin model  
class Admin(models.Model):
    ACCESS_CHOICES = [
        ('SUPER', 'Super'),
        ('STANDARD', 'Standard'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_level = models.CharField(max_length=10, choices=ACCESS_CHOICES)

    def __str__(self):
        return f"Admin - {self.user.full_name}"
#parkinglot model
class ParkingLot(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    total_slots = models.PositiveIntegerField()
    available_slots = models.PositiveIntegerField()
    created_by = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
#parking slot model
class ParkingSlot(models.Model):
    SLOT_TYPE_CHOICES = [
        ('REGULAR', 'Regular'),
        ('EV', 'EV'),
        ('HANDICAP', 'Handicap'),
    ]

    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('RESERVED', 'Reserved'),
        ('OCCUPIED', 'Occupied'),
        ('DISABLED', 'Disabled'),
    ]

    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE)
    slot_number = models.CharField(max_length=20)
    slot_type = models.CharField(max_length=10, choices=SLOT_TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='AVAILABLE')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['parking_lot', 'slot_number'],
                name='unique_slot_number_per_lot',
            )
        ]

    def __str__(self):
        return f"{self.parking_lot.name} - {self.slot_number}"
#reservation model
class Reservation(models.Model):
    RESERVATION_TYPE_CHOICES = [
        ('HOURLY', 'Hourly'),
        ('DAILY', 'Daily'),
        ('MONTHLY', 'Monthly'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    slot = models.ForeignKey(ParkingSlot, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    reservation_type = models.CharField(max_length=10, choices=RESERVATION_TYPE_CHOICES)
    reservation_code = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    scanned_by_email = models.EmailField(blank=True)

    def __str__(self):
        return self.reservation_code
#pyment model
class Payment(models.Model):
    METHOD_CHOICES = [
        ('CARD', 'Card'),
        ('WALLET', 'Wallet'),
        ('UPI', 'UPI'),
    ]

    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('PENDING', 'Pending'),
    ]

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    owner_earning = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    payment_status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    transaction_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.reservation.reservation_code} - {self.payment_status}"


class AuditLog(models.Model):
    actor_email = models.EmailField()
    action = models.CharField(max_length=80)
    entity = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=64, blank=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} by {self.actor_email}"
#notification model
class Notification(models.Model):
    TYPE_CHOICES = [
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('APP', 'App'),
    ]

    STATUS_CHOICES = [
        ('SENT', 'Sent'),
        ('PENDING', 'Pending'),
        ('FAILED', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    notification_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification to {self.user.full_name}"
#analytics model
class Analytics(models.Model):
    admin_id = models.ForeignKey(
        Admin,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE)
    peak_hours = models.CharField(max_length=50)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2)
    usage_rate = models.DecimalField(max_digits=5, decimal_places=2)
    report_date = models.DateField()

    def __str__(self):
        return f"Analytics - {self.parking_lot.name}"


class ReservationReminder(models.Model):
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Reminder sent for {self.reservation.reservation_code}"