from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Marker not found in {path}: {old[:120]!r}')
    target.write_text(text.replace(old, new, 1), encoding='utf-8')

replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt', '''        Field("ФИО работника", s.workerName, vm::updateWorker, "Например: Иванов И.И.", s.errors["worker"])
        PermitField(s.permitNumber, permitMemories, vm::updatePermit, vm::selectPermit, s.errors["permit"])
        StagePicker(''', '''        Field("ФИО работника", s.workerName, vm::updateWorker, "Например: Иванов И.И.", s.errors["worker"])
        StructuralUnitPicker(s.structuralUnit, vm::updateStructuralUnit, s.errors["structuralUnit"])
        PermitField(s.permitNumber, permitMemories, vm::updatePermit, vm::selectPermit, s.errors["permit"])
        ApprovalStatusCard(s)
        StagePicker(''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt', '''                CheckLine(s.workerName.trim().length >= 3, "ФИО указано")
                CheckLine(s.permitNumber.trim().length >= 3 && s.errors["permit"] == null, "Номер НД корректен")''', '''                CheckLine(s.workerName.trim().length >= 3, "ФИО указано")
                CheckLine(s.structuralUnit in structuralUnits, "Структурное подразделение выбрано")
                CheckLine(s.permitNumber.trim().length >= 3 && s.errors["permit"] == null, "Номер НД корректен")''')

picker_ui = '''
@Composable
private fun StructuralUnitPicker(value: String, onSelect: (String) -> Unit, error: String?) {
    var open by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text("Структурное подразделение", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
        Box {
            OutlinedCard(
                modifier = Modifier.fillMaxWidth().clickable { open = true },
                shape = RoundedCornerShape(11.dp),
            ) {
                Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Business, null, tint = Blue)
                    Spacer(Modifier.width(9.dp))
                    Text(value.ifBlank { "Выберите подразделение" }, Modifier.weight(1f), color = if (value.isBlank()) Color.Gray else Color.Unspecified)
                    Icon(Icons.Default.ArrowDropDown, null)
                }
            }
            DropdownMenu(expanded = open, onDismissRequest = { open = false }, modifier = Modifier.fillMaxWidth(.92f)) {
                structuralUnits.forEach { unit ->
                    DropdownMenuItem(
                        text = { Text(unit, fontWeight = if (unit == value) FontWeight.Bold else FontWeight.Normal) },
                        onClick = { onSelect(unit); open = false },
                    )
                }
            }
        }
        if (error != null) Text(error, color = Red, fontSize = 12.sp)
    }
}

@Composable
private fun ApprovalStatusCard(s: FormState) {
    val approval = s.approvalSummary ?: return
    if (s.permitNumber.trim().length < 3 || approval.status == "none") return
    val pending = approval.status == "pending"
    val approved = approval.status == "approved"
    val bg = when {
        pending -> Color(0xFFFFF4DF)
        approved -> Color(0xFFE7F7EC)
        else -> Color(0xFFEAF3FF)
    }
    val accent = when {
        pending -> Orange
        approved -> Green
        else -> Blue
    }
    Surface(color = bg, shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(13.dp), verticalAlignment = Alignment.Top) {
            Icon(if (approved) Icons.Default.CheckCircle else Icons.Default.Schedule, null, tint = accent)
            Spacer(Modifier.width(9.dp))
            Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(approvalStatusLabel(approval.status), color = accent, fontWeight = FontWeight.Bold)
                Text(
                    when {
                        pending -> "Передано на сервер. Ожидающих разрешения этапов: ${approval.pending_count}."
                        approved -> "Оператор подтвердил последние переданные этапы. Работы можно проводить."
                        else -> "Для этого события отдельное разрешение оператора не требуется."
                    },
                    fontSize = 12.sp,
                    color = Color.DarkGray,
                )
            }
        }
    }
}

'''
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt', '@Composable\nprivate fun PermitField(', picker_ui + '@Composable\nprivate fun PermitField(')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt', '''                    Text(e.stage_label, fontWeight = FontWeight.SemiBold)
                    Text(e.field_value, color = Color.DarkGray)''', '''                    Text(e.stage_label, fontWeight = FontWeight.SemiBold)
                    if (!e.structural_unit.isNullOrBlank()) Text(e.structural_unit.orEmpty(), color = Blue, fontSize = 12.sp)
                    Text(e.field_value, color = Color.DarkGray)''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt', '''                    Text(
                        if (e.exported_at == null) "На сервере · не выгружено" else "Выгружено оператором",
                        color = if (e.exported_at == null) Orange else Green,
                        fontSize = 12.sp,
                        modifier = Modifier.padding(top = 7.dp),
                    )''', '''                    Text(
                        if (e.approval_required) approvalStatusLabel(e.approval_status) else "Разрешение не требуется",
                        color = if (e.approval_status == "approved") Green else if (e.approval_status == "pending") Orange else Blue,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(top = 7.dp),
                    )
                    Text(
                        if (e.exported_at == null) "На сервере · не выгружено" else "Выгружено оператором",
                        color = Color.Gray,
                        fontSize = 11.sp,
                    )''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt', '"2. Введите номер НД. Ранее использованные номера появляются в подсказках и могут быть подставлены одним нажатием.\\n\\n" +', '"2. Выберите структурное подразделение из списка, затем введите номер НД. Ранее использованные номера появляются в подсказках.\\n\\n" +')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoApp.kt', '"6. После нажатия «Сохранить этап» данные сначала сохраняются на телефоне. Если интернета нет, они останутся в очереди и отправятся автоматически после появления сети.\\n\\n" +', '"6. После «Сохранить этап» данные отправляются оператору. Для всех этапов, кроме остановки, дождитесь статуса «Работы можно проводить». Приложение автоматически обновляет статус выбранного НД. При отсутствии интернета запись остаётся в очереди и отправляется позже.\\n\\n" +')
print('android ui v2 applied')
