from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Specialty, DoctorProfile, DoctorSlot, Appointment, PatientProfile

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'phone', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'phone')}),
    )

class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialty', 'is_approved', 'consultation_fee')
    list_filter = ('is_approved', 'specialty')
    search_fields = ('user__username', 'user__email')

class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'doctor', 'status', 'payment_status', 'created_at')
    list_filter = ('status', 'payment_status')
    search_fields = ('patient__username', 'doctor__username')

admin.site.register(User, CustomUserAdmin)
admin.site.register(Specialty)
admin.site.register(DoctorProfile, DoctorProfileAdmin)
admin.site.register(DoctorSlot)
admin.site.register(Appointment, AppointmentAdmin)
admin.site.register(PatientProfile)