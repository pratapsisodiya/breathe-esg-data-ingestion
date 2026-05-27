from django.contrib import admin
from .models import Tenant, UserProfile

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created_at"]

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "tenant", "role"]
    list_filter = ["tenant", "role"]
