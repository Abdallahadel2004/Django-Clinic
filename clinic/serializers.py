from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Specialty, DoctorProfile, PatientProfile, DoctorSlot, Appointment

User = get_user_model()

class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = '__all__'

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'phone', 'first_name', 'last_name']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            role=validated_data.get('role', 'patient'),
            phone=validated_data.get('phone', ''),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user


class DoctorProfileSerializer(serializers.ModelSerializer):
    specialty_name = serializers.ReadOnlyField(source='specialty.name')

    class Meta:
        model = DoctorProfile
        fields = ['id', 'specialty', 'specialty_name', 'bio', 'consultation_fee', 'clinic_address', 'is_approved']
        read_only_fields = ['is_approved']


class PatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = ['id', 'date_of_birth', 'gender', 'blood_type', 'address']


class DoctorDetailSerializer(serializers.ModelSerializer):
    profile = DoctorProfileSerializer(source='doctor_profile', read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'phone', 'profile']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class DoctorSlotSerializer(serializers.ModelSerializer):
    doctor_name = serializers.ReadOnlyField(source='doctor.get_full_name')

    class Meta:
        model = DoctorSlot
        fields = ['id', 'doctor', 'doctor_name', 'date', 'day', 'time', 'is_booked']


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.ReadOnlyField(source='patient.get_full_name')
    doctor_name = serializers.ReadOnlyField(source='doctor.get_full_name')
    slot_details = DoctorSlotSerializer(source='slot', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_name', 'doctor', 'doctor_name', 'slot', 'slot_details',
            'status', 'consultation_fee', 'payment_status', 'payment_method', 
            'payment_card_last4', 'paid_at', 'created_at',
            'diagnosis', 'prescription', 'doctor_notes'
        ]
        read_only_fields = ['patient', 'status', 'payment_status', 'paid_at']