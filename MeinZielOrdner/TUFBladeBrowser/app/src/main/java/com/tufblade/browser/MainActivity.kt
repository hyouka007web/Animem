package com.tufblade.browser

import android.os.Bundle
import android.view.KeyEvent
import android.view.inputmethod.EditorInfo
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.snackbar.Snackbar
import com.tufblade.browser.adblock.AdBlockEngine
import com.tufblade.browser.adblock.RedirectShield
import com.tufblade.browser.databinding.ActivityMainBinding
import org.mozilla.geckoview.GeckoSession
import org.mozilla.geckoview.GeckoSessionSettings
import org.mozilla.geckoview.GeckoView

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var geckoView: GeckoView
    private lateinit var geckoSession: GeckoSession
    private lateinit var adBlockEngine: AdBlockEngine
    private lateinit var redirectShield: RedirectShield

    private val startPage = "https://start.duckduckgo.com"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        adBlockEngine = AdBlockEngine.loadFromAssets(this)
        redirectShield = RedirectShield(adBlockEngine) { uri, reason ->
            runOnUiThread { showBlockedToast(uri, reason) }
        }

        setupGeckoSession()
        setupTopBar()
    }

    private fun setupGeckoSession() {
        val app = application as TufBladeApp

        val sessionSettings = GeckoSessionSettings.Builder()
            .usePrivateMode(false)
            .userAgentMode(GeckoSessionSettings.USER_AGENT_MODE_MOBILE)
            .build()

        geckoSession = GeckoSession(sessionSettings)
        geckoSession.navigationDelegate = redirectShield
        geckoSession.contentDelegate = redirectShield
        geckoSession.open(app.geckoRuntime)

        geckoView = GeckoView(this)
        geckoView.setSession(geckoSession)
        binding.contentContainer.addView(geckoView)

        geckoSession.loadUri(startPage)
    }

    private fun setupTopBar() {
        binding.urlField.setText(startPage)
        binding.urlField.setOnEditorActionListener { _, actionId, event ->
            val isGo = actionId == EditorInfo.IME_ACTION_GO
            val isEnter = event?.keyCode == KeyEvent.KEYCODE_ENTER
            if (isGo || isEnter) {
                loadFromUrlField()
                true
            } else {
                false
            }
        }

        binding.menuButton.setOnClickListener {
            // TODO: Hauptmenü — Videothek & Sniffer / Scrapling Suite / Downloads /
            // Übersetzung / System-Performance (siehe Menüstruktur-Konzept)
            Snackbar.make(binding.root, "Hauptmenü — TODO", Snackbar.LENGTH_SHORT).show()
        }
    }

    private fun loadFromUrlField() {
        var input = binding.urlField.text.toString().trim()
        if (input.isEmpty()) return

        if (!input.startsWith("http://") && !input.startsWith("https://")) {
            // Simple Heuristik: enthält es einen Punkt und keine Leerzeichen -> URL, sonst Suche
            input = if (input.contains(" ") || !input.contains(".")) {
                "https://start.duckduckgo.com/?q=${input.replace(" ", "+")}"
            } else {
                "https://$input"
            }
        }
        adBlockEngine.resetCounter()
        geckoSession.loadUri(input)
    }

    private fun showBlockedToast(uri: String, reason: RedirectShield.BlockReason) {
        binding.shieldBadge.text = adBlockEngine.blockedCount.toString()

        val label = when (reason) {
            RedirectShield.BlockReason.AD_HOST -> "Werbung/Tracker blockiert"
            RedirectShield.BlockReason.POPUP_NO_GESTURE -> "Popup ohne Nutzeraktion blockiert"
            RedirectShield.BlockReason.REDIRECT_NO_GESTURE -> "Weiterleitung blockiert"
        }

        // Nur bei Redirect/Popup eine sichtbare Meldung mit "trotzdem öffnen" —
        // Ad-Host-Blocks passieren zu oft für einen Toast pro Treffer.
        if (reason != RedirectShield.BlockReason.AD_HOST) {
            Snackbar.make(binding.root, label, Snackbar.LENGTH_LONG)
                .setAction("Trotzdem öffnen") { geckoSession.loadUri(uri) }
                .show()
        }
    }

    override fun onDestroy() {
        geckoSession.close()
        super.onDestroy()
    }
}
