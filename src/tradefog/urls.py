"""URL configuration for tradefog."""

from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from django.views.i18n import JavaScriptCatalog, set_language

from tradefog.views import HomeView

urlpatterns = i18n_patterns(
    path(
        "set-language/",
        set_language,
        name="set_language",
    ),
    path(
        "",
        HomeView.as_view(),
        name="home",
    ),
    path(
        "login/",
        LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "logout/",
        LogoutView.as_view(),
        name="logout",
    ),
    path(
        "jsi18n/",
        JavaScriptCatalog.as_view(),
        name="javascript-catalog",
    ),
    path("admin/", admin.site.urls),
    prefix_default_language=True,
)
