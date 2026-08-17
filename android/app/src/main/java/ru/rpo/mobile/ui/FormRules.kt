package ru.rpo.mobile.ui

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
