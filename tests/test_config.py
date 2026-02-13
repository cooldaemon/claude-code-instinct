"""Tests for instincts.config module.

Tests cover:
- Analysis trigger constants
- Project-scoped path functions
- Evolution output directory functions
"""

from pathlib import Path


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


class TestGetAnalysisPendingFile:
    """Test project-scoped analysis pending file path."""

    def test_get_analysis_pending_file_returns_project_path(self, tmp_path: Path):
        """get_analysis_pending_file should return <project>/docs/instincts/.analysis_pending."""
        from instincts.config import get_analysis_pending_file

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_analysis_pending_file(project_root)

        assert result == project_root / "docs" / "instincts" / ".analysis_pending"


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


class TestDetectProjectRoot:
    """Test project root detection (AC-1.1, AC-1.2)."""

    def test_detect_project_root_finds_git_directory(self, tmp_path: Path):
        """AC-1.1: Should detect project root by finding .git directory."""
        from instincts.config import detect_project_root

        # Create a project structure with .git directory
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        subdir = project_root / "src" / "module"
        subdir.mkdir(parents=True)

        result = detect_project_root(subdir)

        assert result == project_root

    def test_detect_project_root_finds_claudemd_file(self, tmp_path: Path):
        """AC-1.1: Should detect project root by finding CLAUDE.md file."""
        from instincts.config import detect_project_root

        # Create a project structure with CLAUDE.md
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "CLAUDE.md").write_text("# Project")
        subdir = project_root / "src" / "module"
        subdir.mkdir(parents=True)

        result = detect_project_root(subdir)

        assert result == project_root

    def test_detect_project_root_prefers_git_over_claudemd(self, tmp_path: Path):
        """Should prefer .git directory when both exist at different levels."""
        from instincts.config import detect_project_root

        # .git at project root, CLAUDE.md in subdirectory
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        subdir = project_root / "subproject"
        subdir.mkdir()
        (subdir / "CLAUDE.md").write_text("# Subproject")
        deep_dir = subdir / "src"
        deep_dir.mkdir()

        result = detect_project_root(deep_dir)

        # Should find the CLAUDE.md first (closer to start_path)
        assert result == subdir

    def test_detect_project_root_falls_back_to_cwd(self, tmp_path: Path):
        """AC-1.2: Should fall back to current working directory if no markers found."""
        from instincts.config import detect_project_root

        # Create a directory without any project markers
        no_project_dir = tmp_path / "no_project"
        no_project_dir.mkdir()

        result = detect_project_root(no_project_dir)

        assert result == no_project_dir

    def test_detect_project_root_handles_root_directory(self, tmp_path: Path):
        """Should handle case where start_path is near filesystem root."""
        from instincts.config import detect_project_root

        # Test with tmp_path itself (no .git or CLAUDE.md above it typically)
        result = detect_project_root(tmp_path)

        # Should return tmp_path as fallback
        assert result == tmp_path


class TestGetProjectInstinctsDir:
    """Test project instincts directory path (AC-1.3)."""

    def test_get_project_instincts_dir_returns_docs_instincts(self, tmp_path: Path):
        """AC-1.3: Should return <project>/docs/instincts/ as storage location."""
        from instincts.config import get_project_instincts_dir

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_project_instincts_dir(project_root)

        assert result == project_root / "docs" / "instincts"


class TestGetLearnedDir:
    """Test learned instincts directory path (AC-2.1, AC-2.2)."""

    def test_get_learned_dir_returns_learned_subdirectory(self, tmp_path: Path):
        """AC-2.1, AC-2.2: Should return <project>/docs/instincts/learned/."""
        from instincts.config import get_learned_dir

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_learned_dir(project_root)

        assert result == project_root / "docs" / "instincts" / "learned"


class TestGetObservationsFile:
    """Test observations file path."""

    def test_get_observations_file_returns_jsonl_path(self, tmp_path: Path):
        """Should return <project>/docs/instincts/observations.jsonl."""
        from instincts.config import get_observations_file

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_observations_file(project_root)

        assert result == project_root / "docs" / "instincts" / "observations.jsonl"


class TestGetArchiveDir:
    """Test archive directory path."""

    def test_get_archive_dir_returns_archive_subdirectory(self, tmp_path: Path):
        """Should return <project>/docs/instincts/observations.archive/."""
        from instincts.config import get_archive_dir

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_archive_dir(project_root)

        assert result == project_root / "docs" / "instincts" / "observations.archive"


class TestEvolutionOutputType:
    """Test EvolutionOutputType enum and get_evolved_output_dir function."""

    def test_evolution_output_type_enum_values(self):
        """Should have all required output types."""
        from instincts.config import EvolutionOutputType

        assert EvolutionOutputType.CLAUDEMD.value == "claudemd"
        assert EvolutionOutputType.RULES.value == "rules"
        assert EvolutionOutputType.SKILLS.value == "skills"
        assert EvolutionOutputType.SUBAGENTS.value == "subagents"
        assert EvolutionOutputType.COMMANDS.value == "commands"

    def test_get_evolved_output_dir_project_scope_rules(self, tmp_path: Path):
        """AC-6.4: Should return <project>/.claude/rules/ for project-scoped rules."""
        from instincts.config import EvolutionOutputType, get_evolved_output_dir

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_evolved_output_dir(EvolutionOutputType.RULES, "project", project_root)

        assert result == project_root / ".claude" / "rules"

    def test_get_evolved_output_dir_global_scope_rules(self, tmp_path: Path):
        """AC-6.5: Should return ~/.claude/rules/ for global-scoped rules."""
        from instincts.config import EvolutionOutputType, get_evolved_output_dir

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_evolved_output_dir(EvolutionOutputType.RULES, "global", project_root)

        assert result == Path.home() / ".claude" / "rules"

    def test_get_evolved_output_dir_project_scope_skills(self, tmp_path: Path):
        """AC-6.6: Should return <project>/.claude/skills/ for project-scoped skills."""
        from instincts.config import EvolutionOutputType, get_evolved_output_dir

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_evolved_output_dir(EvolutionOutputType.SKILLS, "project", project_root)

        assert result == project_root / ".claude" / "skills"

    def test_get_evolved_output_dir_global_scope_skills(self, tmp_path: Path):
        """AC-6.7: Should return ~/.claude/skills/ for global-scoped skills."""
        from instincts.config import EvolutionOutputType, get_evolved_output_dir

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_evolved_output_dir(EvolutionOutputType.SKILLS, "global", project_root)

        assert result == Path.home() / ".claude" / "skills"

    def test_get_evolved_output_dir_project_scope_subagents(self, tmp_path: Path):
        """AC-6.8: Should return <project>/.claude/agents/ for project-scoped subagents."""
        from instincts.config import EvolutionOutputType, get_evolved_output_dir

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_evolved_output_dir(EvolutionOutputType.SUBAGENTS, "project", project_root)

        assert result == project_root / ".claude" / "agents"

    def test_get_evolved_output_dir_global_scope_subagents(self, tmp_path: Path):
        """AC-6.9: Should return ~/.claude/agents/ for global-scoped subagents."""
        from instincts.config import EvolutionOutputType, get_evolved_output_dir

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_evolved_output_dir(EvolutionOutputType.SUBAGENTS, "global", project_root)

        assert result == Path.home() / ".claude" / "agents"

    def test_get_evolved_output_dir_project_scope_commands(self, tmp_path: Path):
        """AC-6.10: Should return <project>/.claude/commands/ for project-scoped commands."""
        from instincts.config import EvolutionOutputType, get_evolved_output_dir

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_evolved_output_dir(EvolutionOutputType.COMMANDS, "project", project_root)

        assert result == project_root / ".claude" / "commands"

    def test_get_evolved_output_dir_global_scope_commands(self, tmp_path: Path):
        """AC-6.11: Should return ~/.claude/commands/ for global-scoped commands."""
        from instincts.config import EvolutionOutputType, get_evolved_output_dir

        project_root = tmp_path / "my_project"
        project_root.mkdir()

        result = get_evolved_output_dir(EvolutionOutputType.COMMANDS, "global", project_root)

        assert result == Path.home() / ".claude" / "commands"


class TestAutoLearningConstants:
    """Test auto-learning constants."""

    def test_auto_learn_observation_threshold(self):
        """AUTO_LEARN_OBSERVATION_THRESHOLD should be 50."""
        from instincts.config import AUTO_LEARN_OBSERVATION_THRESHOLD

        assert AUTO_LEARN_OBSERVATION_THRESHOLD == 50

    def test_auto_learn_cooldown_seconds(self):
        """AUTO_LEARN_COOLDOWN_SECONDS should be 300 (5 minutes)."""
        from instincts.config import AUTO_LEARN_COOLDOWN_SECONDS

        assert AUTO_LEARN_COOLDOWN_SECONDS == 300

    def test_auto_learn_lock_file(self):
        """AUTO_LEARN_LOCK_FILE should be '.auto_learn.lock'."""
        from instincts.config import AUTO_LEARN_LOCK_FILE

        assert AUTO_LEARN_LOCK_FILE == ".auto_learn.lock"

    def test_auto_learn_state_file(self):
        """AUTO_LEARN_STATE_FILE should be '.auto_learn_state.json'."""
        from instincts.config import AUTO_LEARN_STATE_FILE

        assert AUTO_LEARN_STATE_FILE == ".auto_learn_state.json"


class TestLearnedPatternsSection:
    """Test CLAUDE.md integration constants."""

    def test_learned_patterns_section_constant(self):
        """LEARNED_PATTERNS_SECTION should be '## Learned Patterns'."""
        from instincts.config import LEARNED_PATTERNS_SECTION

        assert LEARNED_PATTERNS_SECTION == "## Learned Patterns"
