package com.kinobox.app

import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.FrameLayout
import androidx.appcompat.app.AppCompatActivity
import androidx.media3.common.MediaItem
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

        // Панель переключения частей [1] [2] [3]
        partsContainer = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(20, 40, 20, 20)
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.TOP
            )
        }
        rootLayout.addView(partsContainer)

        setContentView(rootLayout)

        player = ExoPlayer.Builder(this).build()
        playerView.player = player

        val pid = intent.getIntExtra("PID", 0)
        loadMovieParts(pid)
    }

    private fun loadMovieParts(pid: Int) {
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
                                setBackgroundColor(if (i == 0) Color.parseColor("#E50914") else Color.DKGRAY)
                                setTextColor(Color.WHITE)
                                setOnClickListener {
                                    for (j in 0 until partsContainer.childCount) {
                                        partsContainer.getChildAt(j).setBackgroundColor(Color.DKGRAY)
                                    }
                                    setBackgroundColor(Color.parseColor("#E50914"))
                                    playStream(channelId, msgId)
                                }
                            }
                            partsContainer.addView(btn)
                        }
                    }
                    if (partsArray.length() > 0) {
                        val firstMsgId = partsArray.getJSONObject(0).getInt("msg_id")
                        playStream(channelId, firstMsgId)
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    private fun playStream(channelId: String, msgId: Int) {
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
