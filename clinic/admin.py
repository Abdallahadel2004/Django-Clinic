from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Specialty, DoctorProfile, DoctorSlot, Appointment, PatientProfile, DoctorAvailability


class CustomUserAdmin(UserAdmin):
    list_display  = ('email', 'username', 'role', 'phone', 'auth_provider', 'is_active', 'is_staff')
    list_filter   = ('role', 'auth_provider', 'is_active', 'is_staff')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering      = ('email',)

    # ✅ Use email instead of username in the add/change form
    fieldsets = (
        (None,               {'fields': ('email', 'password')}),
        ('Personal Info',    {'fields': ('first_name', 'last_name', 'username', 'phone')}),
        ('Role & Provider',  {'fields': ('role', 'auth_provider', 'google_id', 'profile_picture')}),
        ('Permissions',      {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates',  {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields':  ('email', 'password1', 'password2', 'role', 'first_name', 'last_name'),
        }),
    )


class DoctorProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'specialty', 'is_approved', 'consultation_fee', 'clinic_phone')
    list_filter   = ('is_approved', 'specialty')
    search_fields = ('user__email', 'user__username')


class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display  = ('doctor', 'day', 'start_time', 'end_time', 'is_active')
    list_filter   = ('day', 'is_active')
    search_fields = ('doctor__email', 'doctor__username')


class AppointmentAdmin(admin.ModelAdmin):
    list_display  = ('id', 'patient', 'doctor', 'status', 'payment_status', 'created_at')
    list_filter   = ('status', 'payment_status')
    search_fields = ('patient__email', 'doctor__email')


admin.site.register(CustomUser,        CustomUserAdmin)
admin.site.register(Specialty)
admin.site.register(DoctorProfile,     DoctorProfileAdmin)
admin.site.register(DoctorSlot)
admin.site.register(DoctorAvailability, DoctorAvailabilityAdmin)
admin.site.register(Appointment,       AppointmentAdmin)
admin.site.register(PatientProfile)