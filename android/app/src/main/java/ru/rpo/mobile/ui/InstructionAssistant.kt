package ru.rpo.mobile.ui

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
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
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

private val AssistantNavy = Color(0xFF073C77)
private val AssistantBlue = Color(0xFF0D63E6)
private val AssistantGreen = Color(0xFF168B48)
private val AssistantRed = Color(0xFFC62828)
private val AssistantOrange = Color(0xFFE87500)
private val AssistantMuted = Color(0xFF718096)
private val AssistantBg = Color(0xFFF4F7FB)

private enum class AssistantView { HOME, FLOW, KNOWLEDGE }

private data class AssistantRisk(
    val id: String,
    val icon: String,
    val title: String,
    val measures: List<String>,
)

private val assistantRisks = listOf(
    AssistantRisk(
        "movement",
        "🚜",
        "Движущаяся техника / механизмы",
        listOf(
            "Определите границы безопасной зоны и исключите нахождение людей в зоне движения.",
            "По возможности устраните источник опасности либо ограничьте контакт с ним.",
        ),
    ),
    AssistantRisk(
        "height",
        "🪜",
        "Падение с высоты",
        listOf(
            "Проверьте исправность системы защиты от падения и средств индивидуальной защиты.",
            "Проверьте леса, подмости, лестницы и точки крепления перед использованием.",
        ),
    ),
    AssistantRisk(
        "pressure",
        "⏱",
        "Давление / энергия среды",
        listOf(
            "Убедитесь, что опасная энергия изолирована и давление снижено до безопасного состояния.",
            "Проверьте блокировки, предупреждающие знаки и невозможность ошибочного включения.",
        ),
    ),
    AssistantRisk(
        "electric",
        "⚡",
        "Электричество",
        listOf(
            "Изолируйте источники энергии перед ремонтом и обслуживанием оборудования.",
            "Проверьте надёжность отключения и невозможность самопроизвольного включения.",
        ),
    ),
    AssistantRisk(
        "fire",
        "🔥",
        "Пожар / взрыв",
        listOf(
            "Обсудите возможные источники воспламенения и меры по их исключению.",
            "При изменении условий немедленно остановите работу и повторно оцените опасности.",
        ),
    ),
    AssistantRisk(
        "gas",
        "☣",
        "Газ / вредные вещества",
        listOf(
            "Проверьте исправность газоанализатора, СИЗОД и спасательного оборудования, если они требуются условиями работ.",
            "При первых признаках отравления, удушения или срабатывании газоанализатора немедленно прекратите работу.",
        ),
    ),
    AssistantRisk(
        "temperature",
        "🌡",
        "Высокая / низкая температура",
        listOf(
            "Обсудите источники высокой или низкой температуры и возможность контакта с ними.",
            "Определите необходимые средства защиты и безопасный порядок выполнения операций.",
        ),
    ),
    AssistantRisk(
        "people",
        "👥",
        "Персонал / нештатные действия",
        listOf(
            "Уточните зону ответственности каждого работника и порядок взаимодействия.",
            "Напомните право приостановить работу, если требования безопасности невозможно соблюдать.",
        ),
    ),
)

private data class KnowledgeCard(val title: String, val body: List<String>, val source: String)

private val knowledgeCards = listOf(
    KnowledgeCard(
        "Что проверить перед началом работ",
        listOf(
            "Требования наряда-допуска понятны исполнителям.",
            "Меры безопасности, указанные в наряде-допуске, выполнены.",
            "Инструмент, оборудование, СИЗ и СКЗ исправны и готовы к применению.",
        ),
        "Основные правила безопасности / РОИ",
    ),
    KnowledgeCard(
        "Если изменились условия работы",
        listOf(
            "Остановите работу.",
            "Сообщите руководителю.",
            "Повторно обсудите опасности, меры безопасности и порядок действий.",
        ),
        "Пять шагов безопасности / РОИ",
    ),
    KnowledgeCard(
        "Когда нужен повторный инструктаж",
        listOf(
            "Изменилась производственная задача.",
            "Изменился состав исполнителей.",
            "Изменилось место проведения работ.",
            "Работы были остановлены или выявлены ранее неучтённые опасности.",
        ),
        "Памятка «Риск ориентированный инструктаж»",
    ),
    KnowledgeCard(
        "Работы на высоте",
        listOf(
            "Проверьте исправность системы защиты от падения перед использованием.",
            "Проверьте устойчивость и состояние лесов, подмостей и лестниц.",
            "Не продолжайте работу при недостаточной видимости и других небезопасных условиях.",
        ),
        "Основные правила безопасности",
    ),
    KnowledgeCard(
        "Изоляция источников энергии",
        listOf(
            "Перед ремонтом и обслуживанием изолируйте опасные источники энергии.",
            "Проверьте блокировки и предупреждающие знаки.",
            "Не снимайте блокировки до полного завершения работ и проверки оборудования.",
        ),
        "Основные правила безопасности",
    ),
    KnowledgeCard(
        "Газоанализатор и СИЗОД",
        listOf(
            "Проверьте исправность газоанализатора, СИЗОД и спасательного оборудования.",
            "Контролируйте воздушную среду в соответствии с условиями проведения работ.",
            "При срабатывании газоанализатора или признаках отравления немедленно прекратите работу.",
        ),
        "Основные правила безопасности",
    ),
)

@Composable
fun InstructionAssistantScreen(state: FormState, modifier: Modifier = Modifier) {
    var view by remember { mutableStateOf(AssistantView.HOME) }
    var step by remember { mutableStateOf(1) }
    var selectedRiskIds by remember { mutableStateOf(setOf<String>()) }
    var completedAt by remember { mutableStateOf(loadCompletion(LocalContext.current, state.permitNumber)) }

    when (view) {
        AssistantView.HOME -> AssistantHome(
            state = state,
            completedAt = completedAt,
            onStart = { step = 1; view = AssistantView.FLOW },
            onKnowledge = { view = AssistantView.KNOWLEDGE },
            onOpenStep = { target -> step = target; view = AssistantView.FLOW },
            modifier = modifier,
        )
        AssistantView.FLOW -> AssistantFlow(
            state = state,
            step = step,
            selectedRiskIds = selectedRiskIds,
            onRiskToggle = { id -> selectedRiskIds = selectedRiskIds.toMutableSet().also { if (!it.add(id)) it.remove(id) } },
            onBackHome = { view = AssistantView.HOME },
            onPrevious = { if (step > 1) step -= 1 else view = AssistantView.HOME },
            onNext = { if (step < 5) step += 1 },
            onComplete = {
                val value = LocalDateTime.now().format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm"))
                saveCompletion(LocalContext.current, state.permitNumber, value)
                completedAt = value
                view = AssistantView.HOME
            },
            modifier = modifier,
        )
        AssistantView.KNOWLEDGE -> AssistantKnowledge(
            onBack = { view = AssistantView.HOME },
            modifier = modifier,
        )
    }
}

private fun completionKey(permitNumber: String): String = "instruction_${permitNumber.trim().uppercase().ifBlank { "general" }}"

private fun loadCompletion(context: Context, permitNumber: String): String =
    context.getSharedPreferences("rpo_instruction_assistant", Context.MODE_PRIVATE)
        .getString(completionKey(permitNumber), "")
        .orEmpty()

private fun saveCompletion(context: Context, permitNumber: String, value: String) {
    context.getSharedPreferences("rpo_instruction_assistant", Context.MODE_PRIVATE)
        .edit()
        .putString(completionKey(permitNumber), value)
        .apply()
}

@Composable
private fun AssistantHome(
    state: FormState,
    completedAt: String,
    onStart: () -> Unit,
    onKnowledge: () -> Unit,
    onOpenStep: (Int) -> Unit,
    modifier: Modifier,
) {
    Column(
        modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Помощник при инструктаже", color = AssistantNavy, fontSize = 24.sp, fontWeight = FontWeight.Black)
        Text(
            "Короткие подсказки для проведения риск-ориентированного инструктажа перед началом работ.",
            color = AssistantMuted,
            fontSize = 12.sp,
        )
        Surface(color = Color(0xFFEAF3FF), shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
            Text(
                "РОИ — модель проведения инструктажа и не является отдельным видом инструктажа.",
                Modifier.padding(12.dp),
                color = AssistantNavy,
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
        PermitAssistantCard(state)
        if (completedAt.isNotBlank()) {
            Surface(color = Color(0xFFEAF8EF), shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
                Text("✓ Последнее прохождение помощника: $completedAt", Modifier.padding(12.dp), color = AssistantGreen, fontWeight = FontWeight.Bold, fontSize = 11.sp)
            }
        }
        Surface(color = Color.White, shape = RoundedCornerShape(18.dp), shadowElevation = 1.dp, modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Что сделать сейчас", color = AssistantNavy, fontWeight = FontWeight.Black, fontSize = 18.sp)
                Surface(
                    color = Color(0xFFEAF3FF),
                    shape = RoundedCornerShape(15.dp),
                    modifier = Modifier.fillMaxWidth().clickable(onClick = onStart),
                ) {
                    Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                        AssistantEmoji("▶", AssistantBlue)
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text("Провести инструктаж", fontWeight = FontWeight.Black, fontSize = 16.sp, color = AssistantNavy)
                            Text("5 последовательных шагов", color = AssistantMuted, fontSize = 11.sp)
                        }
                        Text("›", color = AssistantBlue, fontSize = 28.sp)
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                    AssistantShortcut("🛡", "Основные\nопасности", Modifier.weight(1f)) { onOpenStep(2) }
                    AssistantShortcut("⛑", "Меры\nбезопасности", Modifier.weight(1f)) { onOpenStep(3) }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                    AssistantShortcut("⚠", "Нештатная\nситуация", Modifier.weight(1f)) { onOpenStep(4) }
                    AssistantShortcut("📖", "Мини-база\nзнаний", Modifier.weight(1f), onKnowledge)
                }
            }
        }
        AssistantProgress(step = 0)
        Button(
            onClick = onStart,
            modifier = Modifier.fillMaxWidth().height(54.dp),
            colors = ButtonDefaults.buttonColors(containerColor = AssistantBlue),
            shape = RoundedCornerShape(15.dp),
        ) { Text("▶  Начать инструктаж", fontWeight = FontWeight.Black, fontSize = 16.sp) }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun PermitAssistantCard(state: FormState) {
    val permit = state.permitNumber.trim().uppercase()
    Surface(color = Color.White, shape = RoundedCornerShape(18.dp), shadowElevation = 1.dp, modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            AssistantEmoji("📄", AssistantBlue)
            Spacer(Modifier.width(11.dp))
            Column(Modifier.weight(1f)) {
                Text(if (permit.isBlank()) "НД не выбран" else "НД $permit", color = AssistantNavy, fontWeight = FontWeight.Black, fontSize = 17.sp)
                Text(state.structuralUnit.ifBlank { "Выберите НД во вкладке «Работа»" }, color = AssistantMuted, fontSize = 11.sp)
                if (state.workerName.isNotBlank()) Text(state.workerName, color = AssistantMuted, fontSize = 11.sp)
            }
            Surface(color = Color(0xFFE7F7EC), shape = RoundedCornerShape(50)) {
                Text("Перед началом работ", Modifier.padding(horizontal = 9.dp, vertical = 6.dp), color = AssistantGreen, fontWeight = FontWeight.Bold, fontSize = 9.sp)
            }
        }
    }
}

@Composable
private fun AssistantShortcut(icon: String, title: String, modifier: Modifier, onClick: () -> Unit) {
    Surface(
        color = Color.White,
        shape = RoundedCornerShape(14.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFDCE6F3)),
        modifier = modifier.clickable(onClick = onClick),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(icon, fontSize = 22.sp)
            Spacer(Modifier.width(8.dp))
            Text(title, Modifier.weight(1f), color = AssistantNavy, fontWeight = FontWeight.Bold, fontSize = 12.sp)
            Text("›", color = AssistantMuted, fontSize = 21.sp)
        }
    }
}

@Composable
private fun AssistantEmoji(text: String, accent: Color) {
    Box(Modifier.size(46.dp).background(accent.copy(alpha = .11f), CircleShape), contentAlignment = Alignment.Center) {
        Text(text, fontSize = 22.sp)
    }
}

@Composable
private fun AssistantFlow(
    state: FormState,
    step: Int,
    selectedRiskIds: Set<String>,
    onRiskToggle: (String) -> Unit,
    onBackHome: () -> Unit,
    onPrevious: () -> Unit,
    onNext: () -> Unit,
    onComplete: () -> Unit,
    modifier: Modifier,
) {
    Column(
        modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Инструктаж: шаг $step из 5", color = AssistantNavy, fontSize = 23.sp, fontWeight = FontWeight.Black)
        when (step) {
            1 -> StepOne()
            2 -> StepTwo(selectedRiskIds, onRiskToggle)
            3 -> StepThree(selectedRiskIds)
            4 -> StepFour()
            else -> StepFive(state)
        }
        AssistantProgress(step)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (step > 1) OutlinedButton(onClick = onPrevious, modifier = Modifier.weight(.8f), shape = RoundedCornerShape(14.dp)) { Text("Назад") }
            else TextButton(onClick = onBackHome, modifier = Modifier.weight(.8f)) { Text("К обзору") }
            if (step < 5) {
                Button(
                    onClick = onNext,
                    modifier = Modifier.weight(1.5f).height(50.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = AssistantBlue),
                    shape = RoundedCornerShape(14.dp),
                ) { Text(nextStepLabel(step), fontWeight = FontWeight.Bold) }
            } else {
                Button(
                    onClick = onComplete,
                    modifier = Modifier.weight(1.5f).height(50.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = AssistantGreen),
                    shape = RoundedCornerShape(14.dp),
                ) { Text("Завершить помощник", fontWeight = FontWeight.Bold) }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

private fun nextStepLabel(step: Int): String = when (step) {
    1 -> "Далее: опасности"
    2 -> "Далее: меры"
    3 -> "Далее: нештатные"
    else -> "Далее: готовность"
}

@Composable
private fun StepOne() {
    Text("Обсудите характер предстоящей работы", color = AssistantNavy, fontWeight = FontWeight.Black, fontSize = 18.sp)
    Text("Совместно с исполнителями проговорите, что и как будет выполняться.", color = AssistantMuted, fontSize = 12.sp)
    AssistantChecklistCard(
        listOf(
            "📋" to ("Последовательность этапов и операций" to "Обсудите, какие работы будут выполняться и в какой последовательности."),
            "👥" to ("Зона ответственности каждого работника" to "Уточните роли и обязанности участников работ."),
            "🔧" to ("Состояние инструмента и оборудования" to "Проверьте исправность и пригодность к работе."),
            "⛑" to ("Наличие и исправность СИЗ и СКЗ" to "Убедитесь, что необходимые средства защиты есть и исправны."),
        )
    )
    Surface(color = Color(0xFFFFF4E8), shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
        Text("💡 Подсказка: попросите одного из работников кратко повторить порядок действий.", Modifier.padding(12.dp), color = Color(0xFF9B4C00), fontWeight = FontWeight.SemiBold, fontSize = 11.sp)
    }
}

@Composable
private fun AssistantChecklistCard(items: List<Pair<String, Pair<String, String>>>) {
    Surface(color = Color.White, shape = RoundedCornerShape(18.dp), shadowElevation = 1.dp, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            items.forEachIndexed { index, item ->
                Row(Modifier.padding(vertical = 9.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(item.first, fontSize = 23.sp)
                    Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)) {
                        Text(item.second.first, color = AssistantNavy, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        Text(item.second.second, color = AssistantMuted, fontSize = 10.sp)
                    }
                }
                if (index != items.lastIndex) HorizontalDivider(color = Color(0xFFE7EDF5))
            }
        }
    }
}

@Composable
private fun StepTwo(selectedRiskIds: Set<String>, onRiskToggle: (String) -> Unit) {
    Text("Определите основные опасности", color = AssistantNavy, fontWeight = FontWeight.Black, fontSize = 18.sp)
    Text("Выберите опасности, которые нужно обсудить с бригадой перед началом работ.", color = AssistantMuted, fontSize = 12.sp)
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        assistantRisks.chunked(2).forEach { pair ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                pair.forEach { risk ->
                    val selected = risk.id in selectedRiskIds
                    Surface(
                        color = if (selected) Color(0xFFEAF3FF) else Color.White,
                        shape = RoundedCornerShape(14.dp),
                        border = androidx.compose.foundation.BorderStroke(if (selected) 2.dp else 1.dp, if (selected) AssistantBlue else Color(0xFFDCE6F3)),
                        modifier = Modifier.weight(1f).clickable { onRiskToggle(risk.id) },
                    ) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(risk.icon, fontSize = 22.sp)
                            Spacer(Modifier.width(7.dp))
                            Text(risk.title, Modifier.weight(1f), color = AssistantNavy, fontWeight = FontWeight.Bold, fontSize = 11.sp)
                            Text(if (selected) "✓" else "○", color = if (selected) AssistantBlue else AssistantMuted, fontWeight = FontWeight.Black)
                        }
                    }
                }
                if (pair.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
    Surface(color = Color(0xFFEAF3FF), shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
        Text("ℹ Выбранные опасности будут использованы в подсказках по мерам безопасности.", Modifier.padding(12.dp), color = AssistantNavy, fontSize = 11.sp)
    }
}

@Composable
private fun StepThree(selectedRiskIds: Set<String>) {
    Text("Обсудите меры безопасности", color = AssistantNavy, fontWeight = FontWeight.Black, fontSize = 18.sp)
    Text("Для каждого выявленного риска проговорите конкретные меры защиты.", color = AssistantMuted, fontSize = 12.sp)
    val selected = assistantRisks.filter { it.id in selectedRiskIds }
    if (selected.isEmpty()) {
        Surface(color = Color(0xFFFFF4E8), shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
            Text("На предыдущем шаге опасности не выбраны. Используйте общую последовательность: устранить источник → ограничить контакт → применить организационные меры и СИЗ.", Modifier.padding(13.dp), color = Color(0xFF8A4A00), fontSize = 11.sp)
        }
    } else {
        selected.forEach { risk ->
            Surface(color = Color.White, shape = RoundedCornerShape(16.dp), shadowElevation = 1.dp, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(13.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("${risk.icon} ${risk.title}", color = AssistantNavy, fontWeight = FontWeight.Black, fontSize = 14.sp)
                    risk.measures.forEach { Text("• $it", color = AssistantMuted, fontSize = 11.sp) }
                }
            }
        }
    }
    Surface(color = Color(0xFFEAF8EF), shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
        Text("Напомните: каждый исполнитель имеет право отказаться от работы или приостановить её, если требования безопасности невозможно соблюдать, и должен сообщить об этом руководителю.", Modifier.padding(13.dp), color = AssistantGreen, fontWeight = FontWeight.SemiBold, fontSize = 11.sp)
    }
}

@Composable
private fun StepFour() {
    Text("Обсудите действия в нештатной ситуации", color = AssistantNavy, fontWeight = FontWeight.Black, fontSize = 18.sp)
    Text("Бригада должна заранее понимать порядок действий при изменении обстановки.", color = AssistantMuted, fontSize = 12.sp)
    AssistantChecklistCard(
        listOf(
            "⚠" to ("Что может пойти не так" to "Обсудите возможные непредвиденные ситуации для конкретной работы."),
            "🛑" to ("Остановка работы" to "При изменении условий прекратите выполнение операции и сообщите руководителю."),
            "🚪" to ("Эвакуация" to "Обсудите порядок выхода из опасной зоны и место безопасного сбора, если это предусмотрено объектом."),
            "📞" to ("Связь" to "Проверьте наличие и исправность средств связи и уточните используемые на объекте номера экстренных служб."),
        )
    )
}

@Composable
private fun StepFive(state: FormState) {
    Text("Определите готовность приступить к безопасному выполнению работ", color = AssistantNavy, fontWeight = FontWeight.Black, fontSize = 18.sp)
    Text("Завершите инструктаж коротким устным опросом и убедитесь, что у работников не осталось вопросов.", color = AssistantMuted, fontSize = 12.sp)
    Surface(color = Color.White, shape = RoundedCornerShape(18.dp), shadowElevation = 1.dp, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Задайте 2–3 вопроса", color = AssistantNavy, fontWeight = FontWeight.Black, fontSize = 15.sp)
            Text("1. Какова последовательность вашей работы?", fontSize = 12.sp)
            Text("2. Какие основные опасности есть на этом рабочем месте?", fontSize = 12.sp)
            Text("3. Что вы сделаете, если условия работы изменятся?", fontSize = 12.sp)
            Text("4. Какие меры защиты необходимо соблюдать?", fontSize = 12.sp)
        }
    }
    Surface(color = Color(0xFFEAF8EF), shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(13.dp)) {
            Text("Перед завершением", color = AssistantGreen, fontWeight = FontWeight.Black, fontSize = 13.sp)
            Text("• Выясните, есть ли дополнительные вопросы у работников.", color = AssistantMuted, fontSize = 11.sp)
            Text("• Проверьте знания устным опросом по специфике работы и технологическим операциям.", color = AssistantMuted, fontSize = 11.sp)
            Text("• Решение о готовности к безопасному выполнению работ принимает ответственное лицо.", color = AssistantMuted, fontSize = 11.sp)
            if (state.permitNumber.isNotBlank()) Text("НД: ${state.permitNumber.trim().uppercase()}", color = AssistantNavy, fontWeight = FontWeight.Bold, fontSize = 11.sp, modifier = Modifier.padding(top = 6.dp))
        }
    }
}

@Composable
private fun AssistantProgress(step: Int) {
    Surface(color = Color.White, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Text("РОИ — шаги инструктажа", color = AssistantNavy, fontWeight = FontWeight.Bold, fontSize = 12.sp)
            Spacer(Modifier.height(8.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
                val labels = listOf("Подготовка", "Опасности", "Меры", "Нештатные", "Готовность")
                labels.forEachIndexed { index, label ->
                    val active = step == index + 1
                    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.weight(1f)) {
                        Box(
                            Modifier.size(30.dp).background(if (active) AssistantBlue else Color(0xFFEAF0F7), CircleShape),
                            contentAlignment = Alignment.Center,
                        ) { Text("${index + 1}", color = if (active) Color.White else AssistantMuted, fontWeight = FontWeight.Black, fontSize = 11.sp) }
                        Spacer(Modifier.height(4.dp))
                        Text(label, color = if (active) AssistantBlue else AssistantMuted, fontSize = 8.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun AssistantKnowledge(onBack: () -> Unit, modifier: Modifier) {
    var query by remember { mutableStateOf("") }
    val filtered = knowledgeCards.filter { card ->
        query.isBlank() || (card.title + " " + card.body.joinToString(" ")).contains(query.trim(), ignoreCase = true)
    }
    Column(
        modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("Мини-база знаний", color = AssistantNavy, fontSize = 24.sp, fontWeight = FontWeight.Black)
        Text("Краткие подсказки по материалам РОИ, методики «Пять шагов» и основных правил безопасности.", color = AssistantMuted, fontSize = 12.sp)
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("Что нужно уточнить?") },
            singleLine = true,
            shape = RoundedCornerShape(14.dp),
        )
        if (filtered.isEmpty()) {
            Surface(color = Color.White, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth()) {
                Text("По запросу ничего не найдено в локальной базе подсказок.", Modifier.padding(16.dp), color = AssistantMuted)
            }
        }
        filtered.forEach { card ->
            Surface(color = Color.White, shape = RoundedCornerShape(16.dp), shadowElevation = 1.dp, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Text(card.title, color = AssistantNavy, fontWeight = FontWeight.Black, fontSize = 14.sp)
                    card.body.forEach { Text("• $it", color = AssistantMuted, fontSize = 11.sp) }
                    Text("Источник: ${card.source}", color = AssistantBlue, fontSize = 9.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 4.dp))
                }
            }
        }
        Button(onClick = onBack, modifier = Modifier.fillMaxWidth().height(50.dp), shape = RoundedCornerShape(14.dp)) {
            Text("Вернуться к инструктажу", fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.height(8.dp))
    }
}
