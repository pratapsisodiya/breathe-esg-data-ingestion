from django.db import models
from django.contrib.auth.models import User


class Tenant(models.Model):
    """
    Represents a client company ingesting ESG data into the platform.

    Multi-tenancy strategy: row-level isolation via tenant FK on every model.
    This is the simplest approach for a prototype and avoids the complexity of
    separate schemas or databases. Every API view filters its queryset by
    request.user.profile.tenant, so one tenant can never see another's data.

    A more production-grade approach would use PostgreSQL row-level security (RLS)
    or separate database schemas per tenant to make the isolation impossible to
    accidentally bypass at the view layer. That's noted in TRADEOFFS.md.
    """

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """
    Extends Django's built-in User with tenant membership and role.

    We use a OneToOneField rather than swapping AUTH_USER_MODEL to keep the
    prototype simple while retaining full Django admin compatibility.
    """

    class Role(models.TextChoices):
        ANALYST = "analyst", "Analyst"
        ADMIN = "admin", "Admin"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ANALYST)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} @ {self.tenant.name}"
