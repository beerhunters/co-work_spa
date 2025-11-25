"""
Password security utilities with bcrypt hashing.

Provides secure password hashing with bcrypt (12 rounds) and backward compatibility
with existing werkzeug pbkdf2 hashes for seamless migration.
"""

import bcrypt
from werkzeug.security import check_password_hash
from utils.logger import get_logger

logger = get_logger(__name__)


def hash_password_bcrypt(password: str, rounds: int = 12) -> str:
    """
    Hash password using bcrypt with specified rounds.

    Args:
        password: Plain text password to hash
        rounds: Number of bcrypt rounds (default: 12, recommended for security)

    Returns:
        Hashed password string in werkzeug-compatible format

    Security Notes:
        - Uses bcrypt algorithm (much stronger than pbkdf2)
        - 12 rounds provides good balance between security and performance
        - Each round doubles the computation time (2^12 = 4096 iterations)
        - Automatically includes cryptographically secure salt
    """
    if not password:
        raise ValueError("Password cannot be empty")

    # Use native bcrypt library for full control over rounds
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=rounds)
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)

    # Convert to werkzeug-compatible format: bcrypt$<hash>
    # Bcrypt hash is already in the format $2b$rounds$salt+hash
    hashed = f"bcrypt${hashed_bytes.decode('utf-8')}"

    logger.debug(f"Password hashed with bcrypt (rounds={rounds})")
    return hashed


def verify_password_with_upgrade(
    stored_hash: str,
    provided_password: str
) -> tuple[bool, bool, str | None]:
    """
    Verify password against stored hash with automatic upgrade support.

    This function:
    1. Checks if password is correct (works with both bcrypt and pbkdf2)
    2. Detects if hash is using old algorithm (pbkdf2)
    3. Returns new bcrypt hash if upgrade is needed

    Args:
        stored_hash: The hashed password from database
        provided_password: Plain text password to verify

    Returns:
        Tuple of (is_valid, needs_upgrade, new_hash):
            - is_valid: True if password matches
            - needs_upgrade: True if hash should be upgraded to bcrypt
            - new_hash: New bcrypt hash (only if needs_upgrade=True)

    Example:
        >>> is_valid, needs_upgrade, new_hash = verify_password_with_upgrade(
        ...     stored_hash=user.password_hash,
        ...     provided_password="user_input"
        ... )
        >>> if is_valid:
        ...     if needs_upgrade:
        ...         user.password_hash = new_hash
        ...         db.commit()
        ...     # Continue with login
    """
    if not stored_hash or not provided_password:
        return False, False, None

    # Check if this is our bcrypt format
    if stored_hash.startswith("bcrypt$"):
        # Extract the actual bcrypt hash (remove "bcrypt$" prefix)
        bcrypt_hash = stored_hash[7:]  # Skip "bcrypt$"
        try:
            # Verify using native bcrypt
            password_bytes = provided_password.encode('utf-8')
            hash_bytes = bcrypt_hash.encode('utf-8')
            is_valid = bcrypt.checkpw(password_bytes, hash_bytes)

            if is_valid:
                # Already using bcrypt, no upgrade needed
                return True, False, None
            else:
                return False, False, None
        except Exception as e:
            logger.error(f"Error verifying bcrypt hash: {e}")
            return False, False, None
    else:
        # Old format (pbkdf2, scrypt, etc.) - use werkzeug
        is_valid = check_password_hash(stored_hash, provided_password)

        if not is_valid:
            return False, False, None

        # Password is valid but using old algorithm - upgrade to bcrypt
        new_hash = hash_password_bcrypt(provided_password)
        logger.info(
            "Password hash upgraded from legacy algorithm to bcrypt",
            extra={"old_method": stored_hash.split("$")[0] if "$" in stored_hash else "unknown"}
        )
        return True, True, new_hash


def verify_password_simple(stored_hash: str, provided_password: str) -> bool:
    """
    Simple password verification without upgrade logic.

    Use this when you only need to check if password is correct,
    without caring about hash format.

    Args:
        stored_hash: The hashed password from database
        provided_password: Plain text password to verify

    Returns:
        True if password matches, False otherwise
    """
    if not stored_hash or not provided_password:
        return False

    # Use the upgrade function but ignore upgrade logic
    is_valid, _, _ = verify_password_with_upgrade(stored_hash, provided_password)
    return is_valid


def is_bcrypt_hash(password_hash: str) -> bool:
    """
    Check if a password hash is using bcrypt algorithm.

    Args:
        password_hash: The hashed password to check

    Returns:
        True if hash uses bcrypt, False otherwise
    """
    return password_hash.startswith("bcrypt$") if password_hash else False


def get_hash_algorithm(password_hash: str) -> str:
    """
    Extract algorithm name from password hash.

    Args:
        password_hash: The hashed password

    Returns:
        Algorithm name (e.g., "bcrypt", "pbkdf2", "unknown")
    """
    if not password_hash:
        return "unknown"

    if "$" in password_hash:
        return password_hash.split("$")[0]

    return "unknown"


# Backward compatibility aliases
hash_password = hash_password_bcrypt
verify_password = verify_password_simple
