from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):

    email = models.EmailField(unique=True)
    tg_nickname = models.CharField(default="", null=True, blank=True)
    tg_approved = models.BooleanField(default=False)
    chat_id = models.CharField(default="", null=True, blank=True)

    def __str__(self):
        return self.username


SUB_STATUS_CHOICES = [
    ("incomplete", "incomplete"),
    ("incomplete_expired", "incomplete_expired"),
    ("trialing", "trialing"),
    ("active", "active"),
    ("past_due", "past_due"),
    ("canceled", "canceled"),
    ("unpaid", "unpaid"),
    ("paused", "paused"),
    ("null", "null"),
]


class BillingProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="billing")
    stripe_customer_id = models.CharField(max_length=120, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=120, blank=True, default="")
    price_id = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=32, choices=SUB_STATUS_CHOICES, default="null")
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    trial_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_active(self) -> bool:
        return self.status in ["trialing", "active"] and (
            not self.current_period_end or self.current_period_end >= timezone.now()
        )

    def __str__(self):
        return f"BillingProfile for {self.user.username}"


class PendingRegistration(models.Model):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150)
    password_hash = models.CharField(max_length=128)
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    tries = models.PositiveSmallIntegerField(default=0)
    resend_count = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() >= self.expires_at


class PasswordResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_codes")
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(default=timezone.now)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timezone.timedelta(minutes=10)

    def __str__(self):
        return f"ResetCode({self.user.email}, {self.code}, used={self.is_used})"
