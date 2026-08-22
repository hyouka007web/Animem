package com.tufblade.browser.adblock

import android.content.Context
import android.net.Uri
import java.io.BufferedReader
import java.io.InputStreamReader

/**
 * "Verstärkter" Adblocker, Ebene 2 (Ebene 1 = Geckos natives ContentBlocking in TufBladeApp.kt).
 *
 * Funktionsweise wie klassische Adblock-Browser: eine Host-Sperrliste
 * (EasyList/EasyPrivacy-Format, hier als reduzierte Beispiel-Liste unter
 * assets/blocklist_hosts.txt) wird beim Start einmal geladen und in ein
 * HashSet gemappt -> O(1)-Lookup pro Request, kein spürbarer Overhead.
 *
 * WICHTIG (TODO für Produktivbetrieb):
 * Diese Beispiel-Liste ist bewusst klein gehalten. Für echten EasyList/
 * EasyPrivacy-Umfang: die .txt-Dateien von easylist.to beim App-Start oder
 * per WorkManager-Job periodisch herunterladen, mit diesem Parser einlesen
 * und lokal cachen (nicht ins Repo einchecken — Lizenz/Aktualität).
 */
class AdBlockEngine private constructor(
    private val blockedHosts: HashSet<String>,
    private val blockedSubstrings: List<String>
) {
    var blockedCount: Int = 0
        private set

    /** true = Request wird geblockt. Ruft man aus NavigationDelegate.onLoadRequest auf. */
    fun shouldBlock(uri: Uri): Boolean {
        val host = uri.host ?: return false

        // 1) exakter oder Subdomain-Treffer gegen die Host-Liste
        var h = host
        while (h.isNotEmpty()) {
            if (blockedHosts.contains(h)) {
                blockedCount++
                return true
            }
            val dot = h.indexOf('.')
            if (dot < 0) break
            h = h.substring(dot + 1)
        }

        // 2) grobe Pattern-Treffer (z. B. "/ads/", "doubleclick", Tracking-Pixel-Pfade)
        val fullUrl = uri.toString()
        for (pattern in blockedSubstrings) {
            if (fullUrl.contains(pattern, ignoreCase = true)) {
                blockedCount++
                return true
            }
        }
        return false
    }

    fun resetCounter() {
        blockedCount = 0
    }

    companion object {
        private const val ASSET_PATH = "blocklist_hosts.txt"

        fun loadFromAssets(context: Context): AdBlockEngine {
            val hosts = HashSet<String>()
            val substrings = mutableListOf<String>()

            context.assets.open(ASSET_PATH).use { input ->
                BufferedReader(InputStreamReader(input)).forEachLine { rawLine ->
                    val line = rawLine.trim()
                    if (line.isEmpty() || line.startsWith("#") || line.startsWith("!")) return@forEachLine

                    when {
                        // Adblock-Plus-Style: ||domain.tld^
                        line.startsWith("||") -> {
                            val end = line.indexOf('^').takeIf { it > 0 } ?: line.length
                            hosts.add(line.substring(2, end).lowercase())
                        }
                        // Hosts-Datei-Style: 0.0.0.0 domain.tld
                        line.startsWith("0.0.0.0 ") || line.startsWith("127.0.0.1 ") -> {
                            val parts = line.split(Regex("\\s+"))
                            if (parts.size >= 2) hosts.add(parts[1].lowercase())
                        }
                        // Alles andere als grober Substring-Filter
                        else -> substrings.add(line.lowercase())
                    }
                }
            }
            return AdBlockEngine(hosts, substrings)
        }
    }
}
