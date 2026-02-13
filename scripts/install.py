#!/usr/bin/env python3
"""Install claude-code-instinct to ~/.claude/

Creates symlinks for bin/, agents/, and commands/.
Merges hook configuration into settings.json.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.utils import (
    check_prerequisites,
    create_symlink,
    error,
    get_hook_command,
    info,
    is_instinct_hook,
    load_settings,
    save_settings,
)


# NOTE: create_data_directories has been removed (AC-8.1, AC-8.2, AC-8.3)
# With project-scoped storage, observations and learned instincts are stored per-project
# in <project>/docs/instincts/ rather than globally in ~/.claude/instincts/


def _create_hook_config(script_name: str, claude_dir: Path) -> dict[str, object]:
    """Create a hook configuration dictionary."""
    return {
        "matcher": "*",
        "hooks": [
            {
                "type": "command",
                "command": get_hook_command(script_name, claude_dir),
            }
        ],
    }


def _add_hook_if_missing(
    hooks: dict[str, list[dict[str, object]]],
    hook_type: str,
    script_name: str,
    hook_config: dict[str, object],
) -> None:
    """Add a hook to settings if not already present."""
    if hook_type not in hooks:
        hooks[hook_type] = []

    hook_exists = any(is_instinct_hook(h, script_name) for h in hooks[hook_type])
    if hook_exists:
        info(f"{hook_type} hook already exists")
        return

    hooks[hook_type].append(hook_config)
    info(f"Added {hook_type} hook")


def merge_hook_config(settings_path: Path, claude_dir: Path) -> bool:
    """Merge hook configuration into settings.json.

    Args:
        settings_path: Path to settings.json
        claude_dir: Base claude directory for hook commands

    Returns:
        True if successful, False otherwise.
    """
    settings = load_settings(settings_path)
    if settings is None:
        return False

    if "hooks" not in settings:
        settings["hooks"] = {}

    hooks = settings["hooks"]

    pre_hook = _create_hook_config("observe_pre.py", claude_dir)
    post_hook = _create_hook_config("observe_post.py", claude_dir)

    _add_hook_if_missing(hooks, "PreToolUse", "observe_pre.py", pre_hook)
    _add_hook_if_missing(hooks, "PostToolUse", "observe_post.py", post_hook)

    return save_settings(settings_path, settings)


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).parent.parent.resolve()


def main() -> int:
    """Main install function."""
    parser = argparse.ArgumentParser(
        description="Install claude-code-instinct to ~/.claude/"
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path.home() / ".claude",
        help="Target installation directory (default: ~/.claude/)",
    )
    args = parser.parse_args()

    claude_dir: Path = args.target_dir

    print("=" * 60)
    print("  Installing claude-code-instinct")
    print("=" * 60)
    print()

    if not check_prerequisites(claude_dir):
        return 1

    repo_root = get_repo_root()
    instincts_dir = claude_dir / "instincts"

    symlinks = [
        (repo_root / ".claude" / "instincts" / "bin", instincts_dir / "bin"),
        (repo_root / ".claude" / "instincts" / "agents", instincts_dir / "agents"),
        # NOTE: instinct-status.md removed (US-8)
        (
            repo_root / ".claude" / "commands" / "instinct-evolve.md",
            claude_dir / "commands" / "instinct-evolve.md",
        ),
    ]

    print("Creating symlinks...")
    for source, target in symlinks:
        if not source.exists():
            error(f"Source not found: {source}")
            return 1
        if not create_symlink(source, target):
            return 1

    print()
    print("Configuring hooks...")
    settings_path = claude_dir / "settings.json"
    if not merge_hook_config(settings_path, claude_dir):
        return 1

    print()
    print("=" * 60)
    print("  Installation complete!")
    print("=" * 60)
    print()
    print("Usage:")
    print("  /instinct-evolve  - Evolve learned instincts into rules/skills/commands")
    print()
    print("Observations and learned instincts are stored per-project in:")
    print("  <project>/docs/instincts/")
    print()
    print("Note: Learning happens automatically when enough observations")
    print("are collected (50+ tool usages).")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
