package ru.rpo.mobile.ui

import android.app.Application
import android.net.ConnectivityManager
import android.net.Network
import android.provider.Settings
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import ru.rpo.mobile.data.EventRequest
import ru.rpo.mobile.data.EventResponse
import ru.rpo.mobile.data.PermitSnapshot
import ru.rpo.mobile.data.NetworkState
import ru.rpo.mobile.data.PendingEventStore
import ru.rpo.mobile.data.PendingSyncScheduler
import ru.rpo.mobile.data.QueueSyncEngine
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

data class PermitMemory(
    val permitNumber: String,
    val workerName: String,
    val lastUsedAt: Long,
)

data class FormState(
    val workerName: String = "",
    val permitNumber: String = "",
    val stage: Stage = stages.first(),
    val primaryDate: String = "",
    val primaryTime: String = "",
    val secondaryDate: String = "",
    val secondaryTime: String = "",
    val thirdDate: String = "",
    val thirdTime: String = "",
    val extensionDate: String = "",
    val stopReason: String = "",
    val comment: String = "",
    val errors: Map<String, String> = emptyMap(),
    val sending: Boolean = false,
    val message: String? = null,
    val success: Boolean = false,
    val pendingCount: Int = 0,
    val failedCount: Int = 0,
    val serverSavedStageIds: Set<String> = emptySet(),
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
    private val application = app
    private val prefs = app.getSharedPreferences("rpo", 0)
    private val gson = Gson()
    private val queueStore = PendingEventStore(app)
    private val connectivityManager = app.getSystemService(ConnectivityManager::class.java)
    private var permitLookupJob: Job? = null
    private var serverPermitSnapshot: PermitSnapshot? = null

    private val _state = MutableStateFlow(
        FormState(
            workerName = prefs.getString("worker_name", "") ?: "",
            pendingCount = queueStore.pendingCount(),
            failedCount = queueStore.failedCount(),
        )
    )
    val state: StateFlow<FormState> = _state.asStateFlow()

    private val _history = MutableStateFlow<List<EventResponse>>(emptyList())
    val history: StateFlow<List<EventResponse>> = _history.asStateFlow()

    private val _permitMemories = MutableStateFlow(loadPermitMemories())
    val permitMemories: StateFlow<List<PermitMemory>> = _permitMemories.asStateFlow()

    val deviceId: String = Settings.Secure.getString(app.contentResolver, Settings.Secure.ANDROID_ID)
        ?: "android-${UUID.randomUUID()}"

    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            viewModelScope.launch { syncPending(showMessage = false) }
        }
    }

    init {
        PendingSyncScheduler.schedule(app)
        runCatching { connectivityManager.registerDefaultNetworkCallback(networkCallback) }
        if (NetworkState.isConnected(app) && queueStore.pendingCount() > 0) {
            viewModelScope.launch { syncPending(showMessage = false) }
        }
    }

    override fun onCleared() {
        runCatching { connectivityManager.unregisterNetworkCallback(networkCallback) }
        super.onCleared()
    }

    private fun loadPermitMemories(): List<PermitMemory> {
        val raw = prefs.getString("permit_memories", "[]") ?: "[]"
        val type = object : TypeToken<List<PermitMemory>>() {}.type
        return try {
            (gson.fromJson<List<PermitMemory>>(raw, type) ?: emptyList()).sortedByDescending { it.lastUsedAt }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun rememberPermit(permitNumber: String, workerName: String) {
        val normalized = permitNumber.trim().uppercase()
        val updated = _permitMemories.value
            .filterNot { it.permitNumber.equals(normalized, ignoreCase = true) }
            .toMutableList()
        updated.add(0, PermitMemory(normalized, workerName.trim(), System.currentTimeMillis()))
        val limited = updated.take(30)
        prefs.edit().putString("permit_memories", gson.toJson(limited)).apply()
        _permitMemories.value = limited
    }

    private fun blankStageFields(base: FormState, stage: Stage = base.stage): FormState = base.copy(
        stage = stage,
        primaryDate = "",
        primaryTime = "",
        secondaryDate = "",
        secondaryTime = "",
        thirdDate = "",
        thirdTime = "",
        extensionDate = "",
        stopReason = "",
        comment = "",
        errors = base.errors.filterKeys { it == "worker" || it == "permit" },
        message = null,
    )

    private fun snapshotDateTime(snapshot: PermitSnapshot, key: String?): Pair<String, String> {
        if (key == null) return "" to ""
        val raw = snapshot.fields[key]?.field_value.orEmpty().trim()
        val parsed = runCatching { LocalDateTime.parse(raw, valueFmt) }.getOrNull() ?: return "" to ""
        return parsed.toLocalDate().format(dateFmt) to parsed.toLocalTime().format(timeFmt)
    }

    private fun applySnapshotToStage(base: FormState, stage: Stage, snapshot: PermitSnapshot?): FormState {
        val cleared = blankStageFields(base, stage)
        if (snapshot == null || !snapshot.permit_number.equals(base.permitNumber.trim(), ignoreCase = true)) return cleared
        val first = snapshotDateTime(snapshot, stage.first.key)
        val second = snapshotDateTime(snapshot, stage.second?.key)
        val third = snapshotDateTime(snapshot, stage.third?.key)
        val stageFields = listOfNotNull(stage.first.key, stage.second?.key, stage.third?.key).mapNotNull { snapshot.fields[it] }
        val commonComment = stageFields.firstOrNull { it.comment.isNotBlank() }?.comment.orEmpty()
        return cleared.copy(
            primaryDate = first.first,
            primaryTime = first.second,
            secondaryDate = second.first,
            secondaryTime = second.second,
            thirdDate = third.first,
            thirdTime = third.second,
            extensionDate = if (stage.kind == StageKind.EXTENSION_DATE) snapshot.fields[stage.first.key]?.field_value.orEmpty() else "",
            stopReason = if (stage.kind == StageKind.STOP) snapshot.fields[stage.first.key]?.comment.orEmpty() else "",
            comment = if (stage.kind == StageKind.STOP) "" else commonComment,
        )
    }

    private fun schedulePermitLookup(permitNumber: String, immediate: Boolean = false) {
        permitLookupJob?.cancel()
        val normalized = permitNumber.trim().uppercase()
        if (!permitRegex.matches(normalized)) {
            serverPermitSnapshot = null
            _state.value = _state.value.copy(serverSavedStageIds = emptySet())
            return
        }
        permitLookupJob = viewModelScope.launch {
            if (!immediate) delay(550)
            if (!NetworkState.isConnected(application)) return@launch
            try {
                val response = ru.rpo.mobile.data.ApiFactory.api.permit(normalized)
                if (_state.value.permitNumber.trim().uppercase() != normalized) return@launch
                if (response.isSuccessful) {
                    val snapshot = response.body() ?: return@launch
                    serverPermitSnapshot = snapshot
                    val filledKeys = snapshot.fields.filterValues { it.field_value.isNotBlank() }.keys
                    val worker = snapshot.worker_name.ifBlank { _state.value.workerName }
                    val base = _state.value.copy(
                        workerName = worker,
                        serverSavedStageIds = savedStageIdsForFieldKeys(filledKeys),
                        errors = _state.value.errors - "worker" - "permit",
                        message = "Ранее заполненные данные по НД загружены с сервера",
                        success = true,
                    )
                    _state.value = applySnapshotToStage(base, base.stage, snapshot)
                    if (worker.isNotBlank()) prefs.edit().putString("worker_name", worker).apply()
                } else if (response.code() == 404) {
                    serverPermitSnapshot = null
                    _state.value = _state.value.copy(serverSavedStageIds = emptySet())
                }
            } catch (_: Exception) {
                // Работа без сети остаётся доступной; серверное автозаполнение повторится при следующем вводе номера.
            }
        }
    }

    fun selectPermit(memory: PermitMemory) {
        val worker = memory.workerName.ifBlank { _state.value.workerName }
        _state.value = blankStageFields(_state.value).copy(
            permitNumber = memory.permitNumber,
            workerName = worker,
            serverSavedStageIds = emptySet(),
            errors = _state.value.errors - "permit" - "worker",
            message = null,
        )
        serverPermitSnapshot = null
        if (worker.isNotBlank()) prefs.edit().putString("worker_name", worker).apply()
        schedulePermitLookup(memory.permitNumber, immediate = true)
    }

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
        serverPermitSnapshot = null
        _state.value = blankStageFields(_state.value).copy(
            permitNumber = value,
            errors = errors,
            serverSavedStageIds = emptySet(),
            message = null,
        )
        schedulePermitLookup(value)
    }

    fun updateStage(v: Stage) {
        val snapshot = serverPermitSnapshot
        _state.value = applySnapshotToStage(_state.value, v, snapshot)
    }

    fun updatePrimaryDate(v: String) { _state.value = _state.value.copy(primaryDate = v.take(10), message = null) }
    fun updatePrimaryTime(v: String) { _state.value = _state.value.copy(primaryTime = v.take(5), message = null) }
    fun updateSecondaryDate(v: String) { _state.value = _state.value.copy(secondaryDate = v.take(10), message = null) }
    fun updateSecondaryTime(v: String) { _state.value = _state.value.copy(secondaryTime = v.take(5), message = null) }
    fun updateThirdDate(v: String) { _state.value = _state.value.copy(thirdDate = v.take(10), message = null) }
    fun updateThirdTime(v: String) { _state.value = _state.value.copy(thirdTime = v.take(5), message = null) }
    fun updateExtensionDate(v: String) { _state.value = _state.value.copy(extensionDate = v.take(10), message = null) }
    fun updateStopReason(v: String) { _state.value = _state.value.copy(stopReason = v.take(500), message = null) }
    fun updateComment(v: String) { _state.value = _state.value.copy(comment = v.take(500), message = null) }

    fun nowPrimary() {
        val n = LocalDateTime.now()
        _state.value = _state.value.copy(primaryDate = n.toLocalDate().format(dateFmt), primaryTime = n.toLocalTime().format(timeFmt), message = null)
    }

    fun nowSecondary() {
        val n = LocalDateTime.now()
        _state.value = _state.value.copy(secondaryDate = n.toLocalDate().format(dateFmt), secondaryTime = n.toLocalTime().format(timeFmt), message = null)
    }

    fun nowThird() {
        val n = LocalDateTime.now()
        _state.value = _state.value.copy(thirdDate = n.toLocalDate().format(dateFmt), thirdTime = n.toLocalTime().format(timeFmt), message = null)
    }

    fun extensionTomorrow() {
        _state.value = _state.value.copy(extensionDate = LocalDate.now().plusDays(1).format(dateFmt), message = null)
    }

    private fun parseDateTime(date: String, time: String, errorKey: String, errors: MutableMap<String, String>): LocalDateTime? {
        val result = parseOperationalDateTime(date, time)
        if (result.error != null) errors[errorKey] = result.error
        return result.value
    }

    private fun validate(s: FormState): ValidationResult {
        val errors = mutableMapOf<String, String>()
        val events = mutableListOf<PendingEvent>()

        if (s.workerName.trim().length < 3) errors["worker"] = "Укажите ФИО работника"
        val permit = s.permitNumber.trim().uppercase()
        if (!permitRegex.matches(permit)) {
            errors["permit"] = if (permit.length < 3) "Введите номер наряда-допуска" else "Номер НД содержит недопустимые символы"
        }

        when (s.stage.kind) {
            StageKind.RANGE_DATETIME -> {
                val start = parseDateTime(s.primaryDate, s.primaryTime, "primary", errors)
                val end = parseDateTime(s.secondaryDate, s.secondaryTime, "secondary", errors)
                if (start != null && end != null && end.isBefore(start)) errors["secondary"] = "Окончание не может быть раньше начала"
                if (start != null && end != null && !end.isBefore(start) && errors["primary"] == null && errors["secondary"] == null) {
                    events += PendingEvent(s.stage.first, start, start.format(valueFmt), s.comment.trim())
                    events += PendingEvent(requireNotNull(s.stage.second), end, end.format(valueFmt), s.comment.trim())
                }
            }

            StageKind.TRIPLE_DATETIME -> {
                val transfer = parseDateTime(s.primaryDate, s.primaryTime, "primary", errors)
                val start = parseDateTime(s.secondaryDate, s.secondaryTime, "secondary", errors)
                val end = parseDateTime(s.thirdDate, s.thirdTime, "third", errors)
                if (transfer != null && start != null && start.isBefore(transfer)) errors["secondary"] = "Начало работ не может быть раньше передачи"
                if (start != null && end != null && end.isBefore(start)) errors["third"] = "Окончание работ не может быть раньше начала"
                if (transfer != null && start != null && end != null && errors.keys.none { it in setOf("primary", "secondary", "third") }) {
                    events += PendingEvent(s.stage.first, transfer, transfer.format(valueFmt), s.comment.trim())
                    events += PendingEvent(requireNotNull(s.stage.second), start, start.format(valueFmt), s.comment.trim())
                    events += PendingEvent(requireNotNull(s.stage.third), end, end.format(valueFmt), s.comment.trim())
                }
            }

            StageKind.DATETIME -> {
                val dt = parseDateTime(s.primaryDate, s.primaryTime, "primary", errors)
                val commentError = resumeCommentError(s.stage.id, s.comment)
                if (commentError != null) errors["comment"] = commentError
                if (dt != null && errors["primary"] == null && errors["comment"] == null) {
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
                if (extension != null && extension.isBefore(LocalDate.now())) errors["extension"] = "Дата продления не может быть в прошлом"
                if (extension != null && errors["extension"] == null) {
                    events += PendingEvent(s.stage.first, LocalDateTime.now(), extension.format(dateFmt), s.comment.trim())
                }
            }
        }
        return ValidationResult(errors, events)
    }

    private fun refreshQueueCounts() {
        _state.value = _state.value.copy(
            pendingCount = queueStore.pendingCount(),
            failedCount = queueStore.failedCount(),
        )
    }

    private suspend fun syncPending(showMessage: Boolean) {
        if (!NetworkState.isConnected(application)) {
            refreshQueueCounts()
            if (showMessage) _state.value = _state.value.copy(message = "Нет сети. Данные сохранены на устройстве и будут отправлены автоматически.", success = true, sending = false)
            return
        }

        val result = QueueSyncEngine.sync(application)
        refreshQueueCounts()
        if (result.pending > 0) PendingSyncScheduler.schedule(application)
        if (result.sent > 0) loadHistory()

        if (showMessage || result.sent > 0 || result.failed > 0) {
            val message = when {
                result.failed > 0 -> "Часть данных сохранена локально, но ${result.failed} записей сервер отклонил. Их можно повторить после проверки."
                result.pending > 0 -> "Данные сохранены. ${result.pending} записей остаются в очереди и будут отправлены автоматически."
                result.sent > 0 -> "Данные переданы на сервер. Отправлено записей: ${result.sent}."
                else -> "Очередь синхронизирована."
            }
            _state.value = _state.value.copy(message = message, success = result.failed == 0, sending = false)
        }
    }

    fun retryPending() {
        queueStore.retryFailed()
        refreshQueueCounts()
        PendingSyncScheduler.schedule(application)
        viewModelScope.launch {
            _state.value = _state.value.copy(sending = true, message = "Повторная отправка...", success = true)
            syncPending(showMessage = true)
        }
    }

    fun send(): Boolean {
        val s = _state.value
        val validation = validate(s)
        if (validation.errors.isNotEmpty() || validation.events.isEmpty()) {
            _state.value = s.copy(errors = validation.errors, message = "Проверьте заполнение", success = false)
            return false
        }

        val requests = validation.events.map { event ->
            EventRequest(
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
        }

        queueStore.enqueueAll(requests)
        rememberPermit(s.permitNumber, s.workerName)
        refreshQueueCounts()
        PendingSyncScheduler.schedule(application)

        _state.value = _state.value.copy(
            errors = emptyMap(),
            message = if (NetworkState.isConnected(application)) "Данные сохранены на устройстве. Выполняется отправка..." else "Нет интернета. Данные сохранены на устройстве и отправятся автоматически при появлении сети.",
            success = true,
            sending = NetworkState.isConnected(application),
        )

        if (NetworkState.isConnected(application)) {
            viewModelScope.launch { syncPending(showMessage = true) }
        }
        return true
    }

    fun loadHistory() {
        viewModelScope.launch {
            try {
                val response = ru.rpo.mobile.data.ApiFactory.api.history(deviceId)
                if (response.isSuccessful) _history.value = response.body().orEmpty()
            } catch (_: Exception) {
            }
        }
    }
}
