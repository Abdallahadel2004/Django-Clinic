from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import Specialty, DoctorProfile, PatientProfile, DoctorSlot, Appointment, DoctorAvailability, Payment, Refund, Review
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.validators import UniqueValidator

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    status = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'name', 'phone', 'role', 'role_display',
            'is_active', 'is_staff', 'status'
        ]
        read_only_fields = ['id', 'full_name', 'role_display', 'status', 'name']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_status(self, obj):
        if not obj.is_active:
            return 'blocked'
        if obj.role == 'doctor':
            try:
                profile = obj.doctor_profile
            except Exception:
                try:
                    profile = obj.doctorprofile
                except Exception:
                    return 'pending'
            if profile and profile.is_approved:
                return 'approved'
            return 'pending'
        return 'approved'


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = '__all__'


class UserRegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'phone', 'first_name', 'last_name']

    def validate_email(self, value):
        if User.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError('A verified account with this email already exists.')
        return value

    def create(self, validated_data):
        email = validated_data['email']
        username = validated_data.get('username') or email.split('@')[0]
        base = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f'{base}{counter}'
            counter += 1
        user = User.objects.create_user(
            email=email,
            username=username,
            password=validated_data['password'],
            role=validated_data.get('role', 'patient'),
            phone=validated_data.get('phone', ''),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        return user


class DoctorProfileSerializer(serializers.ModelSerializer):
    specialty_name = serializers.ReadOnlyField(source='specialty.name')

    class Meta:
        model = DoctorProfile
        fields = ['id', 'specialty', 'specialty_name', 'bio', 'consultation_fee',
                  'clinic_address', 'clinic_phone', 'is_approved']
        read_only_fields = ['is_approved']


class DoctorAvailabilitySerializer(serializers.ModelSerializer):
    doctor_name = serializers.ReadOnlyField(source='doctor.get_full_name')
    doctor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='doctor'),
        required=False
    )

    class Meta:
        model = DoctorAvailability
        fields = ['id', 'doctor', 'doctor_name', 'day', 'start_time', 'end_time', 'is_active']

    def validate(self, data):
        if data['end_time'] <= data['start_time']:
            raise serializers.ValidationError('end_time must be greater than start_time.')
        return data

    def create(self, validated_data):
        if 'doctor' not in validated_data:
            validated_data['doctor'] = self.context['request'].user
        return super().create(validated_data)


class PatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = ['id', 'date_of_birth', 'gender', 'blood_type', 'address']


class DoctorDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    status = serializers.SerializerMethodField()

    specialty_name = serializers.SerializerMethodField()
    specialty_id = serializers.SerializerMethodField()
    bio = serializers.SerializerMethodField()
    consultation_fee = serializers.SerializerMethodField()
    clinic_address = serializers.SerializerMethodField()
    clinic_phone = serializers.SerializerMethodField()
    is_approved = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'phone', 'role', 'role_display', 'is_active',
            'status', 'is_approved',
            'specialty_name', 'specialty_id', 'bio', 'consultation_fee',
            'clinic_address', 'clinic_phone',
        ]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def _get_safe_profile(self, obj):
        if hasattr(obj, 'doctor_profile'):
            return obj.doctor_profile
        if hasattr(obj, 'doctorprofile'):
            return obj.doctorprofile
        return None

    def get_is_approved(self, obj):
        prof = self._get_safe_profile(obj)
        return prof.is_approved if prof else False

    def get_status(self, obj):
        if not obj.is_active:
            return 'blocked'
        prof = self._get_safe_profile(obj)
        if prof and prof.is_approved:
            return 'approved'
        return 'pending'

    def get_specialty_name(self, obj):
        prof = self._get_safe_profile(obj)
        return prof.specialty.name if prof and prof.specialty else 'General Practitioner'

    def get_specialty_id(self, obj):
        
        prof = self._get_safe_profile(obj)
        if prof and prof.specialty:
            return prof.specialty.id
        return None

    def get_bio(self, obj):
        prof = self._get_safe_profile(obj)
        return prof.bio if prof else ''

    def get_consultation_fee(self, obj):
        prof = self._get_safe_profile(obj)
        return str(prof.consultation_fee) if prof else '0.00'

    def get_clinic_address(self, obj):
        prof = self._get_safe_profile(obj)
        return prof.clinic_address if prof else ''

    def get_clinic_phone(self, obj):
        prof = self._get_safe_profile(obj)
        return prof.clinic_phone if prof else ''


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
                raise serializers.ValidationError(
                    f"This time slot overlaps with an existing slot: {slot.time}"
                )

        return data


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'appointment', 'total_amount', 'commission_percentage',
            'commission_fee', 'doctor_payout', 'payment_method',
            'card_last4', 'status', 'paid_at', 'updated_at'
        ]
        read_only_fields = fields


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = [
            'id', 'appointment', 'payment', 'refund_amount',
            'commission_retained', 'reason', 'initiated_by', 'refunded_at'
        ]
        read_only_fields = fields


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.ReadOnlyField(source='patient.get_full_name')
    doctor_name = serializers.ReadOnlyField(source='doctor.get_full_name')
    slot_details = DoctorSlotSerializer(source='slot', read_only=True)
    payment_record = PaymentSerializer(read_only=True)
    refund_record = RefundSerializer(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_name', 'doctor', 'doctor_name',
            'slot', 'slot_details',
            'status', 'consultation_fee', 'payment_status', 'payment_method',
            'payment_card_last4', 'paid_at', 'created_at',
            'diagnosis', 'prescription', 'doctor_notes',
            'platform_commission_percentage', 'platform_commission_fee',
            'doctor_payout', 'cancellation_reason', 'cancelled_by', 'cancelled_at',
            'payment_record', 'refund_record'
        ]
        read_only_fields = [
            'patient', 'status', 'payment_status', 'paid_at',
            'platform_commission_percentage', 'platform_commission_fee',
            'doctor_payout', 'cancellation_reason', 'cancelled_by', 'cancelled_at'
        ]


class ReviewSerializer(serializers.ModelSerializer):
    patient_name = serializers.ReadOnlyField(source='patient.get_full_name')

    class Meta:
        model = Review
        fields = ['id', 'appointment', 'patient', 'patient_name', 'doctor', 'rating', 'comment', 'created_at']
        read_only_fields = ['patient', 'doctor', 'created_at']


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['email'] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['role'] = self.user.role
        data['email'] = self.user.email
        data['uid'] = self.user.id
        return data