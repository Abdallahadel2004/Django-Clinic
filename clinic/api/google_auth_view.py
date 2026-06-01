from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.conf import settings
from clinic.models import DoctorProfile, PatientProfile

User = get_user_model()

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['email'] = user.email
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'role': user.role,
        'email': user.email,
        'uid': user.id,
        'is_approved': getattr(user, 'doctor_profile', None) and user.doctor_profile.is_approved # نرسل حالة الموافقة للفرونت
    }

class GoogleLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        credential = request.data.get('credential')
        requested_role = request.data.get('role', 'patient')
        role = requested_role if requested_role in ['doctor', 'patient'] else 'patient'

        if not credential:
            return Response({'error': 'Google credential token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            google_data = id_token.verify_oauth2_token(credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID)
        except ValueError as e:
            return Response({'error': f'Invalid Google token: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        email = google_data.get('email')
        google_id = google_data.get('sub')
        first_name = google_data.get('given_name', '')
        last_name = google_data.get('family_name', '')
        picture = google_data.get('picture', '')

        user = User.objects.filter(email=email).first()

        if user:
            if not user.google_id:
                user.google_id = google_id
                user.save()
        else:
            user = User.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                google_id=google_id,
                profile_picture=picture,
                auth_provider='google',
                role=role,
                is_active=True,  
            )

            if role == 'doctor':
                DoctorProfile.objects.create(user=user, is_approved=False)
            else:
                PatientProfile.objects.create(user=user)

        tokens = get_tokens_for_user(user)
        return Response(tokens, status=status.HTTP_200_OK)