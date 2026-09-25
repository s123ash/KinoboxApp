package com.kinobox.app

import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
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

        val rootLayout = FrameLayout(this).apply {
            setBackgroundColor(Color.BLACK)
        }

        playerView = PlayerView(this).apply {
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }
        rootLayout.addView(playerView)

        progressBar = ProgressBar(this).apply {
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.CENTER
            )
        }
        rootLayout.addView(progressBar)

        statusText = TextView(this).apply {
            setTextColor(Color.WHITE)
            textSize = 15f
            gravity = Gravity.CENTER
            setPadding(40, 40, 40, 40)
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.CENTER
            )
        }
        rootLayout.addView(statusText)

        partsContainer = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(20, 50, 20, 20)
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.TOP
            )
        }
        rootLayout.addView(partsContainer)

        setContentView(rootLayout)

        initPlayer()

        val pid = intent.getIntExtra("PID", 0)
        loadMovieParts(pid)
    }

    private fun initPlayer() {
        player = ExoPlayer.Builder(this).build()
        playerView.player = player

        player?.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                when (state) {
                    Player.STATE_BUFFERING -> progressBar.visibility = View.VISIBLE
                    Player.STATE_READY -> {
                        progressBar.visibility = View.GONE
                        statusText.visibility = View.GONE
                    }
                    Player.STATE_ENDED -> progressBar.visibility = View.GONE
                    Player.STATE_IDLE -> {}
                }
            }

            override fun onPlayerError(error: PlaybackException) {
                progressBar.visibility = View.GONE
                statusText.visibility = View.VISIBLE
                statusText.text = "Ошибка воспроизведения:\n${error.message}\n(Проверьте VPN/интернет на телефоне)"
            }
        })
    }

    private fun loadMovieParts(pid: Int) {
        statusText.text = "Поиск видео в Telegram..."
        thread {
            try {
                val url = URL("http://127.0.0.1:8080/api/parts?pid=$pid")
                val con = url.openConnection() as HttpURLConnection
                val jsonStr = con.inputStream.bufferedReader().use { it.readText() }
                val data = JSONObject(jsonStr)

                val channelId = data.getString("channel_id")
                val partsArray = data.getJSONArray("parts")

                runOnUiThread {
                    partsContainer.removeAllViews()
                    if (partsArray.length() > 1) {
                        for (i in 0 until partsArray.length()) {
                            val partObj = partsArray.getJSONObject(i)
                            val partNum = partObj.getInt("part")
                            val msgId = partObj.getInt("msg_id")

                            val btn = Button(this).apply {
                                text = "Часть $partNum"
                                setBackgroundColor(if (i == 0) Color.parseColor("#4A6CF7") else Color.DKGRAY)
                                setTextColor(Color.WHITE)
                                setOnClickListener {
                                    for (j in 0 until partsContainer.childCount) {
                                        partsContainer.getChildAt(j).setBackgroundColor(Color.DKGRAY)
                                    }
                                    setBackgroundColor(Color.parseColor("#4A6CF7"))
                                    playStream(channelId, msgId)
                                }
                            }
                            partsContainer.addView(btn)
                        }
                    }

                    if (partsArray.length() > 0) {
                        val firstMsgId = partsArray.getJSONObject(0).getInt("msg_id")
                        playStream(channelId, firstMsgId)
                    } else {
                        statusText.text = "В посте не найдено видео"
                        progressBar.visibility = View.GONE
                    }
                }
            } catch (e: Exception) {
                runOnUiThread {
                    statusText.text = "Не удалось связаться с сервером:\n${e.message}"
                    progressBar.visibility = View.GONE
                }
            }
        }
    }

    private fun playStream(channelId: String, msgId: Int) {
        statusText.text = "Буферизация потока..."
        statusText.visibility = View.VISIBLE
        progressBar.visibility = View.VISIBLE

        val streamUrl = "http://127.0.0.1:8080/stream?channel_id=$channelId&msg_id=$msgId"
        val mediaItem = MediaItem.fromUri(Uri.parse(streamUrl))
        player?.setMediaItem(mediaItem)
        player?.prepare()
        player?.play()
    }

    override fun onStop() {
        super.onStop()
        player?.pause()
    }

    override fun onDestroy() {
        super.onDestroy()
        player?.release()
        player = null
    }
}
