package ru.rpo.mobile.data

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import ru.rpo.mobile.BuildConfig

object ApiFactory {
    val api: RpoApi by lazy {
        Retrofit.Builder().baseUrl(BuildConfig.SERVER_URL).addConverterFactory(GsonConverterFactory.create()).build().create(RpoApi::class.java)
    }
}
