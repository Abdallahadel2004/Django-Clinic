from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail

from ..models import Specialty, DoctorProfile, PatientProfile, DoctorSlot, Appointment, UserOTP, DoctorAvailability, PlatformConfig, Payment, Refund, Review
from .serializers import (
    UserSerializer, UserRegisterSerializer, SpecialtySerializer,
    DoctorProfileSerializer, PatientProfileSerializer, DoctorDetailSerializer,
    DoctorSlotSerializer, AppointmentSerializer, DoctorAvailabilitySerializer, ReviewSerializer
)
from .permissions import IsAdminOrReadOnly

User = get_user_model()


class RegisterViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        email = request.data.get('email')
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            if not existing_user.is_active:
                otp_obj, _ = UserOTP.objects.get_or_create(user=existing_user)
                otp_obj.generate_code()
                self._send_verification_email(existing_user, otp_obj.code)
                return Response({
                    'message': 'This account is already registered but not verified. The verification code (OTP) has been resent to your email.',
                    'email': existing_user.email
                }, status=status.HTTP_200_OK)
            return Response({
                'error': 'This email is already registered and verified. You can log in directly.'
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            user = serializer.save()
            user.is_active = False
            user.save()

            if user.role == 'doctor':
                DoctorProfile.objects.create(user=user)
            elif user.role == 'patient':
                PatientProfile.objects.create(user=user)

            otp_obj, _ = UserOTP.objects.get_or_create(user=user)
            otp_obj.generate_code()

        self._send_verification_email(user, otp_obj.code)
        return Response({
            'message': 'User registered successfully. Please verify your account using the OTP code sent to your email.',
            'email': user.email
        }, status=status.HTTP_201_CREATED)

    def _send_verification_email(self, user, code):
        try:
            send_mail(
                subject='CarePulse - Verify Your Account',
                message=f'Welcome to CarePulse! Your verification code is: {code}. It is valid for 10 minutes.',
                from_email='no-reply@carepulse.com',
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f'Email failed to send: {e}')


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp')

        if not email or not otp_code:
            return Response({'error': 'Email and OTP code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            otp_obj = UserOTP.objects.get(user=user, code=otp_code)

            if not otp_obj.is_valid():
                return Response({'error': 'OTP code has expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)

            if user.is_active:
                return Response({'message': 'Account verified successfully! You can now log in.'}, status=status.HTTP_200_OK)

            user.is_active = True
            user.save()
            otp_obj.delete()
            return Response({'message': 'Account verified successfully! You can now log in.'}, status=status.HTTP_200_OK)
        except (User.DoesNotExist, UserOTP.DoesNotExist):
            return Response({'error': 'Invalid email or OTP code.'}, status=status.HTTP_400_BAD_REQUEST)


class DoctorListViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DoctorDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        if user.is_staff or user.role == 'admin':
            return User.objects.filter(role='doctor')
        try:
            return User.objects.filter(role='doctor', doctor_profile__is_approved=True)
        except Exception:
            return User.objects.filter(role='doctor', doctorprofile__is_approved=True)
class DoctorSlotViewSet(viewsets.ModelViewSet):
    queryset = DoctorSlot.objects.all()
    serializer_class = DoctorSlotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'doctor':
            return DoctorSlot.objects.filter(doctor=user)
        if user.role == 'admin' or user.is_staff:
            return DoctorSlot.objects.all()
        return DoctorSlot.objects.none()

    def perform_create(self, serializer):
        serializer.save(doctor=self.request.user)

    @action(detail=False, methods=['get'], url_path='available')
    def available_slots(self, request):
        today = timezone.now().date()
        slots = DoctorSlot.objects.filter(is_booked=False, date__gte=today)
        doctor_id = request.query_params.get('doctor_id')
        if doctor_id:
            slots = slots.filter(doctor_id=doctor_id)
        serializer = self.get_serializer(slots, many=True)
        return Response(serializer.data)

class DoctorAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = DoctorAvailability.objects.all()
    serializer_class = DoctorAvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'admin':
            queryset = DoctorAvailability.objects.all()
        elif user.role == 'doctor':
            queryset = DoctorAvailability.objects.filter(doctor=user)
        else:
            queryset = DoctorAvailability.objects.none()

        doctor_id = self.request.query_params.get('doctor_id')
        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)
        return queryset

    def perform_create(self, serializer):
        if self.request.user.role != 'doctor' and not self.request.user.is_staff:
            raise permissions.PermissionDenied('Only doctors or admins can create availability schedules.')
        if self.request.user.role == 'doctor':
            serializer.save(doctor=self.request.user)
        else:
            serializer.save()


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Appointment.objects.all()
        if user.role == 'doctor':
            return Appointment.objects.filter(doctor=user)
        return Appointment.objects.filter(patient=user)

    @action(detail=False, methods=['get'], url_path='upcoming')
    def upcoming(self, request):
        queryset = self.get_queryset()
        today = timezone.now().date()
        upcoming_qs = queryset.filter(slot__date__gte=today).exclude(status__in=['Cancelled', 'Completed', 'Rejected'])
        serializer = self.get_serializer(upcoming_qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='past')
    def past(self, request):
        queryset = self.get_queryset()
        today = timezone.now().date()
        past_qs = queryset.filter(slot__date__lt=today) | queryset.filter(status__in=['Completed', 'Cancelled', 'Rejected'])
        serializer = self.get_serializer(past_qs.distinct(), many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='book')
    def book_appointment(self, request):
        slot_id = request.data.get('slot_id')
        doctor_id = request.data.get('doctor_id')
        fee = request.data.get('consultation_fee')
        payment_method_id = request.data.get('payment_method_id', 'pm_card_visa')

        if not slot_id or not doctor_id or fee is None:
            return Response({'error': 'Missing required fields: slot_id, doctor_id, consultation_fee.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from decimal import Decimal
            import stripe
            
            appointment = None
            commission_pct = Decimal('0.00')
            commission_fee = Decimal('0.00')
            doctor_payout = Decimal('0.00')
            total_amount = Decimal(str(fee))

            # Retrieve card details safely from Stripe payment method
            try:
                pm = stripe.PaymentMethod.retrieve(payment_method_id)
                card_last4 = pm.card.last4
            except Exception:
                card_last4 = '4242'

            try:
                intent = stripe.PaymentIntent.create(
                    amount=int(total_amount * 100),
                    currency='egp',
                    payment_method=payment_method_id,
                    confirm=True,
                    automatic_payment_methods={
                        'enabled': True,
                        'allow_redirects': 'never'
                    }
                )
            except stripe.error.StripeError as e:
                return Response({'error': f'Stripe payment failed: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                slot = DoctorSlot.objects.select_for_update().get(id=slot_id, doctor_id=doctor_id, is_booked=False)
                doctor = User.objects.get(id=doctor_id)
                
                # Fetch platform commission percentage
                config = PlatformConfig.get_config()
                commission_pct = config.commission_percentage
                commission_fee = (total_amount * Decimal(str(commission_pct)) / Decimal('100')).quantize(Decimal('0.01'))
                doctor_payout = total_amount - commission_fee

                appointment = Appointment.objects.create(
                    patient=request.user,
                    doctor=doctor,
                    slot=slot,
                    consultation_fee=total_amount,
                    status='Pending',
                    payment_status='Paid',
                    payment_method='Stripe Card',
                    payment_card_last4=card_last4,
                    paid_at=timezone.now(),
                    platform_commission_percentage=commission_pct,
                    platform_commission_fee=commission_fee,
                    doctor_payout=doctor_payout,
                )

                Payment.objects.create(
                    appointment=appointment,
                    total_amount=total_amount,
                    commission_percentage=commission_pct,
                    commission_fee=commission_fee,
                    doctor_payout=doctor_payout,
                    payment_method='Stripe Card',
                    card_last4=card_last4,
                    stripe_payment_intent_id=intent.id,
                    status='Completed',
                )

                slot.is_booked = True
                slot.save()

            # ✅ Send booking confirmation email outside the atomic block
            self._send_booking_confirmation_email(appointment)

            return Response({
                'message': 'Appointment booked successfully!',
                'appointment_id': appointment.id,
                'financial_summary': {
                    'total_amount': f'{total_amount:.2f}',
                    'platform_commission_percentage': f'{commission_pct:.2f}',
                    'platform_commission_fee': f'{commission_fee:.2f}',
                    'doctor_payout': f'{doctor_payout:.2f}',
                    'payment_status': 'Paid',
                    'payment_method': 'Stripe Card',
                    'stripe_payment_intent_id': intent.id
                }
            }, status=status.HTTP_201_CREATED)

        except DoctorSlot.DoesNotExist:
            return Response({'error': 'This appointment slot is unavailable, already booked, or does not belong to this doctor.'}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({'error': 'The specified doctor does not exist in the system.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'An error occurred during booking: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_appointment(self, request, pk=None):
        appointment = self.get_object()
        cancel_reason = request.data.get('reason', 'No specific reason provided.')

        if request.user.role != 'admin' and appointment.doctor != request.user and appointment.patient != request.user:
            return Response({'error': 'You do not have permission to cancel this appointment.'}, status=status.HTTP_403_FORBIDDEN)
        if appointment.status == 'Cancelled':
            return Response({'error': 'This appointment is already cancelled.'}, status=status.HTTP_400_BAD_REQUEST)

        if request.user == appointment.patient:
            cancelled_by = 'patient'
        elif request.user == appointment.doctor:
            cancelled_by = 'doctor'
        else:
            cancelled_by = 'admin'

        try:
            from decimal import Decimal
            refund_amount = Decimal('0.00')

            with transaction.atomic():
                appointment.status = 'Cancelled'
                appointment.cancellation_reason = cancel_reason
                appointment.cancelled_by = cancelled_by
                appointment.cancelled_at = timezone.now()

                if appointment.payment_status == 'Paid':
                    appointment.payment_status = 'Refunded'

                    # Fetch and lock the related Payment record
                    payment = Payment.objects.select_for_update().get(appointment=appointment)
                    payment.status = 'Refunded'
                    
                    stripe_refund_id = None
                    if payment.stripe_payment_intent_id:
                        import stripe
                        try:
                            stripe_refund = stripe.Refund.create(
                                payment_intent=payment.stripe_payment_intent_id
                            )
                            stripe_refund_id = stripe_refund.id
                        except stripe.error.StripeError as e:
                            raise ValueError(f"Stripe refund failed: {str(e)}")

                    payment.save()

                    # Create Refund record (full refund policy)
                    Refund.objects.create(
                        appointment=appointment,
                        payment=payment,
                        refund_amount=payment.total_amount,
                        commission_retained=Decimal('0.00'),
                        reason=cancel_reason,
                        initiated_by=cancelled_by,
                        stripe_refund_id=stripe_refund_id,
                    )
                    refund_amount = payment.total_amount

                appointment.save()

                if appointment.slot:
                    slot = DoctorSlot.objects.select_for_update().get(id=appointment.slot_id)
                    slot.is_booked = False
                    slot.save()

            # ✅ Send notification emails outside the atomic block
            self._send_cancellation_email(appointment, cancel_reason)
            if cancelled_by == 'patient':
                self._send_doctor_cancellation_email(appointment, cancel_reason)

            return Response({
                'message': 'Appointment cancelled successfully. Slot freed, patient notified, and refund processed.',
                'appointment_status': 'Cancelled',
                'payment_status': appointment.payment_status,
                'refund_details': {
                    'refund_amount': f'{refund_amount:.2f}',
                    'commission_retained': '0.00',
                    'refund_policy': 'full_refund',
                    'initiated_by': cancelled_by
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': f'An error occurred during cancellation: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete_appointment(self, request, pk=None):
        appointment = self.get_object()
        appointment.status = 'Completed'
        appointment.diagnosis = request.data.get('diagnosis')
        appointment.prescription = request.data.get('prescription')
        appointment.doctor_notes = request.data.get('doctor_notes')
        appointment.save()
        return Response({'message': 'Appointment completed successfully.'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve_appointment(self, request, pk=None):
        appointment = self.get_object()

        if request.user.role != 'admin' and appointment.doctor != request.user:
            return Response({'error': 'You do not have permission to approve this appointment.'}, status=status.HTTP_403_FORBIDDEN)
        if appointment.status == 'Confirmed':
            return Response({'error': 'This appointment is already confirmed.'}, status=status.HTTP_400_BAD_REQUEST)

        appointment.status = 'Confirmed'
        appointment.doctor_notes = request.data.get('doctor_notes', appointment.doctor_notes)
        appointment.save()

        # ✅ NEW: notify patient that doctor confirmed
        self._send_approval_email(appointment)

        return Response({
            'message': 'Appointment approved successfully.',
            'appointment_status': appointment.status
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject_appointment(self, request, pk=None):
        appointment = self.get_object()

        if request.user.role != 'admin' and appointment.doctor != request.user:
            return Response({'error': 'You do not have permission to reject this appointment.'}, status=status.HTTP_403_FORBIDDEN)
        if appointment.status in ['Rejected', 'Cancelled']:
            return Response({'error': 'This appointment is already closed.'}, status=status.HTTP_400_BAD_REQUEST)

        appointment.status = 'Rejected'
        appointment.doctor_notes = request.data.get('doctor_notes', appointment.doctor_notes)
        if appointment.slot:
            appointment.slot.is_booked = False
            appointment.slot.save()
        appointment.save()

        return Response({
            'message': 'Appointment rejected successfully.',
            'appointment_status': appointment.status
        }, status=status.HTTP_200_OK)

    # ─── Email helpers ────────────────────────────────────────────────────────

    def _send_booking_confirmation_email(self, appointment):
        """Sent to patient immediately after a successful booking."""
        try:
            doctor_name = appointment.doctor.get_full_name() or appointment.doctor.username
            slot_time = appointment.slot.time if appointment.slot else 'N/A'
            slot_date = appointment.slot.date if appointment.slot else 'N/A'
            fee = appointment.consultation_fee
            patient_name = appointment.patient.first_name or appointment.patient.username

            subject = 'CarePulse - Appointment Booking Confirmation'
            message = (
                f'Hello {patient_name},\n\n'
                f'Your appointment with Dr. {doctor_name} has been successfully booked.\n\n'
                f'Details:\n'
                f'  Date      : {slot_date}\n'
                f'  Time      : {slot_time}\n'
                f'  Fee       : {fee} EGP\n'
                f'  Status    : Pending (awaiting doctor confirmation)\n\n'
                'You will receive another email once the doctor confirms your appointment.\n\n'
                'Wishing you good health,\nCarePulse Team'
            )
            send_mail(
                subject=subject,
                message=message,
                from_email='no-reply@carepulse.com',
                recipient_list=[appointment.patient.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f'Failed to send booking confirmation email: {e}')

    def _send_approval_email(self, appointment):
        """Sent to patient when the doctor confirms (approves) the appointment."""
        try:
            doctor_name = appointment.doctor.get_full_name() or appointment.doctor.username
            slot_time = appointment.slot.time if appointment.slot else 'N/A'
            slot_date = appointment.slot.date if appointment.slot else 'N/A'
            patient_name = appointment.patient.first_name or appointment.patient.username

            subject = 'CarePulse - Your Appointment is Confirmed'
            message = (
                f'Hello {patient_name},\n\n'
                f'Great news! Dr. {doctor_name} has confirmed your appointment.\n\n'
                f'Details:\n'
                f'  Date : {slot_date}\n'
                f'  Time : {slot_time}\n\n'
                'Please try to arrive 10 minutes early.\n\n'
                'CarePulse Team'
            )
            send_mail(
                subject=subject,
                message=message,
                from_email='no-reply@carepulse.com',
                recipient_list=[appointment.patient.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f'Failed to send approval email: {e}')

    def _send_cancellation_email(self, appointment, reason):
        """Sent to patient when their appointment is cancelled."""
        try:
            doctor_name = appointment.doctor.get_full_name() or appointment.doctor.username
            slot_time = appointment.slot.time if appointment.slot else 'N/A'
            slot_date = appointment.slot.date if appointment.slot else 'N/A'
            patient_name = appointment.patient.first_name or appointment.patient.username

            subject = 'CarePulse - Your Appointment Has Been Cancelled'
            message = (
                f'Hello {patient_name},\n\n'
                f'We regret to inform you that your appointment with Dr. {doctor_name} '
                f'scheduled on {slot_date} at {slot_time} has been cancelled.\n\n'
                f'Reason: "{reason}"\n\n'
                f'A full refund of {appointment.consultation_fee} EGP has been issued back to your account.\n\n'
                'Wishing you the best of health,\nCarePulse Team'
            )
            send_mail(
                subject=subject,
                message=message,
                from_email='no-reply@carepulse.com',
                recipient_list=[appointment.patient.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f'Failed to send patient cancellation email: {e}')

    def _send_doctor_cancellation_email(self, appointment, reason):
        """Sent to doctor when a patient cancels."""
        try:
            patient_name = appointment.patient.get_full_name() or appointment.patient.username
            slot_time = appointment.slot.time if appointment.slot else 'N/A'
            slot_date = appointment.slot.date if appointment.slot else 'N/A'
            doctor_name = appointment.doctor.get_full_name() or appointment.doctor.username

            subject = 'CarePulse - Appointment Cancelled by Patient'
            message = (
                f'Dear Dr. {doctor_name},\n\n'
                f'We would like to inform you that {patient_name} has cancelled their appointment '
                f'scheduled on {slot_date} at {slot_time}.\n\n'
                f'Cancellation reason: "{reason}"\n\n'
                'The slot has been freed and is now available for new bookings.\n\n'
                'Best regards,\nCarePulse Team'
            )
            send_mail(
                subject=subject,
                message=message,
                from_email='no-reply@carepulse.com',
                recipient_list=[appointment.doctor.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f'Failed to send doctor cancellation email: {e}')


class SpecialtyViewSet(viewsets.ModelViewSet):
    queryset = Specialty.objects.all()
    serializer_class = SpecialtySerializer
    permission_classes = [IsAdminOrReadOnly]


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegisterSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ['update', 'partial_update']:
            return [permissions.IsAuthenticated()]
        if self.action in ['list', 'retrieve', 'destroy', 'approve', 'block']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if request.user != instance and not request.user.is_staff:
            return Response({'error': 'You do not have permission to edit this profile.'}, status=status.HTTP_403_FORBIDDEN)
            
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
    
    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.all()
        if not user.is_staff and user.role != 'admin':
            return User.objects.filter(id=user.id)
        role = self.request.query_params.get('role')
        if role in ['doctor', 'patient', 'admin']:
            queryset = queryset.filter(role=role)
        return queryset

    @action(detail=False, methods=['get'], url_path='me')
    def get_current_user(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='approve', permission_classes=[permissions.IsAdminUser])
    def approve(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        
        is_doctor_approved = False
        if user.role == 'doctor':
            profile, _ = DoctorProfile.objects.get_or_create(user=user)
            profile.is_approved = True
            profile.save()
            is_doctor_approved = True
            
        user.save()
        
        return Response({
            'message': 'User approved successfully.',
            'is_active': user.is_active,
            'is_approved': is_doctor_approved 
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='block', permission_classes=[permissions.IsAdminUser])
    def block(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({
            'message': 'User blocked successfully.',
            'is_active': user.is_active
        }, status=status.HTTP_200_OK)


class DoctorProfileViewSet(viewsets.ModelViewSet):
    queryset = DoctorProfile.objects.all()
    serializer_class = DoctorProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'admin':
            return DoctorProfile.objects.all()
        if user.role == 'doctor':
            return DoctorProfile.objects.filter(user=user)
        return DoctorProfile.objects.none()

    @action(detail=False, methods=['get', 'put', 'patch'], url_path='me')
    def my_profile(self, request):
        if request.user.role != 'doctor':
            return Response({'error': 'Sorry, this profile is intended for doctors only.'}, status=status.HTTP_403_FORBIDDEN)
        profile, _ = DoctorProfile.objects.get_or_create(user=request.user)
        if request.method == 'GET':
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='approve', permission_classes=[permissions.IsAdminUser])
    def approve_profile(self, request, pk=None):
        profile = self.get_object()
        profile.is_approved = True
        profile.save()
        profile.user.is_active = True
        profile.user.save()
        return Response({
            'message': 'Doctor profile approved successfully.',
            'doctor_id': profile.user.id,
            'is_approved': profile.is_approved
        }, status=status.HTTP_200_OK)


class PatientProfileViewSet(viewsets.ModelViewSet):
    queryset = PatientProfile.objects.all()
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get', 'put', 'patch'], url_path='me')
    def my_profile(self, request):
        if request.user.role != 'patient':
            return Response({'error': 'Sorry, this profile is intended for patients only.'}, status=status.HTTP_403_FORBIDDEN)
        profile, _ = PatientProfile.objects.get_or_create(user=request.user)
        if request.method == 'GET':
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    


class ReviewViewSet(viewsets.ModelViewSet):
    """Create and list reviews. POST /reviews/ enforces appointment ownership and completed status.
    GET /reviews/?doctor=<id> returns public reviews for a doctor.
    GET /reviews/my/ returns current patient's reviews.
    """
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Review.objects.all()
        doctor_id = self.request.query_params.get('doctor')
        if doctor_id:
            return qs.filter(doctor_id=doctor_id)
        if user.role == 'doctor':
            return qs.filter(doctor=user)
        # patients see only their reviews by default
        return qs.filter(patient=user)

    @action(detail=False, methods=['get'], url_path='my')
    def my_reviews(self, request):
        qs = Review.objects.filter(patient=request.user)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        appointment_id = request.data.get('appointment')
        rating = request.data.get('rating')
        comment = request.data.get('comment', '').strip()
        if not appointment_id or rating is None:
            return Response({'error': 'appointment and rating are required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            appointment = Appointment.objects.get(id=appointment_id)
        except Appointment.DoesNotExist:
            return Response({'error': 'Appointment not found.'}, status=status.HTTP_400_BAD_REQUEST)
        if appointment.patient != request.user:
            return Response({'error': 'You can only review your own appointment.'}, status=status.HTTP_403_FORBIDDEN)
        if appointment.status != 'Completed':
            return Response({'error': 'Only completed appointments can be reviewed.'}, status=status.HTTP_400_BAD_REQUEST)
        if hasattr(appointment, 'review'):
            return Response({'error': 'This appointment has already been reviewed.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            r = int(rating)
            if r < 1 or r > 5:
                raise ValueError()
        except Exception:
            return Response({'error': 'Rating must be an integer between 1 and 5.'}, status=status.HTTP_400_BAD_REQUEST)
        review = Review.objects.create(
            appointment=appointment,
            patient=request.user,
            doctor=appointment.doctor,
            rating=r,
            comment=comment or None,
        )
        serializer = self.get_serializer(review)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



