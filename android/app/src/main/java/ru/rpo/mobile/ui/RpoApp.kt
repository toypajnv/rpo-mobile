package ru.rpo.mobile.ui

import android.app.DatePickerDialog
import android.content.Context
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.NumberPicker
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.PopupProperties
import androidx.lifecycle.viewmodel.compose.viewModel
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter

private val Navy = Color(0xFF073C77)
private val Blue = Color(0xFF0D63E6)
private val Bg = Color(0xFFF4F7FB)
private val Green = Color(0xFF1B9E50)
private val Red = Color(0xFFD73535)
private val Orange = Color(0xFFE98B00)

enum class Tab { FORM, HISTORY, HELP }

private fun stageMemoryKey(permitNumber: String): String =
    "saved_stages_${permitNumber.trim().uppercase()}"

private fun loadSavedStageIds(context: Context, permitNumber: String): Set<String> {
    val permit = permitNumber.trim().uppercase()
    if (permit.length < 3) return emptySet()
    val prefs = context.getSharedPreferences("rpo", Context.MODE_PRIVATE)
    return prefs.getStringSet(stageMemoryKey(permit), emptySet())?.toSet().orEmpty()
}

private fun persistSavedStageIds(context: Context, permitNumber: String, ids: Set<String>) {
    val permit = permitNumber.trim().uppercase()
    if (permit.length < 3) return
    context.getSharedPreferences("rpo", Context.MODE_PRIVATE)
        .edit()
        .putStringSet(stageMemoryKey(permit), ids.toSet())
        .apply()
}

private fun stageFingerprint(s: FormState): String = listOf(
    s.stage.id,
    s.primaryDate,
    s.primaryTime,
    s.secondaryDate,
    s.secondaryTime,
    s.thirdDate,
    s.thirdTime,
    s.extensionDate,
    s.stopReason,
    s.comment,
    s.replacements.joinToString("~") { "${it.name}:${it.position}" },
).joinToString("|")

@Composable
fun RpoApp(vm: RpoViewModel = viewModel()) {
    val state by vm.state.collectAsState()
    val history by vm.history.collectAsState()
    val permitMemories by vm.permitMemories.collectAsState()
    var tab by remember { mutableStateOf(Tab.FORM) }

    LaunchedEffect(tab) { if (tab == Tab.HISTORY) vm.loadHistory() }

    MaterialTheme(colorScheme = lightColorScheme(primary = Blue, background = Bg, error = Red)) {
        Scaffold(
            containerColor = Bg,
            bottomBar = {
                NavigationBar(containerColor = Color.White) {
                    NavigationBarItem(tab == Tab.FORM, { tab = Tab.FORM }, { Icon(Icons.Default.Assignment, "Форма") }, label = { Text("Форма") })
                    NavigationBarItem(tab == Tab.HISTORY, { tab = Tab.HISTORY }, { Icon(Icons.Default.History, "История") }, label = { Text("История") })
                    NavigationBarItem(tab == Tab.HELP, { tab = Tab.HELP }, { Icon(Icons.Default.HelpOutline, "Справка") }, label = { Text("Справка") })
                }
            },
        ) { pad ->
            Column(Modifier.padding(pad).fillMaxSize()) {
                Header()
                when (tab) {
                    Tab.FORM -> FormScreen(state, permitMemories, vm)
                    Tab.HISTORY -> HistoryScreen(history)
                    Tab.HELP -> HelpScreen()
                }
            }
        }
    }
}

@Composable
private fun Header() {
    Box(Modifier.fillMaxWidth().background(Navy).padding(horizontal = 16.dp, vertical = 14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.HealthAndSafety, null, tint = Color.White, modifier = Modifier.size(34.dp))
            Spacer(Modifier.width(10.dp))
            Column {
                Text("РПО", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Bold)
                Text("Работы повышенной опасности", color = Color.White.copy(alpha = .82f), fontSize = 12.sp)
            }
            Spacer(Modifier.weight(1f))
            Surface(color = Color(0xFF14734C), shape = RoundedCornerShape(50)) {
                Text(
                    "● Без входа",
                    Modifier.padding(horizontal = 7.dp, vertical = 4.dp),
                    color = Color.White,
                    fontSize = 9.sp,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }
    }
}

@Composable
private fun FormScreen(s: FormState, permitMemories: List<PermitMemory>, vm: RpoViewModel) {
    val context = LocalContext.current
    val permitKey = s.permitNumber.trim().uppercase()
    var savedStageIds by remember(permitKey) { mutableStateOf(loadSavedStageIds(context, permitKey)) }
    val combinedSavedStageIds = savedStageIds + s.serverSavedStageIds
    var pendingStage by remember(permitKey) { mutableStateOf<Stage?>(null) }
    var baseline by remember(permitKey, s.stage.id, s.serverSavedStageIds) { mutableStateOf(stageFingerprint(s)) }
    val currentFingerprint = stageFingerprint(s)
    val hasUnsavedChanges = currentFingerprint != baseline

    LaunchedEffect(s.workerName) {
        val cleaned = removeLatinLetters(s.workerName)
        if (cleaned != s.workerName) vm.updateWorker(cleaned)
    }
    LaunchedEffect(s.permitNumber) {
        val cleaned = removeLatinLetters(s.permitNumber)
        if (cleaned != s.permitNumber) vm.updatePermit(cleaned)
    }

    pendingStage?.let { target ->
        AlertDialog(
            onDismissRequest = { pendingStage = null },
            icon = { Icon(Icons.Default.Warning, null, tint = Orange) },
            title = { Text("Текущий этап не сохранён") },
            text = {
                Text(
                    "В этапе «${s.stage.title}» есть изменения. Если переключиться сейчас, они будут сброшены. " +
                        "Нажмите «Остаться и сохранить», затем кнопку «Сохранить этап»."
                )
            },
            confirmButton = {
                TextButton(onClick = { pendingStage = null }) {
                    Text("Остаться и сохранить", fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        pendingStage = null
                        vm.updateStage(target)
                    }
                ) {
                    Text("Переключиться без сохранения", color = Red)
                }
            },
        )
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(13.dp),
    ) {
        if (s.message != null) {
            Surface(
                color = if (s.success) Color(0xFFE9F8EE) else Color(0xFFFFF2E2),
                shape = RoundedCornerShape(12.dp),
            ) {
                Row(Modifier.padding(13.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        if (s.success) Icons.Default.CheckCircle else Icons.Default.Warning,
                        null,
                        tint = if (s.success) Green else Orange,
                    )
                    Spacer(Modifier.width(9.dp))
                    Text(s.message, fontWeight = FontWeight.SemiBold)
                }
            }
        }

        s.systemNotice?.let { notice ->
            Surface(
                color = if (notice.maintenance) Color(0xFFFFF1ED) else Color(0xFFEAF3FF),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Row(Modifier.padding(12.dp), verticalAlignment = Alignment.Top) {
                    Icon(
                        if (notice.maintenance) Icons.Default.Warning else Icons.Default.CloudDone,
                        null,
                        tint = if (notice.maintenance) Red else Blue,
                    )
                    Spacer(Modifier.width(9.dp))
                    Column {
                        Text(notice.message, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                        if (notice.update_available) {
                            Text(
                                "Доступно обновление ${notice.latest_app_version}. Текущая версия продолжит передавать данные.",
                                color = Blue,
                                fontSize = 11.sp,
                            )
                        }
                    }
                }
            }
        }

        if (s.pendingCount > 0 || s.failedCount > 0) {
            Surface(
                color = if (s.failedCount > 0) Color(0xFFFFF1ED) else Color(0xFFFFF7E8),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        if (s.failedCount > 0) Icons.Default.ErrorOutline else Icons.Default.CloudSync,
                        null,
                        tint = if (s.failedCount > 0) Red else Orange,
                    )
                    Spacer(Modifier.width(9.dp))
                    Column(Modifier.weight(1f)) {
                        if (s.pendingCount > 0) Text("В очереди на отправку: ${s.pendingCount}", fontWeight = FontWeight.SemiBold)
                        if (s.failedCount > 0) Text("Требуют повторной проверки: ${s.failedCount}", color = Red, fontSize = 12.sp)
                        Text("Очередь хранится на телефоне и синхронизируется автоматически.", fontSize = 11.sp, color = Color.Gray)
                    }
                    TextButton(onClick = vm::retryPending, enabled = !s.sending) { Text("Повторить") }
                }
            }
        }

        Field("ФИО работника", s.workerName, vm::updateWorker, "Например: Иванов И.И.", s.errors["worker"])
        PermitField(s.permitNumber, permitMemories, vm::updatePermit, vm::selectPermit, s.errors["permit"])
        StagePicker(
            selected = s.stage,
            savedStageIds = combinedSavedStageIds,
            hasUnsavedChanges = hasUnsavedChanges,
            onSelect = { next ->
                if (next.id != s.stage.id) {
                    if (shouldWarnBeforeStageSwitch(s.stage, next, hasUnsavedChanges)) pendingStage = next
                    else vm.updateStage(next)
                }
            },
        )

        Surface(color = Color(0xFFFFF7E8), shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
            Row(Modifier.padding(12.dp), verticalAlignment = Alignment.Top) {
                Icon(Icons.Default.Info, null, tint = Orange, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text(
                    "Каждый этап сохраняется отдельно. После заполнения нажмите «Сохранить этап». " +
                        "Сохранённые этапы отмечаются зелёной галочкой и не потеряются при переключении.",
                    fontSize = 12.sp,
                    color = Color(0xFF6F5200),
                )
            }
        }

        when (s.stage.kind) {
            StageKind.RANGE_DATETIME -> {
                DateTimeBlock(
                    title = s.stage.first.title,
                    date = s.primaryDate,
                    time = s.primaryTime,
                    onDate = vm::updatePrimaryDate,
                    onTime = vm::updatePrimaryTime,
                    onNow = vm::nowPrimary,
                    error = s.errors["primary"],
                )
                DateTimeBlock(
                    title = requireNotNull(s.stage.second).title + " (можно заполнить позже)",
                    date = s.secondaryDate,
                    time = s.secondaryTime,
                    onDate = vm::updateSecondaryDate,
                    onTime = vm::updateSecondaryTime,
                    onNow = vm::nowSecondary,
                    error = s.errors["secondary"],
                )
                Field("Комментарий (необязательно)", s.comment, vm::updateComment, "Комментарий к этапу", null, singleLine = false)
            }

            StageKind.TRIPLE_DATETIME -> {
                DateTimeBlock(
                    title = s.stage.first.title,
                    date = s.primaryDate,
                    time = s.primaryTime,
                    onDate = vm::updatePrimaryDate,
                    onTime = vm::updatePrimaryTime,
                    onNow = vm::nowPrimary,
                    error = s.errors["primary"],
                )
                DateTimeBlock(
                    title = requireNotNull(s.stage.second).title,
                    date = s.secondaryDate,
                    time = s.secondaryTime,
                    onDate = vm::updateSecondaryDate,
                    onTime = vm::updateSecondaryTime,
                    onNow = vm::nowSecondary,
                    error = s.errors["secondary"],
                )
                DateTimeBlock(
                    title = requireNotNull(s.stage.third).title,
                    date = s.thirdDate,
                    time = s.thirdTime,
                    onDate = vm::updateThirdDate,
                    onTime = vm::updateThirdTime,
                    onNow = vm::nowThird,
                    error = s.errors["third"],
                )
                Field("Комментарий (необязательно)", s.comment, vm::updateComment, "Комментарий к этапу", null, singleLine = false)
            }

            StageKind.DATETIME -> {
                DateTimeBlock(
                    title = s.stage.first.title,
                    date = s.primaryDate,
                    time = s.primaryTime,
                    onDate = vm::updatePrimaryDate,
                    onTime = vm::updatePrimaryTime,
                    onNow = vm::nowPrimary,
                    error = s.errors["primary"],
                )
                val resume = s.stage.id == "RESUME_WORK"
                Field(
                    if (resume) "Комментарий (обязательно)" else "Комментарий (необязательно)",
                    s.comment,
                    vm::updateComment,
                    if (resume) "Укажите условия или основание возобновления" else "Комментарий к этапу",
                    if (resume) s.errors["comment"] else null,
                    singleLine = false,
                )
            }

            StageKind.STOP -> {
                DateTimeBlock(
                    title = "Дата и время остановки",
                    date = s.primaryDate,
                    time = s.primaryTime,
                    onDate = vm::updatePrimaryDate,
                    onTime = vm::updatePrimaryTime,
                    onNow = vm::nowPrimary,
                    error = s.errors["primary"],
                )
                Field(
                    "Причина остановки",
                    s.stopReason,
                    vm::updateStopReason,
                    "Обязательно укажите причину",
                    s.errors["stopReason"],
                    singleLine = false,
                )
            }

            StageKind.EXTENSION_DATE -> {
                Text("Новая дата окончания работ", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                DateField(s.extensionDate, vm::updateExtensionDate, s.errors["extension"])
                OutlinedButton(
                    onClick = vm::extensionTomorrow,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                ) {
                    Icon(Icons.Default.Event, null)
                    Spacer(Modifier.width(5.dp))
                    Text("Выбрать завтра", maxLines = 1)
                }
                Field("Комментарий (необязательно)", s.comment, vm::updateComment, "Причина или примечание", null, singleLine = false)
            }

            StageKind.REPLACEMENTS -> {
                Surface(color = Color(0xFFF2F6FC), shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("Замена исполнителей работ", fontWeight = FontWeight.Bold)
                        Text(
                            "Раздел необязательный. Заполняйте его только при фактической замене исполнителей.",
                            color = Color.Gray,
                            fontSize = 12.sp,
                        )
                        s.replacements.forEachIndexed { index, item ->
                            ElevatedCard(Modifier.fillMaxWidth()) {
                                Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text("Исполнитель ${index + 1}", fontWeight = FontWeight.SemiBold)
                                        Spacer(Modifier.weight(1f))
                                        if (s.replacements.size > 1) {
                                            TextButton(onClick = { vm.removeReplacement(index) }) { Text("Удалить", color = Red) }
                                        }
                                    }
                                    Field("ФИО", item.name, { vm.updateReplacementName(index, it) }, "Например: Петров П.П.", null)
                                    Field("Должность / профессия", item.position, { vm.updateReplacementPosition(index, it) }, "Например: электромонтёр", null)
                                }
                            }
                        }
                        OutlinedButton(onClick = vm::addReplacement, modifier = Modifier.fillMaxWidth()) {
                            Icon(Icons.Default.Add, null)
                            Spacer(Modifier.width(6.dp))
                            Text("Добавить ещё исполнителя")
                        }
                        s.errors["replacements"]?.let { Text(it, color = Red, fontSize = 12.sp) }
                    }
                }
            }
        }

        Button(
            onClick = {
                if (vm.send()) {
                    val updated = combinedSavedStageIds + s.stage.id
                    savedStageIds = updated
                    persistSavedStageIds(context, permitKey, updated)
                    baseline = currentFingerprint
                }
            },
            enabled = !s.sending,
            modifier = Modifier.fillMaxWidth().height(58.dp),
            shape = RoundedCornerShape(12.dp),
        ) {
            if (s.sending) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp, color = Color.White)
            else Icon(Icons.Default.Save, null)
            Spacer(Modifier.width(8.dp))
            Text(if (s.sending) "Синхронизация..." else "Сохранить этап", fontWeight = FontWeight.Bold)
        }

        Surface(color = Color(0xFFF0F8F3), shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                CheckLine(s.workerName.trim().length >= 3, "ФИО указано")
                CheckLine(s.permitNumber.trim().length >= 3 && s.errors["permit"] == null, "Номер НД корректен")
                CheckLine(stageDataReady(s), "Обязательные поля этапа заполнены")
                CheckLine(s.stage.id in combinedSavedStageIds && !hasUnsavedChanges, "Текущий этап сохранён")
                CheckLine(true, "При отсутствии сети данные сохранятся локально")
            }
        }
        Spacer(Modifier.height(10.dp))
    }
}

@Composable
private fun PermitField(
    value: String,
    memories: List<PermitMemory>,
    onValue: (String) -> Unit,
    onSelect: (PermitMemory) -> Unit,
    error: String?,
) {
    var expanded by remember { mutableStateOf(false) }
    var latinRejected by remember { mutableStateOf(false) }
    val suggestions = remember(value, memories) {
        val query = value.trim()
        if (query.isBlank()) memories.take(6)
        else memories.filter { it.permitNumber.contains(query, ignoreCase = true) }.take(6)
    }

    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text("Номер наряда-допуска", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
        Box {
            OutlinedTextField(
                value = value,
                onValueChange = { raw ->
                    latinRejected = containsLatinLetters(raw)
                    onValue(removeLatinLetters(raw))
                    expanded = true
                },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("Например: СН-038364", maxLines = 1) },
                singleLine = true,
                isError = error != null || latinRejected,
                shape = RoundedCornerShape(11.dp),
                trailingIcon = {
                    if (memories.isNotEmpty()) {
                        IconButton(onClick = { expanded = true }) {
                            Icon(Icons.Default.History, "Ранее введённые номера")
                        }
                    }
                },
            )
            DropdownMenu(
                expanded = expanded && suggestions.isNotEmpty(),
                onDismissRequest = { expanded = false },
                modifier = Modifier.fillMaxWidth(.92f),
                properties = PopupProperties(focusable = false),
            ) {
                suggestions.forEach { memory ->
                    DropdownMenuItem(
                        text = {
                            Column {
                                Text(memory.permitNumber, fontWeight = FontWeight.SemiBold)
                                if (memory.workerName.isNotBlank()) Text(memory.workerName, fontSize = 11.sp, color = Color.Gray)
                            }
                        },
                        leadingIcon = { Icon(Icons.Default.History, null) },
                        onClick = {
                            onSelect(
                                memory.copy(
                                    permitNumber = removeLatinLetters(memory.permitNumber),
                                    workerName = removeLatinLetters(memory.workerName),
                                )
                            )
                            latinRejected = false
                            expanded = false
                        },
                    )
                }
            }
        }
        if (latinRejected) Text("Используйте русскую раскладку: латинские буквы не принимаются", color = Red, fontSize = 12.sp)
        else if (error != null) Text(error, color = Red, fontSize = 12.sp)
        else if (memories.isNotEmpty()) Text("Введите часть номера или нажмите значок истории для автозаполнения.", color = Color.Gray, fontSize = 11.sp)
    }
}

private val uiDateFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy")

@Composable
private fun DateField(value: String, onDate: (String) -> Unit, error: String?) {
    val context = LocalContext.current
    val openPicker = {
        val initial = runCatching { LocalDate.parse(value, uiDateFormatter) }.getOrElse { LocalDate.now() }
        DatePickerDialog(
            context,
            { _, year, month, day -> onDate(String.format("%02d.%02d.%04d", day, month + 1, year)) },
            initial.year,
            initial.monthValue - 1,
            initial.dayOfMonth,
        ).show()
    }
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        OutlinedButton(
            onClick = openPicker,
            modifier = Modifier.fillMaxWidth().height(56.dp),
            shape = RoundedCornerShape(11.dp),
            contentPadding = PaddingValues(horizontal = 12.dp),
        ) {
            Text(
                value.ifBlank { "Выберите дату" },
                Modifier.weight(1f),
                color = if (value.isBlank()) Color.Gray else Color.Unspecified,
                maxLines = 1,
                softWrap = false,
            )
            Icon(Icons.Default.Event, "Открыть календарь")
        }
        if (error != null) Text(error, color = Red, fontSize = 12.sp)
    }
}

private fun showTimeSpinner(context: Context, value: String, onTime: (String) -> Unit) {
    val initial = runCatching { LocalTime.parse(value, DateTimeFormatter.ofPattern("HH:mm")) }
        .getOrElse { LocalTime.now() }
    val hours = NumberPicker(context).apply {
        minValue = 0
        maxValue = 23
        this.value = initial.hour
        wrapSelectorWheel = true
        setFormatter { String.format("%02d", it) }
    }
    val minutes = NumberPicker(context).apply {
        minValue = 0
        maxValue = 59
        this.value = initial.minute
        wrapSelectorWheel = true
        setFormatter { String.format("%02d", it) }
    }
    val density = context.resources.displayMetrics.density
    val pad = (16 * density).toInt()
    val container = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER
        setPadding(pad, 0, pad, 0)
        addView(hours, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        addView(minutes, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
    }
    android.app.AlertDialog.Builder(context)
        .setTitle("Выберите время")
        .setView(container)
        .setNegativeButton("Отмена", null)
        .setPositiveButton("Выбрать") { _, _ ->
            onTime(String.format("%02d:%02d", hours.value, minutes.value))
        }
        .show()
}

@Composable
private fun TimeField(value: String, onTime: (String) -> Unit) {
    val context = LocalContext.current
    OutlinedButton(
        onClick = { showTimeSpinner(context, value, onTime) },
        modifier = Modifier.fillMaxWidth().height(56.dp),
        shape = RoundedCornerShape(11.dp),
        contentPadding = PaddingValues(horizontal = 12.dp),
    ) {
        Text(
            value.ifBlank { "Выберите время" },
            Modifier.weight(1f),
            color = if (value.isBlank()) Color.Gray else Color.Unspecified,
            maxLines = 1,
            softWrap = false,
        )
        Icon(Icons.Default.Schedule, "Открыть выбор времени")
    }
}

@Composable
private fun DateTimeBlock(
    title: String,
    date: String,
    time: String,
    onDate: (String) -> Unit,
    onTime: (String) -> Unit,
    onNow: () -> Unit,
    error: String?,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
        DateField(date, onDate, error)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
            Box(Modifier.weight(1f)) { TimeField(time, onTime) }
            OutlinedButton(
                onClick = onNow,
                modifier = Modifier.weight(1f).height(56.dp),
                contentPadding = PaddingValues(horizontal = 10.dp),
            ) {
                Icon(Icons.Default.Schedule, null)
                Spacer(Modifier.width(5.dp))
                Text("Сейчас", maxLines = 1, softWrap = false)
            }
        }
    }
}

@Composable
private fun Field(
    label: String?,
    value: String,
    onValue: (String) -> Unit,
    placeholder: String,
    error: String?,
    singleLine: Boolean = true,
) {
    var latinRejected by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        if (label != null) Text(label, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
        OutlinedTextField(
            value = value,
            onValueChange = { raw ->
                latinRejected = containsLatinLetters(raw)
                onValue(removeLatinLetters(raw))
            },
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text(placeholder, maxLines = if (singleLine) 1 else Int.MAX_VALUE) },
            singleLine = singleLine,
            isError = error != null || latinRejected,
            shape = RoundedCornerShape(11.dp),
            minLines = if (singleLine) 1 else 3,
            maxLines = if (singleLine) 1 else 5,
        )
        if (latinRejected) Text("Используйте русскую раскладку: латинские буквы не принимаются", color = Red, fontSize = 12.sp)
        else if (error != null) Text(error, color = Red, fontSize = 12.sp)
    }
}

@Composable
private fun StagePicker(
    selected: Stage,
    savedStageIds: Set<String>,
    hasUnsavedChanges: Boolean,
    onSelect: (Stage) -> Unit,
) {
    var open by remember { mutableStateOf(false) }
    val selectedSaved = selected.id in savedStageIds
    val savedCount = savedStageCount(savedStageIds)

    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("Этап работ", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
        Box {
            OutlinedCard(Modifier.fillMaxWidth().clickable { open = true }, shape = RoundedCornerShape(11.dp)) {
                Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        when {
                            hasUnsavedChanges -> Icons.Default.Edit
                            selectedSaved -> Icons.Default.CheckCircle
                            else -> Icons.Default.Flag
                        },
                        null,
                        tint = when {
                            hasUnsavedChanges -> Orange
                            selectedSaved -> Green
                            else -> Blue
                        },
                    )
                    Spacer(Modifier.width(9.dp))
                    Column(Modifier.weight(1f)) {
                        Text(selected.title, fontWeight = FontWeight.SemiBold)
                        Text(
                            when {
                                hasUnsavedChanges -> "Есть несохранённые изменения"
                                selectedSaved -> "Этап сохранён"
                                else -> "Этап ещё не сохранён"
                            },
                            fontSize = 11.sp,
                            color = when {
                                hasUnsavedChanges -> Orange
                                selectedSaved -> Green
                                else -> Color.Gray
                            },
                        )
                    }
                    Icon(Icons.Default.KeyboardArrowDown, null)
                }
            }
            DropdownMenu(open, { open = false }) {
                stages.forEach { stage ->
                    val saved = stage.id in savedStageIds
                    DropdownMenuItem(
                        text = {
                            Column {
                                Text(stage.title, fontWeight = FontWeight.SemiBold)
                                val eventTitles = listOfNotNull(stage.first.title, stage.second?.title, stage.third?.title)
                                Text(
                                    when {
                                        saved -> "Сохранён"
                                        stage.optional -> "Необязательно"
                                        else -> eventTitles.joinToString(" • ")
                                    },
                                    fontSize = 11.sp,
                                    color = if (saved) Green else Color.Gray,
                                )
                            }
                        },
                        leadingIcon = {
                            Icon(
                                if (saved) Icons.Default.CheckCircle else Icons.Default.RadioButtonUnchecked,
                                null,
                                tint = if (saved) Green else Color.Gray,
                            )
                        },
                        onClick = { onSelect(stage); open = false },
                    )
                }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.CheckCircle, null, tint = Green, modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(6.dp))
            Text("Сохранено обязательных этапов: $savedCount из $requiredStageCount", fontSize = 12.sp, color = Color.Gray)
        }
    }
}

@Composable
private fun CheckLine(ok: Boolean, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(
            if (ok) Icons.Default.CheckCircle else Icons.Default.RadioButtonUnchecked,
            null,
            tint = if (ok) Green else Color.Gray,
            modifier = Modifier.size(19.dp),
        )
        Spacer(Modifier.width(7.dp))
        Text(text, fontSize = 13.sp)
    }
}

@Composable
private fun HistoryScreen(items: List<ru.rpo.mobile.data.EventResponse>) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("История этого устройства", fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Text("Последние записи, подтверждённые сервером", color = Color.Gray)
        if (items.isEmpty()) Text("Переданных записей пока нет.", Modifier.padding(top = 24.dp), color = Color.Gray)
        items.forEach { e ->
            ElevatedCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp)) {
                    Row {
                        Text(e.permit_number, fontWeight = FontWeight.Bold, color = Navy)
                        Spacer(Modifier.weight(1f))
                        Text(e.field_key, color = Blue, fontWeight = FontWeight.Bold)
                    }
                    Text(e.stage_label, fontWeight = FontWeight.SemiBold)
                    Text(e.field_value, color = Color.DarkGray)
                    if (e.comment.isNotBlank()) Text(e.comment, color = Color.Gray, fontSize = 12.sp)
                    Text(
                        if (e.exported_at == null) "На сервере · не выгружено" else "Выгружено оператором",
                        color = if (e.exported_at == null) Orange else Green,
                        fontSize = 12.sp,
                        modifier = Modifier.padding(top = 7.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun HelpScreen() {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Справка", fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Text(
            "1. Укажите ФИО русскими буквами — латиница в полях ввода не принимается. Приложение запомнит ФИО на этом устройстве.\n\n" +
                "2. Введите номер НД. Ранее использованные номера появляются в подсказках и могут быть подставлены одним нажатием.\n\n" +
                "3. Выберите этап. Передача объекта и фактическое начало/окончание работ теперь заполняются отдельными блоками.\n\n" +
                "4. Заполните выбранный этап и обязательно нажмите «Сохранить этап». Сохранённые этапы отмечаются зелёной галочкой. При попытке уйти с изменённого, но не сохранённого этапа приложение покажет предупреждение.\n\n" +
                "5. Дату выбирайте из календаря, время — прокруткой часов и минут или кнопкой «Сейчас». Для подготовки и фактических работ можно сначала передать только начало, а окончание заполнить позже. Для остановки обязательна причина, а для возобновления — комментарий. Для продления РПО укажите новую дату окончания.\n\n" +
                "6. После нажатия «Сохранить этап» данные сначала сохраняются на телефоне. Если интернета нет, они останутся в очереди и отправятся автоматически после появления сети.\n\n" +
                "7. Раздел «Замена исполнителей работ» необязательный. При замене укажите ФИО и должность / профессию каждого нового исполнителя.\n\n" +
                "8. Приложение получает от сервера сообщение о состоянии системы и доступной версии. Старые версии приложения остаются совместимыми с сервером.\n\n" +
                "9. Для синхронизации подходит любая интернет-сеть, включая медленное мобильное соединение 2G. Передаваемые пакеты данных небольшие."
        )
    }
}
