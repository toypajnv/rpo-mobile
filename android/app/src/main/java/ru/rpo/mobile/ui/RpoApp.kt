package ru.rpo.mobile.ui

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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel

private val Navy = Color(0xFF073C77)
private val Blue = Color(0xFF0D63E6)
private val Bg = Color(0xFFF4F7FB)
private val Green = Color(0xFF1B9E50)
private val Red = Color(0xFFD73535)

enum class Tab { FORM, HISTORY, HELP }

@Composable
fun RpoApp(vm: RpoViewModel = viewModel()) {
    val state by vm.state.collectAsState()
    val history by vm.history.collectAsState()
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
                    Tab.FORM -> FormScreen(state, vm)
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
            Icon(Icons.Default.Security, null, tint = Color.White, modifier = Modifier.size(34.dp))
            Spacer(Modifier.width(10.dp))
            Column {
                Text("РПО", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Bold)
                Text("Передача этапов работ", color = Color.White.copy(alpha = .82f), fontSize = 12.sp)
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
private fun FormScreen(s: FormState, vm: RpoViewModel) {
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
                        tint = if (s.success) Green else Color(0xFFE98B00),
                    )
                    Spacer(Modifier.width(9.dp))
                    Text(s.message, fontWeight = FontWeight.SemiBold)
                }
            }
        }

        Field("ФИО работника", s.workerName, vm::updateWorker, "Например: Иванов И.И.", s.errors["worker"])
        Field(
            "Номер наряда-допуска",
            s.permitNumber,
            vm::updatePermit,
            "Например: СН-038364",
            s.errors["permit"],
        )
        StagePicker(s.stage, vm::updateStage)

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
                    title = requireNotNull(s.stage.second).title,
                    date = s.secondaryDate,
                    time = s.secondaryTime,
                    onDate = vm::updateSecondaryDate,
                    onTime = vm::updateSecondaryTime,
                    onNow = vm::nowSecondary,
                    error = s.errors["secondary"],
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
                Field("Комментарий (необязательно)", s.comment, vm::updateComment, "Комментарий к этапу", null, singleLine = false)
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
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
                    Box(Modifier.weight(1f)) {
                        Field(null, s.extensionDate, vm::updateExtensionDate, "ДД.ММ.ГГГГ", s.errors["extension"])
                    }
                    OutlinedButton(onClick = vm::extensionTomorrow, modifier = Modifier.height(56.dp)) {
                        Icon(Icons.Default.Event, null)
                        Spacer(Modifier.width(5.dp))
                        Text("Завтра")
                    }
                }
                Field("Комментарий (необязательно)", s.comment, vm::updateComment, "Причина или примечание", null, singleLine = false)
            }
        }

        Button(
            onClick = vm::send,
            enabled = !s.sending,
            modifier = Modifier.fillMaxWidth().height(58.dp),
            shape = RoundedCornerShape(12.dp),
        ) {
            if (s.sending) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp, color = Color.White)
            else Icon(Icons.Default.Send, null)
            Spacer(Modifier.width(8.dp))
            Text(if (s.sending) "Отправка..." else "Отправить на сервер", fontWeight = FontWeight.Bold)
        }

        Surface(color = Color(0xFFF0F8F3), shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                CheckLine(s.workerName.trim().length >= 3, "ФИО указано")
                CheckLine(s.permitNumber.trim().length >= 3 && s.errors["permit"] == null, "Номер НД корректен")
                CheckLine(s.errors.keys.none { it in setOf("primary", "secondary", "extension", "stopReason") }, "Данные этапа заполнены")
            }
        }
        Spacer(Modifier.height(10.dp))
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
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
            Box(Modifier.weight(1f)) { Field(null, date, onDate, "ДД.ММ.ГГГГ", error) }
            Box(Modifier.weight(.72f)) { Field(null, time, onTime, "ЧЧ:ММ", null) }
            OutlinedButton(onClick = onNow, modifier = Modifier.height(56.dp)) {
                Icon(Icons.Default.Schedule, null)
                Spacer(Modifier.width(4.dp))
                Text("Сейчас")
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
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        if (label != null) Text(label, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
        OutlinedTextField(
            value = value,
            onValueChange = onValue,
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text(placeholder) },
            singleLine = singleLine,
            isError = error != null,
            shape = RoundedCornerShape(11.dp),
            minLines = if (singleLine) 1 else 3,
            maxLines = if (singleLine) 1 else 5,
        )
        if (error != null) Text(error, color = Red, fontSize = 12.sp)
    }
}

@Composable
private fun StagePicker(selected: Stage, onSelect: (Stage) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text("Этап работ", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
        Box {
            OutlinedCard(Modifier.fillMaxWidth().clickable { open = true }, shape = RoundedCornerShape(11.dp)) {
                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Flag, null, tint = Blue)
                    Spacer(Modifier.width(9.dp))
                    Text(selected.title, Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                    Icon(Icons.Default.KeyboardArrowDown, null)
                }
            }
            DropdownMenu(open, { open = false }) {
                stages.forEach { stage ->
                    DropdownMenuItem(
                        text = {
                            Column {
                                Text(stage.title, fontWeight = FontWeight.SemiBold)
                                if (stage.kind == StageKind.RANGE_DATETIME && stage.second != null) {
                                    Text("${stage.first.title} + ${stage.second.title}", fontSize = 11.sp, color = Color.Gray)
                                }
                            }
                        },
                        onClick = { onSelect(stage); open = false },
                    )
                }
            }
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
        Text("Последние передачи на сервер", color = Color.Gray)
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
                        color = if (e.exported_at == null) Color(0xFFE58A00) else Green,
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
            "1. Укажите ФИО — приложение запомнит его на этом устройстве.\n\n" +
                "2. Введите номер НД вручную. Недопустимые символы, например %, будут подсвечены.\n\n" +
                "3. Выберите один из укрупнённых этапов. Для подготовки и начала работ приложение само передаст два связанных события.\n\n" +
                "4. Для дат и времени можно использовать кнопку «Сейчас».\n\n" +
                "5. Для остановки работ обязательно укажите время и причину.\n\n" +
                "6. Для продления РПО укажите новую дату окончания работ.\n\n" +
                "7. Нажмите «Отправить на сервер». Сервер повторно проверит данные и последовательность дат."
        )
    }
}
