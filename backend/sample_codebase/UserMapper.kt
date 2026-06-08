package com.example.mapper

/**
 * Maps user DTOs to display models for the profile screen.
 */
data class UserDto(
    val id: String,
    val name: String?,
    val email: String?,
)

data class UserProfile(
    val userId: String,
    val displayName: String,
    val email: String,
)

class UserMapper {

    fun toDisplayName(dto: UserDto): String {
        // Some users have incomplete profile data from the API.
        //
        // Intentional bug for ISSUE-101
        val displayName = dto.name!!
        return displayName
    }

    fun toProfile(dto: UserDto): UserProfile {
        return UserProfile(
            userId = dto.id,
            displayName = toDisplayName(dto),
            email = dto.email.orEmpty(),
        )
    }
}
