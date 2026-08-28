"""Django admin configuration for application users."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from tradefog.accounts.models import User

admin.site.register(  # pyright: ignore[reportUnknownMemberType]
    User,
    UserAdmin,
)
