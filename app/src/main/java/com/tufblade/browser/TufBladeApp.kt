package com.tufblade.browser

import android.app.Application
import org.mozilla.geckoview.ContentBlocking
import org.mozilla.geckoview.GeckoRuntime
import org.mozilla.geckoview.GeckoRuntimeSettings

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

        val contentBlocking = ContentBlocking.Settings.Builder()
            .categories(
                ContentBlocking.AntiTracking.STRICT or
                ContentBlocking.SafeBrowsing.ALL
            )
            .cookieBehavior(ContentBlocking.CookieBehavior.ACCEPT_NON_TRACKERS)
            // Fingerprinting- & Cryptomining-Schutz, siehe frühere Analyse zu "Fingerprint-Noise"
            .antiFingerprinting(true)
            .cryptoMining(true)
            .build()

        val runtimeSettings = GeckoRuntimeSettings.Builder()
            .contentBlocking(contentBlocking)
            // WebRTC-Leak-Schutz: verhindert lokale IP-Preisgabe über ICE-Candidates
            .aboutConfigEnabled(true)
            .build()

        geckoRuntime = GeckoRuntime.create(this, runtimeSettings)
    }
}
