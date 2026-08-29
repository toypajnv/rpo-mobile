package ru.rpo.mobile.ui

val structuralUnits = listOf(
    "ЦДПН-1",
    "ЦДПН-2",
    "ЦДПН-3",
    "ЦДПН-4",
    "ЦППН-1",
    "ЦППН-2",
    "ЦСДиТГ",
    "ЦСиР",
    "ЦТОиРТ-1",
    "ЦТОиРТ-2",
)

fun structuralUnitError(value: String): String? =
    if (value in structuralUnits) null else "Выберите структурное подразделение"

fun approvalStatusLabel(status: String): String = when (status) {
    "pending" -> "Ожидает разрешения оператора"
    "approved" -> "Работы можно проводить"
    "not_required" -> "Разрешение не требуется"
    else -> "Статус разрешения пока не получен"
}
