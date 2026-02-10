"""Shared utilities for install/uninstall scripts."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def info(msg: str) -> None:
    """Print info message."""
    print(f"[INFO] {msg}")


def warn(msg: str) -> None:
    """Print warning message."""
    print(f"[WARN] {msg}", file=sys.stderr)


def error(msg: str) -> None:
    """Print error message."""
    print(f"[ERROR] {msg}", file=sys.stderr)


def check_prerequisites(claude_dir: Path | None = None) -> bool:
    """Check that prerequisites are met.

    Args:
        claude_dir: Optional custom claude directory. If None, uses ~/.claude/

    Returns:
        True if all prerequisites are met, False otherwise.
    """
    if sys.version_info < (3, 10):
        error("Python 3.10 or higher is required")
        return False

    if claude_dir is None:
        claude_dir = Path.home() / ".claude"

    if not claude_dir.exists():
        error(f"Claude directory not found: {claude_dir}")
        error("Please install Claude Code first")
        return False

    return True


def create_symlink(source: Path, target: Path) -> bool:
    """Create a symlink, removing existing if needed.

    Args:
        source: Source path (must exist)
        target: Target symlink path

    Returns:
        True if successful, False otherwise.
    """
    if target.is_symlink():
        target.unlink()
        info(f"Removed existing symlink: {target}")
    elif target.exists():
        error(f"Target exists and is not a symlink: {target}")
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source)
    info(f"Created symlink: {target} -> {source}")
    return True


def remove_symlink(target: Path) -> bool:
    """Remove a symlink if it exists.

    Args:
        target: Symlink path to remove

    Returns:
        True if removed or didn't exist, False if it exists but is not a symlink.
    """
    if not target.exists() and not target.is_symlink():
        info(f"Symlink does not exist: {target}")
        return True

    if target.is_symlink():
        target.unlink()
        info(f"Removed symlink: {target}")
        return True

    error(f"Target exists and is not a symlink: {target}")
    return False


def load_settings(settings_path: Path) -> dict[str, Any] | None:
    """Load settings.json file.

    Args:
        settings_path: Path to settings.json

    Returns:
        Settings dict, or empty dict if file doesn't exist.
        None if there's a parse error.
    """
    if not settings_path.exists():
        return {}

    try:
        result: dict[str, Any] = json.loads(settings_path.read_text())
        return result
    except json.JSONDecodeError as e:
        error(f"Invalid JSON in {settings_path}: {e}")
        return None


def save_settings(settings_path: Path, settings: dict[str, Any]) -> bool:
    """Save settings to settings.json file.

    Args:
        settings_path: Path to settings.json
        settings: Settings dict to save

    Returns:
        True if successful, False otherwise.
    """
    try:
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        info(f"Updated {settings_path}")
        return True
    except OSError as e:
        error(f"Failed to write {settings_path}: {e}")
        return False


def get_hook_command(script_name: str, claude_dir: Path | None = None) -> str:
    """Get the command path for a hook script.

    Uses ~ for home directory to ensure portability across machines.

    Args:
        script_name: Name of the script (e.g., "observe_pre.py")
        claude_dir: Optional custom claude directory. If None, uses ~/.claude/

    Returns:
        Path to the hook script using ~ notation.
    """
    if claude_dir is None:
        # Use ~ notation for portability
        return f"~/.claude/instincts/bin/{script_name}"

    # Check if claude_dir is under home directory
    home = Path.home()
    try:
        relative = claude_dir.relative_to(home)
        return f"~/{relative}/instincts/bin/{script_name}"
    except ValueError:
        # Not under home directory, use absolute path
        return str(claude_dir / "instincts" / "bin" / script_name)


def is_instinct_hook(hook: dict[str, Any], script_name: str) -> bool:
    """Check if a hook configuration is an instinct hook.

    Args:
        hook: Hook configuration dict
        script_name: Script name to match (e.g., "observe_pre.py")

    Returns:
        True if this hook is for the specified instinct script.
    """
    hooks_list = hook.get("hooks", [])
    if not hooks_list:
        return False
    command: str = hooks_list[0].get("command", "")
    return command.endswith(script_name)
