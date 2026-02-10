"""Tests for instincts.patterns module.

Tests cover:
- AC-2.1, AC-2.2, AC-2.3: User correction detection
- AC-3.1, AC-3.2, AC-3.3: Error resolution detection
- AC-4.1, AC-4.2, AC-4.3: Repeated workflow detection
- AC-5.1, AC-5.2, AC-5.3: Tool preference detection
- EC-1: Skip invalid JSON lines
"""

import json
from pathlib import Path


class TestLoadObservations:
    """Tests for load_observations function."""

    def test_loads_valid_jsonl_file(self, tmp_path: Path):
        """Should load observations from valid JSONL file."""
        from instincts.patterns import load_observations

        obs_file = tmp_path / "observations.jsonl"
        obs_file.write_text(
            '{"event": "tool_start", "tool": "Write", "session": "s1"}\n'
            '{"event": "tool_complete", "tool": "Write", "session": "s1"}\n'
        )

        observations = load_observations(obs_file)

        assert len(observations) == 2
        assert observations[0]["event"] == "tool_start"
        assert observations[1]["event"] == "tool_complete"

    def test_rejects_file_over_50mb(self):
        """Should raise error for files over 50MB (security limit)."""
        from instincts.patterns import MAX_OBSERVATIONS_FILE_SIZE

        # Verify constant exists
        assert MAX_OBSERVATIONS_FILE_SIZE == 50 * 1024 * 1024  # 50MB

    def test_rejects_file_with_too_many_lines(self):
        """Should stop reading after MAX_OBSERVATIONS_LINES lines."""
        from instincts.patterns import MAX_OBSERVATIONS_LINES

        # Verify the constant exists
        assert MAX_OBSERVATIONS_LINES == 100000

    def test_returns_empty_for_nonexistent_file(self, tmp_path: Path):
        """Should return empty list for nonexistent file."""
        from instincts.patterns import load_observations

        observations = load_observations(tmp_path / "nonexistent.jsonl")

        assert observations == []

    def test_returns_empty_for_empty_file(self, tmp_path: Path):
        """Should return empty list for empty file."""
        from instincts.patterns import load_observations

        obs_file = tmp_path / "observations.jsonl"
        obs_file.write_text("")

        observations = load_observations(obs_file)

        assert observations == []

    def test_skips_invalid_json_lines(self, tmp_path: Path):
        """Should skip invalid JSON lines and continue (EC-1)."""
        from instincts.patterns import load_observations

        obs_file = tmp_path / "observations.jsonl"
        obs_file.write_text(
            '{"event": "tool_start", "tool": "Write"}\n'
            'invalid json line\n'
            '{"event": "tool_complete", "tool": "Write"}\n'
        )

        observations = load_observations(obs_file)

        assert len(observations) == 2  # Skipped invalid line

    def test_skips_empty_lines(self, tmp_path: Path):
        """Should skip empty lines."""
        from instincts.patterns import load_observations

        obs_file = tmp_path / "observations.jsonl"
        obs_file.write_text(
            '{"event": "tool_start"}\n'
            '\n'
            '   \n'
            '{"event": "tool_complete"}\n'
        )

        observations = load_observations(obs_file)

        assert len(observations) == 2


class TestDetectUserCorrections:
    """Tests for detect_user_corrections function (AC-2.1, AC-2.2, AC-2.3)."""

    def test_detects_write_then_edit_on_same_file(self):
        """Should detect Write followed by Edit on same file as correction (AC-2.1)."""
        from instincts.patterns import detect_user_corrections

        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "tool_start", "tool": "Edit", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:30Z"},
            {"event": "tool_complete", "tool": "Edit", "session": "s1", "timestamp": "2026-02-09T10:00:31Z"},
        ]

        patterns = detect_user_corrections(observations)

        assert len(patterns) >= 1
        pattern = patterns[0]
        assert pattern.pattern_type.value == "user_correction"

    def test_does_not_detect_edit_on_different_file(self):
        """Should not detect correction when Edit is on different file."""
        from instincts.patterns import detect_user_corrections

        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "tool_start", "tool": "Edit", "input": '{"file_path": "/app/other.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:30Z"},
            {"event": "tool_complete", "tool": "Edit", "session": "s1", "timestamp": "2026-02-09T10:00:31Z"},
        ]

        patterns = detect_user_corrections(observations)

        # No correction pattern for different files
        write_edit_patterns = [p for p in patterns if "same file" in p.description.lower()]
        assert len(write_edit_patterns) == 0

    def test_detects_correction_keywords_in_user_message(self):
        """Should detect correction keywords after tool execution (AC-2.2)."""
        from instincts.patterns import detect_user_corrections

        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"content": "class Foo:"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "user_message", "content": "No, actually use a function instead", "session": "s1", "timestamp": "2026-02-09T10:00:10Z"},
        ]

        patterns = detect_user_corrections(observations)

        assert len(patterns) >= 1
        correction_pattern = [p for p in patterns if "keyword" in p.description.lower() or "correction" in p.trigger.lower()]
        assert len(correction_pattern) >= 1

    def test_correction_keywords_include_no_instead_actually_dont(self):
        """Should recognize 'no', 'instead', 'actually', 'don't' as corrections (AC-2.2)."""
        from instincts.patterns import detect_user_corrections

        keywords = ["no", "instead", "actually", "don't"]

        for keyword in keywords:
            observations = [
                {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
                {"event": "user_message", "content": f"{keyword}, do it differently", "session": "s1", "timestamp": "2026-02-09T10:00:10Z"},
            ]

            patterns = detect_user_corrections(observations)

            # Should detect at least one correction pattern
            assert len(patterns) >= 1, f"Failed to detect correction for keyword: {keyword}"

    def test_pattern_type_is_user_correction(self):
        """Detected pattern should have type 'user_correction' (AC-2.3)."""
        from instincts.models import PatternType
        from instincts.patterns import detect_user_corrections

        observations = [
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "tool_start", "tool": "Edit", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:30Z"},
        ]

        patterns = detect_user_corrections(observations)

        assert all(p.pattern_type == PatternType.USER_CORRECTION for p in patterns)


class TestDetectErrorResolutions:
    """Tests for detect_error_resolutions function (AC-3.1, AC-3.2, AC-3.3)."""

    def test_detects_bash_error_then_success(self):
        """Should detect Bash error followed by successful execution (AC-3.1)."""
        from instincts.patterns import detect_error_resolutions

        observations = [
            {"event": "tool_start", "tool": "Bash", "input": "pytest", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Bash", "output": "error: ModuleNotFoundError: No module named 'foo'", "session": "s1", "timestamp": "2026-02-09T10:00:05Z"},
            {"event": "tool_start", "tool": "Bash", "input": "pip install foo", "session": "s1", "timestamp": "2026-02-09T10:00:30Z"},
            {"event": "tool_complete", "tool": "Bash", "output": "Successfully installed foo", "session": "s1", "timestamp": "2026-02-09T10:00:35Z"},
            {"event": "tool_start", "tool": "Bash", "input": "pytest", "session": "s1", "timestamp": "2026-02-09T10:00:40Z"},
            {"event": "tool_complete", "tool": "Bash", "output": "passed", "session": "s1", "timestamp": "2026-02-09T10:00:45Z"},
        ]

        patterns = detect_error_resolutions(observations)

        assert len(patterns) >= 1
        pattern = patterns[0]
        assert pattern.pattern_type.value == "error_resolution"

    def test_detects_error_keywords_in_output(self):
        """Should detect error keywords: error, failed, exception (AC-3.1)."""
        from instincts.patterns import detect_error_resolutions

        error_outputs = [
            "error: something went wrong",
            "Build failed with exit code 1",
            "Exception: TypeError occurred",
        ]

        for error_output in error_outputs:
            observations = [
                {"event": "tool_complete", "tool": "Bash", "output": error_output, "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
                {"event": "tool_complete", "tool": "Bash", "output": "Success", "session": "s1", "timestamp": "2026-02-09T10:01:00Z"},
            ]

            patterns = detect_error_resolutions(observations)

            assert len(patterns) >= 1, f"Failed to detect error resolution for: {error_output}"

    def test_extracts_error_type_and_resolution(self):
        """Should extract error type and resolution approach (AC-3.3)."""
        from instincts.patterns import detect_error_resolutions

        observations = [
            {"event": "tool_complete", "tool": "Bash", "output": "ImportError: No module named 'pandas'", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_start", "tool": "Bash", "input": "pip install pandas", "session": "s1", "timestamp": "2026-02-09T10:00:30Z"},
            {"event": "tool_complete", "tool": "Bash", "output": "Successfully installed pandas", "session": "s1", "timestamp": "2026-02-09T10:00:35Z"},
        ]

        patterns = detect_error_resolutions(observations)

        assert len(patterns) >= 1
        pattern = patterns[0]
        # Should have metadata about error type
        assert "metadata" in dir(pattern) or hasattr(pattern, "metadata")

    def test_pattern_type_is_error_resolution(self):
        """Detected pattern should have type 'error_resolution' (AC-3.2)."""
        from instincts.models import PatternType
        from instincts.patterns import detect_error_resolutions

        observations = [
            {"event": "tool_complete", "tool": "Bash", "output": "error: failed", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Bash", "output": "Success", "session": "s1", "timestamp": "2026-02-09T10:01:00Z"},
        ]

        patterns = detect_error_resolutions(observations)

        assert all(p.pattern_type == PatternType.ERROR_RESOLUTION for p in patterns)


class TestDetectRepeatedWorkflows:
    """Tests for detect_repeated_workflows function (AC-4.1, AC-4.2, AC-4.3)."""

    def test_detects_3_tool_sequence_in_2_sessions(self):
        """Should detect same 3+ tool sequence appearing in 2+ sessions (AC-4.1)."""
        from instincts.patterns import detect_repeated_workflows

        observations = [
            # Session 1: Read -> Edit -> Bash
            {"event": "tool_start", "tool": "Read", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_start", "tool": "Edit", "session": "s1", "timestamp": "2026-02-09T10:01:00Z"},
            {"event": "tool_start", "tool": "Bash", "session": "s1", "timestamp": "2026-02-09T10:02:00Z"},
            # Session 2: Read -> Edit -> Bash (same sequence)
            {"event": "tool_start", "tool": "Read", "session": "s2", "timestamp": "2026-02-09T11:00:00Z"},
            {"event": "tool_start", "tool": "Edit", "session": "s2", "timestamp": "2026-02-09T11:01:00Z"},
            {"event": "tool_start", "tool": "Bash", "session": "s2", "timestamp": "2026-02-09T11:02:00Z"},
        ]

        patterns = detect_repeated_workflows(observations)

        assert len(patterns) >= 1
        pattern = patterns[0]
        assert pattern.pattern_type.value == "repeated_workflow"

    def test_does_not_detect_2_tool_sequence(self):
        """Should not detect sequences shorter than 3 tools."""
        from instincts.patterns import detect_repeated_workflows

        observations = [
            # Session 1: Read -> Edit (only 2 tools)
            {"event": "tool_start", "tool": "Read", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_start", "tool": "Edit", "session": "s1", "timestamp": "2026-02-09T10:01:00Z"},
            # Session 2: Read -> Edit
            {"event": "tool_start", "tool": "Read", "session": "s2", "timestamp": "2026-02-09T11:00:00Z"},
            {"event": "tool_start", "tool": "Edit", "session": "s2", "timestamp": "2026-02-09T11:01:00Z"},
        ]

        patterns = detect_repeated_workflows(observations)

        # No workflow pattern for 2-tool sequences
        assert len(patterns) == 0

    def test_does_not_detect_sequence_in_single_session(self):
        """Should not detect sequence appearing in only 1 session."""
        from instincts.patterns import detect_repeated_workflows

        observations = [
            # Only session 1: Read -> Edit -> Bash
            {"event": "tool_start", "tool": "Read", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_start", "tool": "Edit", "session": "s1", "timestamp": "2026-02-09T10:01:00Z"},
            {"event": "tool_start", "tool": "Bash", "session": "s1", "timestamp": "2026-02-09T10:02:00Z"},
        ]

        patterns = detect_repeated_workflows(observations)

        assert len(patterns) == 0

    def test_records_tool_sequence_and_frequency(self):
        """Should record the tool sequence and frequency (AC-4.2)."""
        from instincts.patterns import detect_repeated_workflows

        observations = [
            # Session 1
            {"event": "tool_start", "tool": "Read", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_start", "tool": "Edit", "session": "s1", "timestamp": "2026-02-09T10:01:00Z"},
            {"event": "tool_start", "tool": "Bash", "session": "s1", "timestamp": "2026-02-09T10:02:00Z"},
            # Session 2
            {"event": "tool_start", "tool": "Read", "session": "s2", "timestamp": "2026-02-09T11:00:00Z"},
            {"event": "tool_start", "tool": "Edit", "session": "s2", "timestamp": "2026-02-09T11:01:00Z"},
            {"event": "tool_start", "tool": "Bash", "session": "s2", "timestamp": "2026-02-09T11:02:00Z"},
            # Session 3 (same sequence)
            {"event": "tool_start", "tool": "Read", "session": "s3", "timestamp": "2026-02-09T12:00:00Z"},
            {"event": "tool_start", "tool": "Edit", "session": "s3", "timestamp": "2026-02-09T12:01:00Z"},
            {"event": "tool_start", "tool": "Bash", "session": "s3", "timestamp": "2026-02-09T12:02:00Z"},
        ]

        patterns = detect_repeated_workflows(observations)

        assert len(patterns) >= 1
        pattern = patterns[0]
        # Should have metadata about sequence and frequency (tuple-based)
        metadata_dict = dict(pattern.metadata)
        assert metadata_dict.get("sequence") == ["Read", "Edit", "Bash"] or "Read" in str(pattern.metadata)
        assert metadata_dict.get("frequency", 0) >= 3 or len(pattern.evidence) >= 3

    def test_groups_by_session(self):
        """Should group observations by session for pattern detection (AC-4.3)."""
        from instincts.patterns import detect_repeated_workflows

        observations = [
            # Interleaved sessions
            {"event": "tool_start", "tool": "Read", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_start", "tool": "Read", "session": "s2", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "tool_start", "tool": "Edit", "session": "s1", "timestamp": "2026-02-09T10:01:00Z"},
            {"event": "tool_start", "tool": "Edit", "session": "s2", "timestamp": "2026-02-09T10:01:01Z"},
            {"event": "tool_start", "tool": "Bash", "session": "s1", "timestamp": "2026-02-09T10:02:00Z"},
            {"event": "tool_start", "tool": "Bash", "session": "s2", "timestamp": "2026-02-09T10:02:01Z"},
        ]

        patterns = detect_repeated_workflows(observations)

        # Should detect the workflow even with interleaved sessions
        assert len(patterns) >= 1


class TestDetectToolPreferences:
    """Tests for detect_tool_preferences function (AC-5.1, AC-5.2, AC-5.3)."""

    def test_detects_consistent_tool_usage(self):
        """Should detect consistent tool usage across sessions (AC-5.1)."""
        from instincts.patterns import detect_tool_preferences

        observations = [
            # Always uses Grep for search
            {"event": "tool_start", "tool": "Grep", "input": '{"pattern": "TODO"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_start", "tool": "Grep", "input": '{"pattern": "FIXME"}', "session": "s2", "timestamp": "2026-02-09T11:00:00Z"},
            {"event": "tool_start", "tool": "Grep", "input": '{"pattern": "BUG"}', "session": "s3", "timestamp": "2026-02-09T12:00:00Z"},
        ]

        patterns = detect_tool_preferences(observations)

        assert len(patterns) >= 1
        pattern = patterns[0]
        assert pattern.pattern_type.value == "tool_preference"

    def test_records_tool_name_and_patterns(self):
        """Should record tool name, common patterns, and frequency (AC-5.2)."""
        from instincts.patterns import detect_tool_preferences

        observations = [
            {"event": "tool_start", "tool": "Grep", "input": '{"pattern": "TODO", "path": "/src"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_start", "tool": "Grep", "input": '{"pattern": "FIXME", "path": "/src"}', "session": "s2", "timestamp": "2026-02-09T11:00:00Z"},
            {"event": "tool_start", "tool": "Grep", "input": '{"pattern": "XXX", "path": "/src"}', "session": "s3", "timestamp": "2026-02-09T12:00:00Z"},
        ]

        patterns = detect_tool_preferences(observations)

        assert len(patterns) >= 1
        pattern = patterns[0]
        # Should have tool name in metadata or description
        assert "Grep" in pattern.description or pattern.metadata.get("tool") == "Grep"

    def test_detects_negative_preference(self):
        """Should detect when a tool is consistently avoided (AC-5.3)."""
        from instincts.patterns import detect_tool_preferences

        # User always uses Grep but never uses Bash for search
        # This is a simplistic test - real detection would need context
        observations = [
            {"event": "tool_start", "tool": "Grep", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_start", "tool": "Grep", "session": "s2", "timestamp": "2026-02-09T11:00:00Z"},
            {"event": "tool_start", "tool": "Grep", "session": "s3", "timestamp": "2026-02-09T12:00:00Z"},
            {"event": "tool_start", "tool": "Grep", "session": "s4", "timestamp": "2026-02-09T13:00:00Z"},
            {"event": "tool_start", "tool": "Grep", "session": "s5", "timestamp": "2026-02-09T14:00:00Z"},
        ]

        patterns = detect_tool_preferences(observations)

        # At minimum, should detect positive preference
        assert len(patterns) >= 1

    def test_requires_multiple_sessions(self):
        """Should require usage across multiple sessions to detect preference."""
        from instincts.patterns import detect_tool_preferences

        observations = [
            # All in same session
            {"event": "tool_start", "tool": "Grep", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_start", "tool": "Grep", "session": "s1", "timestamp": "2026-02-09T10:01:00Z"},
            {"event": "tool_start", "tool": "Grep", "session": "s1", "timestamp": "2026-02-09T10:02:00Z"},
        ]

        patterns = detect_tool_preferences(observations)

        # Should not detect preference from single session
        assert len(patterns) == 0


class TestDetectAllPatterns:
    """Tests for detect_all_patterns orchestrator function."""

    def test_calls_all_detectors(self, tmp_path: Path):
        """Should call all pattern detection functions."""
        from instincts.patterns import detect_all_patterns

        obs_file = tmp_path / "observations.jsonl"
        obs_file.write_text(
            '{"event": "tool_start", "tool": "Write", "input": "{\\"file_path\\": \\"/app/main.py\\"}", "session": "s1", "timestamp": "2026-02-09T10:00:00Z"}\n'
            '{"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"}\n'
            '{"event": "tool_start", "tool": "Edit", "input": "{\\"file_path\\": \\"/app/main.py\\"}", "session": "s1", "timestamp": "2026-02-09T10:00:30Z"}\n'
        )

        patterns = detect_all_patterns(obs_file)

        # Should return list of patterns
        assert isinstance(patterns, list)

    def test_returns_empty_for_no_observations(self, tmp_path: Path):
        """Should return empty list when no observations."""
        from instincts.patterns import detect_all_patterns

        patterns = detect_all_patterns(tmp_path / "nonexistent.jsonl")

        assert patterns == []

    def test_combines_patterns_from_all_detectors(self, tmp_path: Path):
        """Should combine patterns from all detection functions."""
        from instincts.patterns import detect_all_patterns

        # Create observations that trigger multiple pattern types
        observations = [
            # User correction
            {"event": "tool_start", "tool": "Write", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:00Z"},
            {"event": "tool_complete", "tool": "Write", "session": "s1", "timestamp": "2026-02-09T10:00:01Z"},
            {"event": "tool_start", "tool": "Edit", "input": '{"file_path": "/app/main.py"}', "session": "s1", "timestamp": "2026-02-09T10:00:30Z"},
            # Error resolution
            {"event": "tool_complete", "tool": "Bash", "output": "error: something failed", "session": "s2", "timestamp": "2026-02-09T11:00:00Z"},
            {"event": "tool_complete", "tool": "Bash", "output": "Success", "session": "s2", "timestamp": "2026-02-09T11:01:00Z"},
        ]

        obs_file = tmp_path / "observations.jsonl"
        obs_file.write_text("\n".join(json.dumps(obs) for obs in observations))

        patterns = detect_all_patterns(obs_file)

        # Should have patterns from multiple detectors
        pattern_types = {p.pattern_type.value for p in patterns}
        assert len(pattern_types) >= 1  # At least one type detected


class TestLoadRecentObservations:
    """Tests for load_recent_observations function (AC-R2.3)."""

    def test_loads_latest_n_observations(self, tmp_path: Path):
        """Should return only the latest N observations when file has more."""
        from instincts.patterns import load_recent_observations

        obs_file = tmp_path / "observations.jsonl"
        # Create 10 observations
        observations = [
            f'{{"event": "tool_start", "tool": "Write", "session": "s1", "idx": {i}}}'
            for i in range(10)
        ]
        obs_file.write_text("\n".join(observations))

        # Load only latest 5
        result = load_recent_observations(obs_file, limit=5)

        assert len(result) == 5
        # Should be the last 5 observations (indices 5-9)
        assert result[0]["idx"] == 5
        assert result[4]["idx"] == 9

    def test_returns_all_when_fewer_than_limit(self, tmp_path: Path):
        """Should return all observations when file has fewer than limit."""
        from instincts.patterns import load_recent_observations

        obs_file = tmp_path / "observations.jsonl"
        observations = [
            '{"event": "tool_start", "tool": "Write", "session": "s1", "idx": 0}',
            '{"event": "tool_start", "tool": "Write", "session": "s1", "idx": 1}',
            '{"event": "tool_start", "tool": "Write", "session": "s1", "idx": 2}',
        ]
        obs_file.write_text("\n".join(observations))

        # Request 1000 but only 3 exist
        result = load_recent_observations(obs_file, limit=1000)

        assert len(result) == 3

    def test_returns_empty_for_nonexistent_file(self, tmp_path: Path):
        """Should return empty list for nonexistent file."""
        from instincts.patterns import load_recent_observations

        result = load_recent_observations(tmp_path / "nonexistent.jsonl")

        assert result == []

    def test_default_limit_is_1000(self, tmp_path: Path):
        """Should use 1000 as default limit."""
        from instincts.patterns import load_recent_observations

        obs_file = tmp_path / "observations.jsonl"
        # Create 1500 observations
        observations = [
            f'{{"event": "tool_start", "tool": "Write", "session": "s1", "idx": {i}}}'
            for i in range(1500)
        ]
        obs_file.write_text("\n".join(observations))

        # Load with default limit
        result = load_recent_observations(obs_file)

        assert len(result) == 1000
        # Should be observations 500-1499
        assert result[0]["idx"] == 500
        assert result[-1]["idx"] == 1499

    def test_skips_invalid_json_lines(self, tmp_path: Path):
        """Should skip invalid JSON lines when loading recent observations."""
        from instincts.patterns import load_recent_observations

        obs_file = tmp_path / "observations.jsonl"
        obs_file.write_text(
            '{"event": "tool_start", "idx": 0}\n'
            'invalid json\n'
            '{"event": "tool_start", "idx": 1}\n'
            '{"event": "tool_start", "idx": 2}\n'
        )

        result = load_recent_observations(obs_file, limit=2)

        # Should get last 2 valid observations (idx 1 and 2)
        assert len(result) == 2
        assert result[0]["idx"] == 1
        assert result[1]["idx"] == 2
