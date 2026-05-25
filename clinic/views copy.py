from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

from .models import Specialty, DoctorProfile, PatientProfile, DoctorSlot, Appointment
from .serializers import (
    UserRegisterSerializer, SpecialtySerializer, DoctorProfileSerializer,
    PatientProfileSerializer, DoctorDetailSerializer, DoctorSlotSerializer, AppointmentSerializer
)

User = get_user_model()

# 1️⃣ تسجيل مستخدم جديد (دكتور أو مريض)
class RegisterViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny] # أي حد يقدر يسجل حساب

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # إنشاء البروفايل تلقائياً بناءً على الـ Role المختار
        if user.role == 'doctor':
            DoctorProfile.objects.create(user=user)
        elif user.role == 'patient':
            PatientProfile.objects.create(user=user)
            
        return Response({
            "message": "User registered successfully!",
            "user": serializer.data
        }, status=status.HTTP_201_CREATED)


# 2️⃣ تصفية وعرض الأطباء المعتمدين (Approved Doctors) للمرضى
class DoctorListViewSet(viewsets.ReadOnlyModelViewSet):
    # جلب الدكاترة المقبولين من الأدمن فقط
    queryset = User.objects.filter(role='doctor', doctor_profile__is_approved=True)
    serializer_class = DoctorDetailSerializer
    permission_classes = [permissions.IsAuthenticated]


# 3️⃣ إدارة المواعيد المتاحة (Slots)
class DoctorSlotViewSet(viewsets.ModelViewSet):
    queryset = DoctorSlot.objects.all()
    serializer_class = DoctorSlotSerializer
    permission_classes = [permissions.IsAuthenticated]

    # جلب المواعيد الفاضية والمستقبلية فقط (للـ React Landing & Dashboard)
    @action(detail=False, methods=['get'], url_path='available')
    def available_slots(self, request):
        today = timezone.now().date()
        slots = DoctorSlot.objects.filter(is_booked=False, date__gte=today)
        serializer = self.get_serializer(slots, many=True)
        return Response(serializer.data)


# 4️⃣ إدارة الحجوزات والروشتات (Appointments & Core Logic)
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

    # 🛡️ الـ Core Logic: حجز ميعاد مع حماية من الـ Double Booking وضمان الـ Transaction
    @action(detail=False, methods=['post'], url_path='book')
    def book_appointment(self, request):
        slot_id = request.data.get('slot_id')
        doctor_id = request.data.get('doctor_id')
        fee = request.data.get('consultation_fee')
        last4 = request.data.get('payment_card_last4', '')

        try:
            # استخدام atomic لضمان إن العمليتين يتموا مع بعض أو يتلغوا مع بعض (حماية من الـ Race Condition)
            with transaction.atomic():
                # عمل select_for_update لقفل السطر في الداتا بيز لحين انتهاء الحجز (مفيش اتنين يحجزوا نفس الثانية)
                slot = DoctorSlot.objects.select_for_update().get(id=slot_id, is_booked=False)
                doctor = User.objects.get(id=doctor_id)

                appointment = Appointment.objects.create(
                    patient=request.user,
                    doctor=doctor,
                    slot=slot,
                    consultation_fee=fee,
                    status='Pending',
                    payment_status='Paid', # الدفع التجريبي الناجح من الـ React
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
            return [permissions.IsAdminUser()] # الأدمن فقط يعدل التخصصات
        return [permissions.IsAuthenticated()] # الكل يقدر يشوف التخصصات