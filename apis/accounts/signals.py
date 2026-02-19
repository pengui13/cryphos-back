from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import BillingProfile

User = settings.AUTH_USER_MODEL


@receiver(post_save, sender=User)
def create_billing_profile(sender, instance, created, **kwargs):
    if created:
        BillingProfile.objects.get_or_create(user=instance)
