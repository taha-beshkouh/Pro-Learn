from django.contrib.auth import logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.api.serializers import (
    LoginInputSerializer,
    LoginResponseSerializer,
    RegistrationInputSerializer,
    UserOutputSerializer,
)
from apps.accounts.services import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    RegistrationData,
    authenticate_user,
    register_and_start_session,
    start_authenticated_session,
)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registration"

    def post(self, request):
        serializer = RegistrationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = register_and_start_session(
                request=request,
                data=RegistrationData(**serializer.validated_data),
            )
        except EmailAlreadyRegistered as exc:
            raise ValidationError(
                {"email": ["A user with this email already exists."]},
                code="unique",
            ) from exc

        return Response(UserOutputSerializer(user).data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = authenticate_user(request=request, **serializer.validated_data)
        except InvalidCredentials as exc:
            raise ValidationError(
                {"detail": "Unable to log in with the provided credentials."},
                code="invalid_credentials",
            ) from exc

        role_conflict = start_authenticated_session(request=request, user=user)
        return Response(
            LoginResponseSerializer(
                user,
                context={"role_conflict": role_conflict},
            ).data
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserOutputSerializer(request.user).data)

