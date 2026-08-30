package ru.rpo.mobile.ui

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

/** A grouped stage is complete only when every event that belongs to it exists on the server. */
fun savedStageIdsForFieldKeys(fieldKeys: Set<String>): Set<String> = stages
    .filter { stage ->
        val keys = listOfNotNull(stage.first.key, stage.second?.key, stage.third?.key)
        keys.all { it in fieldKeys }
    }
    .map { it.id }
    .toSet()

fun shouldWarnBeforeStageSwitch(current: Stage, target: Stage, hasUnsavedChanges: Boolean): Boolean =
    current.id != target.id && hasUnsavedChanges
