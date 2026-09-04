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
PWA_VERSION = "1.2.2"
PWA_URL = _core.PWA_URL
DASHBOARD_ASSET_VERSION = "20260904-2"
DASHBOARD_PHONE_VERSION = "20260903-1"
PWA_ENTRY_HOTFIX_VERSION = "20260901-1"
PWA_HISTORY_STATUS_VERSION = "20260901-1"

_core.LATEST_MOBILE_VERSION = LATEST_MOBILE_VERSION
_core.MOBILE_APK_URL = MOBILE_APK_URL
_core.PWA_VERSION = PWA_VERSION
_core.PWA_URL = PWA_URL
_core.app.version = "0.7.4"

# Keep the historical JSON artifact on the server for rollback/local-import
# compatibility, but email only the XLSX requested by the operator.
_original_send_export = _core.send_export


def _send_xlsx_export_only(recipient, subject, body, attachments, idempotency_key=None):
    xlsx_attachments = [path for path in attachments if path.suffix.lower() == ".xlsx"]
    if not xlsx_attachments:
        raise RuntimeError("В выгрузке отсутствует файл Excel")
    return _original_send_export(
        recipient,
        subject,
        body,
        xlsx_attachments,
        idempotency_key=idempotency_key,
    )


_core.send_export = _send_xlsx_export_only
send_export = _core.send_export


def _install_dashboard_assets() -> None:
    """Serve fresh dashboard controls, roles and a phone-only adaptive interface."""
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

    # Detect a real phone before paint. Tablets have a short CSS screen side above
    # 540 px and therefore retain the unchanged desktop/tablet dashboard.
    phone_assets = f"""
<script id=\"dashboard-phone-detect\">(() => {{
  const coarse = window.matchMedia?.('(pointer: coarse)').matches ?? false;
  const shortSide = Math.min(window.screen?.width || innerWidth, window.screen?.height || innerHeight);
  if (coarse && shortSide <= 540) document.documentElement.classList.add('mobile-phone');
}})();</script>
<link rel=\"stylesheet\" href=\"/static/dashboard-mobile.css?v={DASHBOARD_PHONE_VERSION}\">
<script src=\"/static/dashboard-mobile.js?v={DASHBOARD_PHONE_VERSION}\" defer></script>
"""
    if "dashboard-phone-detect" not in source:
        source = source.replace("</head>", f"{phone_assets}</head>", 1)

    # Role marker is rendered from the authenticated server user. Existing users
    # remain operators by default; managers receive the read-only presentation.
    source = source.replace(
        '<body class="app-body">',
        '<body class="app-body" data-role="{{ operator.role or \'operator\' }}">',
        1,
    )
    source = source.replace(
        '    <a href="#settings" data-tab-link="settings">⚙ Настройки</a>',
        '    {% if operator.role != \'manager\' %}<a href="#settings" data-tab-link="settings">⚙ Настройки</a>{% endif %}',
        1,
    )
    source = source.replace(
        '<span>{{ operator.username }}</span>',
        '<span>{{ operator.username }}{% if operator.role == \'manager\' %} · Руководитель{% endif %}</span>',
        1,
    )

    # Extend the existing admin-only Users tab with user creation and role labels.
    create_user_marker = "    {% for u in users %}"
    create_user_block = """    {% if request.query_params.get('user') == 'created' %}<div class=\"alert success\">Пользователь создан.</div>{% elif request.query_params.get('user') == 'exists' %}<div class=\"alert\">Пользователь с таким логином уже существует.</div>{% endif %}
    <form class=\"password-reset-form manager-create-form\" method=\"post\" action=\"/users/create\">
      <label>Логин нового пользователя<input type=\"text\" name=\"username\" minlength=\"3\" maxlength=\"80\" autocomplete=\"off\" required placeholder=\"Например: Руководитель_ЦДПН\"></label>
      <label>Роль<select name=\"role\" required><option value=\"manager\">Руководитель — только просмотр</option><option value=\"operator\">Оператор — рабочий доступ</option></select></label>
      <label>Пароль<input type=\"password\" name=\"password\" minlength=\"10\" autocomplete=\"new-password\" required placeholder=\"Не менее 10 символов\"></label>
      <button class=\"primary\" type=\"submit\">Добавить пользователя</button>
    </form>
"""
    if create_user_marker in source and "/users/create" not in source:
        source = source.replace(create_user_marker, create_user_block + create_user_marker, 1)

    old_role_label = "<span><b>{{ u.username }}</b><small>{% if u.username == operator.username %}Администратор · текущий вход{% else %}Оператор панели{% endif %}</small></span>"
    new_role_label = "<span><b>{{ u.username }}</b><small>{% if u.username == operator.username %}Администратор · текущий вход{% elif u.role == 'manager' %}Руководитель · только просмотр{% else %}Оператор панели{% endif %}</small></span>"
    source = source.replace(old_role_label, new_role_label, 1)

    decision_tag = (
        f'<script src="/static/dashboard-decisions.js?v={DASHBOARD_ASSET_VERSION}"></script>'
    )
    if decision_tag not in source:
        source = source.replace("</body>", f"{decision_tag}</body>")

    manager_ui = """
<style id=\"manager-readonly-style\">
body[data-role=\"manager\"] [data-tab-link=\"settings\"],
body[data-role=\"manager\"] .approve-button,
body[data-role=\"manager\"] .allow-button,
body[data-role=\"manager\"] .deny-button,
body[data-role=\"manager\"] .review-approve,
body[data-role=\"manager\"] .review-reject,
body[data-role=\"manager\"] .danger-button,
body[data-role=\"manager\"] #tab-exports .export-card,
body[data-role=\"manager\"] #preview-modal {display:none!important}
body[data-role=\"manager\"] #tab-exports .exports-grid{grid-template-columns:1fr}
body[data-role=\"manager\"] .manager-readonly-banner{margin:0 0 14px;padding:12px 16px;border:1px solid #b9c7d8;background:#f5f8fc;border-radius:12px;font-weight:700;color:#344054}
</style>
<script id=\"manager-readonly-ui\">
(() => {
  if (document.body.dataset.role !== 'manager') return;
  const allowedTabs = new Set(['home','transmissions','works','analytics','exports']);
  const enforceAllowedTab = () => {
    const current = (location.hash || '#home').slice(1);
    if (!allowedTabs.has(current)) history.replaceState(null, '', `${location.pathname}${location.search}#home`);
  };
  enforceAllowedTab();
  window.addEventListener('hashchange', enforceAllowedTab, true);
  document.querySelectorAll('[data-open-tab=\"exports\"]').forEach(button => {
    if (button.textContent.includes('Сформировать')) button.textContent = 'Открыть историю выгрузок';
  });
  const banner = document.createElement('div');
  banner.className = 'manager-readonly-banner';
  banner.textContent = 'Режим «Руководитель»: только просмотр, фильтрация и аналитика. Согласование, запрет, изменение, удаление и отправка выгрузок отключены.';
  const filter = document.querySelector('#global-filter');
  if (filter) filter.insertAdjacentElement('afterend', banner);
  else document.querySelector('main header')?.insertAdjacentElement('afterend', banner);
})();
</script>
"""
    if "manager-readonly-ui" not in source:
        source = source.replace("</body>", f"{manager_ui}</body>")

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

# Data review is separate from the safety work prohibition: an operator can reject
# an erroneous/backdated transmission without globally blocking the permit.
from .transmission_review import install_transmission_review
install_transmission_review(_core)
review_transmission = _core.review_transmission

# Manager access is installed after all operator mutation routes so the read-only
# server guard covers allow/deny/reject, legacy approval, exports and future writes.
from .manager_access import install_manager_access
install_manager_access(_core)
is_manager = _core.is_manager
create_operator_user = _core.create_operator_user

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
        # Register the service worker immediately, before the worker can add the app
        # to the Home Screen. This fixes iOS installations that otherwise launched
        # Safari's black "iPhone is not connected to the Internet" error page.
        early_sw = """<script id=\"pwa-early-service-worker\">if('serviceWorker' in navigator){navigator.serviceWorker.register('/app/sw.js',{scope:'/app/'}).then(r=>r.update()).catch(()=>{});}</script>"""
        if "pwa-early-service-worker" not in source:
            source = source.replace("</head>", f"{early_sw}</head>", 1)
        if permit_tag not in source:
            source = source.replace("</body>", f"  {permit_tag}\n</body>")
        if history_tag not in source:
            source = source.replace("</body>", f"  {history_tag}\n</body>")
        source = source.replace(
            "PWA 1.2.1 · статусы запрета в истории · единая система с Android РПО 2.2.1.",
            "PWA 1.2.2 · устойчивый запуск на iPhone · единая система с Android РПО 2.2.2.",
        )
        source = source.replace(
            "PWA 1.2.1 · статусы запрета в истории · единая система с Android РПО 2.2.2.",
            "PWA 1.2.2 · устойчивый запуск на iPhone · единая система с Android РПО 2.2.2.",
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
