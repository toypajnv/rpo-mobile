from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    if old not in content:
        raise RuntimeError(f"Expected block not found in {path}: {old[:100]!r}")
    write(path, content.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Server: compatibility, optional replacement workers, operator account,
# deletion, and mobile feedback/status API.
# ---------------------------------------------------------------------------
write("server/app/stages.py", '''STAGES = {
    "AT": {"label": "Начало подготовки", "order": 10, "kind": "datetime"},
    "AU": {"label": "Окончание подготовки", "order": 20, "kind": "datetime", "after": "AT"},
    "AV": {"label": "Передача ОП к ОБПР", "order": 30, "kind": "datetime", "after": "AU"},
    "AX": {"label": "Допуск со стороны допускающего", "order": 40, "kind": "datetime"},
    "AY": {"label": "Фактическое начало работ", "order": 50, "kind": "datetime", "after": "AV"},
    "AZ": {"label": "Остановка работ", "order": 60, "kind": "datetime", "after": "AY", "comment_required": True},
    "BA": {"label": "Возобновление работ", "order": 70, "kind": "datetime", "after": "AZ", "comment_required": True},
    "BC": {"label": "Фактическое окончание работ", "order": 80, "kind": "datetime", "after": "AY"},
    "BD": {"label": "Выполнение мероприятий по завершению", "order": 90, "kind": "datetime", "after": "BC"},
    "BE": {"label": "Продление РПО", "order": 95, "kind": "text"},
    "RI": {"label": "Замена исполнителей работ", "order": 97, "kind": "text", "optional": True},
    "BF": {"label": "Выполнение мероприятий по передаче объекта", "order": 100, "kind": "datetime", "after": "BD"},
    "BG": {"label": "Закрытие ЭНД", "order": 105, "kind": "text"},
    "BH": {"label": "Передача площадки эксплуатирующей организации", "order": 110, "kind": "datetime", "after": "BF"},
}
''')

write("server/app/schemas.py", '''from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import re


# Legacy fields stay accepted permanently so already installed APKs keep working.
ALLOWED_FIELDS = {"AT", "AU", "AV", "AX", "AY", "AZ", "BA", "BC", "BD", "BE", "BF", "BG", "BH", "RI"}


class EventCreate(BaseModel):
    # The first APKs always sent these values, but they are optional on the server
    # so an older/minimal client is not rejected after future server upgrades.
    client_event_id: str | None = Field(default=None, min_length=8, max_length=64)
    device_id: str = Field(default="legacy-device", min_length=2, max_length=160)
    worker_name: str = Field(min_length=3, max_length=180)
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
        if not re.fullmatch(r"[0-9A-ZА-ЯЁ._/\\\\\- ]{3,80}", value):
            raise ValueError("Номер НД содержит недопустимые символы")
        return value


class EventOut(BaseModel):
    id: int
    worker_name: str
    permit_number: str
    field_key: str
    stage_label: str
    event_time: datetime
    field_value: str
    comment: str
    received_at: datetime
    exported_at: datetime | None

    model_config = {"from_attributes": True}
''')

write("server/app/services/validation.py", '''from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import MobileEvent
from ..schemas import EventCreate
from ..stages import STAGES


class EventValidationError(ValueError):
    pass


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_event(db: Session, payload: EventCreate) -> None:
    now = datetime.now(timezone.utc)
    event_time = _aware_utc(payload.event_time)
    if event_time > now + timedelta(minutes=5):
        raise EventValidationError("Дата/время события не может быть в будущем")
    if event_time < now - timedelta(days=45):
        raise EventValidationError("Дата события слишком старая. Проверьте дату и время")

    stage = STAGES[payload.field_key]

    # Mandatory stop/resume comments are enforced by current APKs. The server
    # deliberately does not reject a missing comment here: older installed APKs
    # must remain able to synchronize after a server update.
    if stage["kind"] == "text" and len(payload.field_value.strip()) < 2:
        raise EventValidationError("Заполните значение для выбранного этапа")

    after_key = stage.get("after")
    if not after_key:
        return

    previous = db.scalar(
        select(MobileEvent)
        .where(
            MobileEvent.permit_number == payload.permit_number,
            MobileEvent.field_key == after_key,
        )
        .order_by(MobileEvent.event_time.desc())
        .limit(1)
    )
    if previous:
        prev_time = _aware_utc(previous.event_time)
        if event_time < prev_time:
            raise EventValidationError(
                f"Дата/время этапа не может быть раньше «{previous.stage_label}» "
                f"({prev_time.astimezone().strftime('%d.%m.%Y %H:%M')})"
            )
''')

main = read("server/app/main.py")
main = main.replace("import json\n", "import json\nimport hashlib\n", 1)
main = main.replace(
    'DASHBOARD_STAGE_KEYS = ("AT", "AU", "AV", "AY", "AZ", "BA", "BE", "BC")\n',
    'REQUIRED_DASHBOARD_STAGE_KEYS = ("AT", "AU", "AV", "AY", "AZ", "BA", "BE", "BC")\n'
    'DASHBOARD_STAGE_KEYS = REQUIRED_DASHBOARD_STAGE_KEYS + ("RI",)\n'
    'LATEST_MOBILE_VERSION = "1.1.5"\n'
    'MIN_SUPPORTED_MOBILE_VERSION = "1.0.1"\n'
    'MOBILE_APK_URL = "https://github.com/toypajnv/rpo-mobile/releases/download/v1.1.5-test/rpo-mobile-1.1.5.apk"\n'
    'DEFAULT_OPERATOR_USERNAME = "Operator"\n'
    'DEFAULT_OPERATOR_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$hBSN4f5Hetyo+a4aOvCP3A$7bYB1iB2/8/sS0w1AYTNrdAg3QyVP7KdhTOP2PHCNys"\n',
    1,
)
main = main.replace(
    "    ensure_admin()\n    ensure_permit_records()\n",
    "    ensure_admin()\n    ensure_default_operator()\n    ensure_permit_records()\n",
    1,
)
main = main.replace('app = FastAPI(title=settings.app_name, version="0.3.1", lifespan=lifespan)', 'app = FastAPI(title=settings.app_name, version="0.4.0", lifespan=lifespan)', 1)
needle = '''def ensure_admin() -> None:
    with SessionLocal() as db:
        user = db.scalar(select(Operator).where(Operator.username == settings.admin_username))
        if not user:
            db.add(Operator(username=settings.admin_username, password_hash=hash_password(settings.admin_password)))
            db.commit()
'''
replacement = needle + '''

def ensure_default_operator() -> None:
    """Create the shared Operator account without storing its plain password."""
    with SessionLocal() as db:
        user = db.scalar(select(Operator).where(Operator.username == DEFAULT_OPERATOR_USERNAME))
        if not user:
            db.add(Operator(
                username=DEFAULT_OPERATOR_USERNAME,
                password_hash=DEFAULT_OPERATOR_PASSWORD_HASH,
                is_active=True,
            ))
            db.commit()


def is_admin(operator: Operator | None) -> bool:
    return bool(operator and operator.username == settings.admin_username)
'''
if needle not in main:
    raise RuntimeError("ensure_admin block not found")
main = main.replace(needle, replacement, 1)
main = main.replace(
    '''def _dashboard_stage_keys() -> list[str]:
    return [key for key in DASHBOARD_STAGE_KEYS if key in STAGES]
''',
    '''def _dashboard_stage_keys() -> list[str]:
    return [key for key in DASHBOARD_STAGE_KEYS if key in STAGES]


def _required_dashboard_stage_keys() -> list[str]:
    return [key for key in REQUIRED_DASHBOARD_STAGE_KEYS if key in STAGES]
''',
    1,
)
main = main.replace(
    '''    visible_keys = _dashboard_stage_keys()
    filled = sum(1 for key in visible_keys if _has_stage(data, key))
    total = len(visible_keys) or 1
''',
    '''    visible_keys = _dashboard_stage_keys()
    required_keys = _required_dashboard_stage_keys()
    filled = sum(1 for key in required_keys if _has_stage(data, key))
    total = len(required_keys) or 1
''',
    1,
)

old_create = '''@app.post("/api/mobile/events", response_model=EventOut, status_code=201)
def create_mobile_event(payload: EventCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(MobileEvent).where(MobileEvent.client_event_id == payload.client_event_id))
    if existing:
        return existing
    try:
        validate_event(db, payload)
    except EventValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    event = MobileEvent(
        client_event_id=payload.client_event_id,
        device_id=payload.device_id,
        worker_name=payload.worker_name,
        permit_number=payload.permit_number,
        field_key=payload.field_key,
        stage_label=payload.stage_label,
        event_time=dt_utc(payload.event_time),
        field_value=payload.field_value,
        comment=payload.comment,
    )
'''
new_create = '''def _effective_client_event_id(payload: EventCreate) -> str:
    if payload.client_event_id:
        return payload.client_event_id
    raw = "|".join([
        payload.device_id,
        payload.worker_name,
        payload.permit_number,
        payload.field_key,
        payload.event_time.isoformat(),
        payload.field_value,
        payload.comment,
    ])
    return "legacy-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


@app.post("/api/mobile/events", response_model=EventOut, status_code=201)
def create_mobile_event(payload: EventCreate, db: Session = Depends(get_db)):
    client_event_id = _effective_client_event_id(payload)
    existing = db.scalar(select(MobileEvent).where(MobileEvent.client_event_id == client_event_id))
    if existing:
        return existing
    try:
        validate_event(db, payload)
    except EventValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    event = MobileEvent(
        client_event_id=client_event_id,
        device_id=payload.device_id,
        worker_name=payload.worker_name,
        permit_number=payload.permit_number,
        field_key=payload.field_key,
        stage_label=payload.stage_label.strip() or STAGES[payload.field_key]["label"],
        event_time=dt_utc(payload.event_time),
        field_value=payload.field_value,
        comment=payload.comment,
    )
'''
if old_create not in main:
    raise RuntimeError("create_mobile_event block not found")
main = main.replace(old_create, new_create, 1)

permit_marker = '@app.get("/api/mobile/permit")\ndef mobile_permit_lookup('
config_block = '''def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = []
    for raw in (value or "").split(".")[:3]:
        digits = "".join(ch for ch in raw if ch.isdigit())
        parts.append(int(digits or 0))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


@app.get("/api/mobile/config")
def mobile_config(app_version: str = Query(default="", max_length=32)):
    update_available = bool(app_version) and _version_tuple(app_version) < _version_tuple(LATEST_MOBILE_VERSION)
    message = "Связь с сервером установлена. Система РПО работает штатно."
    if update_available:
        message += f" Доступна версия приложения {LATEST_MOBILE_VERSION}."
    return {
        "status": "ok",
        "server_version": app.version,
        "latest_app_version": LATEST_MOBILE_VERSION,
        "minimum_supported_version": MIN_SUPPORTED_MOBILE_VERSION,
        "update_available": update_available,
        "update_required": False,
        "maintenance": False,
        "message": message,
        "apk_url": MOBILE_APK_URL,
        "checked_at": utcnow().isoformat(),
    }


'''
if permit_marker not in main:
    raise RuntimeError("mobile permit marker not found")
main = main.replace(permit_marker, config_block + permit_marker, 1)

main = main.replace(
    '''        "app_version": app.version,
    }
    return dict(
''',
    '''        "app_version": app.version,
        "mobile_version": LATEST_MOBILE_VERSION,
    }
    users = list(db.scalars(select(Operator).order_by(Operator.username.asc())))
    return dict(
''',
    1,
)
main = main.replace(
    '''        settings_view=settings_view,
    )
''',
    '''        settings_view=settings_view,
        users=users,
    )
''',
    1,
)
main = main.replace(
    '''def dashboard(request: Request, operator: Operator = Depends(current_operator), db: Session = Depends(get_db)):
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"operator": operator, **dashboard_context(db)})
''',
    '''def dashboard(request: Request, operator: Operator = Depends(current_operator), db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"operator": operator, "is_admin": is_admin(operator), **dashboard_context(db)},
    )
''',
    1,
)
main = main.replace(
    '''            "stage_items": item["stage_items"],
        })
''',
    '''            "stage_items": item["stage_items"],
            "can_delete": is_admin(operator),
        })
''',
    1,
)

export_preview_marker = '@app.get("/api/operator/export-preview")\ndef export_preview('
operator_actions = '''@app.delete("/api/operator/permits/{record_id}")
def delete_permit_record(
    record_id: int,
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
):
    if not is_admin(operator):
        raise HTTPException(status_code=403, detail="Удаление доступно только администратору")
    record = db.get(PermitRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Наряд-допуск не найден")
    permit_number = record.permit_number
    raw_events = list(db.scalars(select(MobileEvent).where(MobileEvent.permit_number == permit_number)))
    for event in raw_events:
        db.delete(event)
    db.delete(record)
    db.commit()
    return {"status": "deleted", "permit_number": permit_number, "events_deleted": len(raw_events)}


@app.post("/users/{operator_id}/password")
def reset_operator_password(
    operator_id: int,
    password: Annotated[str, Form()],
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
):
    if not is_admin(operator):
        raise HTTPException(status_code=403, detail="Управление пользователями доступно только администратору")
    target = db.get(Operator, operator_id)
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if len(password) < 10:
        raise HTTPException(status_code=400, detail="Пароль должен содержать не менее 10 символов")
    target.password_hash = hash_password(password)
    target.is_active = True
    db.commit()
    return RedirectResponse("/dashboard?user=password-updated#users", status_code=303)


'''
if export_preview_marker not in main:
    raise RuntimeError("export preview marker not found")
main = main.replace(export_preview_marker, operator_actions + export_preview_marker, 1)
write("server/app/main.py", main)

# ---------------------------------------------------------------------------
# Android data contract and stages.
# ---------------------------------------------------------------------------
write("android/app/src/main/java/ru/rpo/mobile/data/Models.kt", '''package ru.rpo.mobile.data

data class EventRequest(
    val client_event_id: String,
    val device_id: String,
    val worker_name: String,
    val permit_number: String,
    val field_key: String,
    val stage_label: String,
    val event_time: String,
    val field_value: String,
    val comment: String,
)

data class EventResponse(
    val id: Long,
    val worker_name: String,
    val permit_number: String,
    val field_key: String,
    val stage_label: String,
    val event_time: String,
    val field_value: String,
    val comment: String,
    val received_at: String,
    val exported_at: String?,
)

data class ApiError(val detail: String? = null)


data class PermitFieldSnapshot(
    val field_value: String = "",
    val event_time: String = "",
    val comment: String = "",
)

data class PermitSnapshot(
    val permit_number: String,
    val worker_name: String,
    val updated_at: String,
    val fields: Map<String, PermitFieldSnapshot> = emptyMap(),
)

data class MobileConfig(
    val status: String = "ok",
    val server_version: String = "",
    val latest_app_version: String = "",
    val minimum_supported_version: String = "",
    val update_available: Boolean = false,
    val update_required: Boolean = false,
    val maintenance: Boolean = false,
    val message: String = "",
    val apk_url: String = "",
    val checked_at: String = "",
)
''')

write("android/app/src/main/java/ru/rpo/mobile/data/RpoApi.kt", '''package ru.rpo.mobile.data

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface RpoApi {
    @POST("api/mobile/events")
    suspend fun sendEvent(@Body body: EventRequest): Response<EventResponse>

    @GET("api/mobile/events")
    suspend fun history(@Query("device_id") deviceId: String, @Query("limit") limit: Int = 30): Response<List<EventResponse>>

    @GET("api/mobile/permit")
    suspend fun permit(@Query("permit_number") permitNumber: String): Response<PermitSnapshot>

    @GET("api/mobile/config")
    suspend fun config(@Query("app_version") appVersion: String): Response<MobileConfig>
}
''')

write("android/app/src/main/java/ru/rpo/mobile/ui/Stages.kt", '''package ru.rpo.mobile.ui

enum class StageKind { RANGE_DATETIME, TRIPLE_DATETIME, DATETIME, STOP, EXTENSION_DATE, REPLACEMENTS }

data class StageEvent(val key: String, val title: String)

data class Stage(
    val id: String,
    val title: String,
    val kind: StageKind,
    val first: StageEvent,
    val second: StageEvent? = null,
    val third: StageEvent? = null,
    val optional: Boolean = false,
)

val stages = listOf(
    Stage(
        id = "PREPARATION",
        title = "Подготовка",
        kind = StageKind.RANGE_DATETIME,
        first = StageEvent("AT", "Начало подготовки"),
        second = StageEvent("AU", "Окончание подготовки"),
    ),
    Stage(
        id = "TRANSFER_WORK",
        title = "Передача объекта",
        kind = StageKind.DATETIME,
        first = StageEvent("AV", "Передача ОП к ОБПР"),
    ),
    Stage(
        id = "ACTUAL_WORK",
        title = "Фактическое начало и окончание работ",
        kind = StageKind.RANGE_DATETIME,
        first = StageEvent("AY", "Фактическое начало работ"),
        second = StageEvent("BC", "Фактическое окончание работ"),
    ),
    Stage(
        id = "STOP_WORK",
        title = "Остановка работ",
        kind = StageKind.STOP,
        first = StageEvent("AZ", "Остановка работ"),
    ),
    Stage(
        id = "RESUME_WORK",
        title = "Возобновление работ",
        kind = StageKind.DATETIME,
        first = StageEvent("BA", "Возобновление работ"),
    ),
    Stage(
        id = "EXTEND_WORK",
        title = "Продление РПО",
        kind = StageKind.EXTENSION_DATE,
        first = StageEvent("BE", "Продление РПО"),
    ),
    Stage(
        id = "REPLACEMENTS",
        title = "Замена исполнителей работ",
        kind = StageKind.REPLACEMENTS,
        first = StageEvent("RI", "Замена исполнителей работ"),
        optional = true,
    ),
)

val requiredStages: List<Stage> = stages.filterNot { it.optional }
val requiredStageCount: Int = requiredStages.size

fun savedStageCount(savedStageIds: Set<String>): Int = requiredStages.count { it.id in savedStageIds }

fun savedStageIdsForFieldKeys(fieldKeys: Set<String>): Set<String> = stages
    .filter { stage -> listOfNotNull(stage.first.key, stage.second?.key, stage.third?.key).all { it in fieldKeys } }
    .map { it.id }
    .toSet()

fun shouldWarnBeforeStageSwitch(current: Stage, target: Stage, hasUnsavedChanges: Boolean): Boolean =
    current.id != target.id && hasUnsavedChanges
''')

write("android/app/src/main/java/ru/rpo/mobile/ui/FormRules.kt", '''package ru.rpo.mobile.ui

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.format.DateTimeFormatter

internal val rpoDateFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy")
internal val rpoTimeFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("HH:mm")
internal val rpoDateTimeFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm")

private val latinLetterRegex = Regex("[A-Za-z]")

data class OperationalDateTimeResult(val value: LocalDateTime?, val error: String?)
data class ReplacementEntry(val name: String = "", val position: String = "")

fun containsLatinLetters(value: String): Boolean = latinLetterRegex.containsMatchIn(value)

fun removeLatinLetters(value: String): String = value.filterNot { it in 'A'..'Z' || it in 'a'..'z' }

fun encodeReplacements(entries: List<ReplacementEntry>): String = entries
    .map { ReplacementEntry(it.name.trim(), it.position.trim()) }
    .filter { it.name.isNotBlank() || it.position.isNotBlank() }
    .joinToString("\n") { "${it.name}\t${it.position}" }

fun decodeReplacements(value: String): List<ReplacementEntry> {
    val parsed = value.lines().mapNotNull { line ->
        val parts = line.split('\t', limit = 2)
        if (parts.size == 2) ReplacementEntry(parts[0].trim(), parts[1].trim()) else null
    }.filter { it.name.isNotBlank() || it.position.isNotBlank() }
    return parsed.ifEmpty { listOf(ReplacementEntry()) }
}

fun replacementsReady(entries: List<ReplacementEntry>): Boolean {
    val used = entries.filter { it.name.isNotBlank() || it.position.isNotBlank() }
    return used.isNotEmpty() && used.all { it.name.trim().length >= 3 && it.position.trim().length >= 2 }
}

fun parseOperationalDateTime(
    date: String,
    time: String,
    now: LocalDateTime = LocalDateTime.now(),
): OperationalDateTimeResult {
    if (date.isBlank() || time.isBlank()) return OperationalDateTimeResult(null, "Укажите дату и время")
    val value = try {
        LocalDateTime.of(LocalDate.parse(date, rpoDateFormatter), LocalTime.parse(time, rpoTimeFormatter))
    } catch (_: Exception) {
        return OperationalDateTimeResult(null, "Проверьте дату и время")
    }
    if (value.isAfter(now.plusMinutes(5))) {
        return OperationalDateTimeResult(value, "Дата и время фактического этапа не могут быть в будущем")
    }
    if (value.isBefore(now.minusDays(45))) {
        return OperationalDateTimeResult(value, "Дата события слишком старая")
    }
    return OperationalDateTimeResult(value, null)
}

fun resumeCommentError(stageId: String, comment: String): String? =
    if (stageId == "RESUME_WORK" && comment.trim().length < 3) "Комментарий при возобновлении обязателен" else null

private fun parseFilledDateTime(date: String, time: String): LocalDateTime? = runCatching {
    LocalDateTime.of(LocalDate.parse(date, rpoDateFormatter), LocalTime.parse(time, rpoTimeFormatter))
}.getOrNull()

fun stageDataReady(state: FormState): Boolean = when (state.stage.kind) {
    StageKind.RANGE_DATETIME -> {
        val start = parseFilledDateTime(state.primaryDate, state.primaryTime)
        val end = parseFilledDateTime(state.secondaryDate, state.secondaryTime)
        start != null && end != null && !end.isBefore(start)
    }

    StageKind.TRIPLE_DATETIME -> {
        val first = parseFilledDateTime(state.primaryDate, state.primaryTime)
        val second = parseFilledDateTime(state.secondaryDate, state.secondaryTime)
        val third = parseFilledDateTime(state.thirdDate, state.thirdTime)
        first != null && second != null && third != null && !second.isBefore(first) && !third.isBefore(second)
    }

    StageKind.DATETIME -> {
        val value = parseFilledDateTime(state.primaryDate, state.primaryTime)
        value != null && (state.stage.id != "RESUME_WORK" || state.comment.trim().length >= 3)
    }

    StageKind.STOP ->
        parseFilledDateTime(state.primaryDate, state.primaryTime) != null && state.stopReason.trim().length >= 3

    StageKind.EXTENSION_DATE ->
        runCatching { LocalDate.parse(state.extensionDate, rpoDateFormatter) }.isSuccess

    StageKind.REPLACEMENTS -> replacementsReady(state.replacements)
}
''')

# ViewModel additions.
vm = read("android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt")
vm = vm.replace("import androidx.lifecycle.AndroidViewModel\n", "import androidx.lifecycle.AndroidViewModel\nimport ru.rpo.mobile.BuildConfig\n", 1)
vm = vm.replace("import ru.rpo.mobile.data.PermitSnapshot\n", "import ru.rpo.mobile.data.PermitSnapshot\nimport ru.rpo.mobile.data.MobileConfig\n", 1)
vm = vm.replace(
    '''    val comment: String = "",
    val errors: Map<String, String> = emptyMap(),
''',
    '''    val comment: String = "",
    val replacements: List<ReplacementEntry> = listOf(ReplacementEntry()),
    val systemNotice: MobileConfig? = null,
    val errors: Map<String, String> = emptyMap(),
''',
    1,
)
vm = vm.replace(
    '''        comment = "",
        errors = base.errors.filterKeys { it == "worker" || it == "permit" },
''',
    '''        comment = "",
        replacements = listOf(ReplacementEntry()),
        errors = base.errors.filterKeys { it == "worker" || it == "permit" },
''',
    1,
)
vm = vm.replace(
    '''            comment = if (stage.kind == StageKind.STOP) "" else commonComment,
        )
''',
    '''            comment = if (stage.kind == StageKind.STOP) "" else commonComment,
            replacements = if (stage.kind == StageKind.REPLACEMENTS) {
                decodeReplacements(snapshot.fields[stage.first.key]?.field_value.orEmpty())
            } else listOf(ReplacementEntry()),
        )
''',
    1,
)
vm = vm.replace(
    '''        override fun onAvailable(network: Network) {
            viewModelScope.launch { syncPending(showMessage = false) }
        }
''',
    '''        override fun onAvailable(network: Network) {
            viewModelScope.launch {
                checkSystemStatus()
                syncPending(showMessage = false)
            }
        }
''',
    1,
)
vm = vm.replace(
    '''        if (NetworkState.isConnected(app) && queueStore.pendingCount() > 0) {
            viewModelScope.launch { syncPending(showMessage = false) }
        }
''',
    '''        if (NetworkState.isConnected(app)) {
            viewModelScope.launch {
                checkSystemStatus()
                if (queueStore.pendingCount() > 0) syncPending(showMessage = false)
            }
        }
''',
    1,
)
vm = vm.replace(
    '''    fun updateComment(v: String) { _state.value = _state.value.copy(comment = v.take(500), message = null) }

    fun nowPrimary() {
''',
    '''    fun updateComment(v: String) { _state.value = _state.value.copy(comment = v.take(500), message = null) }

    fun updateReplacementName(index: Int, value: String) {
        val updated = _state.value.replacements.toMutableList()
        if (index !in updated.indices) return
        updated[index] = updated[index].copy(name = value.take(180))
        _state.value = _state.value.copy(replacements = updated, message = null)
    }

    fun updateReplacementPosition(index: Int, value: String) {
        val updated = _state.value.replacements.toMutableList()
        if (index !in updated.indices) return
        updated[index] = updated[index].copy(position = value.take(180))
        _state.value = _state.value.copy(replacements = updated, message = null)
    }

    fun addReplacement() {
        if (_state.value.replacements.size >= 12) return
        _state.value = _state.value.copy(replacements = _state.value.replacements + ReplacementEntry(), message = null)
    }

    fun removeReplacement(index: Int) {
        val current = _state.value.replacements
        if (index !in current.indices) return
        val updated = current.filterIndexed { i, _ -> i != index }.ifEmpty { listOf(ReplacementEntry()) }
        _state.value = _state.value.copy(replacements = updated, message = null)
    }

    fun nowPrimary() {
''',
    1,
)
vm = vm.replace(
    '''            StageKind.EXTENSION_DATE -> {
                val extension = try {
                    LocalDate.parse(s.extensionDate, dateFmt)
                } catch (_: Exception) {
                    errors["extension"] = "Проверьте дату продления"
                    null
                }
                if (extension != null && extension.isBefore(LocalDate.now())) errors["extension"] = "Дата продления не может быть в прошлом"
                if (extension != null && errors["extension"] == null) {
                    events += PendingEvent(s.stage.first, LocalDateTime.now(), extension.format(dateFmt), s.comment.trim())
                }
            }
''',
    '''            StageKind.EXTENSION_DATE -> {
                val extension = try {
                    LocalDate.parse(s.extensionDate, dateFmt)
                } catch (_: Exception) {
                    errors["extension"] = "Проверьте дату продления"
                    null
                }
                if (extension != null && extension.isBefore(LocalDate.now())) errors["extension"] = "Дата продления не может быть в прошлом"
                if (extension != null && errors["extension"] == null) {
                    events += PendingEvent(s.stage.first, LocalDateTime.now(), extension.format(dateFmt), s.comment.trim())
                }
            }

            StageKind.REPLACEMENTS -> {
                if (!replacementsReady(s.replacements)) {
                    errors["replacements"] = "Для каждой замены укажите ФИО и должность / профессию"
                } else {
                    events += PendingEvent(
                        s.stage.first,
                        LocalDateTime.now(),
                        encodeReplacements(s.replacements),
                        "",
                    )
                }
            }
''',
    1,
)
load_history_marker = '''    fun loadHistory() {
'''
status_func = '''    private suspend fun checkSystemStatus() {
        if (!NetworkState.isConnected(application)) return
        try {
            val response = ru.rpo.mobile.data.ApiFactory.api.config(BuildConfig.VERSION_NAME)
            if (response.isSuccessful) {
                _state.value = _state.value.copy(systemNotice = response.body())
            }
        } catch (_: Exception) {
            // Feedback is informational and must never block field work.
        }
    }

'''
if load_history_marker not in vm:
    raise RuntimeError("loadHistory marker not found")
vm = vm.replace(load_history_marker, status_func + load_history_marker, 1)
write("android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt", vm)

# RpoApp additions.
ui = read("android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt")
ui = ui.replace(
    '''    s.comment,
).joinToString("|")
''',
    '''    s.comment,
    s.replacements.joinToString("~") { "${it.name}:${it.position}" },
).joinToString("|")
''',
    1,
)
ui = ui.replace(
    '''        if (s.pendingCount > 0 || s.failedCount > 0) {
''',
    '''        s.systemNotice?.let { notice ->
            Surface(
                color = if (notice.maintenance) Color(0xFFFFF1ED) else Color(0xFFEAF3FF),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Row(Modifier.padding(12.dp), verticalAlignment = Alignment.Top) {
                    Icon(
                        if (notice.maintenance) Icons.Default.Warning else Icons.Default.CloudDone,
                        null,
                        tint = if (notice.maintenance) Red else Blue,
                    )
                    Spacer(Modifier.width(9.dp))
                    Column {
                        Text(notice.message, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                        if (notice.update_available) {
                            Text(
                                "Доступно обновление ${notice.latest_app_version}. Текущая версия продолжит передавать данные.",
                                color = Blue,
                                fontSize = 11.sp,
                            )
                        }
                    }
                }
            }
        }

        if (s.pendingCount > 0 || s.failedCount > 0) {
''',
    1,
)
old_extension = '''            StageKind.EXTENSION_DATE -> {
                Text("Новая дата окончания работ", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                DateField(s.extensionDate, vm::updateExtensionDate, s.errors["extension"])
                OutlinedButton(
                    onClick = vm::extensionTomorrow,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                ) {
                    Icon(Icons.Default.Event, null)
                    Spacer(Modifier.width(5.dp))
                    Text("Выбрать завтра", maxLines = 1)
                }
                Field("Комментарий (необязательно)", s.comment, vm::updateComment, "Причина или примечание", null, singleLine = false)
            }
'''
new_extension = old_extension + '''
            StageKind.REPLACEMENTS -> {
                Surface(color = Color(0xFFF2F6FC), shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("Замена исполнителей работ", fontWeight = FontWeight.Bold)
                        Text(
                            "Раздел необязательный. Заполняйте его только при фактической замене исполнителей.",
                            color = Color.Gray,
                            fontSize = 12.sp,
                        )
                        s.replacements.forEachIndexed { index, item ->
                            ElevatedCard(Modifier.fillMaxWidth()) {
                                Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text("Исполнитель ${index + 1}", fontWeight = FontWeight.SemiBold)
                                        Spacer(Modifier.weight(1f))
                                        if (s.replacements.size > 1) {
                                            TextButton(onClick = { vm.removeReplacement(index) }) { Text("Удалить", color = Red) }
                                        }
                                    }
                                    Field("ФИО", item.name, { vm.updateReplacementName(index, it) }, "Например: Петров П.П.", null)
                                    Field("Должность / профессия", item.position, { vm.updateReplacementPosition(index, it) }, "Например: электромонтёр", null)
                                }
                            }
                        }
                        OutlinedButton(onClick = vm::addReplacement, modifier = Modifier.fillMaxWidth()) {
                            Icon(Icons.Default.Add, null)
                            Spacer(Modifier.width(6.dp))
                            Text("Добавить ещё исполнителя")
                        }
                        s.errors["replacements"]?.let { Text(it, color = Red, fontSize = 12.sp) }
                    }
                }
            }
'''
if old_extension not in ui:
    raise RuntimeError("extension UI block not found")
ui = ui.replace(old_extension, new_extension, 1)
ui = ui.replace(
    'Text("Сохранено этапов: $savedCount из ${stages.size}", fontSize = 12.sp, color = Color.Gray)',
    'Text("Сохранено обязательных этапов: $savedCount из $requiredStageCount", fontSize = 12.sp, color = Color.Gray)',
    1,
)
ui = ui.replace(
    '''                                Text(
                                    if (saved) "Сохранён" else eventTitles.joinToString(" • "),
                                    fontSize = 11.sp,
                                    color = if (saved) Green else Color.Gray,
                                )
''',
    '''                                Text(
                                    when {
                                        saved -> "Сохранён"
                                        stage.optional -> "Необязательно"
                                        else -> eventTitles.joinToString(" • ")
                                    },
                                    fontSize = 11.sp,
                                    color = if (saved) Green else Color.Gray,
                                )
''',
    1,
)
ui = ui.replace(
    '"7. Для синхронизации подходит любая интернет-сеть, включая медленное мобильное соединение 2G. Передаваемые пакеты данных небольшие."',
    '"7. Раздел «Замена исполнителей работ» необязательный. При замене укажите ФИО и должность / профессию каждого нового исполнителя.\\n\\n" +\n                "8. Приложение получает от сервера сообщение о состоянии системы и доступной версии. Старые версии приложения остаются совместимыми с сервером.\\n\\n" +\n                "9. Для синхронизации подходит любая интернет-сеть, включая медленное мобильное соединение 2G. Передаваемые пакеты данных небольшие."',
    1,
)
write("android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt", ui)

# Version bump.
replace_once("android/app/build.gradle.kts", 'versionCode = 7', 'versionCode = 8')
replace_once("android/app/build.gradle.kts", 'versionName = "1.1.4"', 'versionName = "1.1.5"')

# ---------------------------------------------------------------------------
# Dashboard UI: Operator account management and admin-only deletion.
# ---------------------------------------------------------------------------
tpl = read("server/app/templates/dashboard.html")
tpl = tpl.replace("app.css?v=20260815-4", "app.css?v=20260821-1")
tpl = tpl.replace("dashboard.js?v=20260815-4", "dashboard.js?v=20260821-1")
tpl = tpl.replace(
    '    <a href="#users" data-tab-link="users">♙ Пользователи</a>\n',
    '    {% if is_admin %}<a href="#users" data-tab-link="users">♙ Пользователи</a>{% endif %}\n',
    1,
)
tpl = tpl.replace('id="works-body">', 'id="works-body" data-can-delete="{{ \'true\' if is_admin else \'false\' }}">', 1)
tpl = tpl.replace(
    '<th>Этапы</th><th>Выгрузка</th></tr>',
    '<th>Этапы</th><th>Выгрузка</th><th>Действия</th></tr>',
    1,
)
old_users = '''<section class="tab-section" id="tab-users" data-tab="users" hidden>
  <article class="panel settings-panel"><div class="panel-title"><div><h2>Пользователи</h2><p class="muted panel-note">Пользователи операторской панели</p></div></div>
    <div class="settings-row"><span><b>{{ operator.username }}</b><small>Текущий оператор</small></span><span class="badge done">Активен</span></div>
    <div class="info-box">В релизе 1 используется один оператор. Управление ролями и несколькими операторами можно добавить отдельным этапом.</div>
  </article>
</section>
'''
new_users = '''{% if is_admin %}
<section class="tab-section" id="tab-users" data-tab="users" hidden>
  <article class="panel settings-panel"><div class="panel-title"><div><h2>Пользователи</h2><p class="muted panel-note">Администратор управляет доступом операторов. Пользователь Operator не может удалять НД.</p></div></div>
    {% if request.query_params.get('user') == 'password-updated' %}<div class="alert success">Пароль пользователя обновлён.</div>{% endif %}
    {% for u in users %}
      <div class="settings-row user-access-row">
        <span><b>{{ u.username }}</b><small>{% if u.username == operator.username %}Администратор · текущий вход{% else %}Оператор панели{% endif %}</small></span>
        <span class="badge {% if u.is_active %}done{% else %}pending{% endif %}">{{ 'Активен' if u.is_active else 'Отключён' }}</span>
      </div>
      {% if u.username != operator.username %}
      <form class="password-reset-form" method="post" action="/users/{{ u.id }}/password">
        <label>Новый пароль для {{ u.username }}<input type="password" name="password" minlength="10" autocomplete="new-password" required placeholder="Не менее 10 символов"></label>
        <button class="primary" type="submit">Задать новый пароль</button>
      </form>
      {% endif %}
    {% endfor %}
    <div class="info-box">Удаление нарядов-допусков доступно только администратору. Операторы могут просматривать данные, аналитику и выполнять выгрузки.</div>
  </article>
</section>
{% endif %}
'''
if old_users not in tpl:
    raise RuntimeError("users template block not found")
tpl = tpl.replace(old_users, new_users, 1)
tpl = tpl.replace(
    '<div class="settings-row"><span><b>Модель данных</b><small>Операционная таблица</small></span><strong>1 НД = 1 строка</strong></div>',
    '<div class="settings-row"><span><b>Модель данных</b><small>Операционная таблица</small></span><strong>1 НД = 1 строка</strong></div>\n      <div class="settings-row"><span><b>Мобильная версия</b><small>Рекомендуемая версия приложения</small></span><strong>{{ settings_view.mobile_version }}</strong></div>',
    1,
)
write("server/app/templates/dashboard.html", tpl)

js = read("server/app/static/dashboard.js")
js = js.replace(
    '''    const body=document.querySelector('#works-body');
    if(!body)return;
''',
    '''    const body=document.querySelector('#works-body');
    if(!body)return;
    const canDelete=body.dataset.canDelete==='true';
''',
    1,
)
old_map = '''    body.innerHTML=rows.map(e=>`<tr><td>${esc(fmt(e.updated_at))}</td><td><b>${esc(e.permit_number)}</b></td><td><b>${esc(e.worker_name)}</b></td><td><span class="work-state ${esc(e.status_class)}">${esc(e.status)}</span></td><td><div class="progress"><span style="width:${Number(e.progress)||0}%"></span></div><small>${Number(e.stage_count)||0} из ${Number(e.stage_total)||0}</small></td><td class="works-stage-cell">${stageDetails(e,openPermits.has(e.permit_number))}</td><td><span class="badge ${e.exported?'done':'pending'}">${e.exported?'Выгружено':'Не выгружено'}</span></td></tr>`).join('');
'''
new_map = '''    body.innerHTML=rows.map(e=>{
      const action=(canDelete&&e.can_delete)?`<button type="button" class="danger-button" data-delete-permit="${Number(e.id)}" data-permit-number="${esc(e.permit_number)}">Удалить</button>`:'—';
      return `<tr><td>${esc(fmt(e.updated_at))}</td><td><b>${esc(e.permit_number)}</b></td><td><b>${esc(e.worker_name)}</b></td><td><span class="work-state ${esc(e.status_class)}">${esc(e.status)}</span></td><td><div class="progress"><span style="width:${Number(e.progress)||0}%"></span></div><small>${Number(e.stage_count)||0} из ${Number(e.stage_total)||0}</small></td><td class="works-stage-cell">${stageDetails(e,openPermits.has(e.permit_number))}</td><td><span class="badge ${e.exported?'done':'pending'}">${e.exported?'Выгружено':'Не выгружено'}</span></td><td>${action}</td></tr>`;
    }).join('');
'''
if old_map not in js:
    raise RuntimeError("works render block not found")
js = js.replace(old_map, new_map, 1)
insert_after = '''setInterval(()=>{refreshWorks();refreshTransmissions()},5000);
'''
delete_handler = '''setInterval(()=>{refreshWorks();refreshTransmissions()},5000);

document.addEventListener('click',async e=>{
  const button=e.target.closest('[data-delete-permit]');
  if(!button)return;
  const id=Number(button.dataset.deletePermit);
  const permit=button.dataset.permitNumber||'';
  if(!id||!confirm(`Удалить НД ${permit}? Будут удалены сам НД и все полученные с телефонов события по нему. История уже выполненных выгрузок сохранится.`))return;
  button.disabled=true;
  try{
    const r=await fetch(`/api/operator/permits/${id}`,{method:'DELETE',credentials:'same-origin',headers:{'Accept':'application/json'}});
    let data={}; try{data=await r.json()}catch(_){}
    if(!r.ok)throw new Error(data.detail||'Не удалось удалить запись');
    await Promise.all([refreshWorks(),refreshTransmissions()]);
  }catch(err){alert(err.message||'Ошибка удаления');button.disabled=false;}
});
'''
if insert_after not in js:
    raise RuntimeError("refresh interval marker not found")
js = js.replace(insert_after, delete_handler, 1)
write("server/app/static/dashboard.js", js)

css_path = "server/app/static/app.css"
css = read(css_path)
css += '''

.danger-button{border:1px solid #efb4b4;background:#fff5f5;color:#b42318;border-radius:9px;padding:7px 10px;font-weight:700;cursor:pointer}
.danger-button:hover{background:#fee4e2}.danger-button:disabled{opacity:.55;cursor:wait}
.password-reset-form{display:grid;grid-template-columns:minmax(220px,1fr) auto;gap:10px;align-items:end;padding:10px 0 18px;border-bottom:1px solid #edf1f6}
.password-reset-form label{display:grid;gap:5px;font-size:13px;font-weight:600}.password-reset-form input{height:42px;border:1px solid #cdd6e2;border-radius:9px;padding:0 11px;font:inherit}.password-reset-form .primary{height:42px}.stage-detail-line strong{white-space:pre-wrap}
@media(max-width:720px){.password-reset-form{grid-template-columns:1fr}.password-reset-form .primary{width:100%}}
'''
write(css_path, css)

# Production smoke must verify the new feedback API after VPS auto-deploy.
smoke = read(".github/workflows/production-smoke.yml")
smoke = smoke.replace(
    "          required = '/api/mobile/permit'\n          if required not in paths:\n              raise SystemExit(f'Missing deployed API route: {required}')\n          print(f'Deployed API route confirmed: {required}')\n",
    "          required = ['/api/mobile/permit', '/api/mobile/config']\n          for route in required:\n              if route not in paths:\n                  raise SystemExit(f'Missing deployed API route: {route}')\n              print(f'Deployed API route confirmed: {route}')\n",
    1,
)
smoke += '''
      - name: Verify old APK compatibility status
        shell: bash
        run: |
          set -euo pipefail
          curl -fsS --max-time 10 'https://rpo-mng.ru/api/mobile/config?app_version=1.0.1' -o /tmp/mobile-config.json
          python3 - <<'PY'
          import json
          from pathlib import Path
          cfg=json.loads(Path('/tmp/mobile-config.json').read_text())
          assert cfg['status']=='ok'
          assert cfg['latest_app_version']=='1.1.5'
          assert cfg['update_required'] is False
          assert cfg['update_available'] is True
          print('Old APK remains supported; latest mobile version:', cfg['latest_app_version'])
          PY
'''
write(".github/workflows/production-smoke.yml", smoke)

# ---------------------------------------------------------------------------
# Regression tests.
# ---------------------------------------------------------------------------
write("server/tests/test_upgrade_20260821.py", '''from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import (
    DEFAULT_OPERATOR_USERNAME,
    _work_view,
    create_mobile_event,
    delete_permit_record,
    ensure_default_operator,
    mobile_config,
)
from app.models import MobileEvent, Operator, PermitRecord
from app.schemas import EventCreate


class Upgrade20260821Tests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(engine)

    def test_legacy_payload_without_new_metadata_is_still_accepted(self) -> None:
        payload = EventCreate.model_validate({
            "worker_name": "Иванов И.И.",
            "permit_number": "12345",
            "field_key": "BA",
            "event_time": datetime.now(timezone.utc).isoformat(),
            "field_value": "21.08.2026 10:00",
        })
        self.assertIsNone(payload.client_event_id)
        self.assertEqual(payload.stage_label, "")
        self.assertEqual(payload.comment, "")
        with SessionLocal() as db:
            event = create_mobile_event(payload, db)
            self.assertTrue(event.client_event_id.startswith("legacy-"))
            self.assertEqual(event.stage_label, "Возобновление работ")
            self.assertEqual(event.comment, "")

    def test_optional_replacement_stage_is_visible_but_not_progress_required(self) -> None:
        now = datetime.now(timezone.utc)
        record = PermitRecord(
            permit_number="20001",
            device_id="d1",
            worker_name="Иванов",
            data_json=json.dumps({
                "AT": {"field_value": "1"},
                "RI": {"field_value": "Петров П.П.\\tэлектромонтёр"},
            }, ensure_ascii=False),
            first_received_at=now,
            updated_at=now,
        )
        view = _work_view(record)
        self.assertEqual(view["stage_count"], 1)
        self.assertEqual(view["stage_total"], 8)
        self.assertIn("RI", {item["key"] for item in view["stage_items"]})

    def test_operator_account_is_bootstrapped(self) -> None:
        ensure_default_operator()
        with SessionLocal() as db:
            user = db.scalar(select(Operator).where(Operator.username == DEFAULT_OPERATOR_USERNAME))
            self.assertIsNotNone(user)
            self.assertTrue(user.is_active)
            self.assertTrue(user.password_hash.startswith("$argon2"))

    def test_only_admin_can_delete_permit_and_raw_events(self) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            record = PermitRecord(
                permit_number="30001", device_id="d", worker_name="Иванов",
                data_json="{}", first_received_at=now, updated_at=now,
            )
            db.add(record)
            db.flush()
            db.add(MobileEvent(
                client_event_id="delete-test-event",
                device_id="d", worker_name="Иванов", permit_number="30001",
                field_key="AT", stage_label="Начало подготовки", event_time=now,
                field_value="21.08.2026 10:00", comment="",
            ))
            db.commit()
            record_id = record.id

        with SessionLocal() as db:
            operator = Operator(username="Operator", password_hash="x")
            with self.assertRaises(HTTPException) as ctx:
                delete_permit_record(record_id, operator=operator, db=db)
            self.assertEqual(ctx.exception.status_code, 403)

        with SessionLocal() as db:
            admin = Operator(username=settings.admin_username, password_hash="x")
            result = delete_permit_record(record_id, operator=admin, db=db)
            self.assertEqual(result["status"], "deleted")

        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(PermitRecord)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(MobileEvent)), 0)

    def test_mobile_feedback_marks_old_version_supported_not_required(self) -> None:
        cfg = mobile_config("1.0.1")
        self.assertEqual(cfg["latest_app_version"], "1.1.5")
        self.assertTrue(cfg["update_available"])
        self.assertFalse(cfg["update_required"])
        self.assertFalse(cfg["maintenance"])


if __name__ == "__main__":
    unittest.main()
''')

write("android/app/src/test/java/ru/rpo/mobile/ui/ProjectUpgradeTest.kt", '''package ru.rpo.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectUpgradeTest {
    @Test
    fun replacementStageIsOptionalAndDoesNotIncreaseRequiredProgress() {
        val replacement = stages.first { it.id == "REPLACEMENTS" }
        assertTrue(replacement.optional)
        assertEquals(StageKind.REPLACEMENTS, replacement.kind)
        assertEquals("RI", replacement.first.key)
        assertFalse(replacement in requiredStages)
        assertEquals(6, requiredStageCount)
        assertEquals(0, savedStageCount(setOf("REPLACEMENTS")))
    }

    @Test
    fun replacementRowsRoundTripAndRequireBothFields() {
        val rows = listOf(
            ReplacementEntry("Иванов И.И.", "электромонтёр"),
            ReplacementEntry("Петров П.П.", "слесарь"),
        )
        assertTrue(replacementsReady(rows))
        val encoded = encodeReplacements(rows)
        assertEquals(rows, decodeReplacements(encoded))
        assertFalse(replacementsReady(listOf(ReplacementEntry("Иванов И.И.", ""))))
    }

    @Test
    fun replacementStageReadinessUsesReplacementRows() {
        val stage = stages.first { it.id == "REPLACEMENTS" }
        assertFalse(stageDataReady(FormState(stage = stage)))
        assertTrue(stageDataReady(FormState(
            stage = stage,
            replacements = listOf(ReplacementEntry("Иванов И.И.", "машинист")),
        )))
    }
}
''')

# Update existing stage key regression to include the new optional field.
replace_once(
    "android/app/src/test/java/ru/rpo/mobile/ui/StagesTest.kt",
    'assertTrue(keys.containsAll(listOf("AT", "AU", "AV", "AY", "BC", "AZ", "BA", "BE")))',
    'assertTrue(keys.containsAll(listOf("AT", "AU", "AV", "AY", "BC", "AZ", "BA", "BE", "RI")))',
)

# Update server regression expectations for the extra optional field without
# changing the required 8-stage progress calculation.
replace_once(
    "server/tests/test_regressions.py",
    'self.assertEqual(preview["stage_keys"], ["AT", "AU", "AV", "AY", "AZ", "BA", "BE", "BC"])',
    'self.assertEqual(preview["stage_keys"], ["AT", "AU", "AV", "AY", "AZ", "BA", "BE", "BC", "RI"])',
)
replace_once(
    "server/tests/test_regressions.py",
    'self.assertIn("dashboard.js?v=20260815-4", template)\n        self.assertIn("app.css?v=20260815-4", template)',
    'self.assertIn("dashboard.js?v=20260821-1", template)\n        self.assertIn("app.css?v=20260821-1", template)',
)

# Remove this one-shot job from Quality Gate after the patch is committed.
write(".github/workflows/quality-gate.yml", '''name: Quality Gate

on:
  push:
    branches: [develop]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  backend-tests:
    name: Backend regression tests
    runs-on: ubuntu-latest
    timeout-minutes: 10
    env:
      PYTHONPATH: server
      DATABASE_URL: sqlite:////tmp/rpo-quality.db
      SECRET_KEY: quality-gate-secret
      ADMIN_USERNAME: admin
      ADMIN_PASSWORD: QualityGate123!
      MAIL_MODE: file
      EXPORT_DIR: /tmp/rpo-quality-exports
      OUTBOX_DIR: /tmp/rpo-quality-outbox

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python 3.13
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'
          cache: pip
          cache-dependency-path: server/requirements-test.txt

      - name: Validate deployment shell scripts
        run: |
          bash -n ops/autodeploy.sh ops/install-autodeploy.sh
          grep -Fx 'ExecStart=/bin/bash /opt/rpo/ops/autodeploy.sh' ops/rpo-autodeploy.service
          if grep -Eq 'chmod[[:space:]].*ops/autodeploy\\.sh' ops/install-autodeploy.sh; then
            echo 'Installer must not change the tracked autodeploy.sh mode.' >&2
            exit 1
          fi

      - name: Install backend test dependencies
        run: python -m pip install -r server/requirements-test.txt

      - name: Compile backend Python
        run: python -m compileall -q server/app

      - name: Check dashboard JavaScript syntax
        run: node --check server/app/static/dashboard.js

      - name: Run backend regression tests
        run: python -m unittest discover -s server/tests -v

  android-tests:
    name: Android unit tests
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v5
        with:
          distribution: temurin
          java-version: '17'

      - name: Set up Android SDK
        uses: android-actions/setup-android@v3

      - name: Set up Gradle 8.7
        uses: gradle/actions/setup-gradle@v4
        with:
          gradle-version: '8.7'

      - name: Run Android unit tests before APK build
        working-directory: android
        run: gradle --no-daemon testDebugUnitTest
''')

# The script deletes itself so no deployment-only helper reaches main.
Path(__file__).unlink()
