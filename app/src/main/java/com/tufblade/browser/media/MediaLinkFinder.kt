package com.tufblade.browser.media

import java.net.HttpURLConnection
import java.net.URL
import java.util.regex.Pattern

/**
 * Sucht direkte Video-Links im HTML einer Seite (video/source-Tags, og:video
 * Meta-Tags, sowie rohe .mp4/.webm/.m3u8-URLs im Markup). Bewusst simpel
 * gehalten (Regex statt vollem HTML-Parser) - reicht für die meisten Seiten
 * mit direkt eingebettetem Video, deckt aber keine dynamisch per JavaScript
 * nachgeladenen Player ab (dafür bräuchte es echten Media-Sniffer via
 * WebExtension - siehe README-TODO für den Ausbau).
 */
object MediaLinkFinder {

    private val VIDEO_URL_PATTERN = Pattern.compile(
        "https?://[^\"'\\s>]+\\.(mp4|webm|m3u8)(\\?[^\"'\\s>]*)?",
        Pattern.CASE_INSENSITIVE
    )

    /** Blockierender Netzwerkaufruf - immer auf Background-Thread ausführen. */
    fun findVideoUrls(pageUrl: String): List<String> {
        val connection = URL(pageUrl).openConnection() as HttpURLConnection
        connection.connectTimeout = 10000
        connection.readTimeout = 15000
        connection.instanceFollowRedirects = true
        connection.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14)")

        val html = connection.inputStream.bufferedReader().use { it.readText() }
        connection.disconnect()

        val matcher = VIDEO_URL_PATTERN.matcher(html)
        val found = LinkedHashSet<String>()
        while (matcher.find()) {
            found.add(matcher.group().replace("&amp;", "&"))
        }
        return found.toList()
    }
}
