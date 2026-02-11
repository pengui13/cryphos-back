from django.urls import path
from .views import (
    RegisterView,
    create_checkout_session,
    stripe_webhook,
    billing_me,
    RegisterStartView,
    RegisterResendView,
    GetUserTelegram,
    RegisterVerifyView,
    LoginView,
    RefreshTokenView,
    ResetStartView,
    ResetVerifyView,
    create_billing_portal_session,
)

urlpatterns = [
    path("register/start/", RegisterStartView.as_view(), name="register"),
    path("register/verify/", RegisterVerifyView.as_view(), name="register-verify"),
    path("register/resend/", RegisterResendView.as_view(), name="register-resend"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshTokenView.as_view(), name="token_refresh"),
    path("checkout/", create_checkout_session),
    path("portal/", create_billing_portal_session),
    path("webhook/", stripe_webhook),
    path("reset/start/", ResetStartView.as_view(), name="reset-start"),
    path("reset/verify/", ResetVerifyView.as_view(), name="reset-verify"),
    path("get_user_tg/", GetUserTelegram.as_view(), name="get_user_tg"),
    path(
        "billing/create-checkout-session/", create_checkout_session, name="create_checkout_session"
    ),
    path("billing/portal/", create_billing_portal_session, name="create_billing_portal_session"),
    path("billing/me/", billing_me, name="billing_me"),
]
