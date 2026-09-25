package com.kinobox.app

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.webkit.*
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.io.FileOutputStream
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Копируем все необходимые файлы (особенно env.txt)
        copyAsset("env.txt", true)
        copyAsset("tracker.db", false)
        copyAsset("my_session.session", false)
        copyAsset("index.html", true)

        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
        thread(isDaemon = true) {
            try {
                Python.getInstance().getModule("server").callAttr("start_server_main", filesDir.absolutePath)
            } catch (e: Exception) { e.printStackTrace() }
        }

        webView = WebView(this).apply { setBackgroundColor(Color.parseColor("#0D0D11")) }
        setContentView(webView)

        webView.settings.apply {
            javaScriptEnabled = true; domStorageEnabled = true; allowFileAccess = true
            cacheMode = WebSettings.LOAD_DEFAULT; useWideViewPort = true; loadWithOverviewMode = true
        }
        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun onReceivedError(v: WebView?, c: Int, d: String?, u: String?) { v?.postDelayed({ v.reload() }, 1500) }
        }
        webView.addJavascriptInterface(object {
            @JavascriptInterface
            fun openPlayer(pid: Int) {
                startActivity(Intent(this@MainActivity, PlayerActivity::class.java).apply { putExtra("PID", pid) })
            }
        }, "KinoboxNative")

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else { isEnabled = false; onBackPressedDispatcher.onBackPressed() }
            }
        })
        
        // Даем серверу чуть больше времени на первый запуск, затем открываем каталог
        webView.postDelayed({ webView.loadUrl("http://127.0.0.1:8080") }, 2500)
    }

    private fun copyAsset(name: String, overwrite: Boolean) {
        val dest = File(filesDir, name)
        if (overwrite || !dest.exists() || dest.length() == 0L) {
            try {
                assets.open(name).use { input ->
                    dest.parentFile?.mkdirs()
                    FileOutputStream(dest).use { input.copyTo(it) }
                }
            } catch (e: Exception) { e.printStackTrace() }
        }
    }
}