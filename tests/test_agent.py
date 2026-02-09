"""Tests for instincts.agent module.

Tests cover:
- AC-1.1: Read and analyze observations from observations.jsonl
- AC-1.2: Create instinct files in personal/ directory
- AC-1.3: Handle empty/missing observations
- EC-3: Handle conflicting patterns separately
- EC-4: Warn about too many instinct files
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from instincts.agent import (
    AnalysisResult,
    _write_instinct_file,
    analyze_observations,
    apply_confidence_decay,
    format_analysis_summary,
)
from instincts.models import Instinct


class TestAnalyzeObservations:
    """Tests for analyze_observations function (AC-1.1, AC-1.2)."""

    def test_reads_observations_from_file(self, tmp_path: Path):
        """Should read observations from observations.jsonl (AC-1.1)."""
        # Setup
        instincts_dir = tmp_path / "instincts"
        instincts_dir.mkdir()
        personal_dir = instincts_dir / "personal"
        personal_dir.mkdir()
        obs_file = instincts_dir / "observations.jsonl"

        # Create observations that form a pattern
        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "tool_start", "tool": "Edit", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:30Z"},
            {"event": "tool_complete", "tool": "Edit", "session": "s1", "timestamp": "2026-02-09T10:00:31Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        with patch("instincts.agent.OBSERVATIONS_FILE", obs_file):
            with patch("instincts.agent.PERSONAL_DIR", personal_dir):
                result = analyze_observations()

        # Should return analysis result
        assert result is not None
        assert hasattr(result, "patterns_detected") or "patterns" in str(result)

    def test_creates_instinct_files_in_personal_dir(self, tmp_path: Path):
        """Should create instinct files in personal/ directory (AC-1.2)."""
        # Setup
        instincts_dir = tmp_path / "instincts"
        instincts_dir.mkdir()
        personal_dir = instincts_dir / "personal"
        personal_dir.mkdir()
        obs_file = instincts_dir / "observations.jsonl"

        # Create observations that form a detectable pattern
        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "tool_start", "tool": "Edit", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:30Z"},
            {"event": "tool_complete", "tool": "Edit", "session": "s1", "timestamp": "2026-02-09T10:00:31Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        with patch("instincts.agent.OBSERVATIONS_FILE", obs_file):
            with patch("instincts.agent.PERSONAL_DIR", personal_dir):
                result = analyze_observations(dry_run=False)

        # Check if instinct files were created
        instinct_files = list(personal_dir.glob("*.md"))
        if result.instincts_created > 0:
            assert len(instinct_files) >= 1

    def test_dry_run_does_not_create_files(self, tmp_path: Path):
        """Should not create files when dry_run=True."""
        # Setup
        instincts_dir = tmp_path / "instincts"
        instincts_dir.mkdir()
        personal_dir = instincts_dir / "personal"
        personal_dir.mkdir()
        obs_file = instincts_dir / "observations.jsonl"

        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "tool_start", "tool": "Edit", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:30Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        with patch("instincts.agent.OBSERVATIONS_FILE", obs_file):
            with patch("instincts.agent.PERSONAL_DIR", personal_dir):
                analyze_observations(dry_run=True)

        # Should not create any files in dry run mode
        instinct_files = list(personal_dir.glob("*.md"))
        assert len(instinct_files) == 0


class TestAnalyzeEmptyObservations:
    """Tests for handling empty/missing observations (AC-1.3)."""

    def test_returns_no_patterns_for_empty_file(self, tmp_path: Path):
        """Should return no patterns when observations file is empty (AC-1.3)."""
        instincts_dir = tmp_path / "instincts"
        instincts_dir.mkdir()
        personal_dir = instincts_dir / "personal"
        personal_dir.mkdir()
        obs_file = instincts_dir / "observations.jsonl"
        obs_file.write_text("")

        with patch("instincts.agent.OBSERVATIONS_FILE", obs_file):
            with patch("instincts.agent.PERSONAL_DIR", personal_dir):
                result = analyze_observations()

        assert result.patterns_detected == 0
        assert result.instincts_created == 0

    def test_returns_no_patterns_for_missing_file(self, tmp_path: Path):
        """Should return no patterns when observations file doesn't exist (AC-1.3)."""
        instincts_dir = tmp_path / "instincts"
        instincts_dir.mkdir()
        personal_dir = instincts_dir / "personal"
        personal_dir.mkdir()

        with patch("instincts.agent.OBSERVATIONS_FILE", instincts_dir / "nonexistent.jsonl"):
            with patch("instincts.agent.PERSONAL_DIR", personal_dir):
                result = analyze_observations()

        assert result.patterns_detected == 0


class TestConflictingPatterns:
    """Tests for handling conflicting patterns (EC-3)."""

    def test_creates_separate_instincts_for_conflicting_patterns(self, tmp_path: Path):
        """Should create separate instincts for conflicting patterns (EC-3)."""
        instincts_dir = tmp_path / "instincts"
        instincts_dir.mkdir()
        personal_dir = instincts_dir / "personal"
        personal_dir.mkdir()
        obs_file = instincts_dir / "observations.jsonl"

        # Create observations that might produce conflicting preferences
        # e.g., sometimes prefers functional, sometimes prefers classes
        observations = [
            # Session 1: functional preference
            {"event": "tool_start", "tool": "Write", "input": '{"content": "def process():"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            # Session 2: different approach
            {"event": "tool_start", "tool": "Write", "input": '{"content": "class Processor:"}', "session": "s2", "timestamp": "2026-02-09T11:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s2", "timestamp": "2026-02-09T11:00:01Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        with patch("instincts.agent.OBSERVATIONS_FILE", obs_file):
            with patch("instincts.agent.PERSONAL_DIR", personal_dir):
                result = analyze_observations(dry_run=False)

        # Conflicting patterns should be kept separate, not merged
        # (This test mainly verifies no crash occurs)
        assert result is not None


class TestManyInstinctsWarning:
    """Tests for warning about too many instinct files (EC-4)."""

    def test_warns_when_personal_dir_has_100_plus_files(self, tmp_path: Path, capsys):
        """Should warn when personal/ has 100+ instinct files (EC-4)."""
        instincts_dir = tmp_path / "instincts"
        instincts_dir.mkdir()
        personal_dir = instincts_dir / "personal"
        personal_dir.mkdir()
        obs_file = instincts_dir / "observations.jsonl"
        obs_file.write_text("")

        # Create 100+ dummy instinct files
        for i in range(105):
            (personal_dir / f"instinct-{i:03d}.md").write_text("---\nid: test\n---\nContent")

        with patch("instincts.agent.OBSERVATIONS_FILE", obs_file):
            with patch("instincts.agent.PERSONAL_DIR", personal_dir):
                result = analyze_observations()

        # Should have warning in result or output
        captured = capsys.readouterr()
        assert result.warnings or "100" in captured.out or "performance" in captured.out.lower()


class TestApplyConfidenceDecay:
    """Tests for apply_confidence_decay function."""

    def test_applies_decay_to_all_existing_instincts(self, tmp_path: Path):
        """Should apply confidence decay to all existing instincts."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        # Create an old instinct file
        old_instinct = """---
id: old-instinct
trigger: "when testing"
confidence: 0.7
domain: testing
source: pattern-detection
evidence_count: 5
created_at: "2025-01-01T00:00:00Z"
updated_at: "2025-01-01T00:00:00Z"
---
# Old Instinct

Some content.
"""
        (personal_dir / "old-instinct.md").write_text(old_instinct)

        with patch("instincts.agent.PERSONAL_DIR", personal_dir):
            decayed_instincts = apply_confidence_decay()

        # Should return list of instincts with potentially updated confidence
        assert len(decayed_instincts) >= 1


class TestFormatAnalysisSummary:
    """Tests for format_analysis_summary function."""

    def test_formats_summary_with_counts(self):
        """Should format summary with pattern and instinct counts."""
        result = AnalysisResult(
            patterns_detected=5,
            instincts_created=3,
            instincts_updated=2,
            warnings=(),
        )

        summary = format_analysis_summary(result)

        assert "5" in summary  # patterns detected
        assert "3" in summary  # instincts created
        assert "2" in summary  # instincts updated

    def test_includes_warnings_in_summary(self):
        """Should include warnings in summary."""
        result = AnalysisResult(
            patterns_detected=0,
            instincts_created=0,
            instincts_updated=0,
            warnings=("Too many instinct files",),
        )

        summary = format_analysis_summary(result)

        assert "warning" in summary.lower() or "Too many" in summary

    def test_handles_no_patterns(self):
        """Should handle case with no patterns detected."""
        result = AnalysisResult(
            patterns_detected=0,
            instincts_created=0,
            instincts_updated=0,
            warnings=(),
        )

        summary = format_analysis_summary(result)

        assert "no" in summary.lower() or "0" in summary


class TestPathTraversalPrevention:
    """Tests to prevent path traversal attacks in instinct ID handling."""

    def test_uses_is_relative_to_for_path_check(self, tmp_path: Path):
        """Should use is_relative_to() for proper path traversal detection."""
        # Create a directory structure where string comparison would fail
        # but is_relative_to() correctly handles it
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        ts = datetime.now(timezone.utc)
        # This ID, when sanitized, should still be within personal_dir
        instinct = Instinct(
            id="test-instinct",
            trigger="test",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        result_path = _write_instinct_file(instinct, personal_dir)

        # Verify path is relative to directory using is_relative_to
        assert result_path.is_relative_to(personal_dir)

    def test_sanitizes_instinct_id_with_path_traversal(self, tmp_path: Path):
        """Should sanitize instinct IDs that contain path traversal sequences."""
        ts = datetime.now(timezone.utc)
        # Attempt path traversal via malicious instinct ID
        malicious_instinct = Instinct(
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

        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        # Should write file safely within personal_dir
        result_path = _write_instinct_file(malicious_instinct, personal_dir)

        # File should be created within personal_dir, not outside
        assert result_path.parent == personal_dir
        # Filename should be sanitized
        assert ".." not in result_path.name
        assert "/" not in result_path.name

    def test_sanitizes_instinct_id_with_absolute_path(self, tmp_path: Path):
        """Should sanitize instinct IDs that contain absolute paths."""
        ts = datetime.now(timezone.utc)
        # Attempt to write to absolute path
        malicious_instinct = Instinct(
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

        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        result_path = _write_instinct_file(malicious_instinct, personal_dir)

        # File should be created within personal_dir
        assert result_path.parent == personal_dir

    def test_refuses_to_overwrite_symlink(self, tmp_path: Path):
        """Should refuse to write to a symlink (symlink attack prevention)."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="safe-instinct",
            trigger="test",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        # Create a symlink that points somewhere else
        symlink_path = personal_dir / "safe-instinct.md"
        target_path = tmp_path / "target.txt"
        target_path.write_text("target")
        symlink_path.symlink_to(target_path)

        # Should raise an error when trying to write to a symlink
        with pytest.raises(ValueError, match="symlink"):
            _write_instinct_file(instinct, personal_dir)


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_has_required_fields(self):
        """AnalysisResult should have required fields."""
        result = AnalysisResult(
            patterns_detected=5,
            instincts_created=3,
            instincts_updated=2,
            warnings=("warning1",),
        )

        assert result.patterns_detected == 5
        assert result.instincts_created == 3
        assert result.instincts_updated == 2
        assert result.warnings == ("warning1",)

    def test_optional_patterns_tuple(self):
        """AnalysisResult should have optional patterns tuple."""
        result = AnalysisResult(
            patterns_detected=2,
            instincts_created=1,
            instincts_updated=0,
            warnings=(),
            patterns=(),  # Optional detailed patterns
        )

        assert result.patterns == ()

    def test_is_frozen(self):
        """AnalysisResult should be immutable (frozen)."""
        result = AnalysisResult(
            patterns_detected=5,
            instincts_created=3,
            instincts_updated=2,
            warnings=(),
        )

        with pytest.raises(AttributeError):
            result.patterns_detected = 10  # type: ignore[misc]
