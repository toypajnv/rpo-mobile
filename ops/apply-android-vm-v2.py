from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Marker not found in {path}: {old[:120]!r}')
    target.write_text(text.replace(old, new, 1), encoding='utf-8')

replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', 'import ru.rpo.mobile.data.PermitSnapshot\n', 'import ru.rpo.mobile.data.PermitSnapshot\nimport ru.rpo.mobile.data.PermitApprovalSummary\n')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''data class PermitMemory(
    val permitNumber: String,
    val workerName: String,
    val lastUsedAt: Long,
)''', '''data class PermitMemory(
    val permitNumber: String,
    val workerName: String,
    val lastUsedAt: Long,
    val structuralUnit: String? = null,
)''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''data class FormState(
    val workerName: String = "",
    val permitNumber: String = "",''', '''data class FormState(
    val workerName: String = "",
    val structuralUnit: String = "",
    val permitNumber: String = "",''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '    val serverSavedStageIds: Set<String> = emptySet(),\n)', '    val serverSavedStageIds: Set<String> = emptySet(),\n    val approvalSummary: PermitApprovalSummary? = null,\n)')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '    private var permitLookupJob: Job? = null\n    private var serverPermitSnapshot: PermitSnapshot? = null', '    private var permitLookupJob: Job? = null\n    private var approvalPollingJob: Job? = null\n    private var serverPermitSnapshot: PermitSnapshot? = null')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''        FormState(
            workerName = prefs.getString("worker_name", "") ?: "",
            pendingCount = queueStore.pendingCount(),''', '''        FormState(
            workerName = prefs.getString("worker_name", "") ?: "",
            structuralUnit = prefs.getString("structural_unit", "") ?: "",
            pendingCount = queueStore.pendingCount(),''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '        runCatching { connectivityManager.unregisterNetworkCallback(networkCallback) }\n        super.onCleared()', '        runCatching { connectivityManager.unregisterNetworkCallback(networkCallback) }\n        approvalPollingJob?.cancel()\n        super.onCleared()')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''    private fun rememberPermit(permitNumber: String, workerName: String) {
        val normalized = permitNumber.trim().uppercase()
        val updated = _permitMemories.value
            .filterNot { it.permitNumber.equals(normalized, ignoreCase = true) }
            .toMutableList()
        updated.add(0, PermitMemory(normalized, workerName.trim(), System.currentTimeMillis()))''', '''    private fun rememberPermit(permitNumber: String, workerName: String, structuralUnit: String) {
        val normalized = permitNumber.trim().uppercase()
        val updated = _permitMemories.value
            .filterNot { it.permitNumber.equals(normalized, ignoreCase = true) }
            .toMutableList()
        updated.add(0, PermitMemory(normalized, workerName.trim(), System.currentTimeMillis(), structuralUnit))''')

polling_code = '''
    private suspend fun refreshApprovalStatus(permitNumber: String) {
        if (!NetworkState.isConnected(application)) return
        try {
            val response = ru.rpo.mobile.data.ApiFactory.api.permit(permitNumber)
            if (!response.isSuccessful) return
            val snapshot = response.body() ?: return
            if (_state.value.permitNumber.trim().uppercase() != permitNumber) return
            serverPermitSnapshot = snapshot
            val unit = _state.value.structuralUnit.ifBlank { snapshot.structural_unit }
            _state.value = _state.value.copy(
                structuralUnit = unit,
                approvalSummary = snapshot.approval,
            )
            if (unit.isNotBlank()) prefs.edit().putString("structural_unit", unit).apply()
        } catch (_: Exception) {
        }
    }

    private fun startApprovalPolling(permitNumber: String) {
        approvalPollingJob?.cancel()
        if (!permitRegex.matches(permitNumber)) return
        approvalPollingJob = viewModelScope.launch {
            while (_state.value.permitNumber.trim().uppercase() == permitNumber) {
                delay(8000)
                refreshApprovalStatus(permitNumber)
            }
        }
    }

'''
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '    private fun schedulePermitLookup(permitNumber: String, immediate: Boolean = false) {', polling_code + '    private fun schedulePermitLookup(permitNumber: String, immediate: Boolean = false) {')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''                    val base = _state.value.copy(
                        workerName = worker,
                        serverSavedStageIds = savedStageIdsForFieldKeys(filledKeys),''', '''                    val unit = snapshot.structural_unit.ifBlank { _state.value.structuralUnit }
                    val base = _state.value.copy(
                        workerName = worker,
                        structuralUnit = unit,
                        approvalSummary = snapshot.approval,
                        serverSavedStageIds = savedStageIdsForFieldKeys(filledKeys),''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''                    if (worker.isNotBlank()) prefs.edit().putString("worker_name", worker).apply()
                } else if (response.code() == 404) {''', '''                    if (worker.isNotBlank()) prefs.edit().putString("worker_name", worker).apply()
                    if (unit.isNotBlank()) prefs.edit().putString("structural_unit", unit).apply()
                    startApprovalPolling(normalized)
                } else if (response.code() == 404) {''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '                    _state.value = _state.value.copy(serverSavedStageIds = emptySet())\n                }', '                    _state.value = _state.value.copy(serverSavedStageIds = emptySet(), approvalSummary = null)\n                }')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''        val worker = memory.workerName.ifBlank { _state.value.workerName }
        _state.value = blankStageFields(_state.value).copy(
            permitNumber = memory.permitNumber,
            workerName = worker,''', '''        val worker = memory.workerName.ifBlank { _state.value.workerName }
        val unit = memory.structuralUnit.orEmpty().ifBlank { _state.value.structuralUnit }
        _state.value = blankStageFields(_state.value).copy(
            permitNumber = memory.permitNumber,
            workerName = worker,
            structuralUnit = unit,''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''        if (worker.isNotBlank()) prefs.edit().putString("worker_name", worker).apply()
        schedulePermitLookup(memory.permitNumber, immediate = true)''', '''        if (worker.isNotBlank()) prefs.edit().putString("worker_name", worker).apply()
        if (unit.isNotBlank()) prefs.edit().putString("structural_unit", unit).apply()
        schedulePermitLookup(memory.permitNumber, immediate = true)''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''    fun updateWorker(v: String) {
        _state.value = _state.value.copy(workerName = v.take(180), message = null)
        prefs.edit().putString("worker_name", v.take(180)).apply()
    }

    fun updatePermit(v: String) {''', '''    fun updateWorker(v: String) {
        _state.value = _state.value.copy(workerName = v.take(180), message = null)
        prefs.edit().putString("worker_name", v.take(180)).apply()
    }

    fun updateStructuralUnit(v: String) {
        val normalized = if (v in structuralUnits) v else ""
        _state.value = _state.value.copy(
            structuralUnit = normalized,
            errors = _state.value.errors - "structuralUnit",
            message = null,
        )
        prefs.edit().putString("structural_unit", normalized).apply()
    }

    fun updatePermit(v: String) {''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '    fun updatePermit(v: String) {\n        val value = v.uppercase().take(80)', '    fun updatePermit(v: String) {\n        approvalPollingJob?.cancel()\n        val value = v.uppercase().take(80)')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''            permitNumber = value,
            errors = errors,
            serverSavedStageIds = emptySet(),''', '''            permitNumber = value,
            errors = errors,
            serverSavedStageIds = emptySet(),
            approvalSummary = null,''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''        if (s.workerName.trim().length < 3) errors["worker"] = "Укажите ФИО работника"
        val permit = s.permitNumber.trim().uppercase()''', '''        if (s.workerName.trim().length < 3) errors["worker"] = "Укажите ФИО работника"
        structuralUnitError(s.structuralUnit)?.let { errors["structuralUnit"] = it }
        val permit = s.permitNumber.trim().uppercase()''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''                worker_name = s.workerName.trim(),
                permit_number = s.permitNumber.trim().uppercase(),''', '''                worker_name = s.workerName.trim(),
                structural_unit = s.structuralUnit,
                permit_number = s.permitNumber.trim().uppercase(),''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '        rememberPermit(s.permitNumber, s.workerName)\n', '        rememberPermit(s.permitNumber, s.workerName, s.structuralUnit)\n')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''                result.sent > 0 -> "Данные переданы на сервер. Отправлено записей: ${result.sent}."
                else -> "Очередь синхронизирована."''', '''                result.sent > 0 -> "Данные переданы на сервер. Для этапов, кроме остановки, дождитесь статуса «Работы можно проводить»."
                else -> "Очередь синхронизирована."''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', '''            _state.value = _state.value.copy(message = message, success = result.failed == 0, sending = false)
        }
    }''', '''            _state.value = _state.value.copy(message = message, success = result.failed == 0, sending = false)
        }
        val permit = _state.value.permitNumber.trim().uppercase()
        if (result.sent > 0 && permitRegex.matches(permit)) {
            refreshApprovalStatus(permit)
            startApprovalPolling(permit)
        }
    }''')
replace_once('android/app/src/main/java/ru/rpo/mobile/ui/RpoViewModel.kt', 'errors = base.errors.filterKeys { it == "worker" || it == "permit" },', 'errors = base.errors.filterKeys { it == "worker" || it == "permit" || it == "structuralUnit" },')
print('android vm v2 applied')
