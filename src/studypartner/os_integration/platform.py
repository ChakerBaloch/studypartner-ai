"""OS Integration: Platform abstraction layer."""

from __future__ import annotations

import platform
import sys
from enum import Enum


class Platform(str, Enum):
    MACOS = "macos"
    WINDOWS = "windows"
    LINUX = "linux"
    UNKNOWN = "unknown"


def get_platform() -> Platform:
    """Detect the current platform."""
    system = platform.system().lower()
    if system == "darwin":
        return Platform.MACOS
    elif system == "windows":
        return Platform.WINDOWS
    elif system == "linux":
        return Platform.LINUX
    return Platform.UNKNOWN


def is_macos() -> bool:
    return get_platform() == Platform.MACOS


def is_windows() -> bool:
    return get_platform() == Platform.WINDOWS


def get_os_version() -> str:
    """Get the OS version string."""
    return platform.platform()


def check_requirements() -> list[str]:
    """Check platform requirements and return a list of issues.

    Returns an empty list if all requirements are met.
    """
    issues = []
    plat = get_platform()

    if plat == Platform.UNKNOWN:
        issues.append(f"Unsupported platform: {platform.system()}")
        return issues

    if plat == Platform.MACOS:
        # Check macOS version (need 13+ for ScreenCaptureKit)
        version = platform.mac_ver()[0]
        if version:
            major = int(version.split(".")[0])
            if major < 13:
                issues.append(
                    f"macOS 13 (Ventura) or later required. You have: {version}"
                )

        # Check Python version
        if sys.version_info < (3, 11):
            issues.append(
                f"Python 3.11+ required. You have: {sys.version}"
            )

    elif plat == Platform.WINDOWS:
        issues.append("Windows support is not yet implemented (post-hackathon)")

    return issues
