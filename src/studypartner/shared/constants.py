"""Constants and thresholds for StudyPartner."""

import os
from pathlib import Path

# --- Study Phase Thresholds ---
DEFAULT_POMODORO_MINUTES = 45
DEFAULT_BREAK_MINUTES = 10
MAX_INPUT_WITHOUT_OUTPUT_MINUTES = 30
MAX_SAME_PROBLEM_TYPE_MINUTES = 20
RETURN_THRESHOLD_HOURS = 24

# --- Capture Settings ---
DEFAULT_CAPTURE_INTERVAL_SECONDS = 10
SCREENSHOT_WIDTH = 1280
SCREENSHOT_HEIGHT = 720
SCREENSHOT_JPEG_QUALITY = 70



DATA_DIR = Path(os.path.expanduser("~/.studypartner"))
DB_PATH = DATA_DIR / "studypartner.db"
CONFIG_PATH = DATA_DIR / "config.json"
LEARNING_PROFILE_PATH = DATA_DIR / "learning_profile.json"
ADAPTIVE_PROFILE_PATH = DATA_DIR / "adaptive_profile.json"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
LOGS_DIR = DATA_DIR / "logs"

# --- Server Defaults ---
DEFAULT_SERVER_PORT = 8080
DEFAULT_CLOUD_RUN_REGION = "us-west1"

# --- Sensitive App Exclusion List ---
EXCLUDED_APPS = [
    "1Password",
    "Keychain Access",
    "Mail",
    "Messages",
    "FaceTime",
    "Bitwarden",
    "LastPass",
    "Banking",
]

# --- Activity Detection Keywords ---
CODING_KEYWORDS = [
    "def ", "function ", "class ", "import ", "const ", "let ", "var ",
    "return ", "if ", "for ", "while ", "try ", "catch ", "async ",
    "Terminal", "iTerm", "VS Code", "Xcode", "PyCharm", "IntelliJ",
]

AI_CHAT_KEYWORDS = [
    "ChatGPT", "Claude", "Gemini", "Copilot", "chat.openai.com",
    "anthropic", "bard.google.com",
]

# --- Adaptive Engine ---
MIN_EVIDENCE_FOR_PREFERENCE = 5     # Minimum data points before trusting a preference
CONFIDENCE_THRESHOLD = 0.6          # Minimum confidence to use an adaptive weight
DEFAULT_TECHNIQUE_SCORE = 0.5       # Starting score for all techniques
