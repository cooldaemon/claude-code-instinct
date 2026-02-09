"""Tests for instincts.observer module.

Tests cover:
- observe_pre: PreToolUse hook processing
- observe_post: PostToolUse hook processing
- Observation file writing (JSONL format)
- File archiving when size exceeds threshold
- Input truncation for large inputs/outputs
"""

import json
from pathlib import Path
from unittest.mock import patch


class TestObservePre:
    """Tests for observe_pre function."""

    def test_observe_pre_writes_tool_start_event(self, tmp_path: Path):
        """observe_pre should write a tool_start event to observations file."""
        from instincts.observer import observe_pre

        observations_file = tmp_path / "observations.jsonl"
        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.py"},
            "session_id": "session-123",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_pre(hook_data)

        assert observations_file.exists()
        lines = observations_file.read_text().strip().split("\n")
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert event["event"] == "tool_start"
        assert event["tool"] == "Read"
        assert event["session"] == "session-123"
        assert "input" in event
        assert "timestamp" in event

    def test_observe_pre_handles_empty_input(self, tmp_path: Path):
        """observe_pre should handle hook_data with empty tool_input."""
        from instincts.observer import observe_pre

        observations_file = tmp_path / "observations.jsonl"
        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {},
            "session_id": "session-456",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_pre(hook_data)

        event = json.loads(observations_file.read_text().strip())
        assert event["tool"] == "Bash"

    def test_observe_pre_truncates_large_input(self, tmp_path: Path):
        """observe_pre should truncate tool_input larger than 5000 chars."""
        from instincts.observer import observe_pre

        observations_file = tmp_path / "observations.jsonl"
        large_content = "x" * 10000
        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"content": large_content},
            "session_id": "session-789",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_pre(hook_data)

        event = json.loads(observations_file.read_text().strip())
        assert len(event["input"]) <= 5000


class TestObservePost:
    """Tests for observe_post function."""

    def test_observe_post_writes_tool_complete_event(self, tmp_path: Path):
        """observe_post should write a tool_complete event to observations file."""
        from instincts.observer import observe_post

        observations_file = tmp_path / "observations.jsonl"
        hook_data = {
            "hook_type": "PostToolUse",
            "tool_name": "Bash",
            "tool_output": "Hello, World!",
            "session_id": "session-123",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_post(hook_data)

        assert observations_file.exists()
        event = json.loads(observations_file.read_text().strip())
        assert event["event"] == "tool_complete"
        assert event["tool"] == "Bash"
        assert event["session"] == "session-123"
        assert "output" in event
        assert "timestamp" in event

    def test_observe_post_truncates_large_output(self, tmp_path: Path):
        """observe_post should truncate tool_output larger than 5000 chars."""
        from instincts.observer import observe_post

        observations_file = tmp_path / "observations.jsonl"
        large_output = "y" * 10000
        hook_data = {
            "hook_type": "PostToolUse",
            "tool_name": "Read",
            "tool_output": large_output,
            "session_id": "session-456",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_post(hook_data)

        event = json.loads(observations_file.read_text().strip())
        assert len(event["output"]) <= 5000


class TestObservationFileManagement:
    """Tests for observation file management."""

    def test_creates_instincts_dir_if_not_exists(self, tmp_path: Path):
        """observe_pre should create INSTINCTS_DIR if it doesn't exist."""
        from instincts.observer import observe_pre

        instincts_dir = tmp_path / "new_dir"
        observations_file = instincts_dir / "observations.jsonl"

        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Test",
            "tool_input": {},
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", instincts_dir):
                observe_pre(hook_data)

        assert instincts_dir.exists()
        assert observations_file.exists()

    def test_appends_to_existing_file(self, tmp_path: Path):
        """Multiple observations should append to the same file."""
        from instincts.observer import observe_pre

        observations_file = tmp_path / "observations.jsonl"

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_pre({
                    "hook_type": "PreToolUse",
                    "tool_name": "Tool1",
                    "tool_input": {},
                    "session_id": "s1",
                })
                observe_pre({
                    "hook_type": "PreToolUse",
                    "tool_name": "Tool2",
                    "tool_input": {},
                    "session_id": "s1",
                })

        lines = observations_file.read_text().strip().split("\n")
        assert len(lines) == 2


class TestFileArchiving:
    """Tests for file archiving when size exceeds threshold."""

    def test_archives_file_when_exceeds_max_size(self, tmp_path: Path):
        """Should archive observations file when it exceeds MAX_FILE_SIZE_MB."""
        from instincts.observer import observe_pre

        observations_file = tmp_path / "observations.jsonl"
        archive_dir = tmp_path / "observations.archive"

        # Create a file larger than 1MB (use small threshold for testing)
        observations_file.write_text("x" * (1024 * 1024 + 1))  # 1MB + 1 byte

        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Test",
            "tool_input": {},
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                with patch("instincts.observer.ARCHIVE_DIR", archive_dir):
                    with patch("instincts.observer.MAX_FILE_SIZE_MB", 1):
                        observe_pre(hook_data)

        # Archive directory should be created
        assert archive_dir.exists()
        # Old file should be moved to archive
        archived_files = list(archive_dir.glob("observations-*.jsonl"))
        assert len(archived_files) == 1
        # New observation should be in fresh file
        assert observations_file.exists()
        new_content = observations_file.read_text()
        assert "Test" in new_content


class TestAlternativeFieldNames:
    """Tests for handling alternative field names in hook_data."""

    def test_handles_tool_field_instead_of_tool_name(self, tmp_path: Path):
        """Should handle 'tool' field as alternative to 'tool_name'."""
        from instincts.observer import observe_pre

        observations_file = tmp_path / "observations.jsonl"
        hook_data = {
            "hook_type": "PreToolUse",
            "tool": "Read",  # Alternative field name
            "input": {"path": "/tmp"},  # Alternative field name
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_pre(hook_data)

        event = json.loads(observations_file.read_text().strip())
        assert event["tool"] == "Read"

    def test_handles_output_field_instead_of_tool_output(self, tmp_path: Path):
        """Should handle 'output' field as alternative to 'tool_output'."""
        from instincts.observer import observe_post

        observations_file = tmp_path / "observations.jsonl"
        hook_data = {
            "hook_type": "PostToolUse",
            "tool": "Bash",
            "output": "result",  # Alternative field name
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_post(hook_data)

        event = json.loads(observations_file.read_text().strip())
        assert event["output"] == "result"
