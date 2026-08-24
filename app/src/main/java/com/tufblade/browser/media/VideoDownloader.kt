package com.tufblade.browser.media

import android.content.Context
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

data class VideoEntry(
    val id: String,
    val title: String,
    val filePath: String,
    val sourceUrl: String,
    val downloadedAt: String,
    val sizeBytes: Long
)

/**
 * Nativer Video-Downloader (kein Python/Chaquopy) — bewusste Design-
 * Entscheidung: Chaquopy ist laut offizieller Doku nur bis AGP 9.2.x
 * getestet, dieses Projekt nutzt aber schon AGP 9.3.1. Statt das Risiko
 * einer weiteren Absturz-/Build-Schleife einzugehen, lädt dieser
 * Downloader direkte Video-Links (mp4 u.ä.) selbst herunter.
 *
 * EINSCHRÄNKUNG (bewusst, ehrlich kommuniziert): funktioniert für Seiten
 * mit direktem Video-Link (z.B. <video src="...mp4">), NICHT für Seiten,
 * die eine komplexe eigene Extraktion brauchen (YouTube & Co. verschlüsseln
 * ihre Streams clientseitig). Für sowas wäre yt-dlp nötig — siehe README-TODO.
 */
object VideoDownloader {

    private const val INDEX_FILE = "mediathek_index.json"

    fun downloadsDir(context: Context): File =
        File(context.filesDir, "downloads").apply { mkdirs() }

    private fun indexFile(context: Context): File =
        File(downloadsDir(context), INDEX_FILE)

    fun loadIndex(context: Context): List<VideoEntry> {
        val file = indexFile(context)
        if (!file.exists()) return emptyList()
        return try {
            val arr = JSONArray(file.readText())
            (0 until arr.length()).map { i ->
                val o = arr.getJSONObject(i)
                VideoEntry(
                    id = o.getString("id"),
                    title = o.getString("title"),
                    filePath = o.getString("filePath"),
                    sourceUrl = o.getString("sourceUrl"),
                    downloadedAt = o.getString("downloadedAt"),
                    sizeBytes = o.optLong("sizeBytes", 0L)
                )
            }
        } catch (e: Exception) {
            Log.w("VideoDownloader", "Index konnte nicht gelesen werden", e)
            emptyList()
        }
    }

    private fun saveIndex(context: Context, entries: List<VideoEntry>) {
        val arr = JSONArray()
        entries.forEach { e ->
            arr.put(JSONObject().apply {
                put("id", e.id)
                put("title", e.title)
                put("filePath", e.filePath)
                put("sourceUrl", e.sourceUrl)
                put("downloadedAt", e.downloadedAt)
                put("sizeBytes", e.sizeBytes)
            })
        }
        indexFile(context).writeText(arr.toString())
    }

    /**
     * Lädt eine direkte Video-URL synchron herunter (auf Background-Thread aufrufen!).
     * Wirft eine Exception bei Fehlern - Aufrufer fängt das ab.
     */
    fun download(context: Context, videoUrl: String, pageTitle: String): VideoEntry {
        val id = UUID.randomUUID().toString().take(8)
        val extension = guessExtension(videoUrl)
        val targetFile = File(downloadsDir(context), "$id.$extension")

        val connection = URL(videoUrl).openConnection() as HttpURLConnection
        connection.connectTimeout = 15000
        connection.readTimeout = 30000
        connection.instanceFollowRedirects = true

        connection.inputStream.use { input ->
            targetFile.outputStream().use { output ->
                input.copyTo(output, bufferSize = 8 * 1024)
            }
        }
        connection.disconnect()

        val timestamp = SimpleDateFormat("dd.MM.yyyy HH:mm", Locale.GERMANY).format(Date())
        val entry = VideoEntry(
            id = id,
            title = pageTitle.ifBlank { "Video $id" },
            filePath = targetFile.absolutePath,
            sourceUrl = videoUrl,
            downloadedAt = timestamp,
            sizeBytes = targetFile.length()
        )

        val updated = loadIndex(context) + entry
        saveIndex(context, updated)
        return entry
    }

    fun delete(context: Context, entry: VideoEntry) {
        File(entry.filePath).delete()
        val updated = loadIndex(context).filterNot { it.id == entry.id }
        saveIndex(context, updated)
    }

    private fun guessExtension(url: String): String {
        val clean = url.substringBefore("?").substringAfterLast(".")
        return if (clean.length in 2..4) clean else "mp4"
    }
}
