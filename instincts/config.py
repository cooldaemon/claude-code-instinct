"""Configuration and path definitions for Instinct-Based Learning."""

from pathlib import Path

# Base directory for instincts data
INSTINCTS_DIR: Path = Path.home() / ".claude" / "instincts"

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
    """
    INSTINCTS_DIR.mkdir(parents=True, exist_ok=True)
    PERSONAL_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    EVOLVED_DIR.mkdir(parents=True, exist_ok=True)
    EVOLVED_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    EVOLVED_COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
    EVOLVED_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
