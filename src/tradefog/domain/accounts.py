"""Pure account credential policies shared by HTTP and CLI entrypoints."""

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 150
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


def normalize_username(username: str) -> str:
    """Normalize and validate one stable login identifier."""
    normalized = username.strip()
    if (
        len(normalized) < USERNAME_MIN_LENGTH
        or len(normalized) > USERNAME_MAX_LENGTH
        or any(character.isspace() for character in normalized)
    ):
        raise ValueError(
            "Username must be 3-150 characters without whitespace",
        )
    return normalized


def validate_password(password: str) -> str:
    """Validate the shared plaintext password length policy."""
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise ValueError("Password must be 12-128 characters")
    return password
