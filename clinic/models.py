import random
from datetime import timedelta

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