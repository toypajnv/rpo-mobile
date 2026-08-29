package ru.rpo.mobile.data

data class EventRequest(
    val client_event_id: String,
    val device_id: String,
    val worker_name: String,
    val permit_number: String,
    val field_key: String,
    val stage_label: String,
    val event_time: String,
    val field_value: String,
    val comment: String,
    val structural_unit: String? = null,
)

data class EventResponse(
    val id: Long,
    val worker_name: String,
    val permit_number: String,
    val field_key: String,
    val stage_label: String,
    val event_time: String,
    val field_value: String,
    val comment: String,
    val received_at: String,
    val exported_at: String?,
    val structural_unit: String? = null,
    val approval_required: Boolean = false,
    val approval_status: String = "not_required",
    val approved_at: String? = null,
)

data class ApiError(val detail: String? = null)


data class PermitFieldSnapshot(
    val field_value: String = "",
    val event_time: String = "",
    val comment: String = "",
    val event_id: Long = 0,
    val approval_required: Boolean = false,
    val approval_status: String = "not_required",
    val approved_at: String? = null,
)

data class PermitApprovalSummary(
    val status: String = "none",
    val label: String = "",
    val pending_count: Int = 0,
    val approved_count: Int = 0,
    val approved_at: String? = null,
)

data class PermitSnapshot(
    val permit_number: String,
    val worker_name: String,
    val updated_at: String,
    val structural_unit: String = "",
    val approval: PermitApprovalSummary = PermitApprovalSummary(),
    val fields: Map<String, PermitFieldSnapshot> = emptyMap(),
)

data class MobileConfig(
    val status: String = "ok",
    val server_version: String = "",
    val latest_app_version: String = "",
    val minimum_supported_version: String = "",
    val update_available: Boolean = false,
    val update_required: Boolean = false,
    val maintenance: Boolean = false,
    val message: String = "",
    val apk_url: String = "",
    val checked_at: String = "",
)
