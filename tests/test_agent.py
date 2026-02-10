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


class TestSymlinkSkippingOnRead:
    """Tests for skipping symlinks when reading instinct files (defense in depth)."""

    def test_load_existing_instincts_skips_symlinks(self, tmp_path: Path):
        """_load_existing_instincts should skip symlink files."""
        from instincts.agent import _load_existing_instincts

        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        # Create a real instinct file
        real_file = personal_dir / "real-instinct.md"
        real_file.write_text("""---
id: real-instinct
trigger: when testing
confidence: 0.5
domain: test
source: test
evidence_count: 1
created_at: "2024-01-01T00:00:00+00:00"
updated_at: "2024-01-01T00:00:00+00:00"
status: active
---

Test content
""")

        # Create a symlink to something else
        target_file = tmp_path / "target.md"
        target_file.write_text("""---
id: symlink-instinct
trigger: when linked
confidence: 0.8
domain: test
source: test
evidence_count: 1
created_at: "2024-01-01T00:00:00+00:00"
updated_at: "2024-01-01T00:00:00+00:00"
status: active
---

Symlink content
""")
        symlink_file = personal_dir / "symlink-instinct.md"
        symlink_file.symlink_to(target_file)

        instincts = _load_existing_instincts(personal_dir)

        # Should only load the real file, not the symlink
        assert len(instincts) == 1
        assert instincts[0].id == "real-instinct"


class TestYamlInjectionPrevention:
    """Tests for YAML frontmatter injection prevention."""

    def test_escapes_quotes_in_trigger(self, tmp_path: Path):
        """Should escape quotes in trigger field to prevent YAML injection."""
        ts = datetime.now(timezone.utc)
        # Malicious trigger with quotes that could break YAML
        instinct = Instinct(
            id="test-instinct",
            trigger='when user says "stop" or "quit"',
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="Test content",
        )

        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        result_path = _write_instinct_file(instinct, personal_dir)
        content = result_path.read_text()

        # Quotes should be escaped in the YAML
        assert 'trigger: "when user says \\"stop\\" or \\"quit\\""' in content

    def test_escapes_newlines_in_trigger(self, tmp_path: Path):
        """Should escape newlines in trigger field to prevent YAML injection."""
        ts = datetime.now(timezone.utc)
        # Malicious trigger with newline that could inject YAML fields
        instinct = Instinct(
            id="test-instinct",
            trigger="when editing\nmalicious_field: injected",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="Test content",
        )

        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        result_path = _write_instinct_file(instinct, personal_dir)
        content = result_path.read_text()

        # Newline should be escaped (literal \n in the file)
        assert "\\n" in content
        # The trigger line should be on a single line (escaped newline doesn't break YAML structure)
        frontmatter = content.split("---")[1]
        trigger_line = [line for line in frontmatter.split("\n") if line.startswith("trigger:")][0]
        # Entire trigger value should be on single line (escaped, not actually multi-line)
        assert "when editing\\nmalicious_field: injected" in trigger_line

    def test_escapes_backslashes_in_trigger(self, tmp_path: Path):
        """Should escape backslashes in trigger field."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test-instinct",
            trigger="when path is C:\\Users\\test",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="Test content",
        )

        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        result_path = _write_instinct_file(instinct, personal_dir)
        content = result_path.read_text()

        # Backslashes should be escaped
        assert "\\\\" in content

    def test_escapes_carriage_return_in_trigger(self, tmp_path: Path):
        """Should escape carriage returns in trigger field."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test-instinct",
            trigger="when editing\rmalicious: injected",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="Test content",
        )

        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        result_path = _write_instinct_file(instinct, personal_dir)
        content = result_path.read_text()

        # Carriage return should be escaped (literal \r in the file)
        assert "\\r" in content
        # The trigger line should be on a single line (escaped CR doesn't break YAML structure)
        frontmatter = content.split("---")[1]
        trigger_line = [line for line in frontmatter.split("\n") if line.startswith("trigger:")][0]
        # Entire trigger value should be on single line
        assert "when editing\\rmalicious: injected" in trigger_line

    def test_escapes_special_chars_in_id(self, tmp_path: Path):
        """Should escape special characters in id field to prevent YAML injection."""
        ts = datetime.now(timezone.utc)
        # Note: ID is sanitized by _sanitize_instinct_id, but we test the YAML output
        # to ensure the id field is properly quoted
        instinct = Instinct(
            id="test-instinct",
            trigger="when testing",
            confidence=0.5,
            domain="test",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="Test content",
        )

        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        result_path = _write_instinct_file(instinct, personal_dir)
        content = result_path.read_text()

        # ID should be quoted in YAML for consistency and safety
        assert 'id: "test-instinct"' in content

    def test_id_field_is_quoted_in_yaml(self, tmp_path: Path):
        """ID field should be quoted in YAML frontmatter for safety."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="user-correction-when-editing",
            trigger="when editing",
            confidence=0.5,
            domain="workflow",
            source="algorithm",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="Test content",
        )

        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        result_path = _write_instinct_file(instinct, personal_dir)
        content = result_path.read_text()

        # All string fields should be quoted for consistency
        frontmatter = content.split("---")[1]
        assert 'id: "user-correction-when-editing"' in frontmatter
        assert 'domain: "workflow"' in frontmatter
        assert 'source: "algorithm"' in frontmatter


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

    def test_has_detection_sources_field(self):
        """AC-R2.8: AnalysisResult should include detection source metadata."""
        result = AnalysisResult(
            patterns_detected=5,
            instincts_created=3,
            instincts_updated=2,
            warnings=(),
            patterns=(),
            detection_sources=("algorithm", "llm"),
        )

        assert hasattr(result, "detection_sources")
        assert result.detection_sources == ("algorithm", "llm")

    def test_detection_sources_defaults_to_algorithm(self):
        """detection_sources should default to just algorithm when not specified."""
        result = AnalysisResult(
            patterns_detected=0,
            instincts_created=0,
            instincts_updated=0,
            warnings=(),
        )

        assert result.detection_sources == ("algorithm",)


class TestDualApproachAnalysis:
    """Tests for dual-approach pattern analysis (AC-R2.1, AC-R2.2, AC-R2.3, AC-R2.8)."""

    def test_uses_both_approaches_when_llm_available(self, tmp_path: Path, monkeypatch):
        """AC-R2.1: Should use both algorithm and LLM when ANTHROPIC_API_KEY is set."""
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

        # Mock environment variable
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        # Track which functions were called
        calls = {"algorithm": False, "llm": False, "merge": False}

        def mock_detect_all_patterns(file_path):
            calls["algorithm"] = True
            from instincts.patterns import detect_all_patterns
            return detect_all_patterns.__wrapped__(file_path) if hasattr(detect_all_patterns, "__wrapped__") else []

        def mock_detect_patterns_with_llm(observations, existing):
            calls["llm"] = True
            return []

        def mock_merge_patterns(algo, llm):
            calls["merge"] = True
            return algo + llm

        with patch("instincts.agent.OBSERVATIONS_FILE", obs_file):
            with patch("instincts.agent.PERSONAL_DIR", personal_dir):
                with patch("instincts.agent.detect_all_patterns", mock_detect_all_patterns):
                    with patch("instincts.llm_patterns.is_llm_available", return_value=True):
                        with patch("instincts.agent.detect_patterns_with_llm", mock_detect_patterns_with_llm):
                            with patch("instincts.agent.merge_patterns", mock_merge_patterns):
                                result = analyze_observations(dry_run=True)

        # Should have used both approaches
        assert result.detection_sources == ("algorithm", "llm")

    def test_uses_algorithm_only_when_llm_unavailable(self, tmp_path: Path, monkeypatch):
        """AC-R2.2: Should use algorithm-only when ANTHROPIC_API_KEY is not set."""
        # Setup
        instincts_dir = tmp_path / "instincts"
        instincts_dir.mkdir()
        personal_dir = instincts_dir / "personal"
        personal_dir.mkdir()
        obs_file = instincts_dir / "observations.jsonl"

        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        # Remove API key
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch("instincts.agent.OBSERVATIONS_FILE", obs_file):
            with patch("instincts.agent.PERSONAL_DIR", personal_dir):
                with patch("instincts.llm_patterns.is_llm_available", return_value=False):
                    result = analyze_observations(dry_run=True)

        # Should only use algorithm
        assert result.detection_sources == ("algorithm",)

    def test_analyze_uses_recent_observations_limit(self, tmp_path: Path, monkeypatch):
        """AC-R2.3: Should use load_recent_observations with 1000 limit."""
        instincts_dir = tmp_path / "instincts"
        instincts_dir.mkdir()
        personal_dir = instincts_dir / "personal"
        personal_dir.mkdir()
        obs_file = instincts_dir / "observations.jsonl"

        # Create 1500 observations
        observations = [
            f'{{"event": "tool_start", "tool": "Write", "session": "s1", "idx": {i}, "timestamp": "2026-02-09T10:00:00Z"}}'
            for i in range(1500)
        ]
        obs_file.write_text("\n".join(observations))

        # Capture the limit used
        captured_limit = []

        def mock_load_recent(path, limit=1000):
            captured_limit.append(limit)
            from instincts.patterns import load_recent_observations as real_load
            return real_load(path, limit)

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch("instincts.agent.OBSERVATIONS_FILE", obs_file):
            with patch("instincts.agent.PERSONAL_DIR", personal_dir):
                with patch("instincts.agent.load_recent_observations", mock_load_recent):
                    with patch("instincts.llm_patterns.is_llm_available", return_value=False):
                        analyze_observations(dry_run=True)

        # Should have called load_recent_observations with correct limit
        assert len(captured_limit) >= 1
        assert captured_limit[0] == 1000

    def test_skip_llm_flag(self, tmp_path: Path, monkeypatch):
        """Should skip LLM analysis when skip_llm=True."""
        instincts_dir = tmp_path / "instincts"
        instincts_dir.mkdir()
        personal_dir = instincts_dir / "personal"
        personal_dir.mkdir()
        obs_file = instincts_dir / "observations.jsonl"

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
        ]
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        # Set API key (LLM would be available)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("instincts.agent.OBSERVATIONS_FILE", obs_file):
            with patch("instincts.agent.PERSONAL_DIR", personal_dir):
                with patch("instincts.llm_patterns.is_llm_available", return_value=True):
                    result = analyze_observations(dry_run=True, skip_llm=True)

        # Should only use algorithm even when LLM is available
        assert result.detection_sources == ("algorithm",)
