"""URL configuration for tradefog."""

from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from django.views.i18n import JavaScriptCatalog

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
]

urlpatterns += i18n_patterns(
    path(
        "",
        TemplateView.as_view(template_name="tradefog/base.html"),
        name="home",
    ),
    path(
        "jsi18n/",
        JavaScriptCatalog.as_view(),
        name="javascript-catalog",
    ),
    path("admin/", admin.site.urls),
    prefix_default_language=True,
)
