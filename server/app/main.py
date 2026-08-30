"""RPO backend entrypoint for UX release 2.1.

The complete pre-redesign backend is intentionally preserved in ``main_core.py`` so
rollback does not depend on reconstructing old business logic. This wrapper only
updates public version metadata while reusing the proven FastAPI application and
all routes from the preserved core.
"""

from . import main_core as _core

# Re-export the complete historical module surface, including private helper
# functions used by regression tests and maintenance scripts.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

LATEST_MOBILE_VERSION = "2.1.0"
MIN_SUPPORTED_MOBILE_VERSION = _core.MIN_SUPPORTED_MOBILE_VERSION
MOBILE_APK_URL = "https://github.com/toypajnv/rpo-mobile/releases/download/v2.1.0-test/rpo-mobile-2.1.0.apk"
PWA_VERSION = "1.1.1"
PWA_URL = _core.PWA_URL

_core.LATEST_MOBILE_VERSION = LATEST_MOBILE_VERSION
_core.MOBILE_APK_URL = MOBILE_APK_URL
_core.PWA_VERSION = PWA_VERSION
_core.PWA_URL = PWA_URL
_core.app.version = "0.6.0"

app = _core.app
