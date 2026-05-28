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

class RegisterViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        email = request.data.get('email')
        if email and User.objects.filter(email=email).exists():
            return Response({
                "message": "User registered successfully. Please verify your account using the OTP code sent to your email.",
                "email": email
            }, status=status.HTTP_201_CREATED)
            
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            user = serializer.save()
            user.is_active = False
            user.save()
            
            if user.role == 'doctor':
                DoctorProfile.objects.create(user=user)
            elif user.role == 'patient':
                PatientProfile.objects.create(user=user)
            
            otp_obj, created = UserOTP.objects.get_or_create(user=user)
            otp_obj.generate_code()

        try:
            send_mail(
                subject='CarePulse - Verify Your Account',
                message=f'Welcome to CarePulse! Your verification code is: {otp_obj.code}. It is valid for 10 minutes.',
                from_email='no-reply@carepulse.com',
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Email failed to send: {e}")
            
        return Response({
            "message": "User registered successfully. Please verify your account using the OTP code sent to your email.",
            "email": user.email
        }, status=status.HTTP_201_CREATED)


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp')

        if not email or not otp_code:
            return Response({"error": "Email and OTP code are required."}, status=status.HTTP_400_BAD_REQUEST)
        generic_error = Response({"error": "Invalid email or OTP code."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            otp_obj = UserOTP.objects.get(user=user, code=otp_code)

            if not otp_obj.is_valid():
                return Response({"error": "OTP code has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

            if user.is_active:
                return Response({"message": "Account verified successfully! You can now log in."}, status=status.HTTP_200_OK)

            user.is_active = True
            user.save()
            otp_obj.delete()

            return Response({"message": "Account verified successfully! You can now log in."}, status=status.HTTP_200_OK)

        except (User.DoesNotExist, UserOTP.DoesNotExist):
            return generic_error



class DoctorListViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(role='doctor', doctor_profile__is_approved=True)
    serializer_class = DoctorDetailSerializer
    permission_classes = [permissions.IsAuthenticated]


class DoctorSlotViewSet(viewsets.ModelViewSet):
    queryset = DoctorSlot.objects.all()
    serializer_class = DoctorSlotSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='available')
    def available_slots(self, request):
        today = timezone.now().date()
        slots = DoctorSlot.objects.filter(is_booked=False, date__gte=today)
        serializer = self.get_serializer(slots, many=True)
        return Response(serializer.data)


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Appointment.objects.all()
        elif user.role == 'doctor':
            return Appointment.objects.filter(doctor=user)
        return Appointment.objects.filter(patient=user)

    @action(detail=False, methods=['post'], url_path='book')
    def book_appointment(self, request):
        slot_id = request.data.get('slot_id')
        doctor_id = request.data.get('doctor_id')
        fee = request.data.get('consultation_fee')
        last4 = request.data.get('payment_card_last4', '')

        try:
            with transaction.atomic():
                slot = DoctorSlot.objects.select_for_update().get(id=slot_id, is_booked=False)
                doctor = User.objects.get(id=doctor_id)

                appointment = Appointment.objects.create(
                    patient=request.user,
                    doctor=doctor,
                    slot=slot,
                    consultation_fee=fee,
                    status='Pending',
                    payment_status='Paid',
                    payment_method='Online card',
                    payment_card_last4=last4,
                    paid_at=timezone.now()
                )

                slot.is_booked = True
                slot.save()

                return Response({"message": "Appointment booked successfully!", "appointment_id": appointment.id}, status=status.HTTP_201_CREATED)

        except DoctorSlot.DoesNotExist:
            return Response({"error": "This slot is already booked or does not exist."}, status=status.HTTP_400_BAD_REQUEST)


class SpecialtyViewSet(viewsets.ModelViewSet):
    queryset = Specialty.objects.all()
    serializer_class = SpecialtySerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()] 
        return [permissions.IsAuthenticated()] 
    

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get', 'put', 'patch'], url_path='me')
    def get_current_user(self, request):
        user = request.user
        
        if request.method == 'GET':
            serializer = self.get_serializer(user)
            return Response(serializer.data)
            
        elif request.method in ['PUT', 'PATCH']:
            serializer = self.get_serializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        

class DoctorProfileViewSet(viewsets.ModelViewSet):
    queryset = DoctorProfile.objects.all()
    serializer_class = DoctorProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get', 'put', 'patch'], url_path='me')
    def my_profile(self, request):
        profile, created = DoctorProfile.objects.get_or_create(user=request.user)
        
        if request.method == 'GET':
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
            
        elif request.method in ['PUT', 'PATCH']:
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)