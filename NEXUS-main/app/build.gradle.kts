plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android") // NICHT löschen: ohne das kompiliert kein .kt-File
}

android {
    namespace = "com.tufblade.browser"
    compileSdk {
        version = release(37) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        applicationId = "com.tufblade.browser"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0-alpha"

        ndk {
            // FIX: ohne diese Zeile hängt die enthaltene ABI-Auswahl vom
            // Gradle/AGP-Default ab; explizit machen verhindert eine APK,
            // die z.B. nur arm64-v8a enthält und auf einem 32-bit-Gerät
            // sofort mit "Native library not found" abstürzt.
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
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
    kotlin {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }
    buildFeatures {
        viewBinding = true
    }
}

dependencies {
    // GeckoView — Rendering-Engine, ersetzt QtWebEngine für die Android-Zielplattform
    implementation("org.mozilla.geckoview:geckoview:154.0.20260814215756")

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
}

configurations.configureEach {
    resolutionStrategy.force(
        "org.jetbrains.kotlin:kotlin-stdlib:2.2.0",
        "org.jetbrains.kotlin:kotlin-stdlib-jdk7:2.2.0",
        "org.jetbrains.kotlin:kotlin-stdlib-jdk8:2.2.0"
    )
}
