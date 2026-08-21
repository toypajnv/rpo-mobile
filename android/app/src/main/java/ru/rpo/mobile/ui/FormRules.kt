package ru.rpo.mobile.ui

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
    .joinToString("
") { "${it.name}	${it.position}" }

fun decodeReplacements(value: String): List<ReplacementEntry> {
    val parsed = value.lines().mapNotNull { line ->
        val parts = line.split('	', limit = 2)
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
