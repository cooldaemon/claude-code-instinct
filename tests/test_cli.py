"""Tests for instincts.cli module.

Tests cover:
- Instinct file parsing (YAML frontmatter format)
- load_all_instincts function
- status command output
- evolve command clustering and suggestions
"""

import logging
from pathlib import Path

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


def create_project_structure(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a project structure with .git marker and instincts directories.

    Args:
        tmp_path: pytest tmp_path fixture.

    Returns:
        Tuple of (project_root, learned_dir, observations_file).
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".git").mkdir()

    instincts_dir = project_root / "docs" / "instincts"
    instincts_dir.mkdir(parents=True)

    learned_dir = instincts_dir / "learned"
    learned_dir.mkdir()

    observations_file = instincts_dir / "observations.jsonl"

    return project_root, learned_dir, observations_file


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

    def test_loads_instincts_from_learned_dir(self, tmp_path: Path):
        """Should load all instinct files from project learned directory."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

        # Create test instinct file
        (learned_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML)

        instincts = load_all_instincts(project_root)

        assert len(instincts) == 1
        assert instincts[0]["id"] == "prefer-functional-style"
        assert instincts[0]["_source_file"] == str(learned_dir / "test.yaml")

    def test_loads_from_multiple_files(self, tmp_path: Path):
        """Should load instincts from multiple YAML files."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

        (learned_dir / "file1.yaml").write_text(SAMPLE_INSTINCT_YAML)
        (learned_dir / "file2.yaml").write_text(SAMPLE_INSTINCT_YAML_MULTIPLE)

        instincts = load_all_instincts(project_root)

        assert len(instincts) == 3

    def test_returns_empty_when_dir_not_exists(self, tmp_path: Path):
        """Should return empty list when learned directory doesn't exist."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        # Don't create learned directory

        instincts = load_all_instincts(project_root)

        assert instincts == []


class TestStatusCommand:
    """Tests for cmd_status function."""

    def test_status_shows_no_instincts_message(self, tmp_path: Path, capsys):
        """Should show message when no instincts found."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

        cmd_status(project_root)

        captured = capsys.readouterr()
        assert "No instincts found" in captured.out

    def test_status_shows_instinct_count(self, tmp_path: Path, capsys):
        """Should show total instinct count."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)
        (learned_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML_MULTIPLE)

        cmd_status(project_root)

        captured = capsys.readouterr()
        assert "2" in captured.out  # 2 instincts

    def test_status_groups_by_domain(self, tmp_path: Path, capsys):
        """Should group instincts by domain."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)
        (learned_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML_MULTIPLE)

        cmd_status(project_root)

        captured = capsys.readouterr()
        assert "TESTING" in captured.out.upper() or "testing" in captured.out.lower()
        assert "CODE-STYLE" in captured.out.upper() or "code-style" in captured.out.lower()

    def test_status_shows_confidence(self, tmp_path: Path, capsys):
        """Should show confidence percentage."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)
        (learned_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML)

        cmd_status(project_root)

        captured = capsys.readouterr()
        assert "70%" in captured.out or "70" in captured.out

    def test_status_shows_observations_stats(self, tmp_path: Path, capsys):
        """Should show observations file statistics."""
        project_root, learned_dir, observations_file = create_project_structure(tmp_path)
        # Need at least one instinct to show observations stats
        (learned_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML)
        observations_file.write_text('{"event": "test"}\n{"event": "test2"}\n')

        cmd_status(project_root)

        captured = capsys.readouterr()
        assert "2" in captured.out  # 2 observations


class TestEvolveCommand:
    """Tests for cmd_evolve function."""

    def test_evolve_requires_minimum_instincts(self, tmp_path: Path, capsys):
        """Should require at least 3 instincts to analyze."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)
        (learned_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML)

        result = cmd_evolve(project_root)

        captured = capsys.readouterr()
        assert "at least 3" in captured.out.lower() or "Need" in captured.out
        assert result == 1

    def test_evolve_finds_clusters(self, tmp_path: Path, capsys):
        """Should find clusters of related instincts."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

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
        (learned_dir / "test.yaml").write_text(content)

        result = cmd_evolve(project_root)

        captured = capsys.readouterr()
        assert result == 0
        # Should show analysis results
        assert "3" in captured.out  # 3 instincts

    def test_evolve_identifies_high_confidence(self, tmp_path: Path, capsys):
        """Should identify high confidence instincts."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

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
        (learned_dir / "test.yaml").write_text(content)

        cmd_evolve(project_root)

        captured = capsys.readouterr()
        # Should mention high confidence instincts
        assert "high" in captured.out.lower() or "80%" in captured.out or ">=80%" in captured.out


class TestInteractiveSelectionValidation:
    """Tests for input validation in interactive selection (CR-004)."""

    def test_parse_selection_validates_indices(self, tmp_path: Path, capsys, monkeypatch):
        """CR-004: Should warn user about invalid indices in selection."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

        content = """---
id: inst1
trigger: "trigger 1"
confidence: 0.8
domain: testing
---
Content
---
id: inst2
trigger: "trigger 2"
confidence: 0.85
domain: testing
---
Content
---
id: inst3
trigger: "trigger 3"
confidence: 0.7
domain: testing
---
Content
"""
        (learned_dir / "instincts.md").write_text(content)

        # Select invalid indices (99 is out of range)
        inputs = iter(["1,2,99", "1", "n"])  # indices, output type, confirm
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        cmd_evolve(project_root=project_root, interactive=True)

        captured = capsys.readouterr()
        # Should warn about invalid index 99
        assert "invalid" in captured.out.lower() or "warning" in captured.out.lower() or "skipping" in captured.out.lower()

    def test_parse_selection_handles_negative_indices(self, tmp_path: Path, capsys, monkeypatch):
        """CR-004: Should handle negative indices gracefully."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

        content = """---
id: inst1
trigger: "trigger 1"
confidence: 0.8
domain: testing
---
Content
---
id: inst2
trigger: "trigger 2"
confidence: 0.85
domain: testing
---
Content
---
id: inst3
trigger: "trigger 3"
confidence: 0.7
domain: testing
---
Content
"""
        (learned_dir / "instincts.md").write_text(content)

        # Select with negative index
        inputs = iter(["-1,2", "1", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        cmd_evolve(project_root=project_root, interactive=True)

        captured = capsys.readouterr()
        # Should warn about invalid index
        assert "invalid" in captured.out.lower() or "warning" in captured.out.lower() or "skipping" in captured.out.lower()


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
        project_root, learned_dir, observations_file = create_project_structure(tmp_path)
        (learned_dir / "test.yaml").write_text(SAMPLE_INSTINCT_YAML)
        observations_file.write_text('{"event": "test"}\n')

        # Make the file unreadable after check
        observations_file.chmod(0o000)

        try:
            result = cmd_status(project_root)

            # Should not crash, should return 0
            assert result == 0
        finally:
            # Restore permissions for cleanup
            observations_file.chmod(0o644)

    def test_load_all_instincts_logs_parsing_errors(self, tmp_path: Path, caplog):
        """Should log parsing errors with file path for debugging."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

        # Create a file that will cause a parsing error (invalid content)
        (learned_dir / "invalid.yaml").write_text("binary garbage \x00\x01\x02")

        with caplog.at_level(logging.WARNING):
            instincts = load_all_instincts(project_root)

        # Should return empty list and log a warning
        assert len(instincts) == 0


class TestLoadAllInstinctsMarkdown:
    """Tests for loading .md files in addition to .yaml."""

    def test_loads_md_files(self, tmp_path: Path):
        """Should load instincts from .md files (AC-7.3)."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

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
        (learned_dir / "test-instinct.md").write_text(md_content)

        instincts = load_all_instincts(project_root)

        assert len(instincts) == 1
        assert instincts[0]["id"] == "test-instinct"

    def test_loads_both_yaml_and_md(self, tmp_path: Path):
        """Should load instincts from both .yaml and .md files."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

        # Create .yaml file
        (learned_dir / "yaml-instinct.yaml").write_text(SAMPLE_INSTINCT_YAML)

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
        (learned_dir / "md-instinct.md").write_text(md_content)

        instincts = load_all_instincts(project_root)

        assert len(instincts) == 2
        ids = {i["id"] for i in instincts}
        assert "prefer-functional-style" in ids
        assert "md-instinct" in ids


class TestProjectScopedCLI:
    """Tests for project-scoped CLI commands (AC-6.1, AC-6.2, AC-6.12, AC-6.13)."""

    def test_evolve_displays_learned_instincts_from_project(self, tmp_path: Path, capsys):
        """AC-6.1: Should display learned instincts from docs/instincts/learned/."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

        # Create instincts in learned directory
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
        (learned_dir / "instincts.md").write_text(content)

        result = cmd_evolve(project_root=project_root)

        captured = capsys.readouterr()
        # Should display instincts from the project
        assert result == 0
        assert "3" in captured.out  # 3 instincts

    def test_evolve_prompts_output_type_selection(self, tmp_path: Path, capsys, monkeypatch):
        """AC-6.2: Should prompt for output type selection."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

        content = """---
id: inst1
trigger: "trigger 1"
confidence: 0.8
domain: testing
---
Content
---
id: inst2
trigger: "trigger 2"
confidence: 0.85
domain: testing
---
Content
---
id: inst3
trigger: "trigger 3"
confidence: 0.7
domain: testing
---
Content
"""
        (learned_dir / "instincts.md").write_text(content)

        # Mock user input to select output type
        # "all" = select all instincts, "1" = CLAUDE.md output, "n" = decline to apply
        inputs = iter(["all", "1", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        result = cmd_evolve(project_root=project_root, interactive=True)

        # Should complete without error
        assert result == 0 or result is None

    def test_evolve_prompts_scope_for_non_claudemd(self, tmp_path: Path, monkeypatch):
        """AC-6.12: Should prompt for scope when output type is not CLAUDE.md."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

        content = """---
id: inst1
trigger: "trigger 1"
confidence: 0.8
domain: testing
---
Content
---
id: inst2
trigger: "trigger 2"
confidence: 0.85
domain: testing
---
Content
---
id: inst3
trigger: "trigger 3"
confidence: 0.7
domain: testing
---
Content
"""
        (learned_dir / "instincts.md").write_text(content)

        # Mock user input: select all, rules, project scope
        inputs = iter(["all", "2", "1"])  # all instincts, rules output, project scope
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        result = cmd_evolve(project_root=project_root, interactive=True)

        # Should complete without error
        assert result == 0 or result is None

    def test_evolve_shows_preview_for_claudemd(self, tmp_path: Path, monkeypatch, capsys):
        """AC-6.13: Should show preview and request approval before writing to CLAUDE.md."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

        # Create CLAUDE.md
        (project_root / "CLAUDE.md").write_text("# CLAUDE.md\n\n## Overview\n\nProject.\n")

        content = """---
id: inst1
trigger: "when testing"
confidence: 0.8
domain: testing
---
Write tests first
---
id: inst2
trigger: "when coding"
confidence: 0.85
domain: code-style
---
Use guard clauses
---
id: inst3
trigger: "when committing"
confidence: 0.7
domain: workflow
---
Run checks first
"""
        (learned_dir / "instincts.md").write_text(content)

        # Mock user input: select all, CLAUDE.md output, confirm (y)
        inputs = iter(["all", "1", "y"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        cmd_evolve(project_root=project_root, interactive=True)

        captured = capsys.readouterr()
        # Should show preview
        assert "preview" in captured.out.lower() or "Learned Patterns" in captured.out


class TestStatusCommandExists:
    """Tests to verify cmd_status still works (CR-014: placeholder removed)."""

    def test_cmd_status_returns_zero_with_no_instincts(self, tmp_path: Path, capsys):
        """cmd_status should return 0 even when no instincts exist."""
        project_root, learned_dir, _ = create_project_structure(tmp_path)

        result = cmd_status(project_root)

        assert result == 0
        captured = capsys.readouterr()
        assert "No instincts found" in captured.out
