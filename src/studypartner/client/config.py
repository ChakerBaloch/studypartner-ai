"""StudyPartner configuration management."""

from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, Field

from studypartner.shared.constants import CONFIG_PATH, DATA_DIR


class Config(BaseModel):
    """User configuration for StudyPartner."""

    # Cloud Run backend URL
    backend_url: Optional[str] = None

    # Gemini API key (used by server, stored locally for deploy)
    gemini_api_key: Optional[str] = None

    # GCP project ID
    gcp_project_id: Optional[str] = None

    # Capture interval in seconds
    capture_interval_seconds: int = 10

    # Session settings
    default_pomodoro_minutes: int = 45
    default_break_minutes: int = 10

    # Privacy settings
    excluded_apps: list[str] = Field(default_factory=lambda: [
        "1Password", "Keychain Access", "Mail", "Messages",
        "FaceTime", "Bitwarden", "LastPass",
    ])
    auto_delete_screenshots_days: int = 7
    enable_pii_redaction: bool = True

    # Notification preferences
    enable_voice_coaching: bool = True
    enable_notifications: bool = True
    enable_overlay: bool = True

    # Setup complete flag
    setup_complete: bool = False

    @classmethod
    def load(cls) -> Config:
        """Load config from disk, or return defaults."""
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text())
                return cls(**data)
            except (json.JSONDecodeError, ValueError):
                return cls()
        return cls()

    def save(self) -> None:
        """Save config to disk."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(self.model_dump_json(indent=2))

    @property
    def is_configured(self) -> bool:
        """Check if the essential config is present."""
        return bool(self.backend_url and self.setup_complete)
