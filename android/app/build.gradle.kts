plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val configuredServerUrl = (
    providers.gradleProperty("RPO_SERVER_URL").orNull
        ?: System.getenv("RPO_SERVER_URL")
        ?: ""
).trim()
val serverUrl = (if (configuredServerUrl.isNotEmpty()) configuredServerUrl else "https://rpo-mng.ru/")
    .let { if (it.endsWith("/")) it else "$it/" }

val stableTestKeystore = file("rpo-test.keystore")

android {
    namespace = "ru.rpo.mobile"
    compileSdk = 35

    defaultConfig {
        applicationId = "ru.rpo.mobile"
        minSdk = 26
        targetSdk = 35
        versionCode = 6
        versionName = "1.1.3"
        buildConfigField("String", "SERVER_URL", "\"$serverUrl\"")
    }

    if (stableTestKeystore.exists()) {
        signingConfigs {
            create("stableTest") {
                storeFile = stableTestKeystore
                storePassword = "rpo-test-2026"
                keyAlias = "rpo-test"
                keyPassword = "rpo-test-2026"
            }
        }
    }

    buildTypes {
        getByName("debug") {
            if (stableTestKeystore.exists()) {
                signingConfig = signingConfigs.getByName("stableTest")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures { compose = true; buildConfig = true }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }
    kotlinOptions { jvmTarget = "17" }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.06.00"))
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.2")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.2")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    implementation("androidx.work:work-runtime-ktx:2.10.5")
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")

    testImplementation("junit:junit:4.13.2")
}
