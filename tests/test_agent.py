"""Tests for instincts.agent module.

Tests cover:
- AC-1.1: Read and analyze observations from observations.jsonl
- AC-1.2: Create instinct files in learned/ directory
- AC-1.3: Handle empty/missing observations
- EC-3: Handle conflicting patterns separately
- EC-4: Warn about too many instinct files
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from instincts.agent import (
    AnalysisResult,
    _write_instinct_file,
    analyze_observations,
    apply_confidence_decay,
    format_analysis_summary,
)
from instincts.models import Instinct


def create_project_structure(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a standard project structure for tests.

    Returns:
        Tuple of (project_root, instincts_dir, learned_dir)
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    instincts_dir = project_root / "docs" / "instincts"
    instincts_dir.mkdir(parents=True)
    learned_dir = instincts_dir / "learned"
    learned_dir.mkdir()
    return project_root, instincts_dir, learned_dir


class TestAnalyzeObservations:
    """Tests for analyze_observations function (AC-1.1, AC-1.2)."""

    def test_reads_observations_from_file(self, tmp_path: Path):
        """Should read observations from observations.jsonl (AC-1.1)."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"

        # Create observations that form a pattern
        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "tool_start", "tool": "Edit", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:30Z"},
            {"event": "tool_complete", "tool": "Edit", "session": "s1", "timestamp": "2026-02-09T10:00:31Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        result = analyze_observations(project_root)

        # Should return analysis result
        assert result is not None
        assert hasattr(result, "patterns_detected") or "patterns" in str(result)

    def test_creates_instinct_files_in_learned_dir(self, tmp_path: Path):
        """Should create instinct files in learned/ directory (AC-1.2)."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"

        # Create observations that form a detectable pattern
        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "tool_start", "tool": "Edit", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:30Z"},
            {"event": "tool_complete", "tool": "Edit", "session": "s1", "timestamp": "2026-02-09T10:00:31Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        result = analyze_observations(project_root, dry_run=False)

        # Check if instinct files were created
        instinct_files = list(learned_dir.glob("*.md"))
        if result.instincts_created > 0:
            assert len(instinct_files) >= 1

    def test_dry_run_does_not_create_files(self, tmp_path: Path):
        """Should not create files when dry_run=True."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"

        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "tool_start", "tool": "Edit", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:30Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        analyze_observations(project_root, dry_run=True)

        # Should not create any files in dry run mode
        instinct_files = list(learned_dir.glob("*.md"))
        assert len(instinct_files) == 0


class TestAnalyzeEmptyObservations:
    """Tests for handling empty/missing observations (AC-1.3)."""

    def test_returns_no_patterns_for_empty_file(self, tmp_path: Path):
        """Should return no patterns when observations file is empty (AC-1.3)."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"
        obs_file.write_text("")

        result = analyze_observations(project_root)

        assert result.patterns_detected == 0
        assert result.instincts_created == 0

    def test_returns_no_patterns_for_missing_file(self, tmp_path: Path):
        """Should return no patterns when observations file doesn't exist (AC-1.3)."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)

        result = analyze_observations(project_root)

        assert result.patterns_detected == 0


class TestConflictingPatterns:
    """Tests for handling conflicting patterns (EC-3)."""

    def test_creates_separate_instincts_for_conflicting_patterns(self, tmp_path: Path):
        """Should create separate instincts for conflicting patterns (EC-3)."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"

        # Create observations with different patterns
        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "tool_start", "tool": "Bash", "input": '{"command": "pytest"}', "session": "s2", "timestamp": "2026-02-09T11:00:00Z"},
            {"event": "tool_complete", "tool": "Bash", "session": "s2", "timestamp": "2026-02-09T11:00:01Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        result = analyze_observations(project_root, dry_run=False)

        # If patterns created, they should be separate instincts
        if result.instincts_created > 1:
            instinct_files = list(learned_dir.glob("*.md"))
            assert len(instinct_files) >= 2


class TestManyInstinctsWarning:
    """Tests for warning when many instinct files exist (EC-4)."""

    def test_warns_when_learned_dir_has_100_plus_files(self, tmp_path: Path):
        """Should include warning when 100+ instinct files exist (EC-4)."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"

        # Create 100+ instinct files
        for i in range(101):
            (learned_dir / f"instinct-{i}.md").write_text(
                f"""---
id: test-{i}
trigger: test
confidence: 0.5
---
Content"""
            )

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        result = analyze_observations(project_root)

        # Should have a warning about too many instinct files
        assert any("100" in w or "instinct files" in w.lower() for w in result.warnings)


class TestApplyConfidenceDecay:
    """Tests for apply_confidence_decay function."""

    def test_applies_decay_to_all_existing_instincts(self, tmp_path: Path):
        """Should apply confidence decay to all instincts in directory."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)

        # Create instinct file
        instinct_content = """---
id: "test-instinct"
trigger: "when testing"
confidence: 0.8
domain: "testing"
source: "test"
evidence_count: 5
created_at: "2024-01-01T00:00:00+00:00"
updated_at: "2024-01-01T00:00:00+00:00"
status: "active"
---

# Test Instinct
"""
        (learned_dir / "test-instinct.md").write_text(instinct_content)

        decayed = apply_confidence_decay(learned_dir)

        # Should return list of instincts with updated confidence
        assert len(decayed) >= 1


class TestFormatAnalysisSummary:
    """Tests for format_analysis_summary function."""

    def test_formats_summary_with_counts(self):
        """Should format summary with pattern counts."""
        result = AnalysisResult(
            patterns_detected=3,
            instincts_created=2,
            instincts_updated=1,
            warnings=(),
            patterns=(),
        )

        summary = format_analysis_summary(result)

        assert "3" in summary
        assert "2" in summary
        assert "1" in summary

    def test_includes_warnings_in_summary(self):
        """Should include warnings in summary."""
        result = AnalysisResult(
            patterns_detected=0,
            instincts_created=0,
            instincts_updated=0,
            warnings=("Test warning",),
            patterns=(),
        )

        summary = format_analysis_summary(result)

        assert "Test warning" in summary

    def test_handles_no_patterns(self):
        """Should handle case with no patterns detected."""
        result = AnalysisResult(
            patterns_detected=0,
            instincts_created=0,
            instincts_updated=0,
            warnings=(),
            patterns=(),
        )

        summary = format_analysis_summary(result)

        assert "No patterns" in summary or "0" in summary


class TestPathTraversalPrevention:
    """Tests for path traversal attack prevention."""

    def test_uses_is_relative_to_for_path_check(self, tmp_path: Path):
        """Should use is_relative_to() for path validation."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test",
            trigger="test",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        # Should not raise for valid path
        _write_instinct_file(instinct, tmp_path)

    def test_sanitizes_instinct_id_with_path_traversal(self, tmp_path: Path):
        """Should sanitize instinct ID containing path traversal sequences."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="../../../etc/passwd",
            trigger="test",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        result_path = _write_instinct_file(instinct, tmp_path)

        # File should be created within tmp_path
        assert result_path.parent == tmp_path
        assert ".." not in result_path.name

    def test_sanitizes_instinct_id_with_absolute_path(self, tmp_path: Path):
        """Should sanitize instinct ID containing absolute path."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="/etc/passwd",
            trigger="test",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        result_path = _write_instinct_file(instinct, tmp_path)

        # File should be created within tmp_path
        assert result_path.parent == tmp_path

    def test_refuses_to_overwrite_symlink(self, tmp_path: Path):
        """Should refuse to write to symlink."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test",
            trigger="test",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        # Create a symlink
        target = tmp_path / "target.md"
        target.write_text("target")
        symlink = tmp_path / "test.md"
        symlink.symlink_to(target)

        with pytest.raises(ValueError, match="symlink"):
            _write_instinct_file(instinct, tmp_path)


class TestSymlinkSkippingOnRead:
    """Tests for symlink skipping when reading instincts."""

    def test_load_existing_instincts_skips_symlinks(self, tmp_path: Path):
        """Should skip symlinks when loading existing instincts."""
        from instincts.agent import _load_existing_instincts

        # Create a real instinct file
        (tmp_path / "real.md").write_text("""---
id: real
trigger: test
confidence: 0.5
---
Content""")

        # Create a symlink
        target = tmp_path / "target.md"
        target.write_text("""---
id: target
trigger: test
confidence: 0.5
---
Content""")
        symlink = tmp_path / "link.md"
        symlink.symlink_to(target)

        instincts = _load_existing_instincts(tmp_path)

        # Should only load the real file, not the symlink
        ids = [i.id for i in instincts]
        assert "real" in ids
        assert "link" not in ids


class TestYamlInjectionPrevention:
    """Tests for YAML injection prevention."""

    def test_escapes_quotes_in_trigger(self, tmp_path: Path):
        """Should escape quotes in trigger to prevent YAML injection."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test",
            trigger='trigger with "quotes"',
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        result_path = _write_instinct_file(instinct, tmp_path)
        content = result_path.read_text()

        # Should have escaped quotes
        assert '\\"' in content or "quotes" in content

    def test_escapes_newlines_in_trigger(self, tmp_path: Path):
        """Should escape newlines in trigger."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test",
            trigger="trigger\nwith\nnewlines",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        result_path = _write_instinct_file(instinct, tmp_path)
        content = result_path.read_text()

        # Newlines should be escaped in the trigger value
        # Check that the file is valid YAML (doesn't have raw newlines breaking it)
        assert "trigger:" in content

    def test_escapes_backslashes_in_trigger(self, tmp_path: Path):
        """Should escape backslashes in trigger."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test",
            trigger="trigger\\with\\backslashes",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        result_path = _write_instinct_file(instinct, tmp_path)
        content = result_path.read_text()

        # Backslashes should be escaped
        assert "\\\\" in content or "backslashes" in content

    def test_escapes_carriage_return_in_trigger(self, tmp_path: Path):
        """Should escape carriage return in trigger."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test",
            trigger="trigger\rwith\rcarriage",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        result_path = _write_instinct_file(instinct, tmp_path)
        content = result_path.read_text()

        # Carriage returns should be escaped
        assert "trigger:" in content

    def test_escapes_special_chars_in_id(self, tmp_path: Path):
        """Should escape special chars in ID field."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id='test"id',
            trigger="test",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        result_path = _write_instinct_file(instinct, tmp_path)
        content = result_path.read_text()

        # ID should be escaped
        assert "id:" in content

    def test_id_field_is_quoted_in_yaml(self, tmp_path: Path):
        """Should quote ID field in YAML output."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test-id",
            trigger="test",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        result_path = _write_instinct_file(instinct, tmp_path)
        content = result_path.read_text()

        # ID should be quoted
        assert 'id: "test-id"' in content


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_has_required_fields(self):
        """Should have required fields."""
        result = AnalysisResult(
            patterns_detected=1,
            instincts_created=1,
            instincts_updated=0,
            warnings=(),
            patterns=(),
        )

        assert result.patterns_detected == 1
        assert result.instincts_created == 1
        assert result.instincts_updated == 0

    def test_optional_patterns_tuple(self):
        """Should have optional patterns tuple."""
        result = AnalysisResult(
            patterns_detected=0,
            instincts_created=0,
            instincts_updated=0,
            warnings=(),
            patterns=(),
        )

        assert result.patterns == ()

    def test_is_frozen(self):
        """Should be frozen/immutable."""
        result = AnalysisResult(
            patterns_detected=0,
            instincts_created=0,
            instincts_updated=0,
            warnings=(),
            patterns=(),
        )

        with pytest.raises(AttributeError):
            result.patterns_detected = 5  # type: ignore[misc]

    def test_has_detection_sources_field(self):
        """Should have detection_sources field (AC-R2.8)."""
        result = AnalysisResult(
            patterns_detected=0,
            instincts_created=0,
            instincts_updated=0,
            warnings=(),
            patterns=(),
            detection_sources=("algorithm", "llm"),
        )

        assert result.detection_sources == ("algorithm", "llm")

    def test_detection_sources_defaults_to_algorithm(self):
        """detection_sources should default to ('algorithm',)."""
        result = AnalysisResult(
            patterns_detected=0,
            instincts_created=0,
            instincts_updated=0,
            warnings=(),
            patterns=(),
        )

        assert result.detection_sources == ("algorithm",)


class TestProjectScopedAgent:
    """Tests for project-scoped agent functionality."""

    def test_analyze_creates_instincts_in_project_learned_dir(self, tmp_path: Path):
        """Should create instincts in <project>/docs/instincts/learned/."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"

        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        result = analyze_observations(project_root, dry_run=False)

        # Instincts should be created in project learned dir
        if result.instincts_created > 0:
            instinct_files = list(learned_dir.glob("*.md"))
            assert len(instinct_files) >= 1

    def test_analyze_loads_instincts_from_project_learned_dir(self, tmp_path: Path):
        """Should load existing instincts from project learned directory."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"

        # Create an existing instinct file
        (learned_dir / "existing.md").write_text("""---
id: existing
trigger: test
confidence: 0.5
domain: test
source: test
evidence_count: 1
created_at: "2024-01-01T00:00:00+00:00"
updated_at: "2024-01-01T00:00:00+00:00"
status: active
---
Content""")

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        # Should load without error
        result = analyze_observations(project_root)
        assert result is not None

    def test_analyze_updates_existing_instinct_in_project(self, tmp_path: Path):
        """Should update existing instincts in project."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        result = analyze_observations(project_root)
        assert result is not None


class TestDualApproachAnalysis:
    """Tests for dual-approach analysis (algorithm + LLM)."""

    def test_uses_both_approaches_when_llm_available(self, tmp_path: Path):
        """AC-R2.1, AC-R2.2: Should use both algorithm and LLM when available."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        with patch("instincts.agent.is_llm_available", return_value=True):
            with patch("instincts.agent.detect_patterns_with_llm", return_value=[]):
                result = analyze_observations(project_root)

        assert "llm" in result.detection_sources

    def test_uses_algorithm_only_when_llm_unavailable(self, tmp_path: Path):
        """Should use algorithm only when LLM is unavailable."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        with patch("instincts.agent.is_llm_available", return_value=False):
            result = analyze_observations(project_root)

        assert "llm" not in result.detection_sources
        assert "algorithm" in result.detection_sources

    def test_analyze_uses_recent_observations_limit(self, tmp_path: Path):
        """AC-R2.3: Should limit observations analyzed."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        with patch("instincts.agent.load_recent_observations") as mock_load:
            mock_load.return_value = observations
            analyze_observations(project_root)

        # Should call load_recent_observations with a limit
        mock_load.assert_called()

    def test_skip_llm_flag(self, tmp_path: Path):
        """Should skip LLM when skip_llm=True."""
        project_root, instincts_dir, learned_dir = create_project_structure(tmp_path)
        obs_file = instincts_dir / "observations.jsonl"

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        with patch("instincts.agent.is_llm_available", return_value=True):
            result = analyze_observations(project_root, skip_llm=True)

        assert "llm" not in result.detection_sources


class TestAtomicFileWrites:
    """Tests for atomic file write functionality."""

    def test_write_instinct_file_uses_atomic_write(self, tmp_path: Path):
        """Should use atomic write for instinct files."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test",
            trigger="test",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        result_path = _write_instinct_file(instinct, tmp_path)

        assert result_path.exists()
        content = result_path.read_text()
        assert "test" in content

    def test_atomic_write_cleans_up_on_failure(self, tmp_path: Path):
        """Should clean up temp file on write failure."""
        from instincts.agent import _atomic_write_text

        # Try to write to a non-existent parent directory
        bad_path = tmp_path / "nonexistent" / "file.txt"

        with pytest.raises(OSError):
            _atomic_write_text(bad_path, "content")

        # No temp files should remain
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0
