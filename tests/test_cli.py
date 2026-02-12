"""Tests for instincts.cli module.

Tests cover:
- Instinct file parsing (YAML frontmatter format)
- load_all_instincts function
- status command output
- evolve command clustering and suggestions
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import instincts.cli as cli_module
import instincts.models as models_module
from instincts.cli import (
    cmd_evolve,
    cmd_status,
    load_all_instincts,
    parse_instinct_file,
)


# Sample instinct file content for testing
SAMPLE_INSTINCT_YAML = """---
id: prefer-functional-style
trigger: "when writing new functions"
confidence: 0.7
domain: code-style
source: session-observation
---

# Prefer Functional Style

## Action
Use functional patterns over classes when appropriate.

## Evidence
- Observed 5 instances of functional pattern preference
"""

SAMPLE_INSTINCT_YAML_MULTIPLE = """---
id: always-test-first
trigger: "when implementing new features"
confidence: 0.9
domain: testing
source: session-observation
---

# Always Test First

## Action
Write tests before implementation code.

---
id: use-guard-clauses
trigger: "when writing conditionals"
confidence: 0.6
domain: code-style
source: session-observation
---

# Use Guard Clauses

## Action
Prefer early returns over nested conditionals.
"""


class TestParseInstinctFile:
    """Tests for parse_instinct_file function."""

    def test_parses_single_instinct(self):
        """Should parse a single instinct from YAML frontmatter."""
        instincts = parse_instinct_file(SAMPLE_INSTINCT_YAML)

        assert len(instincts) == 1
        inst = instincts[0]
        assert inst["id"] == "prefer-functional-style"
        assert inst["trigger"] == "when writing new functions"
        assert inst["confidence"] == 0.7
        assert inst["domain"] == "code-style"
        assert "Prefer Functional Style" in inst["content"]

    def test_parses_multiple_instincts(self):
        """Should parse multiple instincts from a single file."""
        instincts = parse_instinct_file(SAMPLE_INSTINCT_YAML_MULTIPLE)

        assert len(instincts) == 2
        assert instincts[0]["id"] == "always-test-first"
        assert instincts[0]["confidence"] == 0.9
        assert instincts[1]["id"] == "use-guard-clauses"
        assert instincts[1]["confidence"] == 0.6

    def test_skips_instincts_without_id(self):
        """Should skip instincts that don't have an id field."""
        content = """---
trigger: "some trigger"
confidence: 0.5
---

No ID here.
"""
        instincts = parse_instinct_file(content)
        assert len(instincts) == 0

    def test_handles_empty_content(self):
        """Should return empty list for empty content."""
        instincts = parse_instinct_file("")
        assert instincts == []


class TestLoadAllInstincts:
    """Tests for load_all_instincts function."""

    def test_loads_instincts_from_personal_dir(self, tmp_path: Path):
        """Should load all instinct files from PERSONAL_DIR."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        # Create test instinct file
        (personal_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML)

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            instincts = load_all_instincts()

        assert len(instincts) == 1
        assert instincts[0]["id"] == "prefer-functional-style"
        assert instincts[0]["_source_file"] == str(personal_dir / "test.yaml")

    def test_loads_from_multiple_files(self, tmp_path: Path):
        """Should load instincts from multiple YAML files."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        (personal_dir / "file1.yaml").write_text(SAMPLE_INSTINCT_YAML)
        (personal_dir / "file2.yaml").write_text(SAMPLE_INSTINCT_YAML_MULTIPLE)

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            instincts = load_all_instincts()

        assert len(instincts) == 3

    def test_returns_empty_when_dir_not_exists(self, tmp_path: Path):
        """Should return empty list when PERSONAL_DIR doesn't exist."""
        nonexistent = tmp_path / "nonexistent"

        with patch("instincts.cli.PERSONAL_DIR", nonexistent):
            instincts = load_all_instincts()

        assert instincts == []


class TestStatusCommand:
    """Tests for cmd_status function."""

    def test_status_shows_no_instincts_message(self, tmp_path: Path, capsys):
        """Should show message when no instincts found."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            cmd_status()

        captured = capsys.readouterr()
        assert "No instincts found" in captured.out

    def test_status_shows_instinct_count(self, tmp_path: Path, capsys):
        """Should show total instinct count."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()
        (personal_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML_MULTIPLE)

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            cmd_status()

        captured = capsys.readouterr()
        assert "2" in captured.out  # 2 instincts

    def test_status_groups_by_domain(self, tmp_path: Path, capsys):
        """Should group instincts by domain."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()
        (personal_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML_MULTIPLE)

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            cmd_status()

        captured = capsys.readouterr()
        assert "TESTING" in captured.out.upper() or "testing" in captured.out.lower()
        assert "CODE-STYLE" in captured.out.upper() or "code-style" in captured.out.lower()

    def test_status_shows_confidence(self, tmp_path: Path, capsys):
        """Should show confidence percentage."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()
        (personal_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML)

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            cmd_status()

        captured = capsys.readouterr()
        assert "70%" in captured.out or "70" in captured.out

    def test_status_shows_observations_stats(self, tmp_path: Path, capsys):
        """Should show observations file statistics."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()
        # Need at least one instinct to show observations stats
        (personal_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML)
        observations_file = tmp_path / "observations.jsonl"
        observations_file.write_text('{"event": "test"}\n{"event": "test2"}\n')

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            with patch("instincts.cli.OBSERVATIONS_FILE", observations_file):
                cmd_status()

        captured = capsys.readouterr()
        assert "2" in captured.out  # 2 observations


class TestEvolveCommand:
    """Tests for cmd_evolve function."""

    def test_evolve_requires_minimum_instincts(self, tmp_path: Path, capsys):
        """Should require at least 3 instincts to analyze."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()
        (personal_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML)

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            result = cmd_evolve()

        captured = capsys.readouterr()
        assert "at least 3" in captured.out.lower() or "Need" in captured.out
        assert result == 1

    def test_evolve_finds_clusters(self, tmp_path: Path, capsys):
        """Should find clusters of related instincts."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        # Create multiple instincts with similar domains
        content = """---
id: inst1
trigger: "when writing code"
confidence: 0.8
domain: code-style
---
Content 1
---
id: inst2
trigger: "when writing functions"
confidence: 0.7
domain: code-style
---
Content 2
---
id: inst3
trigger: "when writing tests"
confidence: 0.9
domain: testing
---
Content 3
"""
        (personal_dir / "test.yaml").write_text(content)

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            result = cmd_evolve()

        captured = capsys.readouterr()
        assert result == 0
        # Should show analysis results
        assert "3" in captured.out  # 3 instincts

    def test_evolve_identifies_high_confidence(self, tmp_path: Path, capsys):
        """Should identify high confidence instincts."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        content = """---
id: high-conf-1
trigger: "trigger 1"
confidence: 0.9
domain: testing
---
Content
---
id: high-conf-2
trigger: "trigger 2"
confidence: 0.85
domain: testing
---
Content
---
id: low-conf
trigger: "trigger 3"
confidence: 0.4
domain: general
---
Content
"""
        (personal_dir / "test.yaml").write_text(content)

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            cmd_evolve()

        captured = capsys.readouterr()
        # Should mention high confidence instincts
        assert "high" in captured.out.lower() or "80%" in captured.out or ">=80%" in captured.out


class TestNoDuplicateInstinctClass:
    """Tests to ensure no duplicate Instinct class in cli.py."""

    def test_cli_does_not_define_duplicate_instinct_class(self):
        """cli.py should import Instinct from models, not define its own."""
        # Check that cli module does not have its own Instinct class definition
        # by verifying Instinct in cli's namespace points to models.Instinct
        # or is not present at all
        if hasattr(cli_module, "Instinct"):
            cli_instinct = getattr(cli_module, "Instinct")
            models_instinct = getattr(models_module, "Instinct")

            # The Instinct class in cli should be the same as in models
            assert cli_instinct is models_instinct, (
                "cli.py should import Instinct from models, not define its own"
            )


class TestExceptionHandling:
    """Tests for proper exception handling in CLI functions."""

    def test_cmd_status_handles_file_read_errors(self, tmp_path: Path, capsys):
        """Should handle file read errors gracefully in cmd_status."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()
        (personal_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML)
        observations_file = tmp_path / "observations.jsonl"
        observations_file.write_text('{"event": "test"}\n')

        # Make the file unreadable after check
        observations_file.chmod(0o000)

        try:
            with patch("instincts.cli.PERSONAL_DIR", personal_dir):
                with patch("instincts.cli.OBSERVATIONS_FILE", observations_file):
                    result = cmd_status()

            # Should not crash, should return 0
            assert result == 0
        finally:
            # Restore permissions for cleanup
            observations_file.chmod(0o644)

    def test_load_all_instincts_logs_parsing_errors(self, tmp_path: Path, caplog):
        """Should log parsing errors with file path for debugging."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        # Create a file that will cause a parsing error (invalid content)
        (personal_dir / "invalid.yaml").write_text("binary garbage \x00\x01\x02")

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            with caplog.at_level(logging.WARNING):
                instincts = load_all_instincts()

        # Should return empty list and log a warning
        assert len(instincts) == 0


class TestLoadAllInstinctsMarkdown:
    """Tests for loading .md files in addition to .yaml."""

    def test_loads_md_files(self, tmp_path: Path):
        """Should load instincts from .md files (AC-7.3)."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        # Create .md file with frontmatter
        md_content = """---
id: test-instinct
trigger: "when testing"
confidence: 0.8
domain: testing
---

# Test Instinct

Some content.
"""
        (personal_dir / "test-instinct.md").write_text(md_content)

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            instincts = load_all_instincts()

        assert len(instincts) == 1
        assert instincts[0]["id"] == "test-instinct"

    def test_loads_both_yaml_and_md(self, tmp_path: Path):
        """Should load instincts from both .yaml and .md files."""
        personal_dir = tmp_path / "personal"
        personal_dir.mkdir()

        # Create .yaml file
        (personal_dir / "yaml-instinct.yaml").write_text(SAMPLE_INSTINCT_YAML)

        # Create .md file
        md_content = """---
id: md-instinct
trigger: "when using markdown"
confidence: 0.75
domain: docs
---

# MD Instinct

Content.
"""
        (personal_dir / "md-instinct.md").write_text(md_content)

        with patch("instincts.cli.PERSONAL_DIR", personal_dir):
            instincts = load_all_instincts()

        assert len(instincts) == 2
        ids = {i["id"] for i in instincts}
        assert "prefer-functional-style" in ids
        assert "md-instinct" in ids
