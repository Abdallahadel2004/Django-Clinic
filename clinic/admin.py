from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Specialty, DoctorProfile, DoctorSlot, Appointment,PatientProfile

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'phone', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'phone')}),
    )

admin.site.register(User, CustomUserAdmin)
admin.site.register(Specialty)
admin.site.register(DoctorProfile)
admin.site.register(DoctorSlot)
admin.site.register(Appointment)
admin.site.register(PatientProfile)