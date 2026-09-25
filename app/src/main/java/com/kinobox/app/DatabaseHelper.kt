package com.kinobox.app

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream

class DatabaseHelper(private val context: Context) {
    private val dbName = "tracker.db"

    init {
        copyDatabaseIfNeeded()
    }

    private fun copyDatabaseIfNeeded() {
        val dbFile = context.getDatabasePath(dbName)
        if (!dbFile.exists()) {
            dbFile.parentFile?.mkdirs()
            context.assets.open("databases/$dbName").use { input ->
                FileOutputStream(dbFile).use { output ->
                    input.copyTo(output)
                }
            }
        }
    }

    fun getAllMoviesJson(): String {
        val dbFile = context.getDatabasePath(dbName)
        if (!dbFile.exists()) return "[]"
        
        val db = SQLiteDatabase.openDatabase(dbFile.path, null, SQLiteDatabase.OPEN_READONLY)
        val array = JSONArray()

        val tableCursor = db.rawQuery(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1", null
        )
        var tableName = "movies"
        if (tableCursor.moveToFirst()) {
            tableName = tableCursor.getString(0)
        }
        tableCursor.close()

        val cursor = db.rawQuery("SELECT * FROM $tableName", null)
        val columnNames = cursor.columnNames

        while (cursor.moveToNext()) {
            val obj = JSONObject()
            for (col in columnNames) {
                val index = cursor.getColumnIndex(col)
                obj.put(col, cursor.getString(index))
            }
            array.put(obj)
        }
        cursor.close()
        db.close()
        return array.toString()
    }
}
