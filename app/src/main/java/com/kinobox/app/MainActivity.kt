package com.kinobox.app

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.util.Log
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

        // Копируем базу, сессию и интерфейс во внутреннее хранилище
        copyAssetToFile("tracker.db")
        copyAssetToFile("my_session.session")
        copyAssetToFile(".env")
        copyAssetToFile("index.html")

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        // Запуск Python сервера в фоне
        thread(isDaemon = true) {
            try {
                val py = Python.getInstance()
                py.getModule("server").callAttr("start_server_main", filesDir.absolutePath)
            } catch (e: Exception) {
                Log.e("KinoboxPy", "Ошибка запуска Python: ${e.message}", e)
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

        // Даем серверу время на старт и открываем каталог
        webView.postDelayed({
            webView.loadUrl("http://127.0.0.1:8080")
        }, 2000)
    }

    private fun copyAssetToFile(fileName: String) {
        try {
            val dest = File(filesDir, fileName)
            assets.open(fileName).use { input ->
                val assetSize = input.available().toLong()
                if (!dest.exists() || dest.length() != assetSize) {
                    dest.parentFile?.mkdirs()
                    FileOutputStream(dest).use { output ->
                        input.copyTo(output)
                    }
                    Log.d("KinoboxAsset", "Скопирован $fileName (${dest.length()} байт)")
                }
            }
        } catch (e: Exception) {
            Log.e("KinoboxAsset", "Ошибка копирования $fileName: ${e.message}")
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
                view?.postDelayed({ view.reload() }, 1500)
            }
        }

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
