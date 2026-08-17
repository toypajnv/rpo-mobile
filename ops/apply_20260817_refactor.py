from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, content):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"Missing replacement anchor: {label}")
    return text.replace(old, new, 1)


# ---------- Android stage model ----------
write("android/app/src/main/java/ru/rpo/mobile/ui/Stages.kt", '''package ru.rpo.mobile.ui

enum class StageKind { RANGE_DATETIME, TRIPLE_DATETIME, DATETIME, STOP, EXTENSION_DATE }

data class StageEvent(val key: String, val title: String)

data class Stage(
    val id: String,
    val title: String,
    val kind: StageKind,
    val first: StageEvent,
    val second: StageEvent? = null,
    val third: StageEvent? = null,
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
)

fun savedStageCount(savedStageIds: Set<String>): Int = stages.count { it.id in savedStageIds }

fun savedStageIdsForFieldKeys(fieldKeys: Set<String>): Set<String> = stages
    .filter { stage -> listOfNotNull(stage.first.key, stage.second?.key, stage.third?.key).all { it in fieldKeys } }
    .map { it.id }
    .toSet()

fun shouldWarnBeforeStageSwitch(current: Stage, target: Stage, hasUnsavedChanges: Boolean): Boolean =
    current.id != target.id && hasUnsavedChanges
''')

# ---------- Pure Android validation helpers ----------
write("android/app/src/main/java/ru/rpo/mobile/ui/FormRules.kt", '''package ru.rpo.mobile.ui

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.format.DateTimeFormatter

internal val rpoDateFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy")
internal val rpoTimeFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("HH:mm")
internal val rpoDateTimeFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm")

data class OperationalDateTimeResult(val value: LocalDateTime?, val error: String?)

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
''')

# ---------- API models ----------
models = read("android/app/src/main/java/ru/rpo/mobile/data/Models.kt")
models += '''\n\ndata class PermitFieldSnapshot(\n    val field_value: String = "",\n    val event_time: String = "",\n    val comment: String = "",\n)\n\ndata class PermitSnapshot(\n    val permit_number: String,\n    val worker_name: String,\n    val updated_at: String,\n    val fields: Map<String, PermitFieldSnapshot> = emptyMap(),\n)\n'''
write("android/app/src/main/java/ru/rpo/mobile/data/Models.kt", models)

api = read("android/app/src/main/java/ru/rpo/mobile/data/RpoApi.kt")
api = replace_once(api,
'''    @GET("api/mobile/events")\n    suspend fun history(@Query("device_id") deviceId: String, @Query("limit") limit: Int = 30): Response<List<EventResponse>>\n''',
'''    @GET("api/mobile/events")\n    suspend fun history(@Query("device_id") deviceId: String, @Query("limit") limit: Int = 30): Response<List<EventResponse>>\n\n    @GET("api/mobile/permit")\n    suspend fun permit(@Query("permit_number") permitNumber: String): Response<PermitSnapshot>\n''', "RpoApi permit lookup")
write("android/app/src/main/java/ru/rpo/mobile/data/RpoApi.kt", api)

# ---------- ViewModel ----------
vm = read("android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt")
vm = replace_once(vm, "import kotlinx.coroutines.launch\n", "import kotlinx.coroutines.Job\nimport kotlinx.coroutines.delay\nimport kotlinx.coroutines.launch\n", "coroutine imports")
vm = replace_once(vm, "import ru.rpo.mobile.data.EventResponse\n", "import ru.rpo.mobile.data.EventResponse\nimport ru.rpo.mobile.data.PermitSnapshot\n", "PermitSnapshot import")
vm = replace_once(vm,
'''    val primaryDate: String = LocalDate.now().format(dateFmt),\n    val primaryTime: String = LocalTime.now().format(timeFmt),\n    val secondaryDate: String = LocalDate.now().format(dateFmt),\n    val secondaryTime: String = LocalTime.now().format(timeFmt),\n    val thirdDate: String = LocalDate.now().format(dateFmt),\n    val thirdTime: String = LocalTime.now().format(timeFmt),\n    val extensionDate: String = LocalDate.now().plusDays(1).format(dateFmt),\n''',
'''    val primaryDate: String = "",\n    val primaryTime: String = "",\n    val secondaryDate: String = "",\n    val secondaryTime: String = "",\n    val thirdDate: String = "",\n    val thirdTime: String = "",\n    val extensionDate: String = "",\n''', "blank date defaults")
vm = replace_once(vm, "    val failedCount: Int = 0,\n)", "    val failedCount: Int = 0,\n    val serverSavedStageIds: Set<String> = emptySet(),\n)", "server saved stage state")
vm = replace_once(vm,
"    private val connectivityManager = app.getSystemService(ConnectivityManager::class.java)\n",
"    private val connectivityManager = app.getSystemService(ConnectivityManager::class.java)\n    private var permitLookupJob: Job? = null\n    private var serverPermitSnapshot: PermitSnapshot? = null\n",
"lookup state")

anchor = "    fun selectPermit(memory: PermitMemory) {"
helpers = '''    private fun blankStageFields(base: FormState, stage: Stage = base.stage): FormState = base.copy(\n        stage = stage,\n        primaryDate = "",\n        primaryTime = "",\n        secondaryDate = "",\n        secondaryTime = "",\n        thirdDate = "",\n        thirdTime = "",\n        extensionDate = "",\n        stopReason = "",\n        comment = "",\n        errors = base.errors.filterKeys { it == "worker" || it == "permit" },\n        message = null,\n    )\n\n    private fun snapshotDateTime(snapshot: PermitSnapshot, key: String?): Pair<String, String> {\n        if (key == null) return "" to ""\n        val raw = snapshot.fields[key]?.field_value.orEmpty().trim()\n        val parsed = runCatching { LocalDateTime.parse(raw, valueFmt) }.getOrNull() ?: return "" to ""\n        return parsed.toLocalDate().format(dateFmt) to parsed.toLocalTime().format(timeFmt)\n    }\n\n    private fun applySnapshotToStage(base: FormState, stage: Stage, snapshot: PermitSnapshot?): FormState {\n        val cleared = blankStageFields(base, stage)\n        if (snapshot == null || !snapshot.permit_number.equals(base.permitNumber.trim(), ignoreCase = true)) return cleared\n        val first = snapshotDateTime(snapshot, stage.first.key)\n        val second = snapshotDateTime(snapshot, stage.second?.key)\n        val third = snapshotDateTime(snapshot, stage.third?.key)\n        val stageFields = listOfNotNull(stage.first.key, stage.second?.key, stage.third?.key).mapNotNull { snapshot.fields[it] }\n        val commonComment = stageFields.firstOrNull { it.comment.isNotBlank() }?.comment.orEmpty()\n        return cleared.copy(\n            primaryDate = first.first,\n            primaryTime = first.second,\n            secondaryDate = second.first,\n            secondaryTime = second.second,\n            thirdDate = third.first,\n            thirdTime = third.second,\n            extensionDate = if (stage.kind == StageKind.EXTENSION_DATE) snapshot.fields[stage.first.key]?.field_value.orEmpty() else "",\n            stopReason = if (stage.kind == StageKind.STOP) snapshot.fields[stage.first.key]?.comment.orEmpty() else "",\n            comment = if (stage.kind == StageKind.STOP) "" else commonComment,\n        )\n    }\n\n    private fun schedulePermitLookup(permitNumber: String, immediate: Boolean = false) {\n        permitLookupJob?.cancel()\n        val normalized = permitNumber.trim().uppercase()\n        if (!permitRegex.matches(normalized)) {\n            serverPermitSnapshot = null\n            _state.value = _state.value.copy(serverSavedStageIds = emptySet())\n            return\n        }\n        permitLookupJob = viewModelScope.launch {\n            if (!immediate) delay(550)\n            if (!NetworkState.isConnected(application)) return@launch\n            try {\n                val response = ru.rpo.mobile.data.ApiFactory.api.permit(normalized)\n                if (_state.value.permitNumber.trim().uppercase() != normalized) return@launch\n                if (response.isSuccessful) {\n                    val snapshot = response.body() ?: return@launch\n                    serverPermitSnapshot = snapshot\n                    val filledKeys = snapshot.fields.filterValues { it.field_value.isNotBlank() }.keys\n                    val worker = snapshot.worker_name.ifBlank { _state.value.workerName }\n                    val base = _state.value.copy(\n                        workerName = worker,\n                        serverSavedStageIds = savedStageIdsForFieldKeys(filledKeys),\n                        errors = _state.value.errors - "worker" - "permit",\n                        message = "Ранее заполненные данные по НД загружены с сервера",\n                        success = true,\n                    )\n                    _state.value = applySnapshotToStage(base, base.stage, snapshot)\n                    if (worker.isNotBlank()) prefs.edit().putString("worker_name", worker).apply()\n                } else if (response.code() == 404) {\n                    serverPermitSnapshot = null\n                    _state.value = _state.value.copy(serverSavedStageIds = emptySet())\n                }\n            } catch (_: Exception) {\n                // Работа без сети остаётся доступной; серверное автозаполнение повторится при следующем вводе номера.\n            }\n        }\n    }\n\n'''
vm = replace_once(vm, anchor, helpers + anchor, "ViewModel helper insertion")

pattern = re.compile(r"    fun selectPermit\(memory: PermitMemory\) \{.*?\n    \}\n\n    fun updateWorker", re.S)
replacement = '''    fun selectPermit(memory: PermitMemory) {\n        val worker = memory.workerName.ifBlank { _state.value.workerName }\n        _state.value = blankStageFields(_state.value).copy(\n            permitNumber = memory.permitNumber,\n            workerName = worker,\n            serverSavedStageIds = emptySet(),\n            errors = _state.value.errors - "permit" - "worker",\n            message = null,\n        )\n        serverPermitSnapshot = null\n        if (worker.isNotBlank()) prefs.edit().putString("worker_name", worker).apply()\n        schedulePermitLookup(memory.permitNumber, immediate = true)\n    }\n\n    fun updateWorker'''
vm, count = pattern.subn(replacement, vm, count=1)
if count != 1: raise RuntimeError("selectPermit replacement failed")

pattern = re.compile(r"    fun updatePermit\(v: String\) \{.*?\n    \}\n\n    fun updateStage\(v: Stage\) \{.*?\n    \}\n", re.S)
replacement = '''    fun updatePermit(v: String) {\n        val value = v.uppercase().take(80)\n        val hasInvalidChar = value.any { !permitCharRegex.matches(it.toString()) }\n        val errors = _state.value.errors.toMutableMap()\n        if (hasInvalidChar) errors["permit"] = "Допустимы только буквы, цифры, пробел и символы . _ / -"\n        else errors.remove("permit")\n        serverPermitSnapshot = null\n        _state.value = blankStageFields(_state.value).copy(\n            permitNumber = value,\n            errors = errors,\n            serverSavedStageIds = emptySet(),\n            message = null,\n        )\n        schedulePermitLookup(value)\n    }\n\n    fun updateStage(v: Stage) {\n        val snapshot = serverPermitSnapshot\n        _state.value = applySnapshotToStage(_state.value, v, snapshot)\n    }\n'''
vm, count = pattern.subn(replacement, vm, count=1)
if count != 1: raise RuntimeError("updatePermit/updateStage replacement failed")

pattern = re.compile(r"    private fun parseDateTime\(date: String, time: String, errorKey: String, errors: MutableMap<String, String>\): LocalDateTime\? \{.*?\n    \}\n", re.S)
replacement = '''    private fun parseDateTime(date: String, time: String, errorKey: String, errors: MutableMap<String, String>): LocalDateTime? {\n        val result = parseOperationalDateTime(date, time)\n        if (result.error != null) errors[errorKey] = result.error\n        return result.value\n    }\n'''
vm, count = pattern.subn(replacement, vm, count=1)
if count != 1: raise RuntimeError("parseDateTime replacement failed")

old = '''            StageKind.DATETIME -> {\n                val dt = parseDateTime(s.primaryDate, s.primaryTime, "primary", errors)\n                if (dt != null && errors["primary"] == null) events += PendingEvent(s.stage.first, dt, dt.format(valueFmt), s.comment.trim())\n            }\n'''
new = '''            StageKind.DATETIME -> {\n                val dt = parseDateTime(s.primaryDate, s.primaryTime, "primary", errors)\n                val commentError = resumeCommentError(s.stage.id, s.comment)\n                if (commentError != null) errors["comment"] = commentError\n                if (dt != null && errors["primary"] == null && errors["comment"] == null) {\n                    events += PendingEvent(s.stage.first, dt, dt.format(valueFmt), s.comment.trim())\n                }\n            }\n'''
vm = replace_once(vm, old, new, "resume comment validation")
write("android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt", vm)

# ---------- Compose UI ----------
ui = read("android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt")
ui = replace_once(ui, "import android.content.Context\n", "import android.app.DatePickerDialog\nimport android.content.Context\n", "DatePicker import")
ui = replace_once(ui, "import androidx.lifecycle.viewmodel.compose.viewModel\n", "import androidx.lifecycle.viewmodel.compose.viewModel\nimport java.time.LocalDate\nimport java.time.format.DateTimeFormatter\n", "date imports")
ui = replace_once(ui,
'''    var savedStageIds by remember(permitKey) { mutableStateOf(loadSavedStageIds(context, permitKey)) }\n    var pendingStage by remember(permitKey) { mutableStateOf<Stage?>(null) }\n    var baseline by remember(permitKey, s.stage.id) { mutableStateOf(stageFingerprint(s)) }\n    val currentFingerprint = stageFingerprint(s)\n''',
'''    var savedStageIds by remember(permitKey) { mutableStateOf(loadSavedStageIds(context, permitKey)) }\n    val combinedSavedStageIds = savedStageIds + s.serverSavedStageIds\n    var pendingStage by remember(permitKey) { mutableStateOf<Stage?>(null) }\n    var baseline by remember(permitKey, s.stage.id, s.serverSavedStageIds) { mutableStateOf(stageFingerprint(s)) }\n    val currentFingerprint = stageFingerprint(s)\n''', "combined saved stages")
ui = ui.replace("savedStageIds = savedStageIds,", "savedStageIds = combinedSavedStageIds,", 1)
ui = replace_once(ui, "val updated = savedStageIds + s.stage.id", "val updated = combinedSavedStageIds + s.stage.id", "saved stage button")
ui = replace_once(ui, "CheckLine(s.errors.keys.none { it in setOf(\"primary\", \"secondary\", \"third\", \"extension\", \"stopReason\") }, \"Данные этапа заполнены\")", "CheckLine(s.errors.keys.none { it in setOf(\"primary\", \"secondary\", \"third\", \"extension\", \"stopReason\", \"comment\") }, \"Данные этапа заполнены\")", "checkline errors")
ui = replace_once(ui, "CheckLine(s.stage.id in savedStageIds && !hasUnsavedChanges, \"Текущий этап сохранён\")", "CheckLine(s.stage.id in combinedSavedStageIds && !hasUnsavedChanges, \"Текущий этап сохранён\")", "current saved check")

old = '''                Field("Комментарий (необязательно)", s.comment, vm::updateComment, "Комментарий к этапу", null, singleLine = false)\n            }\n\n            StageKind.STOP -> {'''
new = '''                val resume = s.stage.id == "RESUME_WORK"\n                Field(\n                    if (resume) "Комментарий (обязательно)" else "Комментарий (необязательно)",\n                    s.comment,\n                    vm::updateComment,\n                    if (resume) "Укажите условия или основание возобновления" else "Комментарий к этапу",\n                    if (resume) s.errors["comment"] else null,\n                    singleLine = false,\n                )\n            }\n\n            StageKind.STOP -> {'''
ui = replace_once(ui, old, new, "resume comment UI")

ui = replace_once(ui,
'''                    Box(Modifier.weight(1f)) {\n                        Field(null, s.extensionDate, vm::updateExtensionDate, "ДД.ММ.ГГГГ", s.errors["extension"])\n                    }''',
'''                    Box(Modifier.weight(1f)) {\n                        DateField(s.extensionDate, vm::updateExtensionDate, s.errors["extension"])\n                    }''', "extension calendar")

ui = replace_once(ui,
'''            Box(Modifier.weight(1f)) { Field(null, date, onDate, "ДД.ММ.ГГГГ", error) }''',
'''            Box(Modifier.weight(1f)) { DateField(date, onDate, error) }''', "date calendar in datetime")

anchor = '''@Composable\nprivate fun DateTimeBlock('''
date_field = '''private val uiDateFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy")\n\n@Composable\nprivate fun DateField(value: String, onDate: (String) -> Unit, error: String?) {\n    val context = LocalContext.current\n    val openPicker = {\n        val initial = runCatching { LocalDate.parse(value, uiDateFormatter) }.getOrElse { LocalDate.now() }\n        DatePickerDialog(\n            context,\n            { _, year, month, day -> onDate(String.format("%02d.%02d.%04d", day, month + 1, year)) },\n            initial.year,\n            initial.monthValue - 1,\n            initial.dayOfMonth,\n        ).show()\n    }\n    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {\n        OutlinedButton(\n            onClick = openPicker,\n            modifier = Modifier.fillMaxWidth().height(56.dp),\n            shape = RoundedCornerShape(11.dp),\n            contentPadding = PaddingValues(horizontal = 12.dp),\n        ) {\n            Text(value.ifBlank { "Выберите дату" }, Modifier.weight(1f), color = if (value.isBlank()) Color.Gray else Color.Unspecified)\n            Icon(Icons.Default.Event, "Открыть календарь")\n        }\n        if (error != null) Text(error, color = Red, fontSize = 12.sp)\n    }\n}\n\n@Composable\nprivate fun DateTimeBlock('''
ui = replace_once(ui, anchor, date_field, "DateField insertion")

ui = ui.replace("3. Выберите укрупнённый этап. «Передача и начало работ» содержит передачу, фактическое начало и окончание работ.", "3. Выберите этап. Передача объекта и фактическое начало/окончание работ теперь заполняются отдельными блоками.")
ui = ui.replace("5. Для дат и времени можно использовать кнопку «Сейчас». Для остановки работ обязательно укажите время и причину. Для продления РПО укажите новую дату окончания.", "5. Дату выбирайте из календаря, время вводите вручную или кнопкой «Сейчас». Для остановки обязательна причина, а для возобновления — комментарий. Для продления РПО укажите новую дату окончания.")
write("android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt", ui)

# ---------- Server exact permit lookup ----------
main = read("server/app/main.py")
anchor = '''@app.get("/api/mobile/events", response_model=list[EventOut])\ndef mobile_history'''
endpoint = '''@app.get("/api/mobile/permit")\ndef mobile_permit_lookup(\n    permit_number: str = Query(min_length=3, max_length=80),\n    db: Session = Depends(get_db),\n):\n    normalized = permit_number.strip().upper()\n    record = db.scalar(select(PermitRecord).where(PermitRecord.permit_number == normalized))\n    if not record:\n        raise HTTPException(status_code=404, detail="Наряд-допуск не найден")\n    data = record_data(record)\n    fields = {\n        key: {\n            "field_value": str((data.get(key) or {}).get("field_value", "")),\n            "event_time": str((data.get(key) or {}).get("event_time", "")),\n            "comment": str((data.get(key) or {}).get("comment", "")),\n        }\n        for key in _dashboard_stage_keys()\n        if data.get(key)\n    }\n    return {\n        "permit_number": record.permit_number,\n        "worker_name": record.worker_name,\n        "updated_at": record.updated_at.isoformat(),\n        "fields": fields,\n    }\n\n\n@app.get("/api/mobile/events", response_model=list[EventOut])\ndef mobile_history'''
main = replace_once(main, anchor, endpoint, "server permit endpoint")
write("server/app/main.py", main)

# ---------- Tests ----------
write("android/app/src/test/java/ru/rpo/mobile/ui/FormRulesTest.kt", '''package ru.rpo.mobile.ui\n\nimport java.time.LocalDateTime\nimport org.junit.Assert.assertEquals\nimport org.junit.Assert.assertNull\nimport org.junit.Assert.assertTrue\nimport org.junit.Test\n\nclass FormRulesTest {\n    @Test\n    fun august17CurrentDayIsAccepted() {\n        val now = LocalDateTime.of(2026, 8, 17, 15, 0)\n        val result = parseOperationalDateTime("17.08.2026", "14:30", now)\n        assertNull(result.error)\n        assertEquals(LocalDateTime.of(2026, 8, 17, 14, 30), result.value)\n    }\n\n    @Test\n    fun futureActualEventIsRejectedWithClearMessage() {\n        val now = LocalDateTime.of(2026, 8, 17, 15, 0)\n        val result = parseOperationalDateTime("17.08.2026", "16:00", now)\n        assertTrue(result.error!!.contains("будущем"))\n    }\n\n    @Test\n    fun resumeRequiresComment() {\n        assertEquals("Комментарий при возобновлении обязателен", resumeCommentError("RESUME_WORK", ""))\n        assertNull(resumeCommentError("RESUME_WORK", "Работы можно продолжить"))\n        assertNull(resumeCommentError("TRANSFER_WORK", ""))\n    }\n\n    @Test\n    fun serverFieldsMapToCompletedUserStages() {\n        val ids = savedStageIdsForFieldKeys(setOf("AT", "AU", "AV", "AY", "BC", "BE"))\n        assertTrue("PREPARATION" in ids)\n        assertTrue("TRANSFER_WORK" in ids)\n        assertTrue("ACTUAL_WORK" in ids)\n        assertTrue("EXTEND_WORK" in ids)\n    }\n}\n''')

test_api = read("server/tests/test_api.py")
test_api += '''\n\ndef test_mobile_permit_lookup_returns_previous_server_data():\n    with TestClient(app) as c:\n        payload = event_payload(\n            client_event_id="33333333-3333-3333-3333-333333333333",\n            permit_number="НД-1708",\n            field_key="AT",\n            stage_label="Начало подготовки",\n            field_value="17.08.2026 09:15",\n            event_time="2026-08-17T04:15:00+00:00",\n            comment="Начало подготовки",\n        )\n        created = c.post("/api/mobile/events", json=payload)\n        assert created.status_code == 201, created.text\n        result = c.get("/api/mobile/permit", params={"permit_number": "нд-1708"})\n        assert result.status_code == 200, result.text\n        body = result.json()\n        assert body["permit_number"] == "НД-1708"\n        assert body["worker_name"] == "Иванов Иван Иванович"\n        assert body["fields"]["AT"]["field_value"] == "17.08.2026 09:15"\n        assert body["fields"]["AT"]["comment"] == "Начало подготовки"\n'''
write("server/tests/test_api.py", test_api)

# Version bump
build = read("android/app/build.gradle.kts")
build = replace_once(build, 'versionCode = 5', 'versionCode = 6', 'versionCode')
build = replace_once(build, 'versionName = "1.1.2"', 'versionName = "1.1.3"', 'versionName')
write("android/app/build.gradle.kts", build)

# Remove one-shot automation files from the final generated commit.
(ROOT / "ops/apply_20260817_refactor.py").unlink(missing_ok=True)
(ROOT / ".github/workflows/apply-20260817-refactor.yml").unlink(missing_ok=True)

print("RPO 2026-08-17 refactor applied")
