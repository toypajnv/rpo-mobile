package ru.rpo.mobile.ui

import android.app.Application
import android.provider.Settings
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.Gson
import ru.rpo.mobile.data.ApiFactory
import ru.rpo.mobile.data.ApiError
import ru.rpo.mobile.data.EventRequest
import ru.rpo.mobile.data.EventResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID

private val dateFmt = DateTimeFormatter.ofPattern("dd.MM.yyyy")
private val timeFmt = DateTimeFormatter.ofPattern("HH:mm")

data class FormState(
    val workerName: String = "",
    val permitNumber: String = "",
    val stage: Stage = stages.first(),
    val date: String = LocalDate.now().format(dateFmt),
    val time: String = LocalTime.now().format(timeFmt),
    val customValue: String = "",
    val comment: String = "",
    val errors: Map<String, String> = emptyMap(),
    val sending: Boolean = false,
    val message: String? = null,
    val success: Boolean = false,
)

class RpoViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("rpo", 0)
    private val _state = MutableStateFlow(FormState(workerName = prefs.getString("worker_name", "") ?: ""))
    val state: StateFlow<FormState> = _state.asStateFlow()
    private val _history = MutableStateFlow<List<EventResponse>>(emptyList())
    val history: StateFlow<List<EventResponse>> = _history.asStateFlow()
    val deviceId: String = Settings.Secure.getString(app.contentResolver, Settings.Secure.ANDROID_ID) ?: "android-${UUID.randomUUID()}"

    fun updateWorker(v:String){ _state.value=_state.value.copy(workerName=v, message=null); prefs.edit().putString("worker_name",v).apply() }
    fun updatePermit(v:String){ _state.value=_state.value.copy(permitNumber=v.uppercase(), message=null) }
    fun updateStage(v:Stage){ _state.value=_state.value.copy(stage=v, customValue="", comment="", message=null) }
    fun updateDate(v:String){ _state.value=_state.value.copy(date=v, message=null) }
    fun updateTime(v:String){ _state.value=_state.value.copy(time=v, message=null) }
    fun updateCustom(v:String){ _state.value=_state.value.copy(customValue=v, message=null) }
    fun updateComment(v:String){ _state.value=_state.value.copy(comment=v.take(500), message=null) }
    fun now(){ val n=LocalDateTime.now(); _state.value=_state.value.copy(date=n.toLocalDate().format(dateFmt), time=n.toLocalTime().format(timeFmt), message=null) }

    private fun validate(s:FormState): Pair<Map<String,String>, LocalDateTime?> {
        val e=mutableMapOf<String,String>()
        if(s.workerName.trim().length<3)e["worker"]="Укажите ФИО работника"
        if(s.permitNumber.trim().length<3)e["permit"]="Введите номер наряда-допуска"
        val dt=try{ LocalDateTime.of(LocalDate.parse(s.date,dateFmt),LocalTime.parse(s.time,timeFmt)) }catch(_:Exception){ e["datetime"]="Проверьте дату и время";null }
        if(dt!=null && dt.isAfter(LocalDateTime.now().plusMinutes(5)))e["datetime"]="Дата и время не могут быть в будущем"
        if(s.stage.commentRequired && s.comment.trim().length<3)e["comment"]="Укажите причину остановки"
        if(s.stage.kind==StageKind.TEXT && s.customValue.trim().length<2)e["value"]="Заполните значение этапа"
        return e to dt
    }

    fun send(){
        val s=_state.value; val (errors,dt)=validate(s); if(errors.isNotEmpty()||dt==null){_state.value=s.copy(errors=errors,message="Проверьте заполнение",success=false);return}
        _state.value=s.copy(errors=emptyMap(),sending=true,message=null)
        viewModelScope.launch {
            try{
                val value=if(s.stage.kind==StageKind.DATETIME) dt.format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm")) else s.customValue.trim()
                val req=EventRequest(UUID.randomUUID().toString(),deviceId,s.workerName.trim(),s.permitNumber.trim(),s.stage.key,s.stage.title,dt.atZone(ZoneId.systemDefault()).toOffsetDateTime().toString(),value,s.comment.trim())
                val r=ApiFactory.api.sendEvent(req)
                if(r.isSuccessful){ _state.value=_state.value.copy(sending=false,message="Данные переданы на сервер",success=true); loadHistory() }
                else { val detail=try{Gson().fromJson(r.errorBody()?.string(),ApiError::class.java).detail}catch(_:Exception){null}; _state.value=_state.value.copy(sending=false,message=detail?:"Сервер отклонил данные",success=false) }
            }catch(e:Exception){ _state.value=_state.value.copy(sending=false,message="Нет связи с сервером. Проверьте интернет и повторите отправку.",success=false) }
        }
    }

    fun loadHistory(){ viewModelScope.launch { try{ val r=ApiFactory.api.history(deviceId); if(r.isSuccessful)_history.value=r.body().orEmpty() }catch(_:Exception){} } }
}
