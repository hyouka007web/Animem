plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python") // Python-Backend für yt-dlp / Scrapling — kostenlos seit Chaquopy 12.0.1
}

android {
    namespace = "com.tufblade.browser"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.tufblade.browser"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0-alpha"

        ndk {
            // Chaquopy braucht mind. eine ABI, für den Anfang reicht arm64
            abiFilters += listOf("arm64-v8a")
        }
        python {
            pip {
                // Backend-Module, laufen als reines Python unter Chaquopy
                install("yt-dlp")
                install("scrapling")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
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
        viewBinding = true
    }
}

dependencies {
    // GeckoView — Rendering-Engine, ersetzt QtWebEngine für die Android-Zielplattform
    implementation("org.mozilla.geckoview:geckoview:130.0.20240815120555")

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
}
