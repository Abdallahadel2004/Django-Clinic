from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from .models import Specialty, DoctorProfile, PatientProfile, DoctorSlot, Appointment, Review

User = get_user_model()

class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = '__all__'

class UserRegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        validators=[UniqueValidator(queryset=User.objects.all(), message="This username is already taken.")]
    )
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all(), message="A user with this email already exists.")]
    )
    
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'phone', 'first_name', 'last_name']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
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
    doctor = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = DoctorSlot
        fields = ['id', 'doctor', 'doctor_name', 'date', 'day', 'time', 'is_booked']

    def validate(self, data):
        user = self.context['request'].user
        doctor = user
                
        date = data.get('date')
        time_str = data.get('time')

        if not time_str or ' - ' not in time_str:
            raise serializers.ValidationError("Invalid time format. Use 'HH:MM - HH:MM'.")

        def to_minutes(t_str):
            h, m = map(int, t_str.split(':'))
            return h * 60 + m

        try:
            start_str, end_str = time_str.split(' - ')
            new_start = to_minutes(start_str)
            new_end = to_minutes(end_str)
        except ValueError:
            raise serializers.ValidationError("Invalid time values.")

        existing_slots = DoctorSlot.objects.filter(doctor=doctor, date=date)
        if self.instance:
            existing_slots = existing_slots.exclude(pk=self.instance.pk)

        for slot in existing_slots:
            ex_start_str, ex_end_str = slot.time.split(' - ')
            ex_start = to_minutes(ex_start_str)
            ex_end = to_minutes(ex_end_str)

            if new_start < ex_end and new_end > ex_start:
                raise serializers.ValidationError(f"This time slot overlaps with an existing slot: {slot.time}")
        
        return data

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


class ReviewSerializer(serializers.ModelSerializer):
    patient_name = serializers.ReadOnlyField(source='patient.get_full_name')

    class Meta:
        model = Review
        fields = ['id', 'appointment', 'patient', 'patient_name', 'doctor', 'rating', 'comment', 'created_at']
        read_only_fields = ['patient', 'doctor', 'created_at']

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['username'] = user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['role'] = self.user.role
        data['username'] = self.user.username
        data['uid'] = self.user.id
        return data

__all__ = [
    'UserRegisterSerializer',
    'SpecialtySerializer',
    'DoctorProfileSerializer',
    'PatientProfileSerializer',
    'DoctorDetailSerializer',
    'DoctorSlotSerializer',
    'AppointmentSerializer',
    'ReviewSerializer',
    'CustomTokenObtainPairSerializer',
]