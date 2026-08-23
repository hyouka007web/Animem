plugins {
    id("com.android.application")
    id("com.chaquo.python") // Python-Backend für yt-dlp / Scrapling — kostenlos seit Chaquopy 12.0.1
}

android {
    namespace = "com.tufblade.browser"
    compileSdk = 36

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
        chaquopy {
            defaultConfig {
                version = "3.10"
                pip {
                    // Backend-Module, laufen als reines Python unter Chaquopy
                    install("yt-dlp")
                    install("scrapling")
                }
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
}
