from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import re


# Legacy fields stay accepted permanently so already installed APKs keep working.
ALLOWED_FIELDS = {"AT", "AU", "AV", "AX", "AY", "AZ", "BA", "BC", "BD", "BE", "BF", "BG", "BH", "RI"}
STRUCTURAL_UNITS = (
    "ЦДПН-1", "ЦДПН-2", "ЦДПН-3", "ЦДПН-4",
    "ЦППН-1", "ЦППН-2", "ЦСДиТГ", "ЦСиР", "ЦТОиРТ-1", "ЦТОиРТ-2",
)


class EventCreate(BaseModel):
    # New metadata remains optional on the API so previously installed APKs can
    # continue to synchronize. The current APK requires a structural unit in UI.
    client_event_id: str | None = Field(default=None, min_length=8, max_length=64)
    device_id: str = Field(default="legacy-device", min_length=2, max_length=160)
    worker_name: str = Field(min_length=3, max_length=180)
    structural_unit: str | None = Field(default=None, max_length=80)
    permit_number: str = Field(min_length=3, max_length=80)
    field_key: str
    stage_label: str = Field(default="", max_length=255)
    event_time: datetime
    field_value: str = Field(min_length=1, max_length=4000)
    comment: str = Field(default="", max_length=1000)

    @field_validator("worker_name", "permit_number", "field_key", "field_value")
    @classmethod
    def strip_values(cls, value: str) -> str:
        return value.strip()

    @field_validator("structural_unit")
    @classmethod
    def valid_structural_unit(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().upper().replace("Ё", "Е")
        for unit in STRUCTURAL_UNITS:
            if unit.upper().replace("Ё", "Е") == normalized:
                return unit
        raise ValueError("Неизвестное структурное подразделение")

    @field_validator("field_key")
    @classmethod
    def valid_field(cls, value: str) -> str:
        value = value.upper()
        if value not in ALLOWED_FIELDS:
            raise ValueError("Неизвестный этап работ")
        return value

    @field_validator("permit_number")
    @classmethod
    def valid_permit(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[0-9A-ZА-ЯЁ._/\\\- ]{3,80}", value):
            raise ValueError("Номер НД содержит недопустимые символы")
        return value


class EventOut(BaseModel):
    id: int
    worker_name: str
    structural_unit: str = ""
    permit_number: str
    field_key: str
    stage_label: str
    event_time: datetime
    field_value: str
    comment: str
    approval_required: bool = False
    approval_status: str = "not_required"
    approved_at: datetime | None = None
    received_at: datetime
    exported_at: datetime | None

    model_config = {"from_attributes": True}
