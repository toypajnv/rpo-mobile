package ru.rpo.mobile.ui

enum class StageKind { DATETIME, TEXT }
data class Stage(val key: String, val title: String, val kind: StageKind = StageKind.DATETIME, val commentRequired: Boolean = false)

val stages = listOf(
    Stage("AT", "Начало подготовки"),
    Stage("AU", "Окончание подготовки"),
    Stage("AV", "Передача ОП к ОБПР"),
    Stage("AX", "Допуск со стороны допускающего"),
    Stage("AY", "Фактическое начало работ"),
    Stage("AZ", "Остановка работ", commentRequired = true),
    Stage("BA", "Возобновление работ"),
    Stage("BC", "Фактическое завершение РПО"),
    Stage("BD", "Мероприятия по завершению"),
    Stage("BE", "Продление РПО", kind = StageKind.TEXT),
    Stage("BF", "Передача объекта"),
    Stage("BG", "Закрытие ЭНД", kind = StageKind.TEXT),
    Stage("BH", "Передача площадки эксплуатирующей организации"),
)
