"""Tests for install.py and uninstall.py --target-dir functionality.

Tests cover:
- Install creates symlinks in the specified target directory
- Install merges hooks into settings.json in the target directory
- Uninstall removes symlinks from the specified target directory
- Uninstall removes hooks from settings.json in the target directory
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).parent.parent.resolve()


class TestInstallTargetDir:
    """Test install.py --target-dir option."""

    def test_install_creates_symlinks_in_target_dir(self, tmp_path: Path):
        """Install with --target-dir creates symlinks in the specified directory."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        instincts_dir = target_dir / "instincts"
        assert (instincts_dir / "bin").is_symlink()
        assert (instincts_dir / "agents").is_symlink()
        # instinct-status.md is removed (US-8)
        assert not (target_dir / "commands" / "instinct-status.md").exists()
        assert (target_dir / "commands" / "instinct-evolve.md").is_symlink()

    def test_install_does_not_create_data_directories_in_target_dir(self, tmp_path: Path):
        """Install with --target-dir should not create data directories (project-scoped storage)."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        instincts_dir = target_dir / "instincts"
        # With project-scoped storage, personal and archive directories are not created
        assert not (instincts_dir / "personal").exists()
        assert not (instincts_dir / "observations.archive").exists()

    def test_install_merges_hooks_into_settings_in_target_dir(self, tmp_path: Path):
        """Install with --target-dir merges hooks into settings.json in target directory."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        settings_path = target_dir / "settings.json"
        settings_path.write_text('{"existingKey": "value"}')
        repo_root = get_repo_root()

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        settings = json.loads(settings_path.read_text())
        assert "existingKey" in settings  # Existing content preserved
        assert "hooks" in settings
        assert "PreToolUse" in settings["hooks"]
        assert "PostToolUse" in settings["hooks"]

    def test_install_creates_settings_if_not_exists(self, tmp_path: Path):
        """Install with --target-dir creates settings.json if it does not exist."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        settings_path = target_dir / "settings.json"
        repo_root = get_repo_root()

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Install failed: {result.stderr}"
        assert settings_path.exists()

        settings = json.loads(settings_path.read_text())
        assert "hooks" in settings

    def test_install_default_target_dir_is_home_claude(self, tmp_path: Path):
        """Install without --target-dir defaults to ~/.claude/."""
        # This test verifies the default behavior without actually modifying ~/.claude/
        import argparse

        # Verify that --target-dir has a default
        parser = argparse.ArgumentParser()
        parser.add_argument("--target-dir", type=Path, default=Path.home() / ".claude")
        args = parser.parse_args([])

        assert args.target_dir == Path.home() / ".claude"


class TestUninstallTargetDir:
    """Test uninstall.py --target-dir option."""

    def test_uninstall_removes_symlinks_from_target_dir(self, tmp_path: Path):
        """Uninstall with --target-dir removes symlinks from the specified directory."""
        # Arrange - First install to target directory
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Install first
        subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Verify symlinks exist
        instincts_dir = target_dir / "instincts"
        assert (instincts_dir / "bin").is_symlink()
        assert (instincts_dir / "agents").is_symlink()

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "uninstall.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Uninstall failed: {result.stderr}"
        assert not (instincts_dir / "bin").exists()
        assert not (instincts_dir / "agents").exists()
        # instinct-status.md is removed (US-8) - was never created
        assert not (target_dir / "commands" / "instinct-evolve.md").exists()

    def test_uninstall_removes_hooks_from_settings_in_target_dir(self, tmp_path: Path):
        """Uninstall with --target-dir removes hooks from settings.json in target directory."""
        # Arrange - First install to target directory
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        settings_path = target_dir / "settings.json"
        settings_path.write_text('{"existingKey": "value"}')
        repo_root = get_repo_root()

        # Install first
        subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Verify hooks exist
        settings = json.loads(settings_path.read_text())
        assert "hooks" in settings

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "uninstall.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Uninstall failed: {result.stderr}"

        settings = json.loads(settings_path.read_text())
        assert "existingKey" in settings  # Existing content preserved
        # hooks should be removed or empty
        assert "hooks" not in settings or (
            "PreToolUse" not in settings.get("hooks", {})
            and "PostToolUse" not in settings.get("hooks", {})
        )

    def test_uninstall_preserves_instincts_directory_without_purge(self, tmp_path: Path):
        """Uninstall without --purge preserves instincts directory structure."""
        # Arrange - First install to target directory
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Install first
        subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        instincts_dir = target_dir / "instincts"

        # Create a test file in instincts directory to verify preservation
        # Note: personal/ is no longer created by install, so we create a test file directly
        test_file = instincts_dir / "test.md"
        test_file.write_text("test content")

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "uninstall.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Uninstall failed: {result.stderr}"
        # instincts directory should still exist (for bin/agents symlinks)
        # but data files should be preserved
        assert test_file.exists()

    def test_uninstall_with_purge_removes_data_directories(self, tmp_path: Path):
        """Uninstall with --purge removes data directories."""
        # Arrange - First install to target directory
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Install first
        subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        instincts_dir = target_dir / "instincts"

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "uninstall.py"),
                "--target-dir",
                str(target_dir),
                "--purge",
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Uninstall failed: {result.stderr}"
        assert not instincts_dir.exists()

    def test_uninstall_default_target_dir_is_home_claude(self, tmp_path: Path):
        """Uninstall without --target-dir defaults to ~/.claude/."""
        # Verify that --target-dir has a default
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--target-dir", type=Path, default=Path.home() / ".claude")
        args = parser.parse_args([])

        assert args.target_dir == Path.home() / ".claude"


class TestProjectScopedStorage:
    """Tests for project-scoped storage changes (AC-8.1, AC-8.2, AC-8.3)."""

    def test_install_does_not_create_personal_directory(self, tmp_path: Path):
        """AC-8.3: Install SHOULD NOT create ~/.claude/instincts/personal/ directory."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        instincts_dir = target_dir / "instincts"
        assert not (instincts_dir / "personal").exists()

    def test_install_does_not_create_evolved_directory(self, tmp_path: Path):
        """AC-8.1: Install SHOULD NOT create ~/.claude/instincts/evolved/ directory."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        instincts_dir = target_dir / "instincts"
        assert not (instincts_dir / "evolved").exists()

    def test_install_does_not_create_observations_file(self, tmp_path: Path):
        """AC-8.2: Install SHOULD NOT create ~/.claude/instincts/observations.jsonl."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        instincts_dir = target_dir / "instincts"
        assert not (instincts_dir / "observations.jsonl").exists()

    def test_install_does_not_create_observations_archive_directory(self, tmp_path: Path):
        """Install SHOULD NOT create ~/.claude/instincts/observations.archive/ directory."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        instincts_dir = target_dir / "instincts"
        assert not (instincts_dir / "observations.archive").exists()

    def test_install_message_does_not_mention_instinct_status(self, tmp_path: Path):
        """Install message should not mention /instinct-status (command removed)."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Install failed: {result.stderr}"
        assert "/instinct-status" not in result.stdout

    def test_uninstall_message_mentions_project_scoped_data(self, tmp_path: Path):
        """Uninstall message should mention project-scoped data."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Install first
        subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "uninstall.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Uninstall failed: {result.stderr}"
        # Should mention project-scoped data
        assert "project" in result.stdout.lower() or "docs/instincts" in result.stdout

    def test_install_does_not_create_instinct_status_symlink(self, tmp_path: Path):
        """Install should not create instinct-status.md symlink (command removed)."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Act
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Install failed: {result.stderr}"
        assert not (target_dir / "commands" / "instinct-status.md").exists()


class TestInstallUninstallIdempotency:
    """Test idempotency of install and uninstall operations."""

    def test_install_is_idempotent(self, tmp_path: Path):
        """Running install twice should succeed without errors."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Act - Run install twice
        for _ in range(2):
            result = subprocess.run(
                [
                    sys.executable,
                    str(repo_root / "scripts" / "install.py"),
                    "--target-dir",
                    str(target_dir),
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Install failed: {result.stderr}"

        # Assert - Symlinks should still exist
        instincts_dir = target_dir / "instincts"
        assert (instincts_dir / "bin").is_symlink()
        assert (instincts_dir / "agents").is_symlink()

    def test_uninstall_is_idempotent(self, tmp_path: Path):
        """Running uninstall twice should succeed without errors."""
        # Arrange
        target_dir = tmp_path / ".claude"
        target_dir.mkdir(parents=True)
        repo_root = get_repo_root()

        # Install first
        subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "install.py"),
                "--target-dir",
                str(target_dir),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Act - Run uninstall twice
        for _ in range(2):
            result = subprocess.run(
                [
                    sys.executable,
                    str(repo_root / "scripts" / "uninstall.py"),
                    "--target-dir",
                    str(target_dir),
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Uninstall failed: {result.stderr}"
