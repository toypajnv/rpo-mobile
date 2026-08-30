package ru.rpo.mobile.ui

/**
 * Small pure helpers used by the 2.1 UX shell. Keeping the rules out of Compose
 * makes the wording and recommended next action easy to regression-test.
 */
fun recommendedStage(savedStageIds: Set<String>, approvalStatus: String?): Stage? {
    if (approvalStatus == "stopped") {
        return stages.firstOrNull { it.id == "RESUME_WORK" }
    }
    return requiredStages.firstOrNull { it.id !in savedStageIds }
}

fun contextualActionLabel(state: FormState): String = when (state.stage.id) {
    "PREPARATION" -> when {
        state.primaryDate.isBlank() || state.primaryTime.isBlank() -> "Передать начало подготовки"
        state.secondaryDate.isBlank() && state.secondaryTime.isBlank() -> "Передать окончание подготовки"
        else -> "Передать изменения подготовки"
    }
    "TRANSFER_WORK" -> "Передать объект"
    "ACTUAL_WORK" -> when {
        state.primaryDate.isBlank() || state.primaryTime.isBlank() -> "Передать фактическое начало"
        state.secondaryDate.isBlank() && state.secondaryTime.isBlank() -> "Передать фактическое окончание"
        else -> "Передать изменения по работам"
    }
    "STOP_WORK" -> "Передать остановку работ"
    "RESUME_WORK" -> "Передать возобновление работ"
    "EXTEND_WORK" -> "Передать продление РПО"
    "REPLACEMENTS" -> "Передать замену исполнителей"
    else -> "Передать данные этапа"
}

fun stageReadinessHint(state: FormState): String? {
    if (state.workerName.trim().length < 3) return "Укажите ФИО ответственного"
    if (state.structuralUnit !in structuralUnits) return "Выберите структурное подразделение"
    if (state.permitNumber.trim().length < 3 || state.errors["permit"] != null) return "Укажите корректный номер НД"

    return when (state.stage.kind) {
        StageKind.RANGE_DATETIME -> when {
            state.primaryDate.isBlank() -> "Выберите дату начала"
            state.primaryTime.isBlank() -> "Выберите время начала"
            state.secondaryDate.isNotBlank() && state.secondaryTime.isBlank() -> "Укажите время окончания или очистите дату"
            state.secondaryDate.isBlank() && state.secondaryTime.isNotBlank() -> "Укажите дату окончания или очистите время"
            !stageDataReady(state) -> "Проверьте последовательность даты и времени"
            else -> null
        }
        StageKind.TRIPLE_DATETIME -> if (stageDataReady(state)) null else "Заполните все даты и время этапа"
        StageKind.DATETIME -> when {
            state.primaryDate.isBlank() -> "Выберите дату"
            state.primaryTime.isBlank() -> "Выберите время"
            state.stage.id == "RESUME_WORK" && state.comment.trim().length < 3 -> "Добавьте комментарий к возобновлению"
            !stageDataReady(state) -> "Проверьте дату и время"
            else -> null
        }
        StageKind.STOP -> when {
            state.primaryDate.isBlank() || state.primaryTime.isBlank() -> "Укажите дату и время остановки"
            state.stopReason.trim().length < 3 -> "Укажите причину остановки"
            else -> null
        }
        StageKind.EXTENSION_DATE -> if (state.extensionDate.isBlank()) "Выберите новую дату окончания" else if (!stageDataReady(state)) "Проверьте дату продления" else null
        StageKind.REPLACEMENTS -> if (stageDataReady(state)) null else "Укажите ФИО и должность / профессию исполнителя"
    }
}

fun stageProgressLabel(stage: Stage, savedStageIds: Set<String>, selected: Boolean): String = when {
    stage.id in savedStageIds -> "Передано"
    selected -> "Текущий этап"
    stage.optional -> "Необязательно"
    else -> "Не заполнено"
}
