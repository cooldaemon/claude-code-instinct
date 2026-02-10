"""Observer Agent for Instinct-Based Learning.

This module provides the Observer Agent that:
- Analyzes observations and detects patterns
- Creates/updates instinct files in personal/ directory
- Applies confidence decay to existing instincts
- Generates analysis summaries
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from instincts.confidence import (
    apply_decay_to_instinct,
    calculate_initial_confidence,
    check_dormant_status,
)
from instincts.config import MAX_OBSERVATIONS_FOR_ANALYSIS, OBSERVATIONS_FILE, PERSONAL_DIR
from instincts.llm_patterns import detect_patterns_with_llm, is_llm_available
from instincts.models import Instinct, Pattern
from instincts.pattern_merger import merge_patterns
from instincts.patterns import detect_all_patterns, load_recent_observations

logger = logging.getLogger(__name__)

# Warning threshold for number of instinct files
MAX_INSTINCT_FILES_WARNING: int = 100

# Maximum number of evidence entries to display in instinct content
MAX_EVIDENCE_DISPLAY: int = 5


@dataclass(frozen=True)
class AnalysisResult:
    """Result of pattern analysis.

    Attributes:
        patterns_detected: Number of patterns detected.
        instincts_created: Number of new instincts created.
        instincts_updated: Number of existing instincts updated.
        warnings: Tuple of warning messages (immutable).
        patterns: Tuple of detected patterns (immutable).
        detection_sources: Tuple of detection sources used (AC-R2.8).
    """

    patterns_detected: int
    instincts_created: int
    instincts_updated: int
    warnings: tuple[str, ...]
    patterns: tuple[Pattern, ...] = field(default_factory=tuple)
    detection_sources: tuple[str, ...] = field(default=("algorithm",))


def _generate_instinct_id(pattern: Pattern) -> str:
    """Generate a kebab-case ID from pattern."""
    # Use pattern type and first few words of description
    base = f"{pattern.pattern_type.value}-{pattern.trigger}"
    # Normalize to kebab-case
    normalized = base.lower()
    normalized = "".join(c if c.isalnum() or c == " " else " " for c in normalized)
    words = normalized.split()[:4]  # Limit to 4 words
    return "-".join(words)


def _pattern_to_instinct(pattern: Pattern) -> Instinct:
    """Convert a Pattern to an Instinct."""
    now = datetime.now(timezone.utc)
    evidence_count = len(pattern.evidence)

    return Instinct(
        id=_generate_instinct_id(pattern),
        trigger=pattern.trigger,
        confidence=calculate_initial_confidence(evidence_count),
        domain=pattern.domain,
        source=f"{pattern.pattern_type.value}",
        evidence_count=evidence_count,
        created_at=now,
        updated_at=now,
        content=_generate_instinct_content(pattern),
        status="active",
    )


def _generate_instinct_content(pattern: Pattern) -> str:
    """Generate markdown content for an instinct."""
    lines = [
        f"# {pattern.description}",
        "",
        "## Action",
        "",
        pattern.description,
        "",
        "## Evidence",
        "",
    ]

    for evidence in pattern.evidence[:MAX_EVIDENCE_DISPLAY]:
        lines.append(f"- {evidence.description} (session: {evidence.session_id})")

    if len(pattern.evidence) > MAX_EVIDENCE_DISPLAY:
        remaining = len(pattern.evidence) - MAX_EVIDENCE_DISPLAY
        lines.append(f"- ... and {remaining} more observations")

    return "\n".join(lines)


def _escape_yaml_string(value: str) -> str:
    """Escape a string for safe YAML double-quoted string.

    Prevents YAML injection attacks by escaping special characters
    that could break out of the quoted string context.

    Args:
        value: The raw string value.

    Returns:
        Escaped string safe for YAML double-quoted context.
    """
    # Order matters: escape backslashes first to avoid double-escaping
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace("\n", "\\n")
    escaped = escaped.replace("\r", "\\r")
    return escaped


def _sanitize_instinct_id(instinct_id: str) -> str:
    """Sanitize an instinct ID to prevent path traversal attacks.

    Args:
        instinct_id: The raw instinct ID.

    Returns:
        A safe filename-compatible string.
    """
    # Get just the basename to prevent path traversal
    safe_id = os.path.basename(instinct_id)
    # Defense in depth: handle edge cases where basename may not fully sanitize
    # (e.g., different OS path conventions, unusual characters)

    # Remove dangerous characters, keep only alphanumeric, dash, underscore
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "-", safe_id)

    # Remove leading/trailing dashes and collapse multiple dashes
    safe_id = re.sub(r"-+", "-", safe_id).strip("-")

    # Ensure we have a valid filename
    if not safe_id:
        safe_id = "unnamed-instinct"

    return safe_id


def _write_instinct_file(instinct: Instinct, directory: Path) -> Path:
    """Write an instinct to a markdown file.

    Args:
        instinct: The instinct to write.
        directory: Directory to write the file to.

    Returns:
        Path to the created file.

    Raises:
        ValueError: If the resulting path would be outside the directory.
    """
    # Ensure directory exists with secure permissions
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Sanitize the instinct ID to prevent path traversal
    safe_id = _sanitize_instinct_id(instinct.id)

    # Generate filename
    filename = f"{safe_id}.md"
    file_path = directory / filename

    # Check for symlink attack - refuse to overwrite symlinks
    # This must be checked before resolve() which follows symlinks
    if file_path.is_symlink():
        raise ValueError(f"Refusing to write to symlink: {file_path}")

    # Verify the file path is within the directory (defense in depth)
    resolved_path = file_path.resolve()
    resolved_dir = directory.resolve()
    if not resolved_path.is_relative_to(resolved_dir):
        raise ValueError(f"Path traversal detected: {instinct.id}")

    # Generate file content with YAML frontmatter
    # Escape all string fields to prevent YAML injection
    safe_id = _escape_yaml_string(instinct.id)
    safe_trigger = _escape_yaml_string(instinct.trigger)
    safe_domain = _escape_yaml_string(instinct.domain)
    safe_source = _escape_yaml_string(instinct.source)
    safe_status = _escape_yaml_string(instinct.status)

    content = f"""---
id: "{safe_id}"
trigger: "{safe_trigger}"
confidence: {instinct.confidence}
domain: "{safe_domain}"
source: "{safe_source}"
evidence_count: {instinct.evidence_count}
created_at: "{instinct.created_at.isoformat()}"
updated_at: "{instinct.updated_at.isoformat()}"
status: "{safe_status}"
---

{instinct.content}
"""

    file_path.write_text(content)
    return file_path


def _load_existing_instincts(directory: Path) -> list[Instinct]:
    """Load existing instincts from a directory.

    Args:
        directory: Directory containing instinct files.

    Returns:
        List of Instinct objects.
    """
    instincts: list[Instinct] = []

    if not directory.exists():
        return instincts

    for file_path in directory.glob("*.md"):
        # Skip symlinks for defense in depth
        if file_path.is_symlink():
            logger.warning("Skipping symlink: %s", file_path)
            continue
        try:
            content = file_path.read_text()
            instinct = _parse_instinct_file(content, str(file_path))
            if instinct:
                instincts.append(instinct)
        except (OSError, IOError) as e:
            # File read error - log and skip
            logger.warning("Failed to read instinct file %s: %s", file_path, e)
            continue
        except (ValueError, UnicodeDecodeError) as e:
            # Parsing error - log and skip
            logger.warning("Failed to parse instinct file %s: %s", file_path, e)
            continue

    return instincts


def _parse_frontmatter(frontmatter: str) -> dict[str, Any]:
    """Parse YAML-like frontmatter into a dictionary."""
    data: dict[str, Any] = {}
    for line in frontmatter.strip().split("\n"):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        data[key] = value
    return data


def _parse_timestamp(value: str, default_factory: Any = None) -> datetime:
    """Parse a timestamp string, returning a default if parsing fails."""
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return default_factory() if default_factory else datetime.now(timezone.utc)


def _parse_float(value: Any, default: float) -> float:
    """Parse a value as float, returning default if parsing fails."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_int(value: Any, default: int) -> int:
    """Parse a value as int, returning default if parsing fails."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_instinct_file(content: str, source_file: str) -> Instinct | None:
    """Parse a markdown instinct file.

    Args:
        content: File content with YAML frontmatter.
        source_file: Path to the source file.

    Returns:
        Instinct object or None if parsing fails.
    """
    if not content.strip():
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    data = _parse_frontmatter(parts[1])
    if "id" not in data:
        return None

    markdown_content = parts[2].strip()
    default_confidence = 0.5
    default_evidence_count = 1

    return Instinct(
        id=data.get("id", ""),
        trigger=data.get("trigger", ""),
        confidence=_parse_float(data.get("confidence"), default_confidence),
        domain=data.get("domain", "general"),
        source=data.get("source", "unknown"),
        evidence_count=_parse_int(data.get("evidence_count"), default_evidence_count),
        created_at=_parse_timestamp(
            data.get("created_at", ""), lambda: datetime.now(timezone.utc)
        ),
        updated_at=_parse_timestamp(
            data.get("updated_at", ""), lambda: datetime.now(timezone.utc)
        ),
        content=markdown_content,
        source_file=source_file,
        status=data.get("status", "active"),
    )


def analyze_observations(dry_run: bool = False, skip_llm: bool = False) -> AnalysisResult:
    """Analyze observations and create/update instincts.

    Uses dual-approach detection when LLM is available:
    - Algorithm-based detection (always runs)
    - LLM-based detection (runs when ANTHROPIC_API_KEY is set and skip_llm=False)
    - Results are merged using pattern_merger

    Args:
        dry_run: If True, don't write any files.
        skip_llm: If True, skip LLM analysis even when API key is available.

    Returns:
        AnalysisResult with summary of analysis.
    """
    warnings: list[str] = []
    detection_sources: list[str] = ["algorithm"]

    # Load existing instincts once - reused for LLM context and duplicate checking
    existing_instincts = _load_existing_instincts(PERSONAL_DIR)
    existing_ids = {inst.id for inst in existing_instincts}

    # Check for too many instinct files (EC-4)
    if len(existing_instincts) >= MAX_INSTINCT_FILES_WARNING:
        warnings.append(
            f"Warning: {len(existing_instincts)} instinct files in personal/ - "
            "this may impact performance"
        )

    # Load recent observations for analysis (AC-R2.3)
    observations = load_recent_observations(
        OBSERVATIONS_FILE, limit=MAX_OBSERVATIONS_FOR_ANALYSIS
    )

    if not observations:
        return AnalysisResult(
            patterns_detected=0,
            instincts_created=0,
            instincts_updated=0,
            warnings=tuple(warnings),
            patterns=(),
            detection_sources=tuple(detection_sources),
        )

    # Algorithm-based pattern detection (always runs)
    algorithm_patterns = detect_all_patterns(OBSERVATIONS_FILE)

    # LLM-based pattern detection (AC-R2.1, AC-R2.2)
    llm_patterns: list[Pattern] = []
    use_llm = is_llm_available() and not skip_llm

    if use_llm:
        detection_sources.append("llm")
        # Use already-loaded existing instincts for LLM context (AC-R2.6)
        existing_instincts_dicts = [
            {"id": inst.id, "trigger": inst.trigger, "domain": inst.domain}
            for inst in existing_instincts
        ]
        llm_patterns = detect_patterns_with_llm(observations, existing_instincts_dicts)

    # Merge patterns from both approaches
    if use_llm:
        patterns = merge_patterns(algorithm_patterns, llm_patterns)
    else:
        patterns = algorithm_patterns

    if not patterns:
        return AnalysisResult(
            patterns_detected=0,
            instincts_created=0,
            instincts_updated=0,
            warnings=tuple(warnings),
            patterns=(),
            detection_sources=tuple(detection_sources),
        )

    instincts_created = 0
    instincts_updated = 0

    if not dry_run:
        for pattern in patterns:
            instinct = _pattern_to_instinct(pattern)

            # Check if instinct with similar ID already exists
            if instinct.id in existing_ids:
                # Update existing instinct
                instincts_updated += 1
            else:
                # Create new instinct
                _write_instinct_file(instinct, PERSONAL_DIR)
                instincts_created += 1
                existing_ids.add(instinct.id)

    return AnalysisResult(
        patterns_detected=len(patterns),
        instincts_created=instincts_created,
        instincts_updated=instincts_updated,
        warnings=tuple(warnings),
        patterns=tuple(patterns),
        detection_sources=tuple(detection_sources),
    )


def apply_confidence_decay(directory: Path | None = None) -> list[Instinct]:
    """Apply confidence decay to all existing instincts.

    Args:
        directory: Directory containing instinct files (defaults to PERSONAL_DIR).

    Returns:
        List of instincts with updated confidence.
    """
    if directory is None:
        directory = PERSONAL_DIR

    instincts = _load_existing_instincts(directory)
    decayed_instincts: list[Instinct] = []

    for instinct in instincts:
        decayed = apply_decay_to_instinct(instinct)

        # Check if should be marked dormant
        new_status = check_dormant_status(decayed.confidence)
        if new_status != decayed.status:
            decayed = decayed.with_status(new_status)

        decayed_instincts.append(decayed)

        # Write updated instinct if confidence changed
        if decayed.confidence != instinct.confidence and instinct.source_file:
            _write_instinct_file(decayed, directory)

    return decayed_instincts


def format_analysis_summary(result: AnalysisResult) -> str:
    """Format analysis result as a human-readable summary.

    Args:
        result: AnalysisResult from analysis.

    Returns:
        Formatted summary string.
    """
    lines = [
        "",
        "=" * 60,
        "  PATTERN ANALYSIS SUMMARY",
        "=" * 60,
        "",
        f"  Patterns detected:   {result.patterns_detected}",
        f"  Instincts created:   {result.instincts_created}",
        f"  Instincts updated:   {result.instincts_updated}",
    ]

    if result.warnings:
        lines.append("")
        lines.append("  Warnings:")
        for warning in result.warnings:
            lines.append(f"    - {warning}")

    if result.patterns_detected == 0:
        lines.append("")
        lines.append("  No patterns detected in observations.")

    lines.append("")
    lines.append("=" * 60)
    lines.append("")

    return "\n".join(lines)
