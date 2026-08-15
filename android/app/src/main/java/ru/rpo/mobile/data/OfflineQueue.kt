package ru.rpo.mobile.data

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.TimeUnit

data class QueuedEvent(
    val request: EventRequest,
    val createdAt: Long = System.currentTimeMillis(),
    val state: String = STATE_PENDING,
    val lastError: String? = null,
) {
    companion object {
        const val STATE_PENDING = "pending"
        const val STATE_FAILED = "failed"
    }
}

data class SyncSummary(
    val sent: Int,
    val pending: Int,
    val failed: Int,
    val transientFailure: Boolean,
    val lastError: String? = null,
)

object NetworkState {
    fun isConnected(context: Context): Boolean {
        val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = manager.activeNetwork ?: return false
        val capabilities = manager.getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
}

class PendingEventStore(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    private val gson = Gson()
    private val listType = object : TypeToken<List<QueuedEvent>>() {}.type

    companion object {
        private const val PREFS_NAME = "rpo_offline_queue"
        private const val KEY_QUEUE = "events"
        private val diskLock = Any()
    }

    private fun readUnsafe(): MutableList<QueuedEvent> {
        val raw = prefs.getString(KEY_QUEUE, "[]") ?: "[]"
        return try {
            val decoded: List<QueuedEvent>? = gson.fromJson(raw, listType)
            decoded.orEmpty().toMutableList()
        } catch (_: Exception) {
            mutableListOf()
        }
    }

    private fun writeUnsafe(items: List<QueuedEvent>) {
        prefs.edit().putString(KEY_QUEUE, gson.toJson(items)).commit()
    }

    fun enqueueAll(requests: List<EventRequest>) = synchronized(diskLock) {
        val items = readUnsafe()
        val existingIds = items.mapTo(mutableSetOf()) { it.request.client_event_id }
        requests.forEach { request ->
            if (existingIds.add(request.client_event_id)) items += QueuedEvent(request = request)
        }
        writeUnsafe(items)
    }

    fun pendingItems(): List<QueuedEvent> = synchronized(diskLock) {
        readUnsafe().filter { it.state == QueuedEvent.STATE_PENDING }.sortedBy { it.createdAt }
    }

    fun pendingCount(): Int = synchronized(diskLock) {
        readUnsafe().count { it.state == QueuedEvent.STATE_PENDING }
    }

    fun failedCount(): Int = synchronized(diskLock) {
        readUnsafe().count { it.state == QueuedEvent.STATE_FAILED }
    }

    fun remove(clientEventId: String) = synchronized(diskLock) {
        val items = readUnsafe().filterNot { it.request.client_event_id == clientEventId }
        writeUnsafe(items)
    }

    fun markFailed(clientEventId: String, error: String) = synchronized(diskLock) {
        val items = readUnsafe().map { item ->
            if (item.request.client_event_id == clientEventId) {
                item.copy(state = QueuedEvent.STATE_FAILED, lastError = error.take(500))
            } else item
        }
        writeUnsafe(items)
    }

    fun retryFailed() = synchronized(diskLock) {
        val items = readUnsafe().map { item ->
            if (item.state == QueuedEvent.STATE_FAILED) item.copy(state = QueuedEvent.STATE_PENDING, lastError = null) else item
        }
        writeUnsafe(items)
    }
}

object QueueSyncEngine {
    private val mutex = Mutex()

    suspend fun sync(context: Context): SyncSummary = mutex.withLock {
        val store = PendingEventStore(context)
        var sent = 0
        var newlyFailed = 0
        var transientFailure = false
        var lastError: String? = null

        for (item in store.pendingItems()) {
            try {
                val response = ApiFactory.api.sendEvent(item.request)
                if (response.isSuccessful) {
                    store.remove(item.request.client_event_id)
                    sent += 1
                    continue
                }

                val rawError = response.errorBody()?.string()
                val detail = try {
                    Gson().fromJson(rawError, ApiError::class.java)?.detail
                } catch (_: Exception) {
                    null
                }
                val message = detail ?: "Ошибка сервера HTTP ${response.code()}"
                val code = response.code()
                val temporary = code == 408 || code == 425 || code == 429 || code >= 500

                if (temporary) {
                    transientFailure = true
                    lastError = message
                    break
                } else {
                    store.markFailed(item.request.client_event_id, message)
                    newlyFailed += 1
                    lastError = message
                }
            } catch (e: Exception) {
                transientFailure = true
                lastError = e.message ?: "Нет связи с сервером"
                break
            }
        }

        SyncSummary(
            sent = sent,
            pending = store.pendingCount(),
            failed = store.failedCount(),
            transientFailure = transientFailure,
            lastError = lastError,
        )
    }
}

class PendingSyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val result = QueueSyncEngine.sync(applicationContext)
        return if (result.transientFailure && result.pending > 0) Result.retry() else Result.success()
    }
}

object PendingSyncScheduler {
    private const val WORK_NAME = "rpo-pending-sync"

    fun schedule(context: Context) {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        val request = OneTimeWorkRequestBuilder<PendingSyncWorker>()
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 10, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context.applicationContext)
            .enqueueUniqueWork(WORK_NAME, ExistingWorkPolicy.KEEP, request)
    }
}
