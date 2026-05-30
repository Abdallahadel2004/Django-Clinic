from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('doctor', 'Doctor'),
        ('patient', 'Patient'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='patient')
    phone = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Specialty(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Specialties"

    def __str__(self):
        return self.name


class DoctorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    specialty = models.ForeignKey(Specialty, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctors')
    bio = models.TextField(blank=True, null=True)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=250.00)
    clinic_address = models.TextField(blank=True, null=True)
    clinic_phone = models.CharField(max_length=20, blank=True, null=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username}"


class DoctorAvailability(models.Model):
    DAY_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='availabilities')
    day = models.CharField(max_length=9, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('doctor', 'day', 'start_time', 'end_time')

    def __str__(self):
        return f"{self.doctor.username} available on {self.day} from {self.start_time} to {self.end_time}"


class DoctorSlot(models.Model):
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='slots')
    date = models.DateField()              
    day = models.CharField(max_length=20)   
    time = models.CharField(max_length=50)  
    is_booked = models.BooleanField(default=False) 

    def __str__(self):
        return f"Dr. {self.doctor.username} - {self.date} @ {self.time}"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]
    
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_appointments')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doctor_appointments')
    slot = models.ForeignKey('DoctorSlot', on_delete=models.SET_NULL, null=True, blank=True)

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='Pending')
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2)
    
    payment_status = models.CharField(max_length=15, default='Pending') # Paid, Pending
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    payment_card_last4 = models.CharField(max_length=4, blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    diagnosis = models.TextField(blank=True, null=True)     
    prescription = models.TextField(blank=True, null=True)  
    doctor_notes = models.TextField(blank=True, null=True)   

    def __str__(self):
        return f"Appt #{self.id}: {self.patient.username} with Dr. {self.doctor.username}"
    
class PatientProfile(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    blood_type = models.CharField(max_length=5, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Profile: {self.user.get_full_name() or self.user.username}"
    



import random
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class UserOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='otp')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def generate_code(self):
        self.code = str(random.randint(100000, 999999))
        self.created_at = timezone.now()
        self.save()

    def is_valid(self):
        return timezone.now() < self.created_at + timedelta(minutes=10)

    def __str__(self):
        return f"{self.user.username} - {self.code}"