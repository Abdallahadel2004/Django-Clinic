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
    is_approved = models.BooleanField(default=False) 

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username}"


class DoctorSlot(models.Model):
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='slots')
    date = models.DateField()              # التاريخ: YYYY-MM-DD
    day = models.CharField(max_length=20)   # اسم اليوم: Monday, Tuesday...
    time = models.CharField(max_length=50)  # الفاصل الزمني: "10:00 AM - 10:30 AM"
    is_booked = models.BooleanField(default=False) # لمنع الحجز المزدوج (Double Booking)

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
    slot = models.OneToOneField(DoctorSlot, on_delete=models.CASCADE, related_name='appointment')
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='Pending')
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2)
    
    payment_status = models.CharField(max_length=15, default='Pending') # Paid, Pending
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    payment_card_last4 = models.CharField(max_length=4, blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    diagnosis = models.TextField(blank=True, null=True)      # التشخيص
    prescription = models.TextField(blank=True, null=True)   # الأدوية
    doctor_notes = models.TextField(blank=True, null=True)   # ملاحظات الطبيب

    def __str__(self):
        return f"Appt #{self.id}: {self.patient.username} with Dr. {self.doctor.username}"
    
class PatientProfile(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]
    # مربوط بعلاقة OneToOne مع اليوزر الأساسي اللي نوعه مريض
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    blood_type = models.CharField(max_length=5, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Profile: {self.user.get_full_name() or self.user.username}"