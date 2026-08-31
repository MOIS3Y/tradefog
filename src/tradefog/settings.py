"""Django settings populated by the application configuration."""

from tradefog.config import Settings

_config = Settings()

# Application

SECRET_KEY = _config.application.django_secret_key()
DEBUG = _config.application.debug
ALLOWED_HOSTS = _config.application.allowed_hosts

# Django framework

INSTALLED_APPS = _config.django.installed_apps()
MIDDLEWARE = _config.django.middleware()
ROOT_URLCONF = _config.django.root_urlconf()
ASGI_APPLICATION = _config.django.asgi_application()
DEFAULT_AUTO_FIELD = _config.django.default_auto_field()

# Templates

TEMPLATES = _config.templates.django_templates()

# Database

DATABASES = _config.database.django_databases()

# Authentication

AUTH_USER_MODEL = _config.authentication.user_model()
AUTH_PASSWORD_VALIDATORS = _config.authentication.password_validators()
LOGIN_URL = _config.authentication.login_url()
LOGIN_REDIRECT_URL = _config.authentication.login_redirect_url()
LOGOUT_REDIRECT_URL = _config.authentication.logout_redirect_url()

# Localization

LANGUAGE_CODE = _config.localization.language_code()
LANGUAGES = _config.localization.languages()
LOCALE_PATHS = _config.localization.locale_paths()
TIME_ZONE = _config.localization.time_zone
USE_I18N = _config.localization.use_i18n()
USE_TZ = _config.localization.use_tz()

# Logging

LOGGING = _config.logging.django_logging()

# Static files

STATIC_URL = _config.static.url
STATIC_ROOT = _config.static.root
STATICFILES_DIRS = _config.static.source_dirs()

# User-uploaded media

MEDIA_URL = _config.media.url
MEDIA_ROOT = _config.media.root
TRADEFOG_MAX_ATTACHMENT_SIZE = _config.media.max_attachment_size_bytes()
