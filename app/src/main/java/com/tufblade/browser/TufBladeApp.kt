package com.tufblade.browser

import android.app.Application
import android.util.Log
import org.mozilla.geckoview.ContentBlocking
import org.mozilla.geckoview.GeckoRuntime
import org.mozilla.geckoview.GeckoRuntimeSettings

const val LAST_CRASH_FILE_NAME = "last_crash.txt"

/**
 * Eine GeckoRuntime pro App-Prozess (Mozilla-Vorgabe, mehrere Instanzen sind nicht erlaubt).
 *
 * Hier sitzt die native, "verstärkte" Blocking-Konfiguration:
 * GeckoView bringt Gecko's eingebaute Content-Blocking-Kategorien mit
 * (Disconnect-Tracking-Listen — das Fundament, auf dem auch Firefox Focus basiert).
 * Das ist die Resource-Ebene (Bilder/Skripte/XHR), die ein reiner
 * NavigationDelegate NICHT abdecken kann — siehe AdBlockEngine.kt für die
 * zusätzliche host-basierte Sperrliste auf Navigations-Ebene.
 */
class TufBladeApp : Application() {

    lateinit var geckoRuntime: GeckoRuntime
        private set

    override fun onCreate() {
        super.onCreate()

        val previousHandler = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                filesDir.resolve(LAST_CRASH_FILE_NAME).writeText(Log.getStackTraceString(throwable))
            } finally {
                previousHandler?.uncaughtException(thread, throwable)
            }
        }

        val contentBlocking = ContentBlocking.Settings.Builder()
            .antiTracking(ContentBlocking.AntiTracking.STRICT)
            .safeBrowsing(ContentBlocking.SafeBrowsing.DEFAULT)
            .cookieBehavior(ContentBlocking.CookieBehavior.ACCEPT_NON_TRACKERS)
            .build()

        val runtimeSettings = GeckoRuntimeSettings.Builder()
            .contentBlocking(contentBlocking)
            // WebRTC-Leak-Schutz: verhindert lokale IP-Preisgabe über ICE-Candidates
            .aboutConfigEnabled(true)
            .build()

        try {
            geckoRuntime = GeckoRuntime.create(this, runtimeSettings)
        } catch (e: Throwable) {
            // FIX: Wenn die native GeckoView-Bibliothek für die Geräte-Architektur
            // fehlt/beschädigt ist, knallt es hier sonst sofort und lautlos, bevor
            // MainActivity überhaupt den last_crash.txt-Handler auslesen kann.
            // Wir schreiben die Diagnose selbst und lassen die App kontrolliert
            // in MainActivitys Fehleranzeige laufen statt hart zu crashen.
            Log.e("TufBladeApp", "GeckoRuntime-Initialisierung fehlgeschlagen", e)
            try {
                filesDir.resolve(LAST_CRASH_FILE_NAME).writeText(
                    "GeckoRuntime.create() fehlgeschlagen - vermutlich fehlt die " +
                        "native Library für die Geräte-ABI (siehe app/build.gradle.kts " +
                        "ndk.abiFilters) oder die GeckoView-Version ist inkompatibel.\n\n" +
                        Log.getStackTraceString(e)
                )
            } catch (_: Exception) { }
            throw e
        }
    }
}
