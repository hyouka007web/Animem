package com.tufblade.browser.media

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.tufblade.browser.R

class VideoAdapter(
    private val items: MutableList<VideoEntry>,
    private val onClick: (VideoEntry) -> Unit,
    private val onLongClick: (VideoEntry) -> Unit
) : RecyclerView.Adapter<VideoAdapter.VideoViewHolder>() {

    class VideoViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val thumbnail: ImageView = view.findViewById(R.id.videoThumbnail)
        val title: TextView = view.findViewById(R.id.videoTitle)
        val meta: TextView = view.findViewById(R.id.videoMeta)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VideoViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_video, parent, false)
        return VideoViewHolder(view)
    }

    override fun onBindViewHolder(holder: VideoViewHolder, position: Int) {
        val entry = items[position]
        holder.title.text = entry.title
        holder.meta.text = "${formatSize(entry.sizeBytes)} · ${entry.downloadedAt}"
        holder.itemView.setOnClickListener { onClick(entry) }
        holder.itemView.setOnLongClickListener { onLongClick(entry); true }
        loadThumbnail(entry, holder.thumbnail)
    }

    private fun loadThumbnail(entry: VideoEntry, imageView: ImageView) {
        imageView.setImageDrawable(null)
        Thread {
            try {
                val retriever = android.media.MediaMetadataRetriever()
                retriever.setDataSource(entry.filePath)
                val frame = retriever.getFrameAtTime(0)
                retriever.release()
                if (frame != null) {
                    imageView.post { imageView.setImageBitmap(frame) }
                }
            } catch (e: Exception) {
                // Kein Frame extrahierbar (z.B. beschädigte Datei) - Platzhalter bleibt leer
            }
        }.start()
    }

    override fun getItemCount() = items.size

    fun updateItems(newItems: List<VideoEntry>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    private fun formatSize(bytes: Long): String {
        val mb = bytes / (1024.0 * 1024.0)
        return if (mb >= 1) "%.1f MB".format(mb) else "${bytes / 1024} KB"
    }
}
