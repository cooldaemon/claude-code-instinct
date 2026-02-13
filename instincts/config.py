"""Configuration and path definitions for Instinct-Based Learning."""

from enum import Enum
from pathlib import Path
from typing import Literal

# Analysis trigger constants (auto-trigger feature)
ANALYSIS_TRIGGER_COUNT: int = 200  # Trigger analysis after 200 observations
ANALYSIS_TRIGGER_HOURS: float = 24.0  # Or trigger after 24 hours elapsed
ANALYSIS_MIN_COUNT: int = 20  # Minimum observations for time-based trigger
# CR-013: Consolidated from observer.py for consistent naming
ANALYSIS_TRIGGER_CHECK_INTERVAL: int = 10  # Check trigger every N observations (performance)

# Analysis scope (shared by algorithm and LLM)
MAX_OBSERVATIONS_FOR_ANALYSIS: int = 1000  # Analyze latest 1000 observations

# LLM settings for dual-approach analysis
DEFAULT_LLM_MODEL: str = "claude-3-haiku-20240307"
ANTHROPIC_API_KEY_ENV: str = "ANTHROPIC_API_KEY"

# Auto-learning constants
AUTO_LEARN_OBSERVATION_THRESHOLD: int = 50  # Minimum observations before auto-learning
AUTO_LEARN_COOLDOWN_SECONDS: int = 300  # Cooldown between auto-learning runs (5 minutes)
AUTO_LEARN_LOCK_FILE: str = ".auto_learn.lock"  # Lock file to prevent concurrent runs
AUTO_LEARN_STATE_FILE: str = ".auto_learn_state.json"  # Tracks last analysis state

# CLAUDE.md integration
LEARNED_PATTERNS_SECTION: str = "## Learned Patterns"

# Scope type for evolution
EvolutionScope = Literal["project", "global"]


class EvolutionOutputType(Enum):
    """Types of evolved output artifacts."""

    CLAUDEMD = "claudemd"  # Append to CLAUDE.md
    RULES = "rules"  # .claude/rules/
    SKILLS = "skills"  # .claude/skills/
    SUBAGENTS = "subagents"  # .claude/agents/
    COMMANDS = "commands"  # .claude/commands/


def detect_project_root(start_path: Path) -> Path:
    """Detect the project root by finding markers (.git or CLAUDE.md).

    Args:
        start_path: Directory to start searching from.

    Returns:
        Path to project root, or start_path as fallback if no markers found.
    """
    current = start_path.resolve()

    while current != current.parent:
        # Check for project markers
        if (current / ".git").is_dir():
            return current
        if (current / "CLAUDE.md").is_file():
            return current
        current = current.parent

    # Fallback to start_path if no markers found
    return start_path.resolve()


def get_project_instincts_dir(project_root: Path) -> Path:
    """Get the instincts directory for a project.

    Args:
        project_root: Path to the project root.

    Returns:
        Path to <project>/docs/instincts/
    """
    return project_root / "docs" / "instincts"


def get_learned_dir(project_root: Path) -> Path:
    """Get the learned instincts directory for a project.

    Args:
        project_root: Path to the project root.

    Returns:
        Path to <project>/docs/instincts/learned/
    """
    return get_project_instincts_dir(project_root) / "learned"


def get_observations_file(project_root: Path) -> Path:
    """Get the observations file path for a project.

    Args:
        project_root: Path to the project root.

    Returns:
        Path to <project>/docs/instincts/observations.jsonl
    """
    return get_project_instincts_dir(project_root) / "observations.jsonl"


def get_archive_dir(project_root: Path) -> Path:
    """Get the archive directory for a project.

    Args:
        project_root: Path to the project root.

    Returns:
        Path to <project>/docs/instincts/observations.archive/
    """
    return get_project_instincts_dir(project_root) / "observations.archive"


def get_evolved_output_dir(
    output_type: EvolutionOutputType,
    scope: EvolutionScope,
    project_root: Path,
) -> Path:
    """Get the output directory for evolved artifacts.

    Args:
        output_type: Type of artifact (rules, skills, subagents, commands).
        scope: Scope of the artifact (project or global).
        project_root: Path to the project root (used for project scope).

    Returns:
        Path to the appropriate output directory.
    """
    # Directory mapping for each output type
    dir_names = {
        EvolutionOutputType.RULES: "rules",
        EvolutionOutputType.SKILLS: "skills",
        EvolutionOutputType.SUBAGENTS: "agents",
        EvolutionOutputType.COMMANDS: "commands",
    }

    dir_name = dir_names.get(output_type, "rules")

    if scope == "project":
        return project_root / ".claude" / dir_name
    else:  # global
        return Path.home() / ".claude" / dir_name


def get_analysis_pending_file(project_root: Path) -> Path:
    """Get the analysis pending marker file path for a project.

    Args:
        project_root: Path to the project root.

    Returns:
        Path to <project>/docs/instincts/.analysis_pending
    """
    return get_project_instincts_dir(project_root) / ".analysis_pending"
