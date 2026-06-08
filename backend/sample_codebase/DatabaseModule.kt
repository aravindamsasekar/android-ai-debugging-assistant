package com.example.database

import android.content.Context

/**
 * Provides database dependencies for the app.
 */
object DatabaseModule {

    fun provideDatabase(context: Context): AppDatabase {
        // Missing migration configuration — see ISSUE-103
        return AppDatabase.build(context)
    }

    fun provideUserDao(context: Context): UserDao {
        return provideDatabase(context).userDao()
    }
}
