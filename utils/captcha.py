"""
CAPTCHA validation utility for hCaptcha integration.

Provides server-side validation of CAPTCHA tokens to prevent automated attacks.
"""

import httpx
from typing import Optional, Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)

# hCaptcha verification endpoint
HCAPTCHA_VERIFY_URL = "https://hcaptcha.com/siteverify"


class CaptchaValidator:
    """
    hCaptcha validator for preventing automated login attempts.

    Usage:
        validator = CaptchaValidator(secret_key="your_secret_key")
        is_valid = await validator.verify(token="user_captcha_token", remote_ip="1.2.3.4")
    """

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize CAPTCHA validator.

        Args:
            secret_key: hCaptcha secret key. If None, CAPTCHA validation is disabled.
        """
        self.secret_key = secret_key
        self.enabled = bool(secret_key)

        if not self.enabled:
            logger.warning("CAPTCHA validation is DISABLED (no secret key provided)")

    async def verify(
        self,
        token: str,
        remote_ip: Optional[str] = None,
        sitekey: Optional[str] = None
    ) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        Verify hCaptcha token with hCaptcha API.

        Args:
            token: The CAPTCHA response token from the client
            remote_ip: User's IP address (optional but recommended)
            sitekey: Expected site key (optional, for additional validation)

        Returns:
            Tuple of (is_valid: bool, response_data: dict or None)

        Example:
            is_valid, data = await validator.verify(
                token="user_token_here",
                remote_ip="192.168.1.1"
            )
            if is_valid:
                # CAPTCHA passed
                pass
            else:
                # CAPTCHA failed
                error_codes = data.get("error-codes", []) if data else []
        """
        # If CAPTCHA is disabled, always return True
        if not self.enabled:
            logger.debug("CAPTCHA verification skipped (disabled)")
            return True, {"success": True, "disabled": True}

        # Validate input
        if not token or not isinstance(token, str):
            logger.warning("Invalid CAPTCHA token provided")
            return False, {"success": False, "error-codes": ["missing-input-response"]}

        # Prepare request payload
        payload = {
            "secret": self.secret_key,
            "response": token,
        }

        if remote_ip:
            payload["remoteip"] = remote_ip

        if sitekey:
            payload["sitekey"] = sitekey

        try:
            # Send verification request to hCaptcha
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    HCAPTCHA_VERIFY_URL,
                    data=payload
                )
                response.raise_for_status()

                result = response.json()

                # Check if verification succeeded
                success = result.get("success", False)

                if success:
                    logger.info(
                        f"CAPTCHA verification SUCCESS",
                        extra={
                            "remote_ip": remote_ip,
                            "hostname": result.get("hostname"),
                            "challenge_ts": result.get("challenge_ts")
                        }
                    )
                else:
                    error_codes = result.get("error-codes", [])
                    logger.warning(
                        f"CAPTCHA verification FAILED",
                        extra={
                            "remote_ip": remote_ip,
                            "error_codes": error_codes
                        }
                    )

                return success, result

        except httpx.TimeoutException:
            logger.error("CAPTCHA verification timeout", extra={"remote_ip": remote_ip})
            # On timeout, fail open or closed based on security requirements
            # For authentication, we fail closed (reject)
            return False, {"success": False, "error-codes": ["timeout"]}

        except httpx.HTTPError as e:
            logger.error(
                f"CAPTCHA verification HTTP error: {e}",
                extra={"remote_ip": remote_ip}
            )
            return False, {"success": False, "error-codes": ["http-error"]}

        except Exception as e:
            logger.error(
                f"CAPTCHA verification unexpected error: {e}",
                extra={"remote_ip": remote_ip},
                exc_info=True
            )
            return False, {"success": False, "error-codes": ["server-error"]}


class LoginAttemptTracker:
    """
    Tracks failed login attempts per username to trigger CAPTCHA requirement.

    Uses in-memory storage with automatic cleanup.
    For production at scale, consider Redis-backed storage.
    """

    def __init__(self, captcha_threshold: int = 3):
        """
        Initialize login attempt tracker.

        Args:
            captcha_threshold: Number of failed attempts before requiring CAPTCHA
        """
        self.captcha_threshold = captcha_threshold
        # Dictionary: {username: failed_attempt_count}
        self._attempts: Dict[str, int] = {}

    def record_failed_attempt(self, username: str) -> int:
        """
        Record a failed login attempt for a username.

        Args:
            username: The username that had a failed login

        Returns:
            Current number of failed attempts for this username
        """
        current = self._attempts.get(username, 0)
        self._attempts[username] = current + 1

        logger.debug(
            f"Failed login attempt recorded",
            extra={
                "username": username,
                "total_attempts": self._attempts[username]
            }
        )

        return self._attempts[username]

    def reset_attempts(self, username: str) -> None:
        """
        Reset failed login attempts for a username (after successful login).

        Args:
            username: The username to reset
        """
        if username in self._attempts:
            del self._attempts[username]
            logger.debug(f"Login attempts reset for username", extra={"username": username})

    def requires_captcha(self, username: str) -> bool:
        """
        Check if CAPTCHA is required for this username.

        Args:
            username: The username to check

        Returns:
            True if CAPTCHA is required, False otherwise
        """
        attempts = self._attempts.get(username, 0)
        return attempts >= self.captcha_threshold

    def get_attempt_count(self, username: str) -> int:
        """
        Get the current failed attempt count for a username.

        Args:
            username: The username to check

        Returns:
            Number of failed attempts
        """
        return self._attempts.get(username, 0)

    def cleanup_old_entries(self, max_entries: int = 10000) -> None:
        """
        Cleanup oldest entries if storage grows too large.

        Args:
            max_entries: Maximum number of entries to keep
        """
        if len(self._attempts) > max_entries:
            # Remove oldest 20% of entries
            to_remove = len(self._attempts) - int(max_entries * 0.8)
            usernames_to_remove = list(self._attempts.keys())[:to_remove]

            for username in usernames_to_remove:
                del self._attempts[username]

            logger.info(f"Cleaned up {to_remove} old login attempt entries")


# Global singleton instances
_captcha_validator: Optional[CaptchaValidator] = None
_login_tracker: Optional[LoginAttemptTracker] = None


def get_captcha_validator(secret_key: Optional[str] = None) -> CaptchaValidator:
    """
    Get or create global CAPTCHA validator instance.

    Args:
        secret_key: hCaptcha secret key (only used on first call)

    Returns:
        CaptchaValidator instance
    """
    global _captcha_validator

    if _captcha_validator is None:
        _captcha_validator = CaptchaValidator(secret_key)

    return _captcha_validator


def get_login_tracker(captcha_threshold: int = 3) -> LoginAttemptTracker:
    """
    Get or create global login attempt tracker instance.

    Args:
        captcha_threshold: Number of failed attempts before requiring CAPTCHA

    Returns:
        LoginAttemptTracker instance
    """
    global _login_tracker

    if _login_tracker is None:
        _login_tracker = LoginAttemptTracker(captcha_threshold)

    return _login_tracker
