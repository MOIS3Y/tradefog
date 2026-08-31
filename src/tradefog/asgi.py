"""ASGI entry point for tradefog."""

import os
from typing import cast

from django.core.asgi import get_asgi_application
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp

from tradefog.config import Settings

_ = os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "tradefog.settings",
)

_config = Settings()
_django_application = get_asgi_application()

application = Starlette(
    routes=[
        Mount(
            _config.static.mount_path(),
            app=StaticFiles(
                directory=_config.static.root,
                check_dir=False,
            ),
            name="static",
        ),
        Mount("/", app=cast(ASGIApp, _django_application)),
    ],
)
