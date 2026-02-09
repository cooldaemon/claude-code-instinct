"""Tests for instincts.config module.

Tests cover:
- Path definitions (INSTINCTS_DIR, OBSERVATIONS_FILE, PERSONAL_DIR)
- Path relationships (all paths are under INSTINCTS_DIR)
- ensure_directories function creates required directories
"""

from pathlib import Path
from unittest.mock import patch


class TestConfigPaths:
    """Test path definitions in config module."""

    def test_instincts_dir_is_under_claude_dir(self):
        """INSTINCTS_DIR should be ~/.claude/instincts."""
        from instincts.config import INSTINCTS_DIR

        assert INSTINCTS_DIR == Path.home() / ".claude" / "instincts"

    def test_observations_file_is_under_instincts_dir(self):
        """OBSERVATIONS_FILE should be under INSTINCTS_DIR."""
        from instincts.config import INSTINCTS_DIR, OBSERVATIONS_FILE

        assert OBSERVATIONS_FILE.parent == INSTINCTS_DIR
        assert OBSERVATIONS_FILE.name == "observations.jsonl"

    def test_personal_dir_is_under_instincts_dir(self):
        """PERSONAL_DIR should be under INSTINCTS_DIR."""
        from instincts.config import INSTINCTS_DIR, PERSONAL_DIR

        assert PERSONAL_DIR.parent == INSTINCTS_DIR
        assert PERSONAL_DIR.name == "personal"

    def test_archive_dir_is_under_instincts_dir(self):
        """ARCHIVE_DIR should be under INSTINCTS_DIR."""
        from instincts.config import ARCHIVE_DIR, INSTINCTS_DIR

        assert ARCHIVE_DIR.parent == INSTINCTS_DIR
        assert ARCHIVE_DIR.name == "observations.archive"


class TestEnsureDirectories:
    """Test ensure_directories function."""

    def test_ensure_directories_creates_instincts_dir(self, tmp_path: Path):
        """ensure_directories should create INSTINCTS_DIR."""
        from instincts.config import ensure_directories

        instincts_dir = tmp_path / ".claude" / "instincts"

        with patch("instincts.config.INSTINCTS_DIR", instincts_dir):
            with patch("instincts.config.PERSONAL_DIR", instincts_dir / "personal"):
                with patch(
                    "instincts.config.ARCHIVE_DIR", instincts_dir / "observations.archive"
                ):
                    ensure_directories()

        assert instincts_dir.exists()

    def test_ensure_directories_creates_personal_dir(self, tmp_path: Path):
        """ensure_directories should create PERSONAL_DIR."""
        from instincts.config import ensure_directories

        instincts_dir = tmp_path / ".claude" / "instincts"
        personal_dir = instincts_dir / "personal"

        with patch("instincts.config.INSTINCTS_DIR", instincts_dir):
            with patch("instincts.config.PERSONAL_DIR", personal_dir):
                with patch(
                    "instincts.config.ARCHIVE_DIR", instincts_dir / "observations.archive"
                ):
                    ensure_directories()

        assert personal_dir.exists()

    def test_ensure_directories_is_idempotent(self, tmp_path: Path):
        """ensure_directories should not fail if directories already exist."""
        from instincts.config import ensure_directories

        instincts_dir = tmp_path / ".claude" / "instincts"
        personal_dir = instincts_dir / "personal"
        archive_dir = instincts_dir / "observations.archive"

        # Create directories first
        instincts_dir.mkdir(parents=True)
        personal_dir.mkdir()
        archive_dir.mkdir()

        with patch("instincts.config.INSTINCTS_DIR", instincts_dir):
            with patch("instincts.config.PERSONAL_DIR", personal_dir):
                with patch("instincts.config.ARCHIVE_DIR", archive_dir):
                    # Should not raise
                    ensure_directories()

        assert instincts_dir.exists()
        assert personal_dir.exists()
        assert archive_dir.exists()
