package com.kinobox.app

import android.annotation.SuppressLint
import android.graphics.Color
import android.os.Bundle
import android.util.Log
import android.view.ViewGroup
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var dbHelper: DatabaseHelper

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Перехват фатальных ошибок с выводом на экран вместо мгновенного вылета
        Thread.setDefaultUncaughtExceptionHandler { _, throwable ->
            runOnUiThread {
                showCrashScreen(throwable)
            }
        }

        try {
            dbHelper = DatabaseHelper(this)
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
        } catch (e: Throwable) {
            showCrashScreen(e)
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = true
            allowContentAccess = true
            allowFileAccessFromFileURLs = true
            allowUniversalAccessFromFileURLs = true
            cacheMode = WebSettings.LOAD_DEFAULT
            useWideViewPort = true
            loadWithOverviewMode = true
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(consoleMessage: ConsoleMessage?): Boolean {
                Log.d("KinoboxJS", "[${consoleMessage?.messageLevel()}] ${consoleMessage?.message()}")
                return true
            }
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                // Инжектим безопасную заглушку для Telegram WebApp, чтобы старый JS не падал
                val tgShim = """
                    if (!window.Telegram) window.Telegram = {};
                    if (!window.Telegram.WebApp) {
                        window.Telegram.WebApp = {
                            ready: function() {},
                            expand: function() {},
                            close: function() {},
                            HapticFeedback: { impactOccurred: function() {}, notificationOccurred: function() {} },
                            BackButton: { show: function() {}, hide: function() {}, onClick: function() {} },
                            initDataUnsafe: {}
                        };
                    }
                """.trimIndent()
                view?.evaluateJavascript(tgShim, null)
            }

            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                Log.e("KinoboxWeb", "Ошибка загрузки: ${error?.description}")
            }
        }

        webView.addJavascriptInterface(WebAppBridge(this, dbHelper), "Android")
        webView.loadUrl("file:///android_asset/www/index.html")
    }

    private fun showCrashScreen(throwable: Throwable) {
        val errorText = TextView(this).apply {
            text = "Ошибка при запуске Kinobox:\n\n${throwable.stackTraceToString()}"
            setTextColor(Color.RED)
            setBackgroundColor(Color.BLACK)
            setPadding(40, 60, 40, 40)
            textSize = 14f
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }
        setContentView(errorText)
    }
}
