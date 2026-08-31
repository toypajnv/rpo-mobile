package ru.rpo.mobile.ui

import android.content.Context
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
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.gson.Gson
import ru.rpo.mobile.data.PermitApprovalSummary

private val DenyRed = Color(0xFFB51616)
private val DenyDarkRed = Color(0xFF861010)
private val DenyLight = Color(0xFFFFECEA)
private const val DENIAL_PREFS = "rpo_denial_cache"

private fun denialKey(permit: String) = "denied_${permit.trim().uppercase()}"

private fun loadCachedDenial(context: Context, permit: String): PermitApprovalSummary? {
    if (permit.isBlank()) return null
    val raw = context.getSharedPreferences(DENIAL_PREFS, Context.MODE_PRIVATE)
        .getString(denialKey(permit), null) ?: return null
    return runCatching { Gson().fromJson(raw, PermitApprovalSummary::class.java) }
        .getOrNull()
        ?.takeIf { it.status == "denied" }
}

private fun saveCachedDenial(context: Context, permit: String, denial: PermitApprovalSummary?) {
    if (permit.isBlank()) return
    val edit = context.getSharedPreferences(DENIAL_PREFS, Context.MODE_PRIVATE).edit()
    if (denial?.status == "denied") edit.putString(denialKey(permit), Gson().toJson(denial))
    else edit.remove(denialKey(permit))
    edit.apply()
}

@Composable
fun RpoDecisionAwareApp(vm: RpoViewModel = viewModel()) {
    val state by vm.state.collectAsState()
    val context = LocalContext.current
    val permit = state.permitNumber.trim().uppercase()
    var cachedDenial by remember(permit) { mutableStateOf(loadCachedDenial(context, permit)) }
    val liveApproval = state.approvalSummary

    LaunchedEffect(permit, liveApproval) {
        if (permit.isBlank()) {
            cachedDenial = null
        } else if (liveApproval?.status == "denied") {
            saveCachedDenial(context, permit, liveApproval)
            cachedDenial = liveApproval
        } else if (liveApproval != null) {
            // A successful server snapshot without a denial is authoritative and
            // clears the fail-safe cache left from an earlier operator prohibition.
            saveCachedDenial(context, permit, null)
            cachedDenial = null
        }
    }

    val denial = liveApproval?.takeIf { it.status == "denied" } ?: cachedDenial
    if (denial != null && permit.isNotEmpty()) {
        DeniedPermitScreen(state, denial, vm)
    } else {
        RpoUxApp(vm)
    }
}

@Composable
private fun DeniedPermitScreen(state: FormState, denial: PermitApprovalSummary, vm: RpoViewModel) {
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
