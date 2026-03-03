from django.contrib import admin
from .models import BillingProfile, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'tg_nickname', 'tg_approved', 'chat_id')
    list_filter = ("tg_approved",)
    search_fields = ("username", "email", "tg_nickname")
    readonly_fields = ('email', 'chat_id')

@admin.register(BillingProfile)
class BillingProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'current_period_end',
                    'cancel_at_period_end')
    search_fields = ('user__email',)
    readonly_fields = ('created_at', 'updated_at')
