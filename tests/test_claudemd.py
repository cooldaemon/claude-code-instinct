"""Tests for instincts.claudemd module.

Tests cover:
- AC-7.1: Detect existing "Learned Patterns" section
- AC-7.2: Create "Learned Patterns" section if not exists
- AC-7.3: Organize patterns by category
- AC-7.4: Skip duplicate patterns
- AC-7.5: Format as bullet points under subsections
- EC-8: Create minimal CLAUDE.md if not exists
- EC-9: Append to end if parsing fails
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from instincts.models import Instinct


def _make_instinct(
    id: str,
    trigger: str,
    confidence: float = 0.7,
    domain: str = "general",
    content: str = "Test content",
) -> Instinct:
    """Helper to create test instincts."""
    ts = datetime.now(timezone.utc)
    return Instinct(
        id=id,
        trigger=trigger,
        confidence=confidence,
        domain=domain,
        source="test",
        evidence_count=5,
        created_at=ts,
        updated_at=ts,
        content=content,
    )


class TestClaudeMdSection:
    """Tests for ClaudeMdSection dataclass."""

    def test_claudemd_section_has_required_fields(self):
        """ClaudeMdSection should have title, level, content, start_line, end_line."""
        from instincts.claudemd import ClaudeMdSection

        section = ClaudeMdSection(
            title="Test Section",
            level=2,
            content="Some content here",
            start_line=10,
            end_line=20,
        )

        assert section.title == "Test Section"
        assert section.level == 2
        assert section.content == "Some content here"
        assert section.start_line == 10
        assert section.end_line == 20

    def test_claudemd_section_is_frozen(self):
        """ClaudeMdSection should be immutable (frozen)."""
        from instincts.claudemd import ClaudeMdSection

        section = ClaudeMdSection(
            title="Test",
            level=2,
            content="Content",
            start_line=1,
            end_line=5,
        )

        with pytest.raises(AttributeError):
            section.title = "Modified"  # type: ignore[misc]


class TestParseClaudemd:
    """Tests for parse_claudemd function."""

    def test_parses_sections_from_claudemd(self, tmp_path: Path):
        """Should parse sections with their line numbers."""
        from instincts.claudemd import parse_claudemd

        claudemd = tmp_path / "CLAUDE.md"
        content = """# Project Title

This is the intro.

## Section One

Content for section one.

## Section Two

Content for section two.

### Subsection

More content.
"""
        claudemd.write_text(content)

        sections = parse_claudemd(claudemd)

        # Should find h1 and h2 sections
        assert len(sections) >= 3
        titles = [s.title for s in sections]
        assert "Project Title" in titles
        assert "Section One" in titles
        assert "Section Two" in titles

    def test_returns_empty_for_missing_file(self, tmp_path: Path):
        """Should return empty list if file doesn't exist."""
        from instincts.claudemd import parse_claudemd

        missing_file = tmp_path / "CLAUDE.md"

        sections = parse_claudemd(missing_file)

        assert sections == []


class TestFindLearnedPatternsSection:
    """Tests for find_learned_patterns_section function (AC-7.1)."""

    def test_finds_existing_learned_patterns_section(self, tmp_path: Path):
        """AC-7.1: Should detect existing 'Learned Patterns' section."""
        from instincts.claudemd import parse_claudemd, find_learned_patterns_section

        claudemd = tmp_path / "CLAUDE.md"
        content = """# CLAUDE.md

## Overview

This project does things.

## Learned Patterns

### Code Style
- Use explicit return types

## Other Section

More content.
"""
        claudemd.write_text(content)

        sections = parse_claudemd(claudemd)
        learned_section = find_learned_patterns_section(sections)

        assert learned_section is not None
        assert learned_section.title == "Learned Patterns"

    def test_returns_none_when_no_learned_patterns_section(self, tmp_path: Path):
        """Should return None if no 'Learned Patterns' section exists."""
        from instincts.claudemd import parse_claudemd, find_learned_patterns_section

        claudemd = tmp_path / "CLAUDE.md"
        content = """# CLAUDE.md

## Overview

This project does things.

## Commands

Some commands here.
"""
        claudemd.write_text(content)

        sections = parse_claudemd(claudemd)
        learned_section = find_learned_patterns_section(sections)

        assert learned_section is None


class TestGeneratePatternsContent:
    """Tests for generate_patterns_content function (AC-7.3, AC-7.5)."""

    def test_organizes_patterns_by_category(self):
        """AC-7.3: Should organize patterns by category (domain)."""
        from instincts.claudemd import generate_patterns_content

        instincts = [
            _make_instinct("code-1", "when editing code", domain="code-style"),
            _make_instinct("code-2", "when writing functions", domain="code-style"),
            _make_instinct("test-1", "when writing tests", domain="testing"),
            _make_instinct("workflow-1", "when committing", domain="workflow"),
        ]

        content = generate_patterns_content(instincts)

        # Should have subsections for each domain
        assert "### Code Style" in content or "### code-style" in content
        assert "### Testing" in content or "### testing" in content
        assert "### Workflow" in content or "### workflow" in content

    def test_formats_as_bullet_points(self):
        """AC-7.5: Should format patterns as bullet points."""
        from instincts.claudemd import generate_patterns_content

        instincts = [
            _make_instinct("test-1", "when writing tests", domain="testing", content="Always use pytest"),
        ]

        content = generate_patterns_content(instincts)

        # Should contain bullet points
        assert "- " in content or "* " in content


class TestInsertPatterns:
    """Tests for insert_patterns function."""

    def test_inserts_into_existing_learned_patterns_section(self, tmp_path: Path):
        """Should insert content into existing Learned Patterns section."""
        from instincts.claudemd import insert_patterns

        claudemd = tmp_path / "CLAUDE.md"
        original = """# CLAUDE.md

## Overview

Description here.

## Learned Patterns

## Other Section

More stuff.
"""
        claudemd.write_text(original)

        new_content = """### Testing
- Always write tests first
"""
        preview = insert_patterns(claudemd, new_content)

        # Preview should show the merged content
        assert "Testing" in preview
        assert "Always write tests first" in preview
        assert "Overview" in preview

    def test_adds_learned_patterns_section_at_end(self, tmp_path: Path):
        """AC-7.2: Should add Learned Patterns section at end if not exists."""
        from instincts.claudemd import insert_patterns

        claudemd = tmp_path / "CLAUDE.md"
        original = """# CLAUDE.md

## Overview

Description here.

## Commands

Some commands.
"""
        claudemd.write_text(original)

        new_content = """### Testing
- Always write tests first
"""
        preview = insert_patterns(claudemd, new_content)

        # Should have new Learned Patterns section
        assert "## Learned Patterns" in preview
        assert "Testing" in preview


class TestWritePatterns:
    """Tests for write_patterns function."""

    def test_writes_content_to_claudemd(self, tmp_path: Path):
        """Should write the previewed content to CLAUDE.md."""
        from instincts.claudemd import write_patterns

        claudemd = tmp_path / "CLAUDE.md"
        content = """# CLAUDE.md

## Learned Patterns

### Testing
- Always write tests first
"""

        write_patterns(claudemd, content)

        assert claudemd.exists()
        assert claudemd.read_text() == content


class TestSkipDuplicatePatterns:
    """Tests for duplicate pattern detection (AC-7.4)."""

    def test_detects_duplicate_patterns(self, tmp_path: Path):
        """AC-7.4: Should detect patterns that already exist in CLAUDE.md."""
        from instincts.claudemd import insert_patterns

        claudemd = tmp_path / "CLAUDE.md"
        original = """# CLAUDE.md

## Learned Patterns

### Testing
- Always write tests first
"""
        claudemd.write_text(original)

        # Try to insert the same pattern
        new_content = """### Testing
- Always write tests first
"""
        preview = insert_patterns(claudemd, new_content)

        # Should not duplicate the pattern
        assert preview.count("Always write tests first") == 1


class TestCreateMinimalClaudemd:
    """Tests for create_minimal_claudemd function (EC-8)."""

    def test_creates_minimal_claudemd_with_learned_patterns(self, tmp_path: Path):
        """EC-8: Should create minimal CLAUDE.md with Learned Patterns section."""
        from instincts.claudemd import create_minimal_claudemd

        claudemd = tmp_path / "CLAUDE.md"
        patterns = """### Testing
- Always write tests first
"""

        create_minimal_claudemd(claudemd, patterns)

        assert claudemd.exists()
        content = claudemd.read_text()
        assert "# CLAUDE.md" in content
        assert "## Learned Patterns" in content
        assert "Testing" in content


class TestAppendOnParseFailure:
    """Tests for fallback when parsing fails (EC-9)."""

    def test_appends_to_end_on_parse_failure(self, tmp_path: Path):
        """EC-9: Should append to end of file with clear delimiter if parsing fails."""
        from instincts.claudemd import insert_patterns

        claudemd = tmp_path / "CLAUDE.md"
        # Write content that might cause parsing issues (unusual structure)
        original = """# CLAUDE.md

Some content without proper section structure.

```markdown
## This is in a code block
```

More content.
"""
        claudemd.write_text(original)

        new_content = """### Testing
- Always write tests first
"""
        preview = insert_patterns(claudemd, new_content)

        # Should still contain both original and new content
        assert "Some content" in preview
        assert "## Learned Patterns" in preview
        assert "Testing" in preview


class TestAtomicClaudeMdWrites:
    """Tests for atomic CLAUDE.md writes to prevent corruption (DR-004)."""

    def test_write_patterns_uses_atomic_write(self, tmp_path: Path):
        """DR-004: Should use atomic write (temp file + rename) for CLAUDE.md."""
        import os
        import tempfile
        from unittest.mock import patch

        from instincts.claudemd import write_patterns

        claudemd = tmp_path / "CLAUDE.md"
        content = "# CLAUDE.md\n\n## Learned Patterns\n"

        # Track if atomic write pattern was used
        mkstemp_called = {"called": False}
        rename_called = {"called": False}
        original_mkstemp = tempfile.mkstemp
        original_rename = os.rename

        def tracking_mkstemp(*args, **kwargs):
            mkstemp_called["called"] = True
            return original_mkstemp(*args, **kwargs)

        def tracking_rename(src, dst):
            rename_called["called"] = True
            return original_rename(src, dst)

        with patch("instincts.claudemd.tempfile.mkstemp", tracking_mkstemp):
            with patch("instincts.claudemd.os.rename", tracking_rename):
                write_patterns(claudemd, content)

        # Should have used atomic write pattern
        assert mkstemp_called["called"], "Should use tempfile.mkstemp for atomic write"
        assert rename_called["called"], "Should use os.rename for atomic write"
        # File should exist and have correct content
        assert claudemd.exists()
        assert claudemd.read_text() == content

    def test_atomic_write_cleans_up_on_failure(self, tmp_path: Path):
        """DR-004: Should clean up temp file if write fails."""
        import os
        import tempfile
        from unittest.mock import patch

        from instincts.claudemd import write_patterns

        claudemd = tmp_path / "CLAUDE.md"
        content = "# CLAUDE.md\n"

        # Make fdopen fail after mkstemp succeeds
        original_mkstemp = tempfile.mkstemp
        created_temps: list[str] = []

        def tracking_mkstemp(*args, **kwargs):
            fd, path = original_mkstemp(*args, **kwargs)
            created_temps.append(path)
            return fd, path

        def failing_fdopen(*args, **kwargs):
            raise IOError("Simulated failure")

        with patch("instincts.claudemd.tempfile.mkstemp", tracking_mkstemp):
            with patch("instincts.claudemd.os.fdopen", failing_fdopen):
                with pytest.raises(IOError):
                    write_patterns(claudemd, content)

        # Temp file should be cleaned up
        for temp_path in created_temps:
            assert not os.path.exists(temp_path), f"Temp file should be cleaned up: {temp_path}"

    def test_create_minimal_claudemd_uses_atomic_write(self, tmp_path: Path):
        """DR-004: create_minimal_claudemd should also use atomic write."""
        import os
        import tempfile
        from unittest.mock import patch

        from instincts.claudemd import create_minimal_claudemd

        claudemd = tmp_path / "CLAUDE.md"
        patterns = "### Testing\n- Always test\n"

        # Track if atomic write pattern was used
        mkstemp_called = {"called": False}
        rename_called = {"called": False}
        original_mkstemp = tempfile.mkstemp
        original_rename = os.rename

        def tracking_mkstemp(*args, **kwargs):
            mkstemp_called["called"] = True
            return original_mkstemp(*args, **kwargs)

        def tracking_rename(src, dst):
            rename_called["called"] = True
            return original_rename(src, dst)

        with patch("instincts.claudemd.tempfile.mkstemp", tracking_mkstemp):
            with patch("instincts.claudemd.os.rename", tracking_rename):
                create_minimal_claudemd(claudemd, patterns)

        # Should have used atomic write pattern
        assert mkstemp_called["called"], "Should use tempfile.mkstemp for atomic write"
        assert rename_called["called"], "Should use os.rename for atomic write"
