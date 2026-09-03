"""RPO backend entrypoint for the operator decision-control release.

The complete pre-redesign backend is intentionally preserved in ``main_core.py`` so
rollback does not depend on reconstructing old business logic. Additive feature
modules patch the stable core contract without rewriting its historical routes.
"""

from fastapi.responses import HTMLResponse
from jinja2 import ChoiceLoader, DictLoader

from . import main_core as _core

# Re-export the complete historical module surface, including private helper
# functions used by regression tests and maintenance scripts.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

LATEST_MOBILE_VERSION = "2.2.2"
MIN_SUPPORTED_MOBILE_VERSION = _core.MIN_SUPPORTED_MOBILE_VERSION
MOBILE_APK_URL = "https://github.com/toypajnv/rpo-mobile/releases/download/v2.2.2-test/rpo-mobile-2.2.2.apk"
PWA_VERSION = "1.2.1"
PWA_URL = _core.PWA_URL
DASHBOARD_ASSET_VERSION = "20260901-2"
PWA_ENTRY_HOTFIX_VERSION = "20260901-1"
PWA_HISTORY_STATUS_VERSION = "20260901-1"

_core.LATEST_MOBILE_VERSION = LATEST_MOBILE_VERSION
_core.MOBILE_APK_URL = MOBILE_APK_URL
_core.PWA_VERSION = PWA_VERSION
_core.PWA_URL = PWA_URL
_core.app.version = "0.7.2"


def _install_dashboard_assets() -> None:
    """Serve a fresh dashboard loader and load decision controls directly."""
    template_name = "dashboard.html"
    source_path = _core.BASE_DIR / "templates" / template_name
    source = source_path.read_text(encoding="utf-8")
    loader = f"/static/dashboard.js?v={DASHBOARD_ASSET_VERSION}"
    for old_loader in (
        "/static/dashboard.js?v=20260829-2",
        "/static/dashboard.js?v=20260831-2",
    ):
        source = source.replace(old_loader, loader)
    if loader not in source:
        raise RuntimeError("Dashboard loader reference was not found")

    decision_tag = (
        f'<script src="/static/dashboard-decisions.js?v={DASHBOARD_ASSET_VERSION}"></script>'
    )
    if decision_tag not in source:
        source = source.replace("</body>", f"{decision_tag}</body>")

    _core.templates.env.loader = ChoiceLoader([
        DictLoader({template_name: source}),
        _core.templates.env.loader,
    ])


_install_dashboard_assets()

# Operator decisions are additive: a denied current stage blocks the whole permit
# until an operator explicitly allows that stage again.
from .decision_control import install_decision_control
install_decision_control(_core)
decide_mobile_event = _core.decide_mobile_event
mobile_history = _core.mobile_history

app = _core.app


@app.middleware("http")
async def inject_pwa_release_hotfixes(request, call_next):
    """Inject small no-cache PWA compatibility fixes without rewriting the base shell."""
    if request.method == "GET" and request.url.path == "/app/":
        source = (_core.PWA_DIR / "index.html").read_text(encoding="utf-8")
        permit_tag = (
            f'<script src="/pwa-assets/permit-entry-hotfix.js?v={PWA_ENTRY_HOTFIX_VERSION}" defer></script>'
        )
        history_tag = (
            f'<script src="/pwa-assets/history-status.js?v={PWA_HISTORY_STATUS_VERSION}" defer></script>'
        )
        if permit_tag not in source:
            source = source.replace("</body>", f"  {permit_tag}\n</body>")
        if history_tag not in source:
            source = source.replace("</body>", f"  {history_tag}\n</body>")
        source = source.replace(
            "PWA 1.2.0 · разрешение и запрет оператором · единая система с Android РПО 2.2.0.",
            "PWA 1.2.1 · статусы запрета в истории · единая система с Android РПО 2.2.2.",
        )
        return HTMLResponse(
            source,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )
    return await call_next(request)


# The stop-registry module remains isolated from the RPO permit decision logic.
# Importing it before application startup also registers its SQLAlchemy tables so
# the existing lifespan Base.metadata.create_all() creates them automatically.
from .ostanovka import router as ostanovka_router
app.include_router(ostanovka_router)
