package com.tufblade.browser

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.GridLayoutManager
import androidx.core.content.FileProvider
import com.tufblade.browser.media.VideoAdapter
import com.tufblade.browser.media.VideoDownloader
import java.io.File

class MediathekActivity : AppCompatActivity() {

    private lateinit var adapter: VideoAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_mediathek)

        findViewById<android.widget.ImageButton>(R.id.mediathekBackButton).setOnClickListener {
            finish()
        }

        val grid = findViewById<androidx.recyclerview.widget.RecyclerView>(R.id.mediathekGrid)
        val emptyState = findViewById<android.widget.TextView>(R.id.mediathekEmptyState)
        grid.layoutManager = GridLayoutManager(this, 2)

        val entries = VideoDownloader.loadIndex(this).toMutableList()
        adapter = VideoAdapter(
            items = entries,
            onClick = { entry -> playVideo(entry.filePath) },
            onLongClick = { entry -> confirmDelete(entry) }
        )
        grid.adapter = adapter

        emptyState.visibility = if (entries.isEmpty()) android.view.View.VISIBLE else android.view.View.GONE
    }

    private fun playVideo(path: String) {
        val file = File(path)
        if (!file.exists()) return
        val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", file)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "video/*")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(intent)
    }

    private fun confirmDelete(entry: com.tufblade.browser.media.VideoEntry) {
        AlertDialog.Builder(this)
            .setTitle("Video löschen?")
            .setMessage(entry.title)
            .setPositiveButton("Löschen") { _, _ ->
                VideoDownloader.delete(this, entry)
                refresh()
            }
            .setNegativeButton("Abbrechen", null)
            .show()
    }

    private fun refresh() {
        val entries = VideoDownloader.loadIndex(this)
        adapter.updateItems(entries)
        findViewById<android.widget.TextView>(R.id.mediathekEmptyState).visibility =
            if (entries.isEmpty()) android.view.View.VISIBLE else android.view.View.GONE
    }
}
