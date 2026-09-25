package com.kinobox.app

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
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

        // Копируем файлы окружения в изолированное хранилище
        copyAssetToFiles("tracker.db")
        copyAssetToFiles("my_session.session")
        copyAssetToFiles(".env")

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        // Запуск Python aiohttp стримера в фоне
        thread(isDaemon = true) {
            try {
                val py = Python.getInstance()
                py.getModule("server").callAttr("start_server_main", filesDir.absolutePath)
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }

        webView = WebView(this).apply {
            setBackgroundColor(Color.parseColor("#0D0D11"))
        }
        setContentView(webView)

        setupWebView()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })

        // Даем серверу 2 секунды на инициализацию Pyrogram и открываем каталог
        webView.postDelayed({
            webView.loadUrl("http://127.0.0.1:8080")
        }, 2000)
    }

    private fun copyAssetToFiles(fileName: String) {
        val dest = File(filesDir, fileName)
        if (!dest.exists()) {
            try {
                val pyModule = File(filesDir, "chaquopy/AssetFinder/app/$fileName")
                if (pyModule.exists()) {
                    pyModule.copyTo(dest, overwrite = true)
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = true
            cacheMode = WebSettings.LOAD_DEFAULT
            useWideViewPort = true
            loadWithOverviewMode = true
        }

        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun onReceivedError(view: WebView?, errorCode: Int, description: String?, failingUrl: String?) {
                view?.postDelayed({ view.reload() }, 1000)
            }
        }

        // Мост для вызова нативного плеера по клику из JS
        webView.addJavascriptInterface(object {
            @JavascriptInterface
            fun openPlayer(pid: Int) {
                val intent = Intent(this@MainActivity, PlayerActivity::class.java).apply {
                    putExtra("PID", pid)
                }
                startActivity(intent)
            }
        }, "KinoboxNative")
    }
}
