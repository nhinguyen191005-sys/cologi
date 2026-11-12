from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ExternalUserAccess, UserRole
from .serializers import LoginSerializer


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        password = serializer.validated_data["password"]

        user = authenticate(
            request,
            email=email,
            password=password,
        )

        if user is None or not user.is_active:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "user": {
                    "id": user.pk,
                    "email": user.email,
                    "full_name": user.full_name,
                },
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        roles = list(
            UserRole.objects.filter(
                user=user,
                role__is_active=True,
            )
            .order_by("role__code")
            .values_list("role__code", flat=True)
        )

        external_accesses = list(
            ExternalUserAccess.objects.filter(
                user=user,
                is_active=True,
            )
            .order_by("actor_type")
            .values(
                "actor_type",
                "supplier_id",
                "provider_id",
            )
        )

        return Response(
            {
                "id": user.pk,
                "email": user.email,
                "full_name": user.full_name,
                "roles": roles,
                "external_accesses": external_accesses,
            }
        )