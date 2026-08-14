package ru.rpo.mobile.ui

import android.app.Application
import android.provider.Settings
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.Gson
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import ru.rpo.mobile.BuildConfig
import ru.rpo.mobile.data.ApiError
import ru.rpo.mobile.data.ApiFactory
import ru.rpo.mobile.data.EventRequest
import ru.rpo.mobile.data.EventResponse
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID

private val dateFmt = DateTimeFormatter.ofPattern("dd.MM.yyyy")
private val timeFmt = DateTimeFormatter.ofPattern("HH:mm")
private val valueFmt = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm")
private val permitRegex = Regex("^[0-9A-ZА-ЯЁ._/\\- ]{3,80}$")
private val permitCharRegex = Regex("[0-9A-ZА-ЯЁ._/\\- ]")

data class FormState(
    val workerName: String = "",
    val permitNumber: String = "",
    val stage: Stage = stages.first(),
    val primaryDate: String = LocalDate.now().format(dateFmt),
    val primaryTime: String = LocalTime.now().format(timeFmt),
    val secondaryDate: String = LocalDate.now().format(dateFmt),
    val secondaryTime: String = LocalTime.now().format(timeFmt),
    val extensionDate: String = LocalDate.now().plusDays(1).format(dateFmt),
    val stopReason: String = "",
    val comment: String = "",
    val errors: Map<String, String> = emptyMap(),
    val sending: Boolean = false,
    val message: String? = null,
    val success: Boolean = false,
)

private data class PendingEvent(
    val stage: StageEvent,
    val eventTime: LocalDateTime,
    val fieldValue: String,
    val comment: String,
)

private data class ValidationResult(
    val errors: Map<String, String>,
    val events: List<PendingEvent>,
)

class RpoViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("rpo", 0)
    private val _state = MutableStateFlow(FormState(workerName = prefs.getString("worker_name", "") ?: ""))
    val state: StateFlow<FormState> = _state.asStateFlow()

    private val _history = MutableStateFlow<List<EventResponse>>(emptyList())
    val history: StateFlow<List<EventResponse>> = _history.asStateFlow()

    val deviceId: String = Settings.Secure.getString(app.contentResolver, Settings.Secure.ANDROID_ID)
        ?: "android-${UUID.randomUUID()}"

    fun updateWorker(v: String) {
        _state.value = _state.value.copy(workerName = v.take(180), message = null)
        prefs.edit().putString("worker_name", v.take(180)).apply()
    }

    fun updatePermit(v: String) {
        val value = v.uppercase().take(80)
        val hasInvalidChar = value.any { !permitCharRegex.matches(it.toString()) }
        val errors = _state.value.errors.toMutableMap()
        if (hasInvalidChar) errors["permit"] = "Допустимы только буквы, цифры, пробел и символы . _ / -"
        else errors.remove("permit")
        _state.value = _state.value.copy(permitNumber = value, errors = errors, message = null)
    }

    fun updateStage(v: Stage) {
        val now = LocalDateTime.now()
        _state.value = _state.value.copy(
            stage = v,
            primaryDate = now.toLocalDate().format(dateFmt),
            primaryTime = now.toLocalTime().format(timeFmt),
            secondaryDate = now.toLocalDate().format(dateFmt),
            secondaryTime = now.toLocalTime().format(timeFmt),
            extensionDate = now.toLocalDate().plusDays(1).format(dateFmt),
            stopReason = "",
            comment = "",
            errors = _state.value.errors.filterKeys { it == "worker" || it == "permit" },
            message = null,
        )
    }

    fun updatePrimaryDate(v: String) { _state.value = _state.value.copy(primaryDate = v.take(10), message = null) }
    fun updatePrimaryTime(v: String) { _state.value = _state.value.copy(primaryTime = v.take(5), message = null) }
    fun updateSecondaryDate(v: String) { _state.value = _state.value.copy(secondaryDate = v.take(10), message = null) }
    fun updateSecondaryTime(v: String) { _state.value = _state.value.copy(secondaryTime = v.take(5), message = null) }
    fun updateExtensionDate(v: String) { _state.value = _state.value.copy(extensionDate = v.take(10), message = null) }
    fun updateStopReason(v: String) { _state.value = _state.value.copy(stopReason = v.take(500), message = null) }
    fun updateComment(v: String) { _state.value = _state.value.copy(comment = v.take(500), message = null) }

    fun nowPrimary() {
        val n = LocalDateTime.now()
        _state.value = _state.value.copy(
            primaryDate = n.toLocalDate().format(dateFmt),
            primaryTime = n.toLocalTime().format(timeFmt),
            message = null,
        )
    }

    fun nowSecondary() {
        val n = LocalDateTime.now()
        _state.value = _state.value.copy(
            secondaryDate = n.toLocalDate().format(dateFmt),
            secondaryTime = n.toLocalTime().format(timeFmt),
            message = null,
        )
    }

    fun extensionTomorrow() {
        _state.value = _state.value.copy(
            extensionDate = LocalDate.now().plusDays(1).format(dateFmt),
            message = null,
        )
    }

    private fun parseDateTime(date: String, time: String, errorKey: String, errors: MutableMap<String, String>): LocalDateTime? {
        val dt = try {
            LocalDateTime.of(LocalDate.parse(date, dateFmt), LocalTime.parse(time, timeFmt))
        } catch (_: Exception) {
            errors[errorKey] = "Проверьте дату и время"
            return null
        }
        val now = LocalDateTime.now()
        if (dt.isAfter(now.plusMinutes(5))) errors[errorKey] = "Дата и время не могут быть в будущем"
        if (dt.isBefore(now.minusDays(45))) errors[errorKey] = "Дата события слишком старая"
        return dt
    }

    private fun validate(s: FormState): ValidationResult {
        val errors = mutableMapOf<String, String>()
        val events = mutableListOf<PendingEvent>()

        if (s.workerName.trim().length < 3) errors["worker"] = "Укажите ФИО работника"
        val permit = s.permitNumber.trim().uppercase()
        if (!permitRegex.matches(permit)) {
            errors["permit"] = if (permit.length < 3) {
                "Введите номер наряда-допуска"
            } else {
                "Номер НД содержит недопустимые символы"
            }
        }

        when (s.stage.kind) {
            StageKind.RANGE_DATETIME -> {
                val start = parseDateTime(s.primaryDate, s.primaryTime, "primary", errors)
                val end = parseDateTime(s.secondaryDate, s.secondaryTime, "secondary", errors)
                if (start != null && end != null && end.isBefore(start)) {
                    errors["secondary"] = "Окончание не может быть раньше начала"
                }
                if (start != null && end != null && !end.isBefore(start) && errors["primary"] == null && errors["secondary"] == null) {
                    events += PendingEvent(s.stage.first, start, start.format(valueFmt), s.comment.trim())
                    val second = requireNotNull(s.stage.second)
                    events += PendingEvent(second, end, end.format(valueFmt), s.comment.trim())
                }
            }

            StageKind.DATETIME -> {
                val dt = parseDateTime(s.primaryDate, s.primaryTime, "primary", errors)
                if (dt != null && errors["primary"] == null) {
                    events += PendingEvent(s.stage.first, dt, dt.format(valueFmt), s.comment.trim())
                }
            }

            StageKind.STOP -> {
                val dt = parseDateTime(s.primaryDate, s.primaryTime, "primary", errors)
                if (s.stopReason.trim().length < 3) errors["stopReason"] = "Укажите причину остановки"
                if (dt != null && errors["primary"] == null && errors["stopReason"] == null) {
                    events += PendingEvent(s.stage.first, dt, dt.format(valueFmt), s.stopReason.trim())
                }
            }

            StageKind.EXTENSION_DATE -> {
                val extension = try {
                    LocalDate.parse(s.extensionDate, dateFmt)
                } catch (_: Exception) {
                    errors["extension"] = "Проверьте дату продления"
                    null
                }
                if (extension != null && extension.isBefore(LocalDate.now())) {
                    errors["extension"] = "Дата продления не может быть в прошлом"
                }
                if (extension != null && errors["extension"] == null) {
                    events += PendingEvent(
                        stage = s.stage.first,
                        eventTime = LocalDateTime.now(),
                        fieldValue = extension.format(dateFmt),
                        comment = s.comment.trim(),
                    )
                }
            }
        }

        return ValidationResult(errors, events)
    }

    fun send() {
        val s = _state.value
        val validation = validate(s)
        if (validation.errors.isNotEmpty() || validation.events.isEmpty()) {
            _state.value = s.copy(errors = validation.errors, message = "Проверьте заполнение", success = false)
            return
        }

        _state.value = s.copy(errors = emptyMap(), sending = true, message = null)
        viewModelScope.launch {
            try {
                for (event in validation.events) {
                    val req = EventRequest(
                        client_event_id = UUID.randomUUID().toString(),
                        device_id = deviceId,
                        worker_name = s.workerName.trim(),
                        permit_number = s.permitNumber.trim().uppercase(),
                        field_key = event.stage.key,
                        stage_label = event.stage.title,
                        event_time = event.eventTime.atZone(ZoneId.systemDefault()).toOffsetDateTime().toString(),
                        field_value = event.fieldValue,
                        comment = event.comment,
                    )
                    val response = ApiFactory.api.sendEvent(req)
                    if (!response.isSuccessful) {
                        val detail = try {
                            Gson().fromJson(response.errorBody()?.string(), ApiError::class.java).detail
                        } catch (_: Exception) {
                            null
                        }
                        _state.value = _state.value.copy(
                            sending = false,
                            message = detail ?: "Сервер отклонил данные",
                            success = false,
                        )
                        return@launch
                    }
                }

                _state.value = _state.value.copy(
                    sending = false,
                    message = if (validation.events.size > 1) "Этап передан на сервер (${validation.events.size} события)" else "Данные переданы на сервер",
                    success = true,
                )
                loadHistory()
            } catch (_: Exception) {
                val message = if (BuildConfig.SERVER_URL.contains("10.0.2.2")) {
                    "Сервер не настроен для телефона: эта сборка использует локальный адрес 10.0.2.2. Нужен адрес VPS."
                } else {
                    "Нет связи с сервером. Проверьте интернет и повторите отправку."
                }
                _state.value = _state.value.copy(sending = false, message = message, success = false)
            }
        }
    }

    fun loadHistory() {
        viewModelScope.launch {
            try {
                val response = ApiFactory.api.history(deviceId)
                if (response.isSuccessful) _history.value = response.body().orEmpty()
            } catch (_: Exception) {
            }
        }
    }
}
