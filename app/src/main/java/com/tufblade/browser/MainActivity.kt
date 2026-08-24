package com.tufblade.browser

import android.animation.ValueAnimator
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.view.KeyEvent
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.animation.DecelerateInterpolator
import android.view.inputmethod.EditorInfo
import android.widget.FrameLayout
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.PopupMenu
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.snackbar.Snackbar
import com.tufblade.browser.adblock.AdBlockEngine
import com.tufblade.browser.adblock.RedirectShield
import com.tufblade.browser.databinding.ActivityMainBinding
import com.tufblade.browser.media.MediaLinkFinder
import com.tufblade.browser.media.VideoDownloader
import com.tufblade.browser.tabs.Tab
import com.tufblade.browser.tabs.TabManager
import org.mozilla.geckoview.GeckoSession
import org.mozilla.geckoview.GeckoSessionSettings
import org.mozilla.geckoview.GeckoView
import kotlin.concurrent.thread

/**
 * Angepinnte Sidebar-Web-Apps. Persistiert über NexusSettings (SharedPreferences),
 * Standardwerte siehe NexusSettings.defaultPinnedApps(). Jede öffnet in einem
 * eigenen, isolierten Tab (eigene GeckoSession = eigener Cookie-Container laut
 * design.md-Konzept).
 */

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var adBlockEngine: AdBlockEngine
    private val tabManager = TabManager()

    // PERF-FIX: vorher wurde bei jedem Tab-Wechsel ein komplett neues
    // GeckoView (= neue native Surface) erzeugt und das alte verworfen.
    // Ein einziges, wiederverwendetes GeckoView + setSession() ist der
    // eigentliche "SessionPool"-Gewinn - Tab-Wechsel wird spürbar schneller,
    // ohne die Session-Objekte selbst künstlich zu poolen (das ergibt bei
    // GeckoSession keinen Sinn, da jede Session fest an den Verlauf/Zustand
    // eines Tabs gebunden ist).
    private var geckoView: GeckoView? = null

    private var sidebarExpanded = false
    private val startPage = "https://start.duckduckgo.com"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val previousCrash = filesDir.resolve(LAST_CRASH_FILE_NAME)
        if (previousCrash.exists()) {
            showStackTrace(previousCrash.readText())
            previousCrash.delete()
            return
        }

        adBlockEngine = AdBlockEngine.loadFromAssets(this)
        adBlockEngine.enabled = NexusSettings.isAdBlockEnabled(this)

        try {
            setupSidebar()
            setupTopBar()
            openNewTab(startPage)
        } catch (e: Exception) {
            showStackTrace(android.util.Log.getStackTraceString(e))
        }
    }

    // ---------------------------------------------------------------------
    // Absturz-Diagnose-Anzeige
    // ---------------------------------------------------------------------

    private fun showStackTrace(stackTrace: String) {
        binding.contentContainer.removeAllViews()
        binding.contentContainer.setBackgroundColor(getColor(R.color.bg_base))

        val textView = TextView(this).apply {
            setTextColor(Color.WHITE)
            setBackgroundColor(getColor(R.color.bg_base))
            typeface = Typeface.MONOSPACE
            text = stackTrace
            setTextIsSelectable(true)
            setPadding(24, 24, 24, 24)
        }
        val scrollView = ScrollView(this).apply {
            addView(textView, ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ))
        }
        binding.contentContainer.addView(scrollView, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ))
    }

    // ---------------------------------------------------------------------
    // Sidebar: Ausklappen/Einklappen mit Animation (design.md Motion: 180ms ease-out)
    // ---------------------------------------------------------------------

    private fun setupSidebar() {
        renderSidebarIcons()
        binding.sidebar.setOnClickListener { toggleSidebar() }
    }

    private fun renderSidebarIcons() {
        binding.sidebar.removeAllViews()
        val iconSize = resources.getDimensionPixelSize(R.dimen.sidebar_icon_size)
        val margin = resources.getDimensionPixelSize(R.dimen.space_8)

        NexusSettings.getPinnedApps(this).forEach { app ->
            val button = TextView(this).apply {
                text = app.label.take(2).uppercase()
                setTextColor(getColor(R.color.text_muted))
                textSize = 12f
                gravity = android.view.Gravity.CENTER
                background = getDrawable(R.drawable.ripple_accent_circle)
                layoutParams = LinearLayout.LayoutParams(iconSize, iconSize).apply {
                    topMargin = margin
                    marginStart = margin
                    marginEnd = margin
                }
                setOnClickListener { openNewTab(app.url) }
                setOnLongClickListener {
                    androidx.appcompat.app.AlertDialog.Builder(this@MainActivity)
                        .setTitle("${app.label} entfernen?")
                        .setPositiveButton("Entfernen") { _, _ ->
                            NexusSettings.removePinnedApp(this@MainActivity, app)
                            renderSidebarIcons()
                        }
                        .setNegativeButton("Abbrechen", null)
                        .show()
                    true
                }
            }
            binding.sidebar.addView(button)
        }

        val addButton = TextView(this).apply {
            text = "+"
            setTextColor(getColor(R.color.accent_primary))
            textSize = 20f
            gravity = android.view.Gravity.CENTER
            background = getDrawable(R.drawable.ripple_accent_circle)
            layoutParams = LinearLayout.LayoutParams(iconSize, iconSize).apply {
                topMargin = margin
                marginStart = margin
                marginEnd = margin
            }
            setOnClickListener { showPinAppDialog() }
        }
        binding.sidebar.addView(addButton)
    }

    private fun showPinAppDialog() {
        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            val pad = resources.getDimensionPixelSize(R.dimen.space_16)
            setPadding(pad, pad, pad, pad)
        }
        val labelInput = android.widget.EditText(this).apply { hint = "Kürzel (z.B. YT)" }
        val urlInput = android.widget.EditText(this).apply { hint = "https://..." }
        container.addView(labelInput)
        container.addView(urlInput)

        androidx.appcompat.app.AlertDialog.Builder(this)
            .setTitle("App anpinnen")
            .setView(container)
            .setPositiveButton("Anpinnen") { _, _ ->
                val label = labelInput.text.toString().trim().ifBlank { "APP" }
                var url = urlInput.text.toString().trim()
                if (url.isEmpty()) return@setPositiveButton
                if (!url.startsWith("http://") && !url.startsWith("https://")) {
                    url = "https://$url"
                }
                NexusSettings.addPinnedApp(this, PinnedAppPref(label, url))
                renderSidebarIcons()
            }
            .setNegativeButton("Abbrechen", null)
            .show()
    }

    private fun toggleSidebar() {
        val collapsedWidth = resources.getDimensionPixelSize(R.dimen.sidebar_collapsed_width)
        val expandedWidth = resources.getDimensionPixelSize(R.dimen.sidebar_icon_width)
        val from = if (sidebarExpanded) expandedWidth else collapsedWidth
        val to = if (sidebarExpanded) collapsedWidth else expandedWidth
        sidebarExpanded = !sidebarExpanded

        ValueAnimator.ofInt(from, to).apply {
            duration = 180
            interpolator = DecelerateInterpolator()
            addUpdateListener { anim ->
                val width = anim.animatedValue as Int
                binding.sidebar.layoutParams.width = width
                binding.sidebar.requestLayout()
            }
            start()
        }
    }

    // ---------------------------------------------------------------------
    // Top Bar / Menü
    // ---------------------------------------------------------------------

    private fun setupTopBar() {
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

        binding.menuButton.setOnClickListener { showMainMenu(it) }
    }

    private fun showMainMenu(anchor: View) {
        val popup = PopupMenu(this, anchor)
        popup.menu.add(0, 1, 0, getString(R.string.menu_new_tab))
        popup.menu.add(0, 2, 1, getString(R.string.menu_download))
        popup.menu.add(0, 3, 2, getString(R.string.menu_mediathek))
        popup.menu.add(0, 4, 3, getString(R.string.menu_settings))

        popup.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                1 -> openNewTab(startPage)
                2 -> downloadVideoFromCurrentTab()
                3 -> startActivity(Intent(this, MediathekActivity::class.java))
                4 -> startActivity(Intent(this, SettingsActivity::class.java))
            }
            true
        }
        popup.show()
    }

    // ---------------------------------------------------------------------
    // Tabs
    // ---------------------------------------------------------------------

    private fun openNewTab(url: String): Int {
        val session = createSession()
        val tab = Tab(session = session, title = "Neuer Tab", url = url)
        val index = tabManager.addTab(tab)
        session.loadUri(url)

        renderTabStrip()
        switchToTab(index)
        return index
    }

    private fun createSession(): GeckoSession {
        val sessionSettings = GeckoSessionSettings.Builder()
            .usePrivateMode(false)
            .userAgentMode(GeckoSessionSettings.USER_AGENT_MODE_MOBILE)
            .build()

        val session = GeckoSession(sessionSettings)
        val redirectShield = RedirectShield(
            adBlockEngine = adBlockEngine,
            onBlocked = { blockedUri, reason ->
                runOnUiThread { showBlockedToast(blockedUri, reason) }
            },
            onTitleUpdate = { updatedSession, title ->
                runOnUiThread {
                    val tab = tabManager.tabs.find { it.session == updatedSession }
                    if (tab != null) {
                        tab.title = title?.takeIf { it.isNotBlank() } ?: tab.url
                        renderTabStrip()
                    }
                }
            },
            onLoadingStateChange = { loading ->
                runOnUiThread { binding.loadProgress.visibility = if (loading) View.VISIBLE else View.GONE }
            },
            onAllowedPopup = { popupUri ->
                // GeckoSession-Delegate-Callbacks laufen bereits auf dem Main-Thread,
                // daher läuft runOnUiThread hier synchron und newSession ist beim
                // return sicher gesetzt.
                var newSession: GeckoSession? = null
                runOnUiThread {
                    val popupIndex = openNewTab(popupUri)
                    newSession = tabManager.tabs.getOrNull(popupIndex)?.session
                }
                newSession
            }
        )
        session.navigationDelegate = redirectShield
        session.contentDelegate = redirectShield
        session.progressDelegate = redirectShield
        session.open((application as TufBladeApp).geckoRuntime)
        return session
    }

    private fun switchToTab(index: Int) {
        tabManager.setActive(index)
        val tab = tabManager.activeTab() ?: return

        val view = geckoView ?: GeckoView(this).also { newView ->
            geckoView = newView
            binding.contentContainer.addView(
                newView,
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.MATCH_PARENT
                )
            )
        }
        view.setSession(tab.session)

        binding.urlField.setText(tab.url)
        renderTabStrip()
    }

    private fun closeTab(index: Int) {
        tabManager.closeTab(index)
        if (tabManager.tabs.isEmpty()) {
            openNewTab(startPage)
        } else {
            switchToTab(tabManager.activeIndex)
        }
    }

    private fun renderTabStrip() {
        binding.tabStrip.removeAllViews()
        tabManager.tabs.forEachIndexed { index, tab ->
            val chip = LayoutInflater.from(this).inflate(R.layout.item_tab, binding.tabStrip, false)
            val titleView = chip.findViewById<TextView>(R.id.tabTitle)
            val closeView = chip.findViewById<TextView>(R.id.tabClose)

            titleView.text = tab.title.ifBlank { "Tab" }
            titleView.setTextColor(
                if (index == tabManager.activeIndex) getColor(R.color.accent_primary)
                else getColor(R.color.text_muted)
            )
            chip.setOnClickListener { switchToTab(index) }
            closeView.setOnClickListener { closeTab(index) }

            binding.tabStrip.addView(chip)
        }
    }

    // ---------------------------------------------------------------------
    // URL-Feld / Navigation
    // ---------------------------------------------------------------------

    private fun loadFromUrlField() {
        var input = binding.urlField.text.toString().trim()
        if (input.isEmpty()) return

        if (!input.startsWith("http://") && !input.startsWith("https://")) {
            input = if (input.contains(" ") || !input.contains(".")) {
                val engine = NexusSettings.getSearchEngine(this)
                "${engine.queryUrl}${input.replace(" ", "+")}"
            } else {
                "https://$input"
            }
        }
        adBlockEngine.resetCounter()
        val tab = tabManager.activeTab() ?: return
        tab.url = input
        tab.session.loadUri(input)
        renderTabStrip()
    }

    // ---------------------------------------------------------------------
    // Video-Download
    // ---------------------------------------------------------------------

    private fun downloadVideoFromCurrentTab() {
        val tab = tabManager.activeTab() ?: return
        val pageUrl = binding.urlField.text.toString().trim()
        if (pageUrl.isEmpty()) return

        Snackbar.make(binding.root, getString(R.string.download_started), Snackbar.LENGTH_SHORT).show()

        thread {
            try {
                val candidates = MediaLinkFinder.findVideoUrls(pageUrl)
                if (candidates.isEmpty()) {
                    runOnUiThread {
                        Snackbar.make(binding.root, getString(R.string.download_failed, "kein direkter Video-Link gefunden"), Snackbar.LENGTH_LONG).show()
                    }
                    return@thread
                }
                val entry = VideoDownloader.download(this, candidates.first(), tab.title)
                runOnUiThread {
                    Snackbar.make(binding.root, getString(R.string.download_finished, entry.title), Snackbar.LENGTH_LONG)
                        .setAction(getString(R.string.menu_mediathek)) {
                            startActivity(Intent(this, MediathekActivity::class.java))
                        }
                        .show()
                }
            } catch (e: Exception) {
                runOnUiThread {
                    Snackbar.make(binding.root, getString(R.string.download_failed, e.message ?: "unbekannter Fehler"), Snackbar.LENGTH_LONG).show()
                }
            }
        }
    }

    // ---------------------------------------------------------------------
    // Adblock/Redirect-Shield Feedback
    // ---------------------------------------------------------------------

    private fun showBlockedToast(uri: String, reason: RedirectShield.BlockReason) {
        binding.shieldBadge.text = adBlockEngine.blockedCount.toString()

        val label = when (reason) {
            RedirectShield.BlockReason.AD_HOST -> "Werbung/Tracker blockiert"
            RedirectShield.BlockReason.POPUP_NO_GESTURE -> "Popup ohne Nutzeraktion blockiert"
            RedirectShield.BlockReason.REDIRECT_NO_GESTURE -> "Weiterleitung blockiert"
        }

        if (reason != RedirectShield.BlockReason.AD_HOST) {
            Snackbar.make(binding.root, label, Snackbar.LENGTH_LONG)
                .setAction("Trotzdem öffnen") { tabManager.activeTab()?.session?.loadUri(uri) }
                .show()
        }
    }

    override fun onResume() {
        super.onResume()
        if (::adBlockEngine.isInitialized) {
            adBlockEngine.enabled = NexusSettings.isAdBlockEnabled(this)
        }
        if (::binding.isInitialized) {
            renderSidebarIcons()
        }
    }

    override fun onDestroy() {
        tabManager.closeAll()
        super.onDestroy()
    }
}
