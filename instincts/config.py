"""Configuration and path definitions for Instinct-Based Learning."""

from pathlib import Path

# Base directory for instincts data
INSTINCTS_DIR: Path = Path.home() / ".claude" / "instincts"

# Analysis trigger constants (auto-trigger feature)
ANALYSIS_TRIGGER_COUNT: int = 200  # Trigger analysis after 200 observations
ANALYSIS_TRIGGER_HOURS: float = 24.0  # Or trigger after 24 hours elapsed
ANALYSIS_MIN_COUNT: int = 20  # Minimum observations for time-based trigger

# Analysis scope (shared by algorithm and LLM)
MAX_OBSERVATIONS_FOR_ANALYSIS: int = 1000  # Analyze latest 1000 observations

# Marker file for pending analysis
ANALYSIS_PENDING_FILE: Path = INSTINCTS_DIR / ".analysis_pending"

# LLM settings for dual-approach analysis
DEFAULT_LLM_MODEL: str = "claude-3-haiku-20240307"
ANTHROPIC_API_KEY_ENV: str = "ANTHROPIC_API_KEY"

# Observations log file (JSONL format)
OBSERVATIONS_FILE: Path = INSTINCTS_DIR / "observations.jsonl"

# Directory for learned instincts
PERSONAL_DIR: Path = INSTINCTS_DIR / "personal"

# Archive directory for old observations
ARCHIVE_DIR: Path = INSTINCTS_DIR / "observations.archive"

# Evolved content directories
EVOLVED_DIR: Path = INSTINCTS_DIR / "evolved"
EVOLVED_SKILLS_DIR: Path = EVOLVED_DIR / "skills"
EVOLVED_COMMANDS_DIR: Path = EVOLVED_DIR / "commands"
EVOLVED_AGENTS_DIR: Path = EVOLVED_DIR / "agents"


def ensure_directories() -> None:
    """Create required directories if they don't exist.

    This function is idempotent - safe to call multiple times.
    Directories are created with mode 0o700 (owner read/write/execute only)
    to protect sensitive observation data.
    """
    INSTINCTS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    PERSONAL_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    EVOLVED_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    EVOLVED_SKILLS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    EVOLVED_COMMANDS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    EVOLVED_AGENTS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
