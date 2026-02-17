from django.contrib import admin

from .models import BillingProfile, User

# Register your models here.
admin.site.register(User)
admin.site.register(BillingProfile)
