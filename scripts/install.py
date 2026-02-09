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


def create_data_directories(claude_dir: Path) -> None:
    """Create data directories that should persist.

    Args:
        claude_dir: Base claude directory (e.g., ~/.claude/)
    """
    instincts_dir = claude_dir / "instincts"

    dirs = [
        instincts_dir / "personal",
        instincts_dir / "observations.archive",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        info(f"Created directory: {d}")


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

    pre_hook = {
        "matcher": "*",
        "hooks": [
            {
                "type": "command",
                "command": get_hook_command("observe_pre.py", claude_dir),
            }
        ],
    }
    post_hook = {
        "matcher": "*",
        "hooks": [
            {
                "type": "command",
                "command": get_hook_command("observe_post.py", claude_dir),
            }
        ],
    }

    if "hooks" not in settings:
        settings["hooks"] = {}

    hooks = settings["hooks"]

    # Add PreToolUse hook
    if "PreToolUse" not in hooks:
        hooks["PreToolUse"] = []

    pre_exists = any(is_instinct_hook(h, "observe_pre.py") for h in hooks["PreToolUse"])
    if not pre_exists:
        hooks["PreToolUse"].append(pre_hook)
        info("Added PreToolUse hook")
    else:
        info("PreToolUse hook already exists")

    # Add PostToolUse hook
    if "PostToolUse" not in hooks:
        hooks["PostToolUse"] = []

    post_exists = any(
        is_instinct_hook(h, "observe_post.py") for h in hooks["PostToolUse"]
    )
    if not post_exists:
        hooks["PostToolUse"].append(post_hook)
        info("Added PostToolUse hook")
    else:
        info("PostToolUse hook already exists")

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
        (
            repo_root / ".claude" / "commands" / "instinct-status.md",
            claude_dir / "commands" / "instinct-status.md",
        ),
        (
            repo_root / ".claude" / "commands" / "evolve.md",
            claude_dir / "commands" / "evolve.md",
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
    print("Creating data directories...")
    create_data_directories(claude_dir)

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
    print("  /instinct-status  - Show learned instincts")
    print("  /evolve           - Analyze and evolve instincts")
    print()
    print("Observations will be logged to:")
    print(f"  {instincts_dir / 'observations.jsonl'}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
