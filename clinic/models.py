import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# Custom User Manager
# ─────────────────────────────────────────────────────────────────────────────

class CustomUserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required.')
        email = self.normalize_email(email)

        # Auto-generate a unique username if not supplied
        base_username = extra_fields.pop('username', None) or email.split('@')[0]
        username = base_username
        counter = 1
        while self.model.objects.filter(username=username).exists():
            username = f'{base_username}{counter}'
            counter += 1

        user = self.model(email=email, username=username, **extra_fields)
        if password:
            user.set_password(password)
        else:
            # Google OAuth users have no password
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, password, **extra_fields)


# ─────────────────────────────────────────────────────────────────────────────
# Custom User
# ─────────────────────────────────────────────────────────────────────────────

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('doctor',  'Doctor'),
        ('patient', 'Patient'),
        ('admin',   'Admin'),
    ]

    email    = models.EmailField(unique=True)
    username = models.CharField(max_length=150, blank=True)
    phone    = models.CharField(max_length=20, blank=True)
    role     = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')

    # ✅ Google OAuth fields
    google_id      = models.CharField(max_length=255, blank=True, null=True, unique=True)
    profile_picture = models.URLField(blank=True, null=True)
    auth_provider  = models.CharField(
        max_length=20,
        choices=[('email', 'Email'), ('google', 'Google')],
        default='email',
    )

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CustomUserManager()

    def __str__(self):
        return f'{self.get_full_name()} ({self.email})'


# ─────────────────────────────────────────────────────────────────────────────
# Specialty
# ─────────────────────────────────────────────────────────────────────────────

class Specialty(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'Specialties'

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────────────────────────────────────
# Doctor Profile
# ─────────────────────────────────────────────────────────────────────────────

class DoctorProfile(models.Model):
    user             = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='doctor_profile')
    specialty        = models.ForeignKey(Specialty, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctors')
    bio              = models.TextField(blank=True, null=True)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=250.00)
    clinic_address   = models.TextField(blank=True, null=True)
    clinic_phone     = models.CharField(max_length=20, blank=True, null=True)
    is_approved      = models.BooleanField(default=False)

    def __str__(self):
        return f'Dr. {self.user.get_full_name() or self.user.username}'


# ─────────────────────────────────────────────────────────────────────────────
# Doctor Slot
# ─────────────────────────────────────────────────────────────────────────────

class DoctorSlot(models.Model):
    doctor    = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='slots')
    date      = models.DateField()
    day       = models.CharField(max_length=20)
    time      = models.CharField(max_length=50)
    is_booked = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['doctor', 'date', 'time'],
                name='unique_doctor_date_time_slot'
            )
        ]
        indexes = [
            models.Index(fields=['doctor', 'date']),
            models.Index(fields=['is_booked']),
        ]

    def __str__(self):
        return f'Dr. {self.doctor.username} - {self.date} @ {self.time}'


# ─────────────────────────────────────────────────────────────────────────────
# Doctor Availability
# ─────────────────────────────────────────────────────────────────────────────

class DoctorAvailability(models.Model):
    WEEKDAY_CHOICES = [
        ('mon', 'Monday'),
        ('tue', 'Tuesday'),
        ('wed', 'Wednesday'),
        ('thu', 'Thursday'),
        ('fri', 'Friday'),
        ('sat', 'Saturday'),
        ('sun', 'Sunday'),
    ]

    doctor     = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='availabilities')
    day        = models.CharField(max_length=3, choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time   = models.TimeField()
    is_active  = models.BooleanField(default=True)

    class Meta:
        verbose_name          = 'Doctor Availability'
        verbose_name_plural   = 'Doctor Availabilities'
        ordering              = ['doctor', 'day', 'start_time']

    def __str__(self):
        return f'{self.doctor.username} - {self.get_day_display()} {self.start_time}-{self.end_time}'


# ─────────────────────────────────────────────────────────────────────────────
# Appointment
# ─────────────────────────────────────────────────────────────────────────────

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('Pending',   'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
        ('Rejected',  'Rejected'),
    ]

    patient           = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='patient_appointments')
    doctor            = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='doctor_appointments')
    slot              = models.ForeignKey(DoctorSlot, on_delete=models.SET_NULL, null=True, blank=True)

    status            = models.CharField(max_length=15, choices=STATUS_CHOICES, default='Pending')
    consultation_fee  = models.DecimalField(max_digits=10, decimal_places=2)

    payment_status    = models.CharField(max_length=15, default='Pending')
    payment_method    = models.CharField(max_length=50, blank=True, null=True)
    payment_card_last4 = models.CharField(max_length=4, blank=True, null=True)
    paid_at           = models.DateTimeField(blank=True, null=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    diagnosis         = models.TextField(blank=True, null=True)
    prescription      = models.TextField(blank=True, null=True)
    doctor_notes      = models.TextField(blank=True, null=True)

    # ── NEW financial tracking fields ──
    platform_commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Commission % snapshot at booking time"
    )
    platform_commission_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Commission amount deducted"
    )
    doctor_payout = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Net doctor payout after commission"
    )
    cancellation_reason = models.TextField(blank=True, null=True)
    cancelled_by = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=[('patient', 'Patient'), ('doctor', 'Doctor'), ('admin', 'Admin')]
    )
    cancelled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['doctor', 'status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'Appt #{self.id}: {self.patient.username} with Dr. {self.doctor.username}'


# ─────────────────────────────────────────────────────────────────────────────
# Patient Profile
# ─────────────────────────────────────────────────────────────────────────────

class PatientProfile(models.Model):
    GENDER_CHOICES = [
        ('Male',   'Male'),
        ('Female', 'Female'),
    ]

    user          = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='patient_profile')
    date_of_birth = models.DateField(blank=True, null=True)
    gender        = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    blood_type    = models.CharField(max_length=5, blank=True, null=True)
    address       = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'Profile: {self.user.get_full_name() or self.user.username}'


# ─────────────────────────────────────────────────────────────────────────────
# OTP
# ─────────────────────────────────────────────────────────────────────────────

class UserOTP(models.Model):
    user       = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='otp')
    code       = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def generate_code(self):
        self.code = str(random.randint(100000, 999999))
        self.created_at = timezone.now()
        self.save()

    def is_valid(self):
        return timezone.now() < self.created_at + timedelta(minutes=10)

    def __str__(self):
        return f'{self.user.username} - {self.code}'


# ─────────────────────────────────────────────────────────────────────────────
# Platform Configuration Model [NEW]
# ─────────────────────────────────────────────────────────────────────────────

class PlatformConfig(models.Model):
    """
    Singleton-like config table. Only one row should exist.
    Stores platform-wide financial settings.
    """
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        help_text="Platform commission percentage (e.g., 10.00 means 10%)"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform Configuration"
        verbose_name_plural = "Platform Configuration"

    def save(self, *args, **kwargs):
        # Enforce singleton: always use pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        """Returns the singleton config, creating with defaults if needed."""
        config, _ = cls.objects.get_or_create(pk=1)
        return config

    def __str__(self):
        return f"Platform Commission: {self.commission_percentage}%"


# ─────────────────────────────────────────────────────────────────────────────
# Payment Model [NEW]
# ─────────────────────────────────────────────────────────────────────────────

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('Completed', 'Completed'),
        ('Refunded', 'Refunded'),
        ('Partially_Refunded', 'Partially Refunded'),
    ]

    appointment = models.OneToOneField(
        'Appointment',
        on_delete=models.CASCADE,
        related_name='payment_record'
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Full consultation fee paid by patient"
    )
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Platform commission % at time of booking (snapshot)"
    )
    commission_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Platform commission amount = total_amount * (commission_percentage / 100)"
    )
    doctor_payout = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Net amount payable to doctor = total_amount - commission_fee"
    )
    payment_method = models.CharField(max_length=50, default='Online card')
    card_last4 = models.CharField(max_length=4, blank=True, null=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe PaymentIntent ID")
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='Completed'
    )
    paid_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        indexes = [
            models.Index(fields=['appointment']),
            models.Index(fields=['status']),
            models.Index(fields=['paid_at']),
        ]

    def __str__(self):
        return (
            f"Payment #{self.id} for Appt #{self.appointment_id}: "
            f"Total={self.total_amount}, Commission={self.commission_fee}, "
            f"DoctorPayout={self.doctor_payout}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Refund Model [NEW]
# ─────────────────────────────────────────────────────────────────────────────

class Refund(models.Model):
    INITIATED_BY_CHOICES = [
        ('patient', 'Patient'),
        ('doctor', 'Doctor'),
        ('admin', 'Admin'),
    ]

    appointment = models.OneToOneField(
        'Appointment',
        on_delete=models.CASCADE,
        related_name='refund_record'
    )
    payment = models.OneToOneField(
        'Payment',
        on_delete=models.CASCADE,
        related_name='refund'
    )
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount refunded to patient (equals total_amount — full refund policy)"
    )
    commission_retained = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Commission amount retained by platform (0.00 for full refund policy)"
    )
    reason = models.TextField(blank=True, null=True)
    initiated_by = models.CharField(max_length=10, choices=INITIATED_BY_CHOICES)
    stripe_refund_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe Refund ID")
    refunded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Refund"
        verbose_name_plural = "Refunds"
        indexes = [
            models.Index(fields=['appointment']),
            models.Index(fields=['refunded_at']),
        ]

    def __str__(self):
        return f"Refund #{self.id} for Appt #{self.appointment_id}: {self.refund_amount} EGP"


class Review(models.Model):
    appointment = models.OneToOneField(
        'Appointment', on_delete=models.CASCADE, related_name='review'
    )
    patient = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='reviews'
    )
    doctor = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='doctor_reviews'
    )
    rating = models.IntegerField()
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['doctor']),
            models.Index(fields=['appointment']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Review #{self.id} for Appt #{self.appointment_id} - {self.rating}⭐"
