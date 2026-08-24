// NEXUS Browser — root build file
plugins {
    id("com.android.application") version "9.3.1" apply false
    // FIX: Ohne dieses Plugin wird keine einzige .kt-Datei kompiliert -
    // das ist der eigentliche Grund für den "Absturz": der Build schlägt
    // schon bei der Konfiguration fehl (kotlin{}-Block in app/build.gradle.kts
    // existiert ohne dieses Plugin nicht), es entsteht gar keine gültige APK.
    id("org.jetbrains.kotlin.android") version "2.2.0" apply false
}

tasks.register("clean", Delete::class) {
    delete(rootProject.buildDir)
}
