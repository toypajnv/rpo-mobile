from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Missing replacement anchor: {label}")
    return text.replace(old, new, 1)


# ----- Form rules: real readiness + Cyrillic-only manual text entry -----
form_rules = '''package ru.rpo.mobile.ui

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.format.DateTimeFormatter

internal val rpoDateFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy")
internal val rpoTimeFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("HH:mm")
internal val rpoDateTimeFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm")

private val latinLetterRegex = Regex("[A-Za-z]")

data class OperationalDateTimeResult(val value: LocalDateTime?, val error: String?)

fun containsLatinLetters(value: String): Boolean = latinLetterRegex.containsMatchIn(value)

fun removeLatinLetters(value: String): String = value.filterNot { it in 'A'..'Z' || it in 'a'..'z' }

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
}
'''
write("android/app/src/main/java/ru/rpo/mobile/ui/FormRules.kt", form_rules)


# ----- ViewModel: reject Latin letters in all manually entered text -----
vm = read("android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt")
vm = replace_once(
    vm,
    'private val permitRegex = Regex("^[0-9A-ZА-ЯЁ._/\\\\- ]{3,80}$")\nprivate val permitCharRegex = Regex("[0-9A-ZА-ЯЁ._/\\\\- ]")',
    'private val permitRegex = Regex("^[0-9А-ЯЁ._/\\\\- ]{3,80}$")\nprivate val permitCharRegex = Regex("[0-9А-ЯЁ._/\\\\- ]")',
    "Cyrillic permit regex",
)
vm = replace_once(
    vm,
    '            workerName = prefs.getString("worker_name", "") ?: "",',
    '            workerName = removeLatinLetters(prefs.getString("worker_name", "") ?: ""),',
    "sanitize remembered worker",
)
vm = replace_once(
    vm,
    '        val commonComment = stageFields.firstOrNull { it.comment.isNotBlank() }?.comment.orEmpty()',
    '        val commonComment = removeLatinLetters(stageFields.firstOrNull { it.comment.isNotBlank() }?.comment.orEmpty())',
    "sanitize prefilled comment",
)
vm = replace_once(
    vm,
    '            stopReason = if (stage.kind == StageKind.STOP) snapshot.fields[stage.first.key]?.comment.orEmpty() else "",',
    '            stopReason = if (stage.kind == StageKind.STOP) removeLatinLetters(snapshot.fields[stage.first.key]?.comment.orEmpty()) else "",',
    "sanitize prefilled stop reason",
)
vm = replace_once(
    vm,
    '                    val worker = snapshot.worker_name.ifBlank { _state.value.workerName }',
    '                    val worker = removeLatinLetters(snapshot.worker_name).ifBlank { removeLatinLetters(_state.value.workerName) }',
    "sanitize server worker",
)
vm = replace_once(
    vm,
    '        val worker = memory.workerName.ifBlank { _state.value.workerName }\n        _state.value = blankStageFields(_state.value).copy(\n            permitNumber = memory.permitNumber,',
    '        val worker = removeLatinLetters(memory.workerName).ifBlank { removeLatinLetters(_state.value.workerName) }\n        val permit = removeLatinLetters(memory.permitNumber).uppercase()\n        _state.value = blankStageFields(_state.value).copy(\n            permitNumber = permit,',
    "sanitize selected memory",
)
vm = replace_once(
    vm,
    '        schedulePermitLookup(memory.permitNumber, immediate = true)',
    '        schedulePermitLookup(permit, immediate = true)',
    "lookup sanitized memory",
)
old_updates = '''    fun updateWorker(v: String) {
        _state.value = _state.value.copy(workerName = v.take(180), message = null)
        prefs.edit().putString("worker_name", v.take(180)).apply()
    }

    fun updatePermit(v: String) {
        val value = v.uppercase().take(80)
        val hasInvalidChar = value.any { !permitCharRegex.matches(it.toString()) }
        val errors = _state.value.errors.toMutableMap()
        if (hasInvalidChar) errors["permit"] = "Допустимы только буквы, цифры, пробел и символы . _ / -"
        else errors.remove("permit")
        serverPermitSnapshot = null
        _state.value = blankStageFields(_state.value).copy(
            permitNumber = value,
            errors = errors,
            serverSavedStageIds = emptySet(),
            message = null,
        )
        schedulePermitLookup(value)
    }
'''
new_updates = '''    fun updateWorker(v: String) {
        val rejectedLatin = containsLatinLetters(v)
        val value = removeLatinLetters(v).take(180)
        val errors = _state.value.errors.toMutableMap()
        if (rejectedLatin) errors["worker"] = "Используйте русскую раскладку: латинские буквы не принимаются"
        else errors.remove("worker")
        _state.value = _state.value.copy(workerName = value, errors = errors, message = null)
        prefs.edit().putString("worker_name", value).apply()
    }

    fun updatePermit(v: String) {
        val rejectedLatin = containsLatinLetters(v)
        val value = removeLatinLetters(v).uppercase().take(80)
        val hasInvalidChar = value.any { !permitCharRegex.matches(it.toString()) }
        val errors = _state.value.errors.toMutableMap()
        when {
            rejectedLatin -> errors["permit"] = "Используйте русскую раскладку: латинские буквы не принимаются"
            hasInvalidChar -> errors["permit"] = "Допустимы только русские буквы, цифры, пробел и символы . _ / -"
            else -> errors.remove("permit")
        }
        serverPermitSnapshot = null
        _state.value = blankStageFields(_state.value).copy(
            permitNumber = value,
            errors = errors,
            serverSavedStageIds = emptySet(),
            message = null,
        )
        if (!rejectedLatin) schedulePermitLookup(value)
    }
'''
vm = replace_once(vm, old_updates, new_updates, "worker and permit input handlers")
vm = replace_once(
    vm,
    '    fun updateStopReason(v: String) { _state.value = _state.value.copy(stopReason = v.take(500), message = null) }\n    fun updateComment(v: String) { _state.value = _state.value.copy(comment = v.take(500), message = null) }',
    '''    fun updateStopReason(v: String) {
        val rejectedLatin = containsLatinLetters(v)
        val value = removeLatinLetters(v).take(500)
        val errors = _state.value.errors.toMutableMap()
        if (rejectedLatin) errors["stopReason"] = "Используйте русскую раскладку: латинские буквы не принимаются"
        else errors.remove("stopReason")
        _state.value = _state.value.copy(stopReason = value, errors = errors, message = null)
    }

    fun updateComment(v: String) {
        val rejectedLatin = containsLatinLetters(v)
        val value = removeLatinLetters(v).take(500)
        val errors = _state.value.errors.toMutableMap()
        if (rejectedLatin) errors["comment"] = "Используйте русскую раскладку: латинские буквы не принимаются"
        else errors.remove("comment")
        _state.value = _state.value.copy(comment = value, errors = errors, message = null)
    }''',
    "comment input handlers",
)
write("android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt", vm)


# ----- UI: robust narrow-screen date/time layout + truthful readiness check -----
ui = read("android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt")
ui = replace_once(
    ui,
    '                CheckLine(s.errors.keys.none { it in setOf("primary", "secondary", "third", "extension", "stopReason", "comment") }, "Данные этапа заполнены")',
    '                CheckLine(stageDataReady(s), "Обязательные поля этапа заполнены")',
    "real stage readiness checklist",
)
ui = replace_once(
    ui,
    '            Text(value.ifBlank { "Выберите дату" }, Modifier.weight(1f), color = if (value.isBlank()) Color.Gray else Color.Unspecified)',
    '            Text(\n                value.ifBlank { "Выберите дату" },\n                Modifier.weight(1f),\n                color = if (value.isBlank()) Color.Gray else Color.Unspecified,\n                maxLines = 1,\n                softWrap = false,\n            )',
    "single-line date label",
)
old_datetime = '''        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
            Box(Modifier.weight(1f)) { DateField(date, onDate, error) }
            Box(Modifier.weight(.72f)) { Field(null, time, onTime, "ЧЧ:ММ", null) }
            OutlinedButton(onClick = onNow, modifier = Modifier.height(56.dp)) {
                Icon(Icons.Default.Schedule, null)
                Spacer(Modifier.width(4.dp))
                Text("Сейчас")
            }
        }'''
new_datetime = '''        DateField(date, onDate, error)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
            Box(Modifier.weight(1f)) { Field(null, time, onTime, "ЧЧ:ММ", null) }
            OutlinedButton(
                onClick = onNow,
                modifier = Modifier.weight(1f).height(56.dp),
                contentPadding = PaddingValues(horizontal = 10.dp),
            ) {
                Icon(Icons.Default.Schedule, null)
                Spacer(Modifier.width(5.dp))
                Text("Сейчас", maxLines = 1, softWrap = false)
            }
        }'''
ui = replace_once(ui, old_datetime, new_datetime, "narrow-screen date/time layout")
old_extension = '''                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
                    Box(Modifier.weight(1f)) {
                        DateField(s.extensionDate, vm::updateExtensionDate, s.errors["extension"])
                    }
                    OutlinedButton(onClick = vm::extensionTomorrow, modifier = Modifier.height(56.dp)) {
                        Icon(Icons.Default.Event, null)
                        Spacer(Modifier.width(5.dp))
                        Text("Завтра")
                    }
                }'''
new_extension = '''                DateField(s.extensionDate, vm::updateExtensionDate, s.errors["extension"])
                OutlinedButton(
                    onClick = vm::extensionTomorrow,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                ) {
                    Icon(Icons.Default.Event, null)
                    Spacer(Modifier.width(5.dp))
                    Text("Выбрать завтра", maxLines = 1)
                }'''
ui = replace_once(ui, old_extension, new_extension, "extension date layout")
ui = replace_once(
    ui,
    '                "1. Укажите ФИО — приложение запомнит его на этом устройстве.\\n\\n" +',
    '                "1. Укажите ФИО русскими буквами — латиница в полях ввода не принимается. Приложение запомнит ФИО на этом устройстве.\\n\\n" +',
    "help Russian input note",
)
write("android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt", ui)


# ----- Tests -----
tests = read("android/app/src/test/java/ru/rpo/mobile/ui/FormRulesTest.kt")
tests = replace_once(tests, "import org.junit.Assert.assertEquals\n", "import org.junit.Assert.assertEquals\nimport org.junit.Assert.assertFalse\n", "assertFalse import")
insert = '''
    @Test
    fun blankStageIsNotMarkedReady() {
        assertFalse(stageDataReady(FormState()))
    }

    @Test
    fun preparationIsReadyOnlyAfterBothDateTimesAreFilled() {
        val incomplete = FormState(primaryDate = "19.08.2026", primaryTime = "10:00")
        assertFalse(stageDataReady(incomplete))
        val complete = incomplete.copy(secondaryDate = "19.08.2026", secondaryTime = "11:00")
        assertTrue(stageDataReady(complete))
    }

    @Test
    fun resumeReadinessRequiresComment() {
        val resume = stages.first { it.id == "RESUME_WORK" }
        val base = FormState(stage = resume, primaryDate = "19.08.2026", primaryTime = "10:00")
        assertFalse(stageDataReady(base))
        assertTrue(stageDataReady(base.copy(comment = "Работы разрешено возобновить")))
    }

    @Test
    fun latinLettersAreRejectedFromManualText() {
        assertTrue(containsLatinLetters("Ivanov"))
        assertFalse(containsLatinLetters("Иванов И.И."))
        assertEquals("Иванов ", removeLatinLetters("Иванов Ivanov"))
        assertEquals("666666-СН", removeLatinLetters("666666-СНAB"))
    }
'''
tests = replace_once(tests, "\n    @Test\n    fun serverFieldsMapToCompletedUserStages()", insert + "\n    @Test\n    fun serverFieldsMapToCompletedUserStages()", "new form tests")
write("android/app/src/test/java/ru/rpo/mobile/ui/FormRulesTest.kt", tests)


# ----- Version -----
gradle = read("android/app/build.gradle.kts")
gradle = replace_once(gradle, '        versionCode = 6\n        versionName = "1.1.3"', '        versionCode = 7\n        versionName = "1.1.4"', "version 1.1.4")
write("android/app/build.gradle.kts", gradle)

# Remove one-shot patch machinery from the resulting code commit.
for rel in ["ops/apply_20260819_mobile_ui.py", ".github/workflows/apply-20260819-mobile-ui.yml"]:
    p = ROOT / rel
    if p.exists():
        p.unlink()
