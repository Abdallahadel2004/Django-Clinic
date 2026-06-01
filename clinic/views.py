from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail

from .models import Specialty, DoctorProfile, PatientProfile, DoctorSlot, Appointment, UserOTP
from .serializers import (
    UserRegisterSerializer, SpecialtySerializer, DoctorProfileSerializer,
    PatientProfileSerializer, DoctorDetailSerializer, DoctorSlotSerializer, AppointmentSerializer
)

User = get_user_model()

# --- Register & OTP ---
class RegisterViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        email = request.data.get('email')
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            if not existing_user.is_active:
                otp_obj, created = UserOTP.objects.get_or_create(user=existing_user)
                otp_obj.generate_code()
                self._send_verification_email(existing_user, otp_obj.code)
                return Response({"message": "Verification code resent.", "email": existing_user.email}, status=status.HTTP_200_OK)
            return Response({"error": "Already registered and verified."}, status=status.HTTP_400_BAD_REQUEST)
                
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = serializer.save()
            user.is_active = False  
            user.save()
            if user.role == 'doctor': DoctorProfile.objects.create(user=user)
            elif user.role == 'patient': PatientProfile.objects.create(user=user)
            otp_obj, created = UserOTP.objects.get_or_create(user=user)
            otp_obj.generate_code()
        self._send_verification_email(user, otp_obj.code)
        return Response({"message": "Registered. Please verify OTP.", "email": user.email}, status=status.HTTP_201_CREATED)

    def _send_verification_email(self, user, code):
        send_mail('CarePulse - Verify', f'Code: {code}', 'no-reply@carepulse.com', [user.email])

class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp')
        try:
            user = User.objects.get(email=email)
            otp_obj = UserOTP.objects.get(user=user, code=otp_code)
            if not otp_obj.is_valid(): return Response({"error": "Expired"}, status=status.HTTP_400_BAD_REQUEST)
            user.is_active = True
            user.save()
            otp_obj.delete()
            return Response({"message": "Verified"}, status=status.HTTP_200_OK)
        except (User.DoesNotExist, UserOTP.DoesNotExist):
            return Response({"error": "Invalid"}, status=status.HTTP_400_BAD_REQUEST)

# --- Doctor & Appointment ViewSets ---
class DoctorListViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(role='doctor', doctor_profile__is_approved=True)
    serializer_class = DoctorDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

class DoctorSlotViewSet(viewsets.ModelViewSet):
    queryset = DoctorSlot.objects.all()
    serializer_class = DoctorSlotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(doctor=self.request.user)

    @action(detail=False, methods=['get'], url_path='available')
    def available_slots(self, request):
        slots = DoctorSlot.objects.filter(is_booked=False, date__gte=timezone.now().date())
        doctor_id = request.query_params.get('doctor_id')
        if doctor_id: slots = slots.filter(doctor_id=doctor_id)
        return Response(self.get_serializer(slots, many=True).data)

class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'admin': return Appointment.objects.all()
        return Appointment.objects.filter(doctor=user) if user.role == 'doctor' else Appointment.objects.filter(patient=user)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_appointment(self, request, pk=None):
        appointment = self.get_object()
        appointment.status = 'Cancelled'
        appointment.save()
        return Response({"message": "Cancelled"})


# --- Profiles & Other ---
class SpecialtyViewSet(viewsets.ModelViewSet):
    queryset = Specialty.objects.all()
    serializer_class = SpecialtySerializer
    permission_classes = [permissions.IsAuthenticated]

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.IsAuthenticated]

class DoctorProfileViewSet(viewsets.ModelViewSet):
    queryset = DoctorProfile.objects.all()
    serializer_class = DoctorProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

class PatientProfileViewSet(viewsets.ModelViewSet):
    queryset = PatientProfile.objects.all()
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

__all__ = [
    'RegisterViewSet', 'VerifyOTPView', 'DoctorListViewSet', 'DoctorSlotViewSet',
    'AppointmentViewSet', 'SpecialtyViewSet', 'DoctorProfileViewSet', 'UserViewSet', 'PatientProfileViewSet'
]