package ru.rpo.mobile.data

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface RpoApi {
    @POST("api/mobile/events")
    suspend fun sendEvent(@Body body: EventRequest): Response<EventResponse>

    @GET("api/mobile/events")
    suspend fun history(@Query("device_id") deviceId: String, @Query("limit") limit: Int = 30): Response<List<EventResponse>>

    @GET("api/mobile/permit")
    suspend fun permit(@Query("permit_number") permitNumber: String): Response<PermitSnapshot>
}
