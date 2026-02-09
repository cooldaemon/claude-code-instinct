#!/usr/bin/env python3
"""Uninstall claude-code-instinct from ~/.claude/

Removes symlinks for bin/, agents/, and commands/.
Removes hook configuration from settings.json.
Optionally removes all data with --purge.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.utils import (
    error,
    info,
    is_instinct_hook,
    load_settings,
    remove_symlink,
    save_settings,
    warn,
)


def stop_observer_processes() -> None:
    """Stop any running observer processes."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "observe_pre.py|observe_post.py|instinct_cli.py"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                try:
                    subprocess.run(["kill", pid], check=True)
                    info(f"Stopped observer process: {pid}")
                except subprocess.CalledProcessError:
                    warn(f"Failed to stop process: {pid}")
        else:
            info("No observer processes running")
    except FileNotFoundError:
        warn("pgrep not found, skipping process cleanup")


def remove_hook_config(settings_path: Path) -> bool:
    """Remove hook configuration from settings.json.

    Args:
        settings_path: Path to settings.json

    Returns:
        True if successful, False otherwise.
    """
    if not settings_path.exists():
        info("settings.json does not exist, nothing to remove")
        return True

    settings = load_settings(settings_path)
    if settings is None:
        return False

    hooks = settings.get("hooks", {})
    modified = False

    # Remove PreToolUse hooks
    if "PreToolUse" in hooks:
        original_len = len(hooks["PreToolUse"])
        hooks["PreToolUse"] = [
            h for h in hooks["PreToolUse"] if not is_instinct_hook(h, "observe_pre.py")
        ]
        if len(hooks["PreToolUse"]) < original_len:
            info("Removed PreToolUse hook")
            modified = True
        if not hooks["PreToolUse"]:
            del hooks["PreToolUse"]

    # Remove PostToolUse hooks
    if "PostToolUse" in hooks:
        original_len = len(hooks["PostToolUse"])
        hooks["PostToolUse"] = [
            h
            for h in hooks["PostToolUse"]
            if not is_instinct_hook(h, "observe_post.py")
        ]
        if len(hooks["PostToolUse"]) < original_len:
            info("Removed PostToolUse hook")
            modified = True
        if not hooks["PostToolUse"]:
            del hooks["PostToolUse"]

    # Clean up empty hooks object
    if not hooks and "hooks" in settings:
        del settings["hooks"]

    if modified:
        return save_settings(settings_path, settings)
    else:
        info("No instinct hooks found in settings.json")
        return True


def purge_data(instincts_dir: Path) -> bool:
    """Remove all instinct data.

    Args:
        instincts_dir: Path to ~/.claude/instincts/

    Returns:
        True if successful, False otherwise.
    """
    if not instincts_dir.exists():
        info("Instincts directory does not exist, nothing to purge")
        return True

    try:
        shutil.rmtree(instincts_dir)
        info(f"Removed all data: {instincts_dir}")
        return True
    except OSError as e:
        error(f"Failed to remove {instincts_dir}: {e}")
        return False


def main() -> int:
    """Main uninstall function."""
    parser = argparse.ArgumentParser(
        description="Uninstall claude-code-instinct from ~/.claude/"
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Remove all data including observations and learned instincts",
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
    print("  Uninstalling claude-code-instinct")
    print("=" * 60)
    print()

    instincts_dir = claude_dir / "instincts"

    # Define symlinks to remove
    symlinks = [
        instincts_dir / "bin",
        instincts_dir / "agents",
        claude_dir / "commands" / "instinct-status.md",
        claude_dir / "commands" / "evolve.md",
    ]

    print("Stopping observer processes...")
    stop_observer_processes()

    print()
    print("Removing symlinks...")
    for target in symlinks:
        if not remove_symlink(target):
            warn(f"Could not remove: {target}")

    print()
    print("Removing hook configuration...")
    settings_path = claude_dir / "settings.json"
    if not remove_hook_config(settings_path):
        return 1

    if args.purge:
        print()
        print("Purging all data...")
        if not purge_data(instincts_dir):
            return 1

    print()
    print("=" * 60)
    print("  Uninstallation complete!")
    print("=" * 60)
    print()

    if not args.purge:
        print("Note: Data files were preserved at:")
        print(f"  {instincts_dir}")
        print()
        print("To remove all data, run:")
        print("  ./uninstall --purge")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
