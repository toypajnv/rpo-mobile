package ru.rpo.mobile.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel

private val DenyRed = Color(0xFFB51616)
private val DenyDarkRed = Color(0xFF861010)
private val DenyLight = Color(0xFFFFECEA)

@Composable
fun RpoDecisionAwareApp(vm: RpoViewModel = viewModel()) {
    val state by vm.state.collectAsState()
    val denial = state.approvalSummary?.takeIf { it.status == "denied" }
    if (denial != null && state.permitNumber.trim().isNotEmpty()) {
        DeniedPermitScreen(state, vm)
    } else {
        RpoUxApp(vm)
    }
}

@Composable
private fun DeniedPermitScreen(state: FormState, vm: RpoViewModel) {
    val denial = state.approvalSummary ?: return
    MaterialTheme {
        Surface(color = DenyRed, modifier = Modifier.fillMaxSize()) {
            Column(
                modifier = Modifier.fillMaxSize().padding(horizontal = 22.dp, vertical = 34.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Box(
                    modifier = Modifier.size(88.dp).background(Color.White, CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("!", color = DenyRed, fontSize = 56.sp, fontWeight = FontWeight.Black)
                }
                Spacer(Modifier.height(18.dp))
                Text(
                    "ПРОВЕДЕНИЕ РАБОТ\nЗАПРЕЩЕНО",
                    color = Color.White,
                    fontSize = 27.sp,
                    lineHeight = 30.sp,
                    fontWeight = FontWeight.Black,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(14.dp))
                Surface(
                    color = Color.White.copy(alpha = 0.14f),
                    shape = RoundedCornerShape(16.dp),
                ) {
                    Text(
                        "НД ${state.permitNumber.trim().uppercase()}",
                        modifier = Modifier.padding(horizontal = 18.dp, vertical = 11.dp),
                        color = Color.White,
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Black,
                    )
                }
                Spacer(Modifier.height(16.dp))
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    color = Color.White,
                    shape = RoundedCornerShape(20.dp),
                    shadowElevation = 6.dp,
                ) {
                    Column(Modifier.padding(18.dp)) {
                        Text("Этап, по которому принят запрет", color = Color(0xFF9B4A4A), fontSize = 12.sp)
                        Text(
                            denial.denied_stage.ifBlank { denial.denied_field_key.ifBlank { "Этап работ" } },
                            color = DenyDarkRed,
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Black,
                        )
                        Spacer(Modifier.height(14.dp))
                        Text("Причина запрета", color = Color(0xFF9B4A4A), fontSize = 12.sp)
                        Surface(color = DenyLight, shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
                            Text(
                                denial.denied_reason.ifBlank { "Оператор запретил проведение работ. Уточните причину у оператора." },
                                modifier = Modifier.padding(13.dp),
                                color = DenyDarkRed,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                    }
                }
                Spacer(Modifier.height(17.dp))
                Text(
                    "Не продолжайте работы по этому наряду-допуску до снятия запрета оператором. Статус проверяется автоматически.",
                    color = Color.White,
                    fontSize = 15.sp,
                    lineHeight = 20.sp,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(20.dp))
                Button(
                    onClick = { vm.updatePermit("") },
                    modifier = Modifier.fillMaxWidth().height(54.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = DenyDarkRed),
                    shape = RoundedCornerShape(14.dp),
                ) {
                    Text("Выбрать другой НД", fontWeight = FontWeight.Black, fontSize = 16.sp)
                }
            }
        }
    }
}
