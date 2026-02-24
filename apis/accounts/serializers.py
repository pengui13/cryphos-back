from datetime import timedelta
from random import randint

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PendingRegistration
from .utils import send_verification_code

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["tg_nickname"]


class RegisterStartSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError("Passwords must match.")
        if User.objects.filter(email__iexact=attrs["email"]).exists():
            raise serializers.ValidationError("Email is already in use.")
        if User.objects.filter(username__iexact=attrs["username"]).exists():
            raise serializers.ValidationError("Username is already taken.")
        return attrs

    def create(self, validated_data):

        email = validated_data["email"].strip().lower()
        username = validated_data["username"].strip()
        pw_hash = make_password(validated_data["password"])
        code = f"{randint(0, 999999):06d}"

        pending, _ = PendingRegistration.objects.update_or_create(
            email=email,
            defaults={
                "username": username,
                "password_hash": pw_hash,
                "code": code,
                "expires_at": timezone.now() + timedelta(minutes=10),
                "tries": 0,
            },
        )

        send_verification_code(email, code)
        pending.resend_count = pending.resend_count + 1
        pending.last_sent_at = timezone.now()
        pending.save(update_fields=["resend_count", "last_sent_at"])
        return {"detail": "Verification code sent"}


class RegisterResendSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        try:
            PendingRegistration.objects.get(email=email)
        except PendingRegistration.DoesNotExist as err:
            raise serializers.ValidationError("Invalid code or email") from err
        return attrs

    def create(self, validated_data):
        email = validated_data["email"]
        pending = PendingRegistration.objects.get(email=email)
        code = f"{randint(0, 999999):06d}"
        pending.code = code
        send_verification_code(email, code)
        pending.expires_at = timezone.now() + timedelta(minutes=2)
        pending.save(update_fields=["code", "expires_at"])
        return {"detail": "Account created"}


class RegisterVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        code = attrs["code"].strip()
        try:
            pending = PendingRegistration.objects.get(email=email)
        except PendingRegistration.DoesNotExist as err:
            raise serializers.ValidationError("Invalid code or email") from err
        if pending.is_expired():
            raise serializers.ValidationError("Code has expired. Please restart registration.")
        if pending.tries >= 5:
            raise serializers.ValidationError("Too many attempts. Please restart registration.")
        if code != pending.code:
            pending.tries += 1
            pending.save(update_fields=["tries"])
            raise serializers.ValidationError("Invalid code.")
        attrs["pending"] = pending
        return attrs

    def create(self, validated_data):
        pending = validated_data["pending"]
        if User.objects.filter(email__iexact=pending.email).exists():
            pending.delete()
            return {"detail": "Account already exists. Try logging in."}

        user = User(username=pending.username, email=pending.email)
        user.password = pending.password_hash
        user.is_active = True  # type: ignore[misc]
        user.save()

        pending.delete()
        return {"detail": "Account created"}


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as err:
            raise serializers.ValidationError("Invalid credentials") from err

        user = authenticate(username=user.username, password=password)

        if not user:
            raise serializers.ValidationError("Invalid credentials.")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        tokens = RefreshToken.for_user(user)
        return {
            "access": str(tokens.access_token),
            "refresh": str(tokens),
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        }


class ResetStartSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user with this email")
        return value


class ResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return attrs
