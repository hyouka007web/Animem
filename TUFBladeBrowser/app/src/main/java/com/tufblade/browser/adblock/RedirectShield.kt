package com.tufblade.browser.adblock

import android.net.Uri
import android.util.Log
import org.mozilla.geckoview.AllowOrDeny
import org.mozilla.geckoview.GeckoResult
import org.mozilla.geckoview.GeckoSession
import org.mozilla.geckoview.WebRequestError

/**
 * Weiterleitschutz, wie ihn ältere Adblock-Browser (Brave classic, uBO+
 * Popup-Blocker-Kombo) hatten:
 *
 * 1) Popups (window.open) ohne User-Geste werden abgefangen (onNewSession)
 * 2) Navigationen ohne User-Geste, die kurz nach dem Laden der Seite auf
 *    eine ANDERE Domain zeigen (klassisches "Klick-auf-Download-Button
 *    öffnet 3 Phishing-Tabs"-Muster), werden geblockt statt direkt geladen.
 *
 * Der Nutzer bekommt die geblockte URL für ein paar Sekunden als "trotzdem
 * öffnen"-Option (siehe [lastBlocked]) statt dass sie kommentarlos verschwindet.
 */
class RedirectShield(
    private val adBlockEngine: AdBlockEngine,
    private val onBlocked: (uri: String, reason: BlockReason) -> Unit
) : GeckoSession.NavigationDelegate, GeckoSession.ContentDelegate {

    enum class BlockReason { AD_HOST, POPUP_NO_GESTURE, REDIRECT_NO_GESTURE }

    var lastBlocked: String? = null
        private set

    private var currentDomain: String? = null
    private var lastLoadTimestamp: Long = 0L

    // Kurzes Zeitfenster nach dem Laden, in dem eine domain-fremde,
    // geste-lose Navigation als "unerwünschte Weiterleitung" gilt.
    private val redirectSuspicionWindowMs = 4000L

    override fun onLocationChange(
        session: GeckoSession,
        url: String?,
        perms: MutableList<GeckoSession.PermissionDelegate.ContentPermission>,
        hasUserGesture: Boolean
    ) {
        url?.let {
            currentDomain = Uri.parse(it).host
            lastLoadTimestamp = System.currentTimeMillis()
        }
    }

    override fun onLoadRequest(
        session: GeckoSession,
        request: GeckoSession.NavigationDelegate.LoadRequest
    ): GeckoResult<AllowOrDeny> {
        val uri = Uri.parse(request.uri)

        // Ebene 2 Adblock: Host-/Pattern-Sperrliste
        if (adBlockEngine.shouldBlock(uri)) {
            markBlocked(request.uri, BlockReason.AD_HOST)
            return GeckoResult.deny()
        }

        // Redirect-Verdacht: keine User-Geste, andere Domain, kurz nach Laden
        val timeSinceLoad = System.currentTimeMillis() - lastLoadTimestamp
        val isCrossDomain = currentDomain != null && uri.host != null && uri.host != currentDomain
        if (!request.hasUserGesture && isCrossDomain && timeSinceLoad < redirectSuspicionWindowMs) {
            Log.i("RedirectShield", "Blockiere Weiterleitung ohne Nutzeraktion: ${request.uri}")
            markBlocked(request.uri, BlockReason.REDIRECT_NO_GESTURE)
            return GeckoResult.deny()
        }

        return GeckoResult.allow()
    }

    /** window.open()-Popups ohne User-Geste unterdrücken. */
    override fun onNewSession(
        session: GeckoSession,
        uri: String
    ): GeckoResult<GeckoSession>? {
        markBlocked(uri, BlockReason.POPUP_NO_GESTURE)
        return GeckoResult.fromValue(null) // null = Popup wird nicht geöffnet
    }

    override fun onLoadError(
        session: GeckoSession,
        uri: String?,
        error: WebRequestError
    ): GeckoResult<String>? {
        return null // Standard-Fehlerseite von Gecko verwenden
    }

    private fun markBlocked(uri: String, reason: BlockReason) {
        lastBlocked = uri
        onBlocked(uri, reason)
    }
}
