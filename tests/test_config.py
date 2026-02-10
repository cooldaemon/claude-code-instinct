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

    def test_ensure_directories_uses_restrictive_permissions(self, tmp_path: Path):
        """ensure_directories should create directories with mode 0o700."""
        import stat

        from instincts.config import ensure_directories

        instincts_dir = tmp_path / ".claude" / "instincts"
        personal_dir = instincts_dir / "personal"
        archive_dir = instincts_dir / "observations.archive"
        evolved_dir = instincts_dir / "evolved"
        evolved_skills_dir = evolved_dir / "skills"
        evolved_commands_dir = evolved_dir / "commands"
        evolved_agents_dir = evolved_dir / "agents"

        with patch("instincts.config.INSTINCTS_DIR", instincts_dir):
            with patch("instincts.config.PERSONAL_DIR", personal_dir):
                with patch("instincts.config.ARCHIVE_DIR", archive_dir):
                    with patch("instincts.config.EVOLVED_DIR", evolved_dir):
                        with patch("instincts.config.EVOLVED_SKILLS_DIR", evolved_skills_dir):
                            with patch(
                                "instincts.config.EVOLVED_COMMANDS_DIR", evolved_commands_dir
                            ):
                                with patch(
                                    "instincts.config.EVOLVED_AGENTS_DIR", evolved_agents_dir
                                ):
                                    ensure_directories()

        # Check that directories have restrictive permissions (0o700)
        expected_mode = stat.S_IRWXU  # 0o700 = owner read/write/execute only
        for dir_path in [
            instincts_dir,
            personal_dir,
            archive_dir,
            evolved_dir,
            evolved_skills_dir,
            evolved_commands_dir,
            evolved_agents_dir,
        ]:
            actual_mode = dir_path.stat().st_mode & 0o777
            assert actual_mode == expected_mode, (
                f"{dir_path} has mode {oct(actual_mode)}, expected {oct(expected_mode)}"
            )


class TestAnalysisTriggerConstants:
    """Test analysis trigger constants for auto-trigger feature."""

    def test_analysis_trigger_count_is_200(self):
        """ANALYSIS_TRIGGER_COUNT should be 200."""
        from instincts.config import ANALYSIS_TRIGGER_COUNT

        assert ANALYSIS_TRIGGER_COUNT == 200

    def test_analysis_trigger_hours_is_24(self):
        """ANALYSIS_TRIGGER_HOURS should be 24.0 hours."""
        from instincts.config import ANALYSIS_TRIGGER_HOURS

        assert ANALYSIS_TRIGGER_HOURS == 24.0

    def test_analysis_min_count_is_20(self):
        """ANALYSIS_MIN_COUNT should be 20."""
        from instincts.config import ANALYSIS_MIN_COUNT

        assert ANALYSIS_MIN_COUNT == 20

    def test_max_observations_for_analysis_is_1000(self):
        """MAX_OBSERVATIONS_FOR_ANALYSIS should be 1000."""
        from instincts.config import MAX_OBSERVATIONS_FOR_ANALYSIS

        assert MAX_OBSERVATIONS_FOR_ANALYSIS == 1000

    def test_analysis_pending_file_is_under_instincts_dir(self):
        """ANALYSIS_PENDING_FILE should be under INSTINCTS_DIR."""
        from instincts.config import ANALYSIS_PENDING_FILE, INSTINCTS_DIR

        assert ANALYSIS_PENDING_FILE.parent == INSTINCTS_DIR
        assert ANALYSIS_PENDING_FILE.name == ".analysis_pending"


class TestLLMConstants:
    """Test LLM-related constants for dual-approach feature."""

    def test_default_llm_model(self):
        """DEFAULT_LLM_MODEL should be claude-3-haiku."""
        from instincts.config import DEFAULT_LLM_MODEL

        assert DEFAULT_LLM_MODEL == "claude-3-haiku-20240307"

    def test_anthropic_api_key_env(self):
        """ANTHROPIC_API_KEY_ENV should be ANTHROPIC_API_KEY."""
        from instincts.config import ANTHROPIC_API_KEY_ENV

        assert ANTHROPIC_API_KEY_ENV == "ANTHROPIC_API_KEY"
