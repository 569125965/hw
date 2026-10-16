plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

fun readLocalProp(key: String): String? {
    val f = rootProject.file("local.properties")
    if (!f.exists()) return null
    return f.readLines()
        .map { it.trim() }
        .filter { it.isNotEmpty() && !it.startsWith("#") && it.contains("=") }
        .associate {
            val i = it.indexOf("=")
            it.substring(0, i).trim() to it.substring(i + 1).trim()
        }[key]
}

android {
    namespace = "com.asharelab.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.asharelab.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"

        // 模拟器默认 10.0.2.2；真机在 local.properties 设置 ashare.api.baseUrl
        val apiFromLocal = readLocalProp("ashare.api.baseUrl")
        val apiBase = apiFromLocal ?: "http://10.0.2.2:8000"
        buildConfigField("String", "API_BASE_URL", "\"$apiBase\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            buildConfigField("String", "API_BASE_URL", "\"https://api.example.com\"")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            // 继承 defaultConfig；若 local.properties 有 ashare.api.baseUrl 则已覆盖
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.10.01")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.navigation:navigation-compose:2.8.4")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("com.google.android.material:material:1.12.0")

    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-moshi:2.11.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    implementation("com.squareup.moshi:moshi-kotlin:1.15.1")

    implementation("com.github.PhilJay:MPAndroidChart:v3.1.0")

    debugImplementation("androidx.compose.ui:ui-tooling")
}
