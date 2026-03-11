import random
import requests
import stripe
import throttling as thrott
from bots.models import Bot
from django.conf import settings
from django.contrib.auth import get_user_model
from loguru import logger
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import BillingProfile, PasswordResetCode
from .serializers import (
    LoginSerializer,
    RegisterResendSerializer,
    RegisterStartSerializer,
    RegisterVerifySerializer,
    UserSerializer,
)


User = get_user_model()
stripe.api_key = settings.STRIPE_SECRET_KEY


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):

    user = request.user

    price_id = request.data.get("price_id") or settings.STRIPE_PRICE_ID
    if not price_id:
        return Response(
            {"error": "Price ID not configured"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    bp, _ = BillingProfile.objects.get_or_create(user=user)

    customer_id = bp.stripe_customer_id

    if customer_id:
        try:
            stripe.Customer.retrieve(customer_id)
        except Exception as e:
            logger.error(e)
            customer_id = None

    if not customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"user_id": user.id},
        )
        customer_id = customer.id
        bp.stripe_customer_id = customer_id
        bp.save(update_fields=["stripe_customer_id"])

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            allow_promotion_codes=True,
            automatic_tax={"enabled": False},
            tax_id_collection={"enabled": False},
            subscription_data={
                "metadata": {
                    "user_id": str(user.id),
                    "billing_profile_id": str(bp.id),
                }
            },
            client_reference_id=str(user.id),
            success_url=f"{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/billing/cancel",
        )
    except Exception as e:
        logger.error("Stripe error in create_checkout_session:", e)
        return Response(
            {"error": "Failed to create Stripe Checkout Session"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({"url": session.url}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_billing_portal_session(request):
    """
    Lets the user manage card/cancel themselves.
    """
    user = request.user
    try:
        bp = user.billing
        if not bp.stripe_customer_id:
            return Response({"error": "No Stripe customer"}, status=status.HTTP_400_BAD_REQUEST)
        portal = stripe.billing_portal.Session.create(
            customer=bp.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/account",
        )
        return Response({"url": portal.url})
    except BillingProfile.DoesNotExist:
        return Response({"error": "No billing profile"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def billing_me(request):
    """
    Returns current user's billing/subscription info.
    Used by frontend to know if subscription is active.
    """
    user = request.user
    bp, _ = BillingProfile.objects.get_or_create(user=user)
    bots_amount = Bot.objects.filter(owner=user).count()
    return Response(
        {
            "is_active": bp.is_active,
            "status": bp.status,
            "price_id": bp.price_id,
            "cancel_at_period_end": bp.cancel_at_period_end,
            "current_period_end": bp.current_period_end,
            "trial_end": bp.trial_end,
            "bots_count": bots_amount,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def stripe_webhook(request):
    payload = request.body
    sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.error("WEBHOOK ERROR (signature or payload):", e)
        return Response(status=status.HTTP_400_BAD_REQUEST)

    etype = event["type"]
    data = event["data"]["object"]

    def update_from_subscription(sub, session_meta=None):
        customer_id = sub.get("customer")
        sub_id = sub.get("id")
        meta = sub.get("metadata", {}) or {}
        if session_meta:
            for k, v in session_meta.items():
                meta.setdefault(k, v)


        bp = None

        bp_id = meta.get("billing_profile_id")
        if bp_id:
            bp = BillingProfile.objects.filter(id=bp_id).first()

        if not bp:
            bp = (
                BillingProfile.objects.filter(stripe_subscription_id=sub_id).first()
                or BillingProfile.objects.filter(stripe_customer_id=customer_id).first()
            )

        user = None
        user_id = meta.get("user_id")
        if not bp and user_id:
            try:
                user = User.objects.get(id=user_id)
                bp, _ = BillingProfile.objects.get_or_create(user=user)
            except User.DoesNotExist:
                logger.error("User with id from meta not found:", user_id)

        if not bp and customer_id:
            try:
                cust = stripe.Customer.retrieve(customer_id)
                email = cust.get("email")
            except Exception as e:
                logger.error("Could not retrieve customer in webhook:", e)
                email = None

            if email:
                user = User.objects.filter(email=email).first()
                if user:
                    bp, _ = BillingProfile.objects.get_or_create(user=user)
                    if not bp.stripe_customer_id:
                        bp.stripe_customer_id = customer_id
                        bp.save(update_fields=["stripe_customer_id"])


        items = sub.get("items", {}).get("data", [])
        price = items[0]["price"] if items else {}

        bp.stripe_subscription_id = sub_id
        bp.status = sub.get("status") or "null"
        bp.price_id = price.get("id", "")

        cpe = sub.get("current_period_end")
        te = sub.get("trial_end")
        if cpe:
            bp.current_period_end = timezone.datetime.fromtimestamp(cpe, tz=timezone.utc)
        if te:
            bp.trial_end = timezone.datetime.fromtimestamp(te, tz=timezone.utc)

        bp.cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
        bp.save()

        u = bp.user
        new_flag = bp.is_active
        if u.tg_approved != new_flag:
            u.tg_approved = new_flag
            u.save(update_fields=["tg_approved"])



    if etype == "checkout.session.completed":
        session_meta = data.get("metadata", {}) or {}

        if data.get("customer") and data.get("subscription"):
            sub = stripe.Subscription.retrieve(data["subscription"])
            update_from_subscription(sub, session_meta=session_meta)

    elif etype in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "customer.subscription.paused",
        "customer.subscription.resumed",
    ):
        update_from_subscription(data)

    elif etype == "payment_intent.succeeded":
        invoice_id = data.get("invoice")

        if invoice_id:
            try:
                inv = stripe.Invoice.retrieve(invoice_id)
                sub_id = inv.get("subscription")
                if sub_id:
                    sub = stripe.Subscription.retrieve(sub_id)
                    update_from_subscription(sub)

            except Exception as e:
                logger.error("Error retrieving invoice/subscription:", e)


    elif etype == "invoice.payment_failed":
        bp = BillingProfile.objects.filter(stripe_customer_id=data.get("customer")).first()
        if bp:
            bp.status = "past_due"
            bp.save(update_fields=["status"])
            if bp.user.tg_approved:
                bp.user.tg_approved = False
                bp.user.save(update_fields=["tg_approved"])

    return Response(status=status.HTTP_200_OK)


class RegisterStartView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterStartSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Verification code sent"}, status=status.HTTP_200_OK)


class GetUserTelegram(RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class RegisterVerifyView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterVerifySerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        return Response(payload, status=200)


class RegisterResendView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterResendSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        return Response(payload, status=200)


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_classes = [thrott.AuthTrottle]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class RegisterView(generics.CreateAPIView):
    """Simple registration without email verification - returns tokens"""

    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        email = request.data.get("email", "").strip()
        username = request.data.get("username", email).strip()
        password = request.data.get("password", "")
        password2 = request.data.get("password2", "")

        if not email or not password:
            return Response(
                {"detail": "Email and password are required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if password != password2:
            return Response(
                {"detail": "Passwords do not match"}, status=status.HTTP_400_BAD_REQUEST
            )

        if len(password) < 6:
            return Response(
                {"detail": "Password must be at least 6 characters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {"detail": "User with this email already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"detail": "Username already taken"}, status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "detail": "Account created successfully",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class RefreshTokenView(TokenRefreshView):
    permission_classes = [AllowAny]
    serializer_class = TokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            logger.error(e)
            return Response({"error": "Invalid refresh token"}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


def send_telegram_reset_code(chat_id, code):
    """Send password reset code via Telegram"""
    bot_token = settings.TELEGRAM_BOT_TOKEN

    message = (
        f"🔐 *Password Reset Code*\n\n"
        f"Your code: `{code}`\n\n"
        f"This code expires in 15 minutes.\n"
        f"If you didn't request this, ignore this message."
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    try:
        requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            },
        )
    except Exception as e:
        logger.error(f"Failed to send Telegram reset code: {e}")


class ResetStartView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip()

        if not email:
            return Response({"detail": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "If this email exists, a reset code was sent to Telegram"},
                status=status.HTTP_200_OK,
            )

        if not user.chat_id:
            return Response(
                {"detail": "No Telegram account linked. Please contact support."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = f"{random.randint(100000, 999999)}"

        PasswordResetCode.objects.filter(user=user, is_used=False).update(is_used=True)

        PasswordResetCode.objects.create(user=user, code=code)

        send_telegram_reset_code(user.chat_id, code)

        return Response({"detail": "Reset code sent to your Telegram"}, status=status.HTTP_200_OK)


class AddTelegram(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        telegram_nickname = request.data.get("nickname", "")
        user.tg_nickname = telegram_nickname
        user.save()
        return Response({"resp": "all good"})


class GetTelegramInfo(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({"tg": user.tg_nickname, "chat_id": user.chat_id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response({"ping": True})


class ResetVerifyView(APIView):
    """Verify code and set new password"""

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip()
        code = request.data.get("code", "").strip()
        password = request.data.get("password", "")
        password2 = request.data.get("password2", "")

        if not all([email, code, password]):
            return Response(
                {"detail": "All fields are required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if password != password2:
            return Response(
                {"detail": "Passwords do not match"}, status=status.HTTP_400_BAD_REQUEST
            )

        if len(password) < 6:
            return Response(
                {"detail": "Password must be at least 6 characters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "Invalid email"}, status=status.HTTP_400_BAD_REQUEST)

        reset_code = PasswordResetCode.objects.filter(user=user, code=code, is_used=False).last()

        if not reset_code or reset_code.is_expired():
            return Response(
                {"detail": "Invalid or expired code"}, status=status.HTTP_400_BAD_REQUEST
            )

        reset_code.is_used = True
        reset_code.save()

        user.set_password(password)
        user.save()

        return Response({"detail": "Password has been reset"}, status=status.HTTP_200_OK)
