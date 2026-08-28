"""Application user models."""

from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Extensible application user."""
