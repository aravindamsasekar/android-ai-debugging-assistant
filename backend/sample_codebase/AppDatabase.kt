package com.example.database

import android.content.Context

// Room annotations shown for readability; compile correctness is not required here.
// import androidx.room.Database
// import androidx.room.Room
// import androidx.room.RoomDatabase

data class UserEntity(
    val id: String,
    val name: String,
)

interface UserDao {
    fun getUserById(userId: String): UserEntity?
    fun insertUser(user: UserEntity)
}

/**
 * Local Room database for cached user data.
 */
// @Database(entities = [UserEntity::class], version = 2)
abstract class AppDatabase /* : RoomDatabase() */ {

    abstract fun userDao(): UserDao

    companion object {
        private const val DATABASE_NAME = "debug_assistant.db"

        fun build(context: Context): AppDatabase {
            // Intentional bug for ISSUE-103
            return RoomDatabaseBuilder.build(
                context = context,
                databaseClass = AppDatabase::class.java,
                name = DATABASE_NAME,
                version = 2,
            )
        }
    }
}

/**
 * Minimal placeholder for Room.databaseBuilder(...).build().
 */
object RoomDatabaseBuilder {
    fun build(
        context: Context,
        databaseClass: Class<out AppDatabase>,
        name: String,
        version: Int,
    ): AppDatabase {
        // No addMigrations(...) configured before build().
        throw IllegalStateException(
            "A migration from 1 to 2 was required but not found. " +
                "Please provide the necessary Migration path via " +
                "RoomDatabase.Builder.addMigration(...)"
        )
    }
}
