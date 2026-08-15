package ru.rpo.mobile.ui

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
        id = "START_WORK",
        title = "Передача и начало работ",
        kind = StageKind.TRIPLE_DATETIME,
        first = StageEvent("AV", "Передача ОП к ОБПР"),
        second = StageEvent("AY", "Фактическое начало работ"),
        third = StageEvent("BC", "Окончание работ"),
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

fun shouldWarnBeforeStageSwitch(current: Stage, target: Stage, hasUnsavedChanges: Boolean): Boolean =
    current.id != target.id && hasUnsavedChanges
