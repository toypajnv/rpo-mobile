"""RPO backend entrypoint for the operator decision-control release.

The complete pre-redesign backend is intentionally preserved in ``main_core.py`` so
rollback does not depend on reconstructing old business logic. Additive feature
modules patch the stable core contract without rewriting its historical routes.
"""

from . import main_core as _core

# Re-export the complete historical module surface, including private helper
# functions used by regression tests and maintenance scripts.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

LATEST_MOBILE_VERSION = "2.2.0"
MIN_SUPPORTED_MOBILE_VERSION = _core.MIN_SUPPORTED_MOBILE_VERSION
MOBILE_APK_URL = "https://github.com/toypajnv/rpo-mobile/releases/download/v2.2.0-test/rpo-mobile-2.2.0.apk"
PWA_VERSION = "1.2.0"
PWA_URL = _core.PWA_URL

_core.LATEST_MOBILE_VERSION = LATEST_MOBILE_VERSION
_core.MOBILE_APK_URL = MOBILE_APK_URL
_core.PWA_VERSION = PWA_VERSION
_core.PWA_URL = PWA_URL
_core.app.version = "0.7.0"

# Operator decisions are additive: a denied current stage blocks the whole permit
# until an operator explicitly allows that stage again.
from .decision_control import install_decision_control
install_decision_control(_core)
decide_mobile_event = _core.decide_mobile_event

app = _core.app

# The stop-registry module remains isolated from the RPO permit decision logic.
# Importing it before application startup also registers its SQLAlchemy tables so
# the existing lifespan Base.metadata.create_all() creates them automatically.
from .ostanovka import router as ostanovka_router
app.include_router(ostanovka_router)
