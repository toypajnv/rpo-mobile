from pathlib import Path


def test_dashboard_loader_includes_live_notification_asset():
    server_dir = Path(__file__).resolve().parents[1]
    loader = (server_dir / "app/static/dashboard.js").read_text(encoding="utf-8")
    assert "/static/dashboard-notifications.js?v=20260904-1" in loader


def test_live_notifications_poll_and_attention_contract():
    server_dir = Path(__file__).resolve().parents[1]
    script = (server_dir / "app/static/dashboard-notifications.js").read_text(encoding="utf-8")

    assert "/api/operator/transmissions?limit=30" in script
    assert "Поступили новые данные РПО" in script
    assert "Открыть переданные данные" in script
    assert "rpo-new-badge" in script
    assert "document.title" in script
    assert "playChime" in script
    assert "Notification.requestPermission" in script
    assert "document.body?.dataset?.role === 'manager'" in script
    assert "setInterval(poll, POLL_MS)" in script
