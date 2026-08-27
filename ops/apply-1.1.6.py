from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"Pattern not found in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# Android UI: keep IME open under permit suggestions, restore calendar/time pickers,
# and make the second date/time in range stages optional.
replace_once(
    "android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt",
    "import android.app.DatePickerDialog\nimport android.content.Context\n",
    "import android.app.DatePickerDialog\nimport android.content.Context\nimport android.view.Gravity\nimport android.widget.LinearLayout\nimport android.widget.NumberPicker\n",
)
replace_once(
    "android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt",
    "import androidx.compose.ui.unit.sp\nimport androidx.lifecycle.viewmodel.compose.viewModel\nimport java.time.LocalDate\nimport java.time.format.DateTimeFormatter\n",
    "import androidx.compose.ui.unit.sp\nimport androidx.compose.ui.window.PopupProperties\nimport androidx.lifecycle.viewmodel.compose.viewModel\nimport java.time.LocalDate\nimport java.time.LocalTime\nimport java.time.format.DateTimeFormatter\n",
)
replace_once(
    "android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt",
    """            DropdownMenu(\n                expanded = expanded && suggestions.isNotEmpty(),\n                onDismissRequest = { expanded = false },\n                modifier = Modifier.fillMaxWidth(.92f),\n            ) {""",
    """            DropdownMenu(\n                expanded = expanded && suggestions.isNotEmpty(),\n                onDismissRequest = { expanded = false },\n                modifier = Modifier.fillMaxWidth(.92f),\n                properties = PopupProperties(focusable = false),\n            ) {""",
)
replace_once(
    "android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt",
    "title = requireNotNull(s.stage.second).title,",
    "title = requireNotNull(s.stage.second).title + \" (можно заполнить позже)\",",
)
replace_once(
    "android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt",
    """        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {\n            Box(Modifier.weight(1f)) { Field(null, time, onTime, \"ЧЧ:ММ\", null) }\n            OutlinedButton(""",
    """        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {\n            Box(Modifier.weight(1f)) { TimeField(time, onTime) }\n            OutlinedButton(""",
)
replace_once(
    "android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt",
    """@Composable\nprivate fun DateTimeBlock(""",
    """private fun showTimeSpinner(context: Context, value: String, onTime: (String) -> Unit) {\n    val initial = runCatching { LocalTime.parse(value, DateTimeFormatter.ofPattern(\"HH:mm\")) }\n        .getOrElse { LocalTime.now() }\n    val hours = NumberPicker(context).apply {\n        minValue = 0\n        maxValue = 23\n        this.value = initial.hour\n        wrapSelectorWheel = true\n        setFormatter { String.format(\"%02d\", it) }\n    }\n    val minutes = NumberPicker(context).apply {\n        minValue = 0\n        maxValue = 59\n        this.value = initial.minute\n        wrapSelectorWheel = true\n        setFormatter { String.format(\"%02d\", it) }\n    }\n    val density = context.resources.displayMetrics.density\n    val pad = (16 * density).toInt()\n    val container = LinearLayout(context).apply {\n        orientation = LinearLayout.HORIZONTAL\n        gravity = Gravity.CENTER\n        setPadding(pad, 0, pad, 0)\n        addView(hours, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))\n        addView(minutes, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))\n    }\n    android.app.AlertDialog.Builder(context)\n        .setTitle(\"Выберите время\")\n        .setView(container)\n        .setNegativeButton(\"Отмена\", null)\n        .setPositiveButton(\"Выбрать\") { _, _ ->\n            onTime(String.format(\"%02d:%02d\", hours.value, minutes.value))\n        }\n        .show()\n}\n\n@Composable\nprivate fun TimeField(value: String, onTime: (String) -> Unit) {\n    val context = LocalContext.current\n    OutlinedButton(\n        onClick = { showTimeSpinner(context, value, onTime) },\n        modifier = Modifier.fillMaxWidth().height(56.dp),\n        shape = RoundedCornerShape(11.dp),\n        contentPadding = PaddingValues(horizontal = 12.dp),\n    ) {\n        Text(\n            value.ifBlank { \"Выберите время\" },\n            Modifier.weight(1f),\n            color = if (value.isBlank()) Color.Gray else Color.Unspecified,\n            maxLines = 1,\n            softWrap = false,\n        )\n        Icon(Icons.Default.Schedule, \"Открыть выбор времени\")\n    }\n}\n\n@Composable\nprivate fun DateTimeBlock(""",
)
replace_once(
    "android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt",
    "5. Дату выбирайте из календаря, время вводите вручную или кнопкой «Сейчас». Для остановки обязательна причина, а для возобновления — комментарий. Для продления РПО укажите новую дату окончания.",
    "5. Дату выбирайте из календаря, время — прокруткой часов и минут или кнопкой «Сейчас». Для подготовки и фактических работ можно сначала передать только начало, а окончание заполнить позже. Для остановки обязательна причина, а для возобновления — комментарий. Для продления РПО укажите новую дату окончания.",
)

# Range stages: start is sufficient; an end, when entered, must be complete and not precede the start.
replace_once(
    "android/app/src/main/java/ru/rpo/mobile/ui/FormRules.kt",
    """    StageKind.RANGE_DATETIME -> {\n        val start = parseFilledDateTime(state.primaryDate, state.primaryTime)\n        val end = parseFilledDateTime(state.secondaryDate, state.secondaryTime)\n        start != null && end != null && !end.isBefore(start)\n    }""",
    """    StageKind.RANGE_DATETIME -> {\n        val start = parseFilledDateTime(state.primaryDate, state.primaryTime)\n        val endBlank = state.secondaryDate.isBlank() && state.secondaryTime.isBlank()\n        val endComplete = state.secondaryDate.isNotBlank() && state.secondaryTime.isNotBlank()\n        val end = if (endComplete) parseFilledDateTime(state.secondaryDate, state.secondaryTime) else null\n        start != null && (endBlank || (end != null && !end.isBefore(start)))\n    }""",
)
replace_once(
    "android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt",
    """            StageKind.RANGE_DATETIME -> {\n                val start = parseDateTime(s.primaryDate, s.primaryTime, \"primary\", errors)\n                val end = parseDateTime(s.secondaryDate, s.secondaryTime, \"secondary\", errors)\n                if (start != null && end != null && end.isBefore(start)) errors[\"secondary\"] = \"Окончание не может быть раньше начала\"\n                if (start != null && end != null && !end.isBefore(start) && errors[\"primary\"] == null && errors[\"secondary\"] == null) {\n                    events += PendingEvent(s.stage.first, start, start.format(valueFmt), s.comment.trim())\n                    events += PendingEvent(requireNotNull(s.stage.second), end, end.format(valueFmt), s.comment.trim())\n                }\n            }""",
    """            StageKind.RANGE_DATETIME -> {\n                val start = parseDateTime(s.primaryDate, s.primaryTime, \"primary\", errors)\n                val endDateSet = s.secondaryDate.isNotBlank()\n                val endTimeSet = s.secondaryTime.isNotBlank()\n                val end = when {\n                    !endDateSet && !endTimeSet -> null\n                    endDateSet && endTimeSet -> parseDateTime(s.secondaryDate, s.secondaryTime, \"secondary\", errors)\n                    else -> {\n                        errors[\"secondary\"] = \"Укажите дату и время окончания полностью или оставьте оба поля пустыми\"\n                        null\n                    }\n                }\n                if (start != null && end != null && end.isBefore(start)) errors[\"secondary\"] = \"Окончание не может быть раньше начала\"\n                if (start != null && errors[\"primary\"] == null) {\n                    events += PendingEvent(s.stage.first, start, start.format(valueFmt), s.comment.trim())\n                }\n                if (end != null && start != null && !end.isBefore(start) && errors[\"secondary\"] == null) {\n                    events += PendingEvent(requireNotNull(s.stage.second), end, end.format(valueFmt), s.comment.trim())\n                }\n            }""",
)
replace_once(
    "android/app/src/main/java/ru/rpo/mobile/ui/Stages.kt",
    """fun savedStageIdsForFieldKeys(fieldKeys: Set<String>): Set<String> = stages\n    .filter { stage -> listOfNotNull(stage.first.key, stage.second?.key, stage.third?.key).all { it in fieldKeys } }\n    .map { it.id }\n    .toSet()""",
    """fun savedStageIdsForFieldKeys(fieldKeys: Set<String>): Set<String> = stages\n    .filter { stage ->\n        val keys = listOfNotNull(stage.first.key, stage.second?.key, stage.third?.key)\n        if (stage.kind == StageKind.RANGE_DATETIME) stage.first.key in fieldKeys else keys.all { it in fieldKeys }\n    }\n    .map { it.id }\n    .toSet()""",
)

# Tests for the new partial-range rule.
replace_once(
    "android/app/src/test/java/ru/rpo/mobile/ui/FormRulesTest.kt",
    """    @Test\n    fun preparationIsReadyOnlyAfterBothDateTimesAreFilled() {\n        val incomplete = FormState(primaryDate = \"19.08.2026\", primaryTime = \"10:00\")\n        assertFalse(stageDataReady(incomplete))\n        val complete = incomplete.copy(secondaryDate = \"19.08.2026\", secondaryTime = \"11:00\")\n        assertTrue(stageDataReady(complete))\n    }""",
    """    @Test\n    fun preparationCanBeSavedWithStartOnlyAndValidOptionalEnd() {\n        val startOnly = FormState(primaryDate = \"19.08.2026\", primaryTime = \"10:00\")\n        assertTrue(stageDataReady(startOnly))\n        assertFalse(stageDataReady(startOnly.copy(secondaryDate = \"19.08.2026\")))\n        assertFalse(stageDataReady(startOnly.copy(secondaryDate = \"19.08.2026\", secondaryTime = \"09:59\")))\n        assertTrue(stageDataReady(startOnly.copy(secondaryDate = \"19.08.2026\", secondaryTime = \"11:00\")))\n    }""",
)
replace_once(
    "android/app/src/test/java/ru/rpo/mobile/ui/FormRulesTest.kt",
    """        val ids = savedStageIdsForFieldKeys(setOf(\"AT\", \"AU\", \"AV\", \"AY\", \"BC\", \"BE\"))\n        assertTrue(\"PREPARATION\" in ids)\n        assertTrue(\"TRANSFER_WORK\" in ids)\n        assertTrue(\"ACTUAL_WORK\" in ids)\n        assertTrue(\"EXTEND_WORK\" in ids)""",
    """        val ids = savedStageIdsForFieldKeys(setOf(\"AT\", \"AV\", \"AY\", \"BE\"))\n        assertTrue(\"PREPARATION\" in ids)\n        assertTrue(\"TRANSFER_WORK\" in ids)\n        assertTrue(\"ACTUAL_WORK\" in ids)\n        assertTrue(\"EXTEND_WORK\" in ids)""",
)

# Version and server feedback.
replace_once("android/app/build.gradle.kts", "versionCode = 8", "versionCode = 9")
replace_once("android/app/build.gradle.kts", "versionName = \"1.1.5\"", "versionName = \"1.1.6\"")
replace_once("server/app/main.py", "LATEST_MOBILE_VERSION = \"1.1.5\"", "LATEST_MOBILE_VERSION = \"1.1.6\"")
replace_once(
    "server/app/main.py",
    "MOBILE_APK_URL = \"https://github.com/toypajnv/rpo-mobile/releases/download/v1.1.5-test/rpo-mobile-1.1.5.apk\"",
    "MOBILE_APK_URL = \"https://github.com/toypajnv/rpo-mobile/releases/download/v1.1.6-test/rpo-mobile-1.1.6.apk\"",
)
replace_once("server/app/main.py", "version=\"0.4.0\"", "version=\"0.4.1\"")
replace_all(".github/workflows/production-smoke.yml", "1.1.5", "1.1.6")

print("RPO 1.1.6 patch applied")
