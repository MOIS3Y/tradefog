"""Shared application views."""

from typing import final

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


@final
class HomeView(LoginRequiredMixin, TemplateView):
    """Show the authenticated user's trading-profile overview."""

    template_name = "tradefog/home.html"
