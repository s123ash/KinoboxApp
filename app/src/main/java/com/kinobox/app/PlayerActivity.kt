package com.kinobox.app

import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class PlayerActivity : AppCompatActivity() {
    private var player: ExoPlayer? = null
    private lateinit var playerView: PlayerView
    private lateinit var partsContainer: LinearLayout
    private lateinit var statusText: TextView
    private lateinit var progressBar: ProgressBar

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        val root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        playerView = PlayerView(this).apply {
            layoutParams = FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
        }
        root.addView(playerView)

        progressBar = ProgressBar(this).apply {
            layoutParams = FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER)
        }
        root.addView(progressBar)

        statusText = TextView(this).apply {
            setTextColor(Color.WHITE); textSize = 15f; gravity = Gravity.CENTER
            layoutParams = FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER)
        }
        root.addView(statusText)

        partsContainer = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER; setPadding(20, 50, 20, 20)
            layoutParams = FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP)
        }
        root.addView(partsContainer)
        setContentView(root)

        player = ExoPlayer.Builder(this).build()
        playerView.player = player
        player?.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                when (state) {
                    Player.STATE_BUFFERING -> progressBar.visibility = View.VISIBLE
                    Player.STATE_READY -> { progressBar.visibility = View.GONE; statusText.visibility = View.GONE }
                    Player.STATE_ENDED -> progressBar.visibility = View.GONE
                    else -> {}
                }
            }
            override fun onPlayerError(e: PlaybackException) {
                progressBar.visibility = View.GONE; statusText.visibility = View.VISIBLE
                statusText.text = "Ошибка воспроизведения:\n${e.message}\n(Проверьте VPN/сеть)"
            }
        })

        loadMovieParts(intent.getIntExtra("PID", 0))
    }

    private fun loadMovieParts(pid: Int) {
        statusText.text = "Поиск видео в Telegram..."
        thread {
            try {
                val conn = URL("http://127.0.0.1:8080/api/parts?pid=$pid").openConnection() as HttpURLConnection
                val data = JSONObject(conn.inputStream.bufferedReader().use { it.readText() })
                val cid = data.getString("channel_id")
                val parts = data.getJSONArray("parts")
                runOnUiThread {
                    partsContainer.removeAllViews()
                    if (parts.length() > 1) {
                        for (i in 0 until parts.length()) {
                            val p = parts.getJSONObject(i)
                            val btn = Button(this).apply {
                                text = "Часть ${p.getInt("part")}"
                                setBackgroundColor(if (i == 0) Color.parseColor("#4A6CF7") else Color.DKGRAY)
                                setTextColor(Color.WHITE)
                                setOnClickListener {
                                    for (j in 0 until partsContainer.childCount) partsContainer.getChildAt(j).setBackgroundColor(Color.DKGRAY)
                                    setBackgroundColor(Color.parseColor("#4A6CF7"))
                                    playStream(cid, p.getInt("msg_id"))
                                }
                            }
                            partsContainer.addView(btn)
                        }
                    }
                    if (parts.length() > 0) playStream(cid, parts.getJSONObject(0).getInt("msg_id"))
                    else { statusText.text = "Видео не найдено"; progressBar.visibility = View.GONE }
                }
            } catch (e: Exception) {
                runOnUiThread { statusText.text = "Сервер недоступен: ${e.message}"; progressBar.visibility = View.GONE }
            }
        }
    }

    private fun playStream(cid: String, mid: Int) {
        statusText.text = "Буферизация..."; statusText.visibility = View.VISIBLE; progressBar.visibility = View.VISIBLE
        player?.setMediaItem(MediaItem.fromUri(Uri.parse("http://127.0.0.1:8080/stream?channel_id=$cid&msg_id=$mid")))
        player?.prepare()
        player?.play()
    }

    override fun onStop() { super.onStop(); player?.pause() }
    override fun onDestroy() { super.onDestroy(); player?.release(); player = null }
}