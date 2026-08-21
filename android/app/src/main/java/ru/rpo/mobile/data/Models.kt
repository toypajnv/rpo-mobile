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
)

data class ApiError(val detail: String? = null)


data class PermitFieldSnapshot(
    val field_value: String = "",
    val event_time: String = "",
    val comment: String = "",
)

data class PermitSnapshot(
    val permit_number: String,
    val worker_name: String,
    val updated_at: String,
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
