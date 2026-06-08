package com.example.repository

import com.example.mapper.UserDto
import com.example.mapper.UserMapper
import com.example.mapper.UserProfile

/**
 * Loads user profile data for the profile screen.
 */
class UserRepository(
    private val userMapper: UserMapper,
) {

    fun getProfile(userId: String): UserProfile {
        val dto = fetchUserDto(userId)

        // Map DTO to a profile the UI can render.
        val displayName = userMapper.toDisplayName(dto)
        return UserProfile(
            userId = userId,
            displayName = displayName,
            email = dto.email.orEmpty(),
        )
    }

    private fun fetchUserDto(userId: String): UserDto {
        // Simulates API response where profile name may be missing.
        return when (userId) {
            "user_missing_name" -> UserDto(
                id = userId,
                name = null,
                email = "user@example.com",
            )
            else -> UserDto(
                id = userId,
                name = "Aravind",
                email = "aravind@example.com",
            )
        }
    }
}
