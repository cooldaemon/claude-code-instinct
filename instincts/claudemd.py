"""CLAUDE.md integration module for Instinct-Based Learning.

This module provides CLAUDE.md parsing and manipulation:
- Parse CLAUDE.md structure into sections
- Find existing "Learned Patterns" section
- Generate patterns content from instincts
- Insert patterns into CLAUDE.md
"""

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from instincts.config import LEARNED_PATTERNS_SECTION
from instincts.models import Instinct


@dataclass(frozen=True)
class ClaudeMdSection:
    """A section in a CLAUDE.md file.

    Attributes:
        title: Section title (without # prefix).
        level: Heading level (1 for #, 2 for ##, etc.).
        content: Content of the section.
        start_line: Line number where section starts.
        end_line: Line number where section ends.
    """

    title: str
    level: int
    content: str
    start_line: int
    end_line: int


def parse_claudemd(path: Path) -> list[ClaudeMdSection]:
    """Parse CLAUDE.md into sections.

    Args:
        path: Path to the CLAUDE.md file.

    Returns:
        List of ClaudeMdSection objects.
    """
    if not path.exists():
        return []

    try:
        content = path.read_text()
    except OSError:
        return []

    lines = content.split("\n")
    sections: list[ClaudeMdSection] = []
    current_title: str | None = None
    current_level: int = 0
    current_start: int = 0
    current_content_lines: list[str] = []

    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

    for i, line in enumerate(lines):
        match = heading_pattern.match(line)
        if match:
            # Save previous section if exists
            if current_title is not None:
                sections.append(
                    ClaudeMdSection(
                        title=current_title,
                        level=current_level,
                        content="\n".join(current_content_lines).strip(),
                        start_line=current_start,
                        end_line=i - 1,
                    )
                )

            # Start new section
            current_level = len(match.group(1))
            current_title = match.group(2).strip()
            current_start = i
            current_content_lines = []
        else:
            if current_title is not None:
                current_content_lines.append(line)

    # Save last section
    if current_title is not None:
        sections.append(
            ClaudeMdSection(
                title=current_title,
                level=current_level,
                content="\n".join(current_content_lines).strip(),
                start_line=current_start,
                end_line=len(lines) - 1,
            )
        )

    return sections


def find_learned_patterns_section(
    sections: list[ClaudeMdSection],
) -> ClaudeMdSection | None:
    """Find the "Learned Patterns" section.

    Args:
        sections: List of parsed sections.

    Returns:
        The Learned Patterns section, or None if not found.
    """
    for section in sections:
        if section.title == "Learned Patterns":
            return section
    return None


def _capitalize_domain(domain: str) -> str:
    """Capitalize domain name for subsection header."""
    # Handle hyphenated domains like "code-style"
    return " ".join(word.capitalize() for word in domain.replace("-", " ").split())


def generate_patterns_content(instincts: list[Instinct]) -> str:
    """Generate content for the Learned Patterns section.

    Organizes patterns by domain/category.

    Args:
        instincts: List of instincts to include.

    Returns:
        Formatted markdown content.
    """
    # Group by domain
    by_domain: dict[str, list[Instinct]] = {}
    for inst in instincts:
        domain = inst.domain
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(inst)

    lines: list[str] = []

    for domain in sorted(by_domain.keys()):
        domain_instincts = by_domain[domain]
        capitalized = _capitalize_domain(domain)
        lines.append(f"### {capitalized}")
        lines.append("")

        for inst in domain_instincts:
            # Extract a meaningful description from the instinct
            description = inst.trigger
            if inst.content:
                # Try to get first meaningful line from content
                content_lines = inst.content.strip().split("\n")
                for content_line in content_lines:
                    clean = content_line.strip()
                    if clean and not clean.startswith("#"):
                        description = clean
                        break
            lines.append(f"- {description}")

        lines.append("")

    return "\n".join(lines)


def insert_patterns(path: Path, new_content: str) -> str:
    """Insert patterns content into CLAUDE.md.

    If a Learned Patterns section exists, appends to it.
    Otherwise, adds a new section at the end.

    Args:
        path: Path to the CLAUDE.md file.
        new_content: Content to insert (without section header).

    Returns:
        Preview of the resulting CLAUDE.md content.
    """
    if not path.exists():
        # Create minimal CLAUDE.md with the patterns
        return f"# CLAUDE.md\n\n{LEARNED_PATTERNS_SECTION}\n\n{new_content}"

    try:
        original = path.read_text()
    except OSError:
        return f"# CLAUDE.md\n\n{LEARNED_PATTERNS_SECTION}\n\n{new_content}"

    sections = parse_claudemd(path)
    learned_section = find_learned_patterns_section(sections)

    lines = original.split("\n")

    if learned_section:
        # Insert into existing section
        # Find end of the Learned Patterns section
        insert_line = learned_section.end_line + 1

        # Check for duplicates in existing content
        # Check the entire file for duplicate patterns
        filtered_lines: list[str] = []
        for line in new_content.split("\n"):
            stripped = line.strip()
            # Skip if this exact bullet point already exists in the original file
            if stripped.startswith("- "):
                # Extract the content after "- "
                bullet_content = stripped[2:].strip()
                if bullet_content and bullet_content in original:
                    continue
            # Skip subsection headers if same content already present
            elif stripped.startswith("### "):
                # Keep headers, they're needed for structure
                pass
            filtered_lines.append(line)

        # Check if we have any meaningful new content (not just headers)
        has_new_bullets = any(
            l.strip().startswith("- ") for l in filtered_lines
        )
        if not has_new_bullets:
            # All bullet content was duplicates
            return original

        # Insert new content
        new_lines = lines[:insert_line] + filtered_lines + lines[insert_line:]
        return "\n".join(new_lines)
    else:
        # Add new section at end
        if not original.endswith("\n"):
            original += "\n"
        return f"{original}\n{LEARNED_PATTERNS_SECTION}\n\n{new_content}"


def _atomic_write_text(file_path: Path, content: str) -> None:
    """Write file atomically using temp file + rename.

    This prevents file corruption if the process crashes mid-write.

    Args:
        file_path: Path to the file to write.
        content: Content to write.

    Raises:
        OSError: If write or rename fails.
    """
    directory = file_path.parent
    # Ensure parent directory exists
    directory.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.rename(temp_path, file_path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def write_patterns(path: Path, content: str) -> None:
    """Write content to CLAUDE.md atomically.

    Uses temp file + rename pattern to prevent corruption on crash.

    Args:
        path: Path to the CLAUDE.md file.
        content: Full content to write.
    """
    _atomic_write_text(path, content)


def create_minimal_claudemd(path: Path, patterns: str) -> None:
    """Create a minimal CLAUDE.md with Learned Patterns section.

    Uses atomic write to prevent corruption on crash.

    Args:
        path: Path to create the CLAUDE.md file.
        patterns: Patterns content to include.
    """
    content = f"""# CLAUDE.md

This file provides guidance to Claude Code.

{LEARNED_PATTERNS_SECTION}

{patterns}
"""
    _atomic_write_text(path, content)
