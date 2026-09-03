package ru.rpo.mobile.ui

import android.app.DatePickerDialog
import android.content.Context
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.NumberPicker
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Assignment
import androidx.compose.material.icons.filled.Business
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.CloudDone
import androidx.compose.material.icons.filled.CloudSync
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Event
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.PopupProperties
import androidx.lifecycle.viewmodel.compose.viewModel
import ru.rpo.mobile.data.EventResponse
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter

private val UxNavy = Color(0xFF073C77)
private val UxBlue = Color(0xFF0D63E6)
private val UxBg = Color(0xFFF4F7FB)
private val UxGreen = Color(0xFF1B9E50)
private val UxRed = Color(0xFFD73535)
private val UxOrange = Color(0xFFE98B00)
private val UxText = Color(0xFF17263A)
private val UxMuted = Color(0xFF718096)
private val UxDateFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy")
private val UxTimeFormatter = DateTimeFormatter.ofPattern("HH:mm")

private enum class UxTab { WORK, HISTORY, HELP }
private enum class HistoryFilter { ALL, PENDING, APPROVED, DENIED }

private fun uxFingerprint(s: FormState): String = listOf(
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
fun RpoUxApp(vm: RpoViewModel = viewModel()) {
    val state by vm.state.collectAsState()
    val history by vm.history.collectAsState()
    val memories by vm.permitMemories.collectAsState()
    var tab by remember { mutableStateOf(UxTab.WORK) }

    LaunchedEffect(tab) {
        if (tab == UxTab.HISTORY) vm.loadHistory()
    }

    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = UxBlue,
            background = UxBg,
            surface = Color.White,
            error = UxRed,
        )
    ) {
        Scaffold(
            containerColor = UxBg,
            topBar = { UxHeader(state) },
            bottomBar = {
                Column {
                    if (tab == UxTab.WORK) UxActionDock(state, vm)
                    NavigationBar(containerColor = Color.White) {
                        NavigationBarItem(
                            selected = tab == UxTab.WORK,
                            onClick = { tab = UxTab.WORK },
                            icon = { Icon(Icons.Default.Assignment, "Работа") },
                            label = { Text("Работа") },
                        )
                        NavigationBarItem(
                            selected = tab == UxTab.HISTORY,
                            onClick = { tab = UxTab.HISTORY },
                            icon = { Icon(Icons.Default.History, "История") },
                            label = { Text("История") },
                        )
                        NavigationBarItem(
                            selected = tab == UxTab.HELP,
                            onClick = { tab = UxTab.HELP },
                            icon = { Icon(Icons.Default.HelpOutline, "Справка") },
                            label = { Text("Справка") },
                        )
                    }
                }
            },
        ) { padding ->
            when (tab) {
                UxTab.WORK -> UxWorkScreen(state, memories, vm, Modifier.padding(padding))
                UxTab.HISTORY -> UxHistoryScreen(history, Modifier.padding(padding))
                UxTab.HELP -> UxHelpScreen(Modifier.padding(padding))
            }
        }
    }
}

@Composable
private fun UxHeader(s: FormState) {
    val syncLabel = when {
        s.failedCount > 0 -> "Нужна проверка"
        s.pendingCount > 0 -> "Очередь ${s.pendingCount}"
        else -> "Синхронизировано"
    }
    val syncColor = when {
        s.failedCount > 0 -> UxRed
        s.pendingCount > 0 -> UxOrange
        else -> UxGreen
    }
    Surface(color = UxNavy) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 11.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Surface(color = Color.White.copy(alpha = .12f), shape = RoundedCornerShape(12.dp)) {
                Text(
                    "РПО",
                    Modifier.padding(horizontal = 10.dp, vertical = 9.dp),
                    color = Color.White,
                    fontWeight = FontWeight.Black,
                    fontSize = 14.sp,
                )
            }
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text("Работы повышенной опасности", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                Text("Этапы и разрешения", color = Color.White.copy(alpha = .72f), fontSize = 10.sp)
            }
            Surface(color = syncColor.copy(alpha = .18f), shape = RoundedCornerShape(50)) {
                Row(Modifier.padding(horizontal = 8.dp, vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(7.dp).background(syncColor, RoundedCornerShape(50)))
                    Spacer(Modifier.width(5.dp))
                    Text(syncLabel, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}

@Composable
private fun UxWorkScreen(
    s: FormState,
    memories: List<PermitMemory>,
    vm: RpoViewModel,
    modifier: Modifier = Modifier,
) {
    val permitReady = s.permitNumber.trim().length >= 3 && s.workerName.trim().length >= 3 && s.structuralUnit in structuralUnits
    var editDetails by remember { mutableStateOf(!permitReady) }
    var pendingStage by remember(s.permitNumber) { mutableStateOf<Stage?>(null) }
    var baseline by remember(s.permitNumber, s.stage.id, s.serverSavedStageIds) { mutableStateOf(uxFingerprint(s)) }
    val hasUnsavedChanges = uxFingerprint(s) != baseline

    // Do not collapse the permit details while the worker is typing the permit number.
    // Previously the form became "ready" after the third symbol and immediately closed,
    // forcing the worker to tap "Изменить" repeatedly to finish the same number.

    pendingStage?.let { target ->
        AlertDialog(
            onDismissRequest = { pendingStage = null },
            icon = { Icon(Icons.Default.Warning, null, tint = UxOrange) },
            title = { Text("Есть несохранённые изменения") },
            text = { Text("В текущем этапе есть новые данные. Сохраните их либо подтвердите переход без сохранения.") },
            confirmButton = {
                TextButton(onClick = { pendingStage = null }) { Text("Остаться", fontWeight = FontWeight.Bold) }
            },
            dismissButton = {
                TextButton(onClick = { pendingStage = null; vm.updateStage(target); baseline = uxFingerprint(s) }) {
                    Text("Перейти без сохранения", color = UxRed)
                }
            },
        )
    }

    Column(
        modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (s.systemNotice?.maintenance == true || s.systemNotice?.update_available == true) {
            UxSystemNotice(s)
        }
        if (s.failedCount > 0 || s.pendingCount > 0) {
            UxQueueNotice(s, vm)
        }
        if (s.message != null) {
            UxTransientMessage(s.message, s.success)
        }

        if (permitReady) {
            UxPermitOverview(s, vm, onEdit = { editDetails = !editDetails })
        }

        if (!permitReady || editDetails) {
            UxPermitDetails(s, memories, vm)
        }

        if (s.permitNumber.trim().length >= 3) {
            UxApprovalCard(s)
            UxStageRail(
                selected = s.stage,
                completed = s.serverSavedStageIds,
                onSelect = { next ->
                    if (next.id == s.stage.id) return@UxStageRail
                    if (shouldWarnBeforeStageSwitch(s.stage, next, hasUnsavedChanges)) pendingStage = next
                    else {
                        vm.updateStage(next)
                        baseline = uxFingerprint(s)
                    }
                },
            )
            UxStageEditor(s, vm)
            UxReadinessCard(s)
        } else {
            UxEmptyPermitHint()
        }
        Spacer(Modifier.height(10.dp))
    }
}

@Composable
private fun UxSystemNotice(s: FormState) {
    val notice = s.systemNotice ?: return
    val maintenance = notice.maintenance
    Surface(
        color = if (maintenance) Color(0xFFFFEFED) else Color(0xFFEAF3FF),
        shape = RoundedCornerShape(14.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.Top) {
            Icon(if (maintenance) Icons.Default.Warning else Icons.Default.CloudDone, null, tint = if (maintenance) UxRed else UxBlue)
            Spacer(Modifier.width(9.dp))
            Column {
                Text(if (maintenance) "Система на обслуживании" else "Доступно обновление", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                Text(notice.message, color = UxMuted, fontSize = 11.sp)
            }
        }
    }
}

@Composable
private fun UxQueueNotice(s: FormState, vm: RpoViewModel) {
    Surface(
        color = if (s.failedCount > 0) Color(0xFFFFF0ED) else Color(0xFFFFF7E8),
        shape = RoundedCornerShape(14.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(if (s.failedCount > 0) Icons.Default.Warning else Icons.Default.CloudSync, null, tint = if (s.failedCount > 0) UxRed else UxOrange)
            Spacer(Modifier.width(9.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    if (s.failedCount > 0) "Есть данные, требующие проверки" else "Есть данные в очереди",
                    fontWeight = FontWeight.Bold,
                    fontSize = 12.sp,
                )
                Text("В очереди: ${s.pendingCount} · ошибок: ${s.failedCount}", color = UxMuted, fontSize = 10.sp)
            }
            TextButton(onClick = vm::retryPending, enabled = !s.sending) { Text("Повторить") }
        }
    }
}

@Composable
private fun UxTransientMessage(message: String, success: Boolean) {
    Surface(
        color = if (success) Color(0xFFEAF8EF) else Color(0xFFFFF4DF),
        shape = RoundedCornerShape(14.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(11.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(if (success) Icons.Default.CheckCircle else Icons.Default.Warning, null, tint = if (success) UxGreen else UxOrange)
            Spacer(Modifier.width(8.dp))
            Text(message, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun UxPermitOverview(s: FormState, vm: RpoViewModel, onEdit: () -> Unit) {
    val next = recommendedStage(s.serverSavedStageIds, s.approvalSummary?.status)
    Surface(color = Color.White, shape = RoundedCornerShape(18.dp), shadowElevation = 2.dp, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(15.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.Top) {
                Column(Modifier.weight(1f)) {
                    Text(s.permitNumber.trim().uppercase(), color = UxNavy, fontSize = 21.sp, fontWeight = FontWeight.Black)
                    Text("${s.structuralUnit} · ${s.workerName}", color = UxMuted, fontSize = 11.sp)
                }
                TextButton(onClick = onEdit) {
                    Icon(Icons.Default.Edit, null, modifier = Modifier.size(17.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("Изменить", fontSize = 11.sp)
                }
            }

            val nextTitle = when {
                s.approvalSummary?.status == "stopped" -> "Возобновление работ"
                next != null -> next.title
                else -> "Обязательные этапы заполнены"
            }
            Surface(color = Color(0xFFF0F6FF), shape = RoundedCornerShape(13.dp), modifier = Modifier.fillMaxWidth()) {
                Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Следующее действие", color = UxMuted, fontSize = 10.sp)
                        Text(nextTitle, color = UxNavy, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                    }
                    if (next != null && next.id != s.stage.id) {
                        OutlinedButton(onClick = { vm.updateStage(next) }, contentPadding = PaddingValues(horizontal = 10.dp, vertical = 0.dp)) {
                            Text("Открыть", fontSize = 10.sp)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun UxPermitDetails(s: FormState, memories: List<PermitMemory>, vm: RpoViewModel) {
    Surface(color = Color.White, shape = RoundedCornerShape(18.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(11.dp)) {
            Text("Реквизиты наряда-допуска", fontWeight = FontWeight.Bold, fontSize = 15.sp)
            UxTextField(
                label = "ФИО ответственного",
                value = s.workerName,
                onValue = vm::updateWorker,
                placeholder = "Например: Иванов И.И.",
                error = s.errors["worker"],
            )
            UxStructuralUnitPicker(s.structuralUnit, vm::updateStructuralUnit, s.errors["structuralUnit"])
            UxPermitField(s.permitNumber, memories, vm::updatePermit, vm::selectPermit, s.errors["permit"])
        }
    }
}

@Composable
private fun UxApprovalCard(s: FormState) {
    val approval = s.approvalSummary ?: return
    if (approval.status == "none") return
    val bg: Color
    val accent: Color
    val title: String
    val text: String
    when (approval.status) {
        "stopped" -> {
            bg = Color(0xFFFFEEEE); accent = UxRed; title = "Работы остановлены"
            text = "Передайте «Возобновление работ» и дождитесь разрешения оператора."
        }
        "pending" -> {
            bg = Color(0xFFFFF5E5); accent = UxOrange; title = "Ожидает разрешения"
            text = "Оператору передано ${approval.pending_count} этап(ов). До разрешения работы по этим этапам не продолжайте."
        }
        "approved" -> {
            bg = Color(0xFFEAF8EF); accent = UxGreen; title = "Работы можно проводить"
            text = "Оператор подтвердил последние переданные данные."
        }
        else -> {
            bg = Color(0xFFEAF3FF); accent = UxBlue; title = approval.label.ifBlank { "Статус получен" }
            text = "Состояние синхронизировано с сервером."
        }
    }
    Surface(color = bg, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(13.dp), verticalAlignment = Alignment.Top) {
            Icon(if (approval.status == "approved") Icons.Default.CheckCircle else Icons.Default.Schedule, null, tint = accent)
            Spacer(Modifier.width(9.dp))
            Column {
                Text(title, color = accent, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                Text(text, color = UxText, fontSize = 11.sp)
            }
        }
    }
}

@Composable
private fun UxStageRail(selected: Stage, completed: Set<String>, onSelect: (Stage) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Ход наряда-допуска", fontWeight = FontWeight.Bold, fontSize = 15.sp, modifier = Modifier.weight(1f))
            Text("${savedStageCount(completed)}/${requiredStageCount}", color = UxMuted, fontSize = 11.sp)
        }
        Row(
            Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            stages.forEachIndexed { index, stage ->
                val done = stage.id in completed
                val active = stage.id == selected.id
                val bg = when {
                    done -> Color(0xFFEAF8EF)
                    active -> Color(0xFFEAF3FF)
                    else -> Color.White
                }
                val border = when {
                    done -> UxGreen
                    active -> UxBlue
                    else -> Color(0xFFDCE5EF)
                }
                OutlinedCard(
                    modifier = Modifier.width(150.dp).clickable { onSelect(stage) },
                    shape = RoundedCornerShape(14.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, border),
                    colors = androidx.compose.material3.CardDefaults.outlinedCardColors(containerColor = bg),
                ) {
                    Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Surface(
                                color = if (done) UxGreen else if (active) UxBlue else Color(0xFFE9EEF5),
                                shape = RoundedCornerShape(50),
                            ) {
                                Text(
                                    if (done) "✓" else "${index + 1}",
                                    Modifier.padding(horizontal = 7.dp, vertical = 4.dp),
                                    color = if (done || active) Color.White else UxMuted,
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.Bold,
                                )
                            }
                            Spacer(Modifier.weight(1f))
                            if (stage.optional) Text("необяз.", color = UxMuted, fontSize = 8.sp)
                        }
                        Text(stage.title, fontWeight = FontWeight.SemiBold, fontSize = 11.sp, maxLines = 2)
                        Text(stageProgressLabel(stage, completed, active), color = if (done) UxGreen else if (active) UxBlue else UxMuted, fontSize = 9.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun UxStageEditor(s: FormState, vm: RpoViewModel) {
    Surface(color = Color.White, shape = RoundedCornerShape(18.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Column {
                Text(s.stage.title, fontWeight = FontWeight.Black, fontSize = 18.sp, color = UxNavy)
                Text(
                    if (s.stage.optional) "Необязательный раздел — заполняйте только при необходимости."
                    else "Вводите только фактические данные. Уже переданное повторно не отправляется.",
                    color = UxMuted,
                    fontSize = 11.sp,
                )
            }

            if (s.stage.id in s.serverSavedStageIds) {
                UxAlreadySentNotice("Этот этап полностью передан на сервер. Изменяйте значения только если нужна корректировка.")
            } else if (
                s.stage.kind == StageKind.RANGE_DATETIME &&
                s.primaryDate.isNotBlank() && s.primaryTime.isNotBlank() &&
                s.secondaryDate.isBlank() && s.secondaryTime.isBlank() &&
                s.approvalSummary != null
            ) {
                UxAlreadySentNotice("Начало уже заполнено. При сохранении окончания приложение отправит только новые данные.")
            }

            when (s.stage.kind) {
                StageKind.RANGE_DATETIME -> {
                    UxDateTimeBlock(
                        title = s.stage.first.title,
                        date = s.primaryDate,
                        time = s.primaryTime,
                        onDate = vm::updatePrimaryDate,
                        onTime = vm::updatePrimaryTime,
                        onNow = vm::nowPrimary,
                        error = s.errors["primary"],
                    )
                    UxDateTimeBlock(
                        title = requireNotNull(s.stage.second).title,
                        subtitle = "Можно заполнить позже",
                        date = s.secondaryDate,
                        time = s.secondaryTime,
                        onDate = vm::updateSecondaryDate,
                        onTime = vm::updateSecondaryTime,
                        onNow = vm::nowSecondary,
                        error = s.errors["secondary"],
                    )
                    UxTextField("Комментарий", s.comment, vm::updateComment, "Необязательно", null, singleLine = false)
                }
                StageKind.TRIPLE_DATETIME -> {
                    UxDateTimeBlock(s.stage.first.title, s.primaryDate, s.primaryTime, vm::updatePrimaryDate, vm::updatePrimaryTime, vm::nowPrimary, s.errors["primary"])
                    UxDateTimeBlock(requireNotNull(s.stage.second).title, s.secondaryDate, s.secondaryTime, vm::updateSecondaryDate, vm::updateSecondaryTime, vm::nowSecondary, s.errors["secondary"])
                    UxDateTimeBlock(requireNotNull(s.stage.third).title, s.thirdDate, s.thirdTime, vm::updateThirdDate, vm::updateThirdTime, vm::nowThird, s.errors["third"])
                    UxTextField("Комментарий", s.comment, vm::updateComment, "Необязательно", null, singleLine = false)
                }
                StageKind.DATETIME -> {
                    UxDateTimeBlock(s.stage.first.title, s.primaryDate, s.primaryTime, vm::updatePrimaryDate, vm::updatePrimaryTime, vm::nowPrimary, s.errors["primary"])
                    val resume = s.stage.id == "RESUME_WORK"
                    UxTextField(
                        if (resume) "Комментарий · обязательно" else "Комментарий",
                        s.comment,
                        vm::updateComment,
                        if (resume) "Условия или основание возобновления" else "Необязательно",
                        if (resume) s.errors["comment"] else null,
                        singleLine = false,
                    )
                }
                StageKind.STOP -> {
                    UxDateTimeBlock("Дата и время остановки", s.primaryDate, s.primaryTime, vm::updatePrimaryDate, vm::updatePrimaryTime, vm::nowPrimary, s.errors["primary"])
                    UxTextField("Причина остановки · обязательно", s.stopReason, vm::updateStopReason, "Укажите причину", s.errors["stopReason"], singleLine = false)
                }
                StageKind.EXTENSION_DATE -> {
                    Text("Новая дата окончания работ", fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                    UxDateField(s.extensionDate, vm::updateExtensionDate, s.errors["extension"])
                    OutlinedButton(onClick = vm::extensionTomorrow, modifier = Modifier.fillMaxWidth().height(50.dp)) {
                        Icon(Icons.Default.Event, null)
                        Spacer(Modifier.width(6.dp))
                        Text("Завтра")
                    }
                    UxTextField("Комментарий", s.comment, vm::updateComment, "Причина или примечание", null, singleLine = false)
                }
                StageKind.REPLACEMENTS -> {
                    s.replacements.forEachIndexed { index, item ->
                        ElevatedCard(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(11.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text("Исполнитель ${index + 1}", fontWeight = FontWeight.SemiBold)
                                    Spacer(Modifier.weight(1f))
                                    if (s.replacements.size > 1) TextButton(onClick = { vm.removeReplacement(index) }) { Text("Удалить", color = UxRed) }
                                }
                                UxTextField("ФИО", item.name, { vm.updateReplacementName(index, it) }, "Петров П.П.", null)
                                UxTextField("Должность / профессия", item.position, { vm.updateReplacementPosition(index, it) }, "Электромонтёр", null)
                            }
                        }
                    }
                    OutlinedButton(onClick = vm::addReplacement, modifier = Modifier.fillMaxWidth().height(50.dp)) {
                        Icon(Icons.Default.Add, null)
                        Spacer(Modifier.width(6.dp))
                        Text("Добавить исполнителя")
                    }
                    s.errors["replacements"]?.let { Text(it, color = UxRed, fontSize = 11.sp) }
                }
            }
        }
    }
}

@Composable
private fun UxAlreadySentNotice(text: String) {
    Surface(color = Color(0xFFF0F8F3), shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(10.dp), verticalAlignment = Alignment.Top) {
            Icon(Icons.Default.CheckCircle, null, tint = UxGreen, modifier = Modifier.size(19.dp))
            Spacer(Modifier.width(7.dp))
            Text(text, color = Color(0xFF28583A), fontSize = 10.sp)
        }
    }
}

@Composable
private fun UxReadinessCard(s: FormState) {
    val hint = stageReadinessHint(s)
    Surface(
        color = if (hint == null) Color(0xFFEAF8EF) else Color(0xFFFFF7E8),
        shape = RoundedCornerShape(14.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(11.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(if (hint == null) Icons.Default.CheckCircle else Icons.Default.Warning, null, tint = if (hint == null) UxGreen else UxOrange)
            Spacer(Modifier.width(8.dp))
            Column {
                Text(if (hint == null) "Готово к передаче" else "Осталось заполнить", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                Text(hint ?: "Нажмите кнопку ниже. Уже переданные значения повторно не отправятся.", color = UxMuted, fontSize = 10.sp)
            }
        }
    }
}

@Composable
private fun UxEmptyPermitHint() {
    Surface(color = Color.White, shape = RoundedCornerShape(18.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(22.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(Icons.Default.Assignment, null, tint = UxBlue, modifier = Modifier.size(38.dp))
            Spacer(Modifier.height(8.dp))
            Text("Выберите наряд-допуск", fontWeight = FontWeight.Bold, fontSize = 16.sp)
            Text("После ввода номера приложение покажет статус, этапы и следующее действие.", color = UxMuted, fontSize = 11.sp)
        }
    }
}

@Composable
private fun UxActionDock(s: FormState, vm: RpoViewModel) {
    if (s.permitNumber.trim().length < 3) return
    val hint = stageReadinessHint(s)
    Surface(color = Color.White, shadowElevation = 8.dp) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 9.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            if (hint != null) Text(hint, color = UxOrange, fontSize = 10.sp, fontWeight = FontWeight.SemiBold)
            Button(
                onClick = { vm.send() },
                enabled = !s.sending,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                shape = RoundedCornerShape(13.dp),
            ) {
                if (s.sending) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = Color.White)
                else Icon(Icons.Default.CloudDone, null)
                Spacer(Modifier.width(7.dp))
                Text(if (s.sending) "Синхронизация..." else contextualActionLabel(s), fontWeight = FontWeight.Bold, maxLines = 1)
            }
        }
    }
}

@Composable
private fun UxPermitField(
    value: String,
    memories: List<PermitMemory>,
    onValue: (String) -> Unit,
    onSelect: (PermitMemory) -> Unit,
    error: String?,
) {
    var expanded by remember { mutableStateOf(false) }
    var latinRejected by remember { mutableStateOf(false) }
    val suggestions = remember(value, memories) {
        val q = value.trim()
        if (q.isBlank()) memories.take(6) else memories.filter { it.permitNumber.contains(q, ignoreCase = true) }.take(6)
    }
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text("Номер наряда-допуска", fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
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
                shape = RoundedCornerShape(12.dp),
                trailingIcon = {
                    if (memories.isNotEmpty()) {
                        IconButton(onClick = { expanded = true }) { Icon(Icons.Default.History, "Ранее введённые") }
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
                                Text(memory.permitNumber, fontWeight = FontWeight.Bold)
                                Text(listOfNotNull(memory.structuralUnit, memory.workerName.ifBlank { null }).joinToString(" · "), color = UxMuted, fontSize = 10.sp)
                            }
                        },
                        leadingIcon = { Icon(Icons.Default.History, null) },
                        onClick = {
                            onSelect(memory.copy(permitNumber = removeLatinLetters(memory.permitNumber), workerName = removeLatinLetters(memory.workerName)))
                            expanded = false
                            latinRejected = false
                        },
                    )
                }
            }
        }
        when {
            latinRejected -> Text("Используйте русскую раскладку", color = UxRed, fontSize = 10.sp)
            error != null -> Text(error, color = UxRed, fontSize = 10.sp)
            memories.isNotEmpty() -> Text("Введите часть номера — подсказки не закроют клавиатуру.", color = UxMuted, fontSize = 10.sp)
        }
    }
}

@Composable
private fun UxStructuralUnitPicker(value: String, onSelect: (String) -> Unit, error: String?) {
    var open by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text("Структурное подразделение", fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
        Box {
            OutlinedCard(Modifier.fillMaxWidth().clickable { open = true }, shape = RoundedCornerShape(12.dp)) {
                Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Business, null, tint = UxBlue)
                    Spacer(Modifier.width(8.dp))
                    Text(value.ifBlank { "Выберите подразделение" }, Modifier.weight(1f), color = if (value.isBlank()) UxMuted else UxText)
                    Icon(Icons.Default.ArrowDropDown, null)
                }
            }
            DropdownMenu(expanded = open, onDismissRequest = { open = false }, modifier = Modifier.fillMaxWidth(.92f)) {
                structuralUnits.forEach { item ->
                    DropdownMenuItem(
                        text = { Text(item, fontWeight = if (item == value) FontWeight.Bold else FontWeight.Normal) },
                        onClick = { onSelect(item); open = false },
                    )
                }
            }
        }
        if (error != null) Text(error, color = UxRed, fontSize = 10.sp)
    }
}

@Composable
private fun UxTextField(
    label: String,
    value: String,
    onValue: (String) -> Unit,
    placeholder: String,
    error: String?,
    singleLine: Boolean = true,
) {
    var latinRejected by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(label, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
        OutlinedTextField(
            value = value,
            onValueChange = { raw ->
                latinRejected = containsLatinLetters(raw)
                onValue(removeLatinLetters(raw))
            },
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text(placeholder) },
            singleLine = singleLine,
            minLines = if (singleLine) 1 else 3,
            maxLines = if (singleLine) 1 else 5,
            isError = error != null || latinRejected,
            shape = RoundedCornerShape(12.dp),
        )
        if (latinRejected) Text("Латинские буквы не принимаются", color = UxRed, fontSize = 10.sp)
        else if (error != null) Text(error, color = UxRed, fontSize = 10.sp)
    }
}

@Composable
private fun UxDateField(value: String, onDate: (String) -> Unit, error: String?) {
    val context = LocalContext.current
    val openPicker = {
        val initial = runCatching { LocalDate.parse(value, UxDateFormatter) }.getOrElse { LocalDate.now() }
        DatePickerDialog(
            context,
            { _, year, month, day -> onDate(String.format("%02d.%02d.%04d", day, month + 1, year)) },
            initial.year,
            initial.monthValue - 1,
            initial.dayOfMonth,
        ).show()
    }
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        OutlinedButton(
            onClick = openPicker,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(12.dp),
            contentPadding = PaddingValues(horizontal = 12.dp),
        ) {
            Text(value.ifBlank { "Выберите дату" }, Modifier.weight(1f), color = if (value.isBlank()) UxMuted else UxText, maxLines = 1)
            Icon(Icons.Default.Event, "Календарь")
        }
        if (error != null) Text(error, color = UxRed, fontSize = 10.sp)
    }
}

private fun uxShowTimeSpinner(context: Context, value: String, onTime: (String) -> Unit) {
    val initial = runCatching { LocalTime.parse(value, UxTimeFormatter) }.getOrElse { LocalTime.now() }
    val hours = NumberPicker(context).apply {
        minValue = 0; maxValue = 23; this.value = initial.hour; wrapSelectorWheel = true
        setFormatter { String.format("%02d", it) }
    }
    val minutes = NumberPicker(context).apply {
        minValue = 0; maxValue = 59; this.value = initial.minute; wrapSelectorWheel = true
        setFormatter { String.format("%02d", it) }
    }
    val density = context.resources.displayMetrics.density
    val pad = (16 * density).toInt()
    val container = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER; setPadding(pad, 0, pad, 0)
        addView(hours, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        addView(minutes, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
    }
    android.app.AlertDialog.Builder(context)
        .setTitle("Выберите время")
        .setView(container)
        .setNegativeButton("Отмена", null)
        .setPositiveButton("Выбрать") { _, _ -> onTime(String.format("%02d:%02d", hours.value, minutes.value)) }
        .show()
}

@Composable
private fun UxTimeField(value: String, onTime: (String) -> Unit) {
    val context = LocalContext.current
    OutlinedButton(
        onClick = { uxShowTimeSpinner(context, value, onTime) },
        modifier = Modifier.fillMaxWidth().height(52.dp),
        shape = RoundedCornerShape(12.dp),
        contentPadding = PaddingValues(horizontal = 12.dp),
    ) {
        Text(value.ifBlank { "Выберите время" }, Modifier.weight(1f), color = if (value.isBlank()) UxMuted else UxText, maxLines = 1)
        Icon(Icons.Default.Schedule, "Время")
    }
}

@Composable
private fun UxDateTimeBlock(
    title: String,
    date: String,
    time: String,
    onDate: (String) -> Unit,
    onTime: (String) -> Unit,
    onNow: () -> Unit,
    error: String?,
    subtitle: String? = null,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(title, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, modifier = Modifier.weight(1f))
            if (subtitle != null) Text(subtitle, color = UxMuted, fontSize = 9.sp)
        }
        UxDateField(date, onDate, error)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.weight(1f)) { UxTimeField(time, onTime) }
            OutlinedButton(onClick = onNow, modifier = Modifier.weight(1f).height(52.dp), contentPadding = PaddingValues(horizontal = 8.dp)) {
                Icon(Icons.Default.Schedule, null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(5.dp))
                Text("Сейчас", maxLines = 1)
            }
        }
    }
}

@Composable
private fun UxHistoryScreen(items: List<EventResponse>, modifier: Modifier = Modifier) {
    var query by remember { mutableStateOf("") }
    var filter by remember { mutableStateOf(HistoryFilter.ALL) }
    var expanded by remember { mutableStateOf<String?>(null) }
    val filtered = remember(items, query, filter) {
        items.filter { item ->
            val matchesQuery = query.isBlank() || item.permit_number.contains(query, true) || item.worker_name.contains(query, true) || item.structural_unit.orEmpty().contains(query, true)
            val matchesFilter = when (filter) {
                HistoryFilter.ALL -> true
                HistoryFilter.PENDING -> item.approval_status == "pending"
                HistoryFilter.APPROVED -> item.approval_status == "approved"
                HistoryFilter.DENIED -> item.approval_status == "denied"
            }
            matchesQuery && matchesFilter
        }
    }

    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("История нарядов-допусков", fontSize = 22.sp, fontWeight = FontWeight.Black, color = UxNavy)
        Text("Один НД — одна карточка с ранее переданными этапами.", color = UxMuted, fontSize = 11.sp)
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            modifier = Modifier.fillMaxWidth(),
            leadingIcon = { Icon(Icons.Default.Search, null) },
            placeholder = { Text("Номер НД, ФИО или подразделение") },
            singleLine = true,
            shape = RoundedCornerShape(13.dp),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
            FilterChip(filter == HistoryFilter.ALL, { filter = HistoryFilter.ALL }, { Text("Все") })
            FilterChip(filter == HistoryFilter.PENDING, { filter = HistoryFilter.PENDING }, { Text("Ожидают") })
            FilterChip(filter == HistoryFilter.APPROVED, { filter = HistoryFilter.APPROVED }, { Text("Разрешено") })
            FilterChip(filter == HistoryFilter.DENIED, { filter = HistoryFilter.DENIED }, { Text("Запрещено") })
        }
        if (filtered.isEmpty()) {
            Surface(color = Color.White, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth()) {
                Text("По выбранному фильтру записей нет.", Modifier.padding(20.dp), color = UxMuted)
            }
        }
        filtered.forEach { item ->
            val open = expanded == item.permit_number
            Surface(
                color = if (item.approval_status == "denied") Color(0xFFFFF2F0) else Color.White,
                shape = RoundedCornerShape(16.dp),
                shadowElevation = 1.dp,
                modifier = Modifier.fillMaxWidth().clickable { expanded = if (open) null else item.permit_number },
            ) {
                Column(Modifier.padding(13.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(item.permit_number, color = UxNavy, fontWeight = FontWeight.Black, fontSize = 16.sp)
                            Text("${item.structural_unit.orEmpty().ifBlank { "—" }} · ${item.worker_name}", color = UxMuted, fontSize = 10.sp)
                        }
                        Icon(if (open) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown, null, tint = UxBlue)
                    }
                    val statusColor = when (item.approval_status) {
                        "denied", "stopped" -> UxRed
                        "approved" -> UxGreen
                        "pending" -> UxOrange
                        else -> UxBlue
                    }
                    val statusText = when (item.approval_status) {
                        "denied" -> "Проведение запрещено"
                        "stopped" -> "Работы остановлены"
                        "approved" -> "Разрешено"
                        "pending" -> "Ожидает разрешения"
                        else -> "Разрешение не требуется"
                    }
                    Text(
                        statusText,
                        color = statusColor,
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 10.sp,
                    )
                    if (open) {
                        HorizontalDivider(Modifier.padding(vertical = 4.dp))
                        Text("Хронология переданных данных", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                        item.field_value.lines().filter { it.isNotBlank() }.forEach { line ->
                            Row(verticalAlignment = Alignment.Top) {
                                Box(Modifier.padding(top = 5.dp).size(7.dp).background(UxBlue, RoundedCornerShape(50)))
                                Spacer(Modifier.width(8.dp))
                                Text(line, color = UxText, fontSize = 11.sp, modifier = Modifier.weight(1f))
                            }
                        }
                        if (item.comment.isNotBlank()) {
                            Text("Комментарии", fontWeight = FontWeight.Bold, fontSize = 11.sp, modifier = Modifier.padding(top = 4.dp))
                            Text(item.comment, color = UxMuted, fontSize = 10.sp)
                        }
                    } else {
                        Text("Нажмите, чтобы посмотреть все переданные этапы", color = UxMuted, fontSize = 9.sp)
                    }
                }
            }
        }
        Spacer(Modifier.height(10.dp))
    }
}

@Composable
private fun UxHelpScreen(modifier: Modifier = Modifier) {
    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Справка", fontSize = 22.sp, fontWeight = FontWeight.Black, color = UxNavy)
        UxHelpCard("Работайте по подсказке", "После выбора НД сверху отображается следующее рекомендуемое действие. При необходимости любой этап можно открыть вручную в ленте.")
        UxHelpCard("Передавайте только новое", "Если начало этапа уже передано, при последующем заполнении окончания приложение не отправляет начало повторно.")
        UxHelpCard("Дождитесь разрешения", "Для всех этапов, кроме остановки работ, после передачи дождитесь зелёного статуса «Работы можно проводить».")
        UxHelpCard("Без интернета", "Данные сохраняются на устройстве. В шапке появится счётчик очереди, а отправка возобновится автоматически после появления связи.")
        UxHelpCard("Версия", "РПО Mobile 2.1 · новый интерфейс. Предыдущий интерфейс и APK 2.0.1 сохранены для быстрого отката.")
    }
}

@Composable
private fun UxHelpCard(title: String, text: String) {
    Surface(color = Color.White, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, fontWeight = FontWeight.Bold, fontSize = 14.sp)
            Text(text, color = UxMuted, fontSize = 11.sp)
        }
    }
}
