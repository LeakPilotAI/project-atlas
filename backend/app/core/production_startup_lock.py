"""Independent, default-deny Atlas production startup lock.

This module intentionally provides no authorization or unlock operation.
"""

class ProductionStartupRefused(RuntimeError):
    """Production startup is not authorized."""


def require_startup_authorization() -> None:
    raise ProductionStartupRefused(
        "Atlas production startup is disabled. "
        "Use the separate offline observation entry point."
    )
