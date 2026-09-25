package com.kinobox.app

import android.content.Context
import android.content.Intent
import android.webkit.JavascriptInterface

class WebAppBridge(private val context: Context, private val dbHelper: DatabaseHelper) {

    @JavascriptInterface
    fun getMovies(): String {
        return dbHelper.getMoviesFiltered("all", "ALL", "")
    }

    @JavascriptInterface
    fun getMoviesFiltered(folder: String?, category: String?, search: String?): String {
        return dbHelper.getMoviesFiltered(folder, category, search)
    }

    @JavascriptInterface
    fun getSingleMovie(pid: String?): String {
        return dbHelper.getSingleMovie(pid)
    }

    @JavascriptInterface
    fun getStats(): String {
        return dbHelper.getStats()
    }

    @JavascriptInterface
    fun playMovie(messageId: String, title: String) {
        val intent = Intent(context, PlayerActivity::class.java).apply {
            putExtra("MESSAGE_ID", messageId)
            putExtra("TITLE", title)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        context.startActivity(intent)
    }
}
