from sqlalchemy import inspect, text
from .database import engine


def ensure_v2_columns() -> None:
    """Idempotent migration for installations created before RPO 2.0."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        if "operators" in tables:
            operator_cols = {col["name"] for col in inspector.get_columns("operators")}
            if "role" not in operator_cols:
                conn.execute(text("ALTER TABLE operators ADD COLUMN role VARCHAR(24) NOT NULL DEFAULT 'operator'"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_operators_role ON operators (role)"))

        if "permit_records" not in tables or "mobile_events" not in tables:
            return

        permit_cols = {col["name"] for col in inspector.get_columns("permit_records")}
        event_cols = {col["name"] for col in inspector.get_columns("mobile_events")}

        if "structural_unit" not in permit_cols:
            conn.execute(text("ALTER TABLE permit_records ADD COLUMN structural_unit VARCHAR(80) NOT NULL DEFAULT ''"))

        additions = {
            "structural_unit": "VARCHAR(80) NOT NULL DEFAULT ''",
            "approval_required": "BOOLEAN NOT NULL DEFAULT FALSE",
            "approval_status": "VARCHAR(24) NOT NULL DEFAULT 'not_required'",
            "approved_at": "TIMESTAMP NULL",
            "approved_by_id": "INTEGER NULL",
        }
        for name, ddl in additions.items():
            if name not in event_cols:
                conn.execute(text(f"ALTER TABLE mobile_events ADD COLUMN {name} {ddl}"))

        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_permit_records_structural_unit ON permit_records (structural_unit)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_events_structural_unit ON mobile_events (structural_unit)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_events_approval_status ON mobile_events (approval_status)"))
