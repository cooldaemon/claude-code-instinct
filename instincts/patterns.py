"""Pattern detection algorithms for Instinct-Based Learning.

This module provides functions to detect different types of patterns:
- User corrections (Write followed by Edit, correction keywords)
- Error resolutions (error followed by success)
- Repeated workflows (same tool sequences across sessions)
- Tool preferences (consistent tool usage patterns)
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from instincts.models import Evidence, Pattern, PatternType

# Correction keywords to detect user corrections
CORRECTION_KEYWORDS: tuple[str, ...] = ("no", "instead", "actually", "don't", "dont")

# Error keywords to detect errors in tool output
ERROR_KEYWORDS: tuple[str, ...] = ("error", "failed", "exception", "failure", "traceback")

# Minimum sequence length for workflow detection
MIN_WORKFLOW_SEQUENCE_LENGTH: int = 3

# Minimum sessions for pattern detection
MIN_SESSIONS_FOR_PATTERN: int = 2

# Minimum tool uses for preference detection
MIN_TOOL_USES_FOR_PREFERENCE: int = 3

# Security limits for observations file
MAX_OBSERVATIONS_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
MAX_OBSERVATIONS_LINES: int = 100000


def load_observations(file_path: Path) -> list[dict[str, Any]]:
    """Load observations from a JSONL file.

    Args:
        file_path: Path to the observations.jsonl file.

    Returns:
        List of observation dictionaries.

    Raises:
        ValueError: If file exceeds size limit.
    """
    if not file_path.exists():
        return []

    # Security check: verify file size before reading
    try:
        file_size = file_path.stat().st_size
        if file_size > MAX_OBSERVATIONS_FILE_SIZE:
            raise ValueError(
                f"Observations file exceeds size limit "
                f"({file_size} > {MAX_OBSERVATIONS_FILE_SIZE} bytes)"
            )
    except OSError:
        return []

    observations: list[dict[str, Any]] = []
    line_count = 0

    try:
        with file_path.open() as f:
            for line in f:
                line_count += 1

                # Security check: limit number of lines
                if line_count > MAX_OBSERVATIONS_LINES:
                    break

                line = line.strip()
                if not line:
                    continue
                try:
                    obs = json.loads(line)
                    observations.append(obs)
                except json.JSONDecodeError:
                    # Skip invalid JSON lines (EC-1)
                    continue
    except OSError:
        return []

    return observations


def _extract_file_path(input_str: str) -> str | None:
    """Extract file_path from tool input string."""
    try:
        if isinstance(input_str, str):
            data = json.loads(input_str)
            file_path = data.get("file_path")
            if isinstance(file_path, str):
                return file_path
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _has_error_keywords(text: str) -> bool:
    """Check if text contains error keywords."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in ERROR_KEYWORDS)


def _has_correction_keywords(text: str) -> bool:
    """Check if text contains correction keywords."""
    text_lower = text.lower()
    # Check for word boundaries to avoid false positives
    for keyword in CORRECTION_KEYWORDS:
        # Match keyword at word boundaries
        pattern = rf"\b{re.escape(keyword)}\b"
        if re.search(pattern, text_lower):
            return True
    return False


def _group_by_session(
    observations: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group observations by session ID."""
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obs in observations:
        session = obs.get("session", "unknown")
        by_session[session].append(obs)
    return by_session


def _create_write_edit_pattern(
    obs: dict[str, Any], session_id: str, file_path: str
) -> Pattern:
    """Create a pattern for Write followed by Edit on same file."""
    evidence = Evidence(
        timestamp=datetime.fromisoformat(
            obs.get("timestamp", datetime.now(timezone.utc).isoformat())
        ),
        session_id=session_id,
        description=f"Write followed by Edit on same file: {file_path}",
    )
    return Pattern(
        pattern_type=PatternType.USER_CORRECTION,
        trigger="when editing recently written files",
        description="User corrected content on same file after Write operation",
        evidence=(evidence,),
        domain="workflow",
        metadata=(("file_path", file_path),),
    )


def _create_correction_keyword_pattern(
    obs: dict[str, Any], session_id: str, tool_name: str
) -> Pattern:
    """Create a pattern for user correction keyword after tool execution."""
    evidence = Evidence(
        timestamp=datetime.fromisoformat(
            obs.get("timestamp", datetime.now(timezone.utc).isoformat())
        ),
        session_id=session_id,
        description="User correction keyword detected after tool execution",
    )
    return Pattern(
        pattern_type=PatternType.USER_CORRECTION,
        trigger="when user provides correction feedback",
        description="User correction keyword detected in message",
        evidence=(evidence,),
        domain="feedback",
        metadata=(("tool", tool_name),),
    )


def _find_recent_tool_completion(
    session_obs: list[dict[str, Any]], current_index: int, lookback_limit: int = 5
) -> dict[str, Any] | None:
    """Find the most recent tool completion before current index."""
    for j in range(current_index - 1, max(current_index - lookback_limit, -1), -1):
        prev_obs = session_obs[j]
        if prev_obs.get("event") == "tool_complete":
            return prev_obs
    return None


def _process_write_operation(
    obs: dict[str, Any], recent_writes: dict[str, dict[str, Any]]
) -> None:
    """Track a Write operation for later Edit detection."""
    file_path = _extract_file_path(obs.get("input", ""))
    if file_path:
        recent_writes[file_path] = obs


def _process_edit_operation(
    obs: dict[str, Any],
    session_id: str,
    recent_writes: dict[str, dict[str, Any]],
    patterns: list[Pattern],
) -> None:
    """Check if Edit follows a recent Write on the same file."""
    file_path = _extract_file_path(obs.get("input", ""))
    if not file_path:
        return
    if file_path not in recent_writes:
        return

    patterns.append(_create_write_edit_pattern(obs, session_id, file_path))
    del recent_writes[file_path]


def _process_user_message(
    obs: dict[str, Any],
    session_id: str,
    session_obs: list[dict[str, Any]],
    current_index: int,
    patterns: list[Pattern],
) -> None:
    """Check if user message contains correction keywords after tool execution."""
    content = obs.get("content", "")
    if not _has_correction_keywords(content):
        return

    recent_tool = _find_recent_tool_completion(session_obs, current_index)
    if not recent_tool:
        return

    tool_name = recent_tool.get("tool", "unknown")
    patterns.append(_create_correction_keyword_pattern(obs, session_id, tool_name))


def detect_user_corrections(observations: list[dict[str, Any]]) -> list[Pattern]:
    """Detect user correction patterns.

    Detects:
    - Write tool followed by Edit tool on the same file
    - Tool execution followed by user message with correction keywords

    Args:
        observations: List of observation dictionaries.

    Returns:
        List of detected Pattern objects.
    """
    patterns: list[Pattern] = []
    by_session = _group_by_session(observations)

    for session_id, session_obs in by_session.items():
        session_obs.sort(key=lambda x: x.get("timestamp", ""))
        recent_writes: dict[str, dict[str, Any]] = {}

        for i, obs in enumerate(session_obs):
            event = obs.get("event", "")
            tool = obs.get("tool", "")

            if tool == "Write" and event == "tool_start":
                _process_write_operation(obs, recent_writes)
            elif tool == "Edit" and event == "tool_start":
                _process_edit_operation(obs, session_id, recent_writes, patterns)
            elif event == "user_message":
                _process_user_message(obs, session_id, session_obs, i, patterns)

    return patterns


def _extract_error_type(error_output: str) -> str:
    """Extract the error type from error output text.

    Looks for patterns like 'ImportError', 'TypeError', 'SyntaxException', etc.
    Falls back to the first matching error keyword if no specific type found.
    """
    for keyword in ERROR_KEYWORDS:
        if keyword.lower() not in error_output.lower():
            continue

        # Try to extract specific error type (e.g., ImportError)
        match = re.search(r"(\w+Error|\w+Exception)", error_output)
        if match:
            return match.group(1)
        return keyword

    return "unknown"


def _create_error_resolution_pattern(
    obs: dict[str, Any], session_id: str, error_output: str
) -> Pattern:
    """Create a pattern for an error that was resolved."""
    error_type = _extract_error_type(error_output)
    max_error_output_length = 200

    evidence = Evidence(
        timestamp=datetime.fromisoformat(
            obs.get("timestamp", datetime.now(timezone.utc).isoformat())
        ),
        session_id=session_id,
        description=f"Error ({error_type}) resolved with successful execution",
    )
    return Pattern(
        pattern_type=PatternType.ERROR_RESOLUTION,
        trigger="when encountering errors",
        description=f"Error resolution: {error_type} was resolved",
        evidence=(evidence,),
        domain="error-handling",
        metadata=(
            ("error_type", error_type),
            ("error_output", error_output[:max_error_output_length]),
        ),
    )


def detect_error_resolutions(observations: list[dict[str, Any]]) -> list[Pattern]:
    """Detect error resolution patterns.

    Detects Bash tool errors followed by successful execution.

    Args:
        observations: List of observation dictionaries.

    Returns:
        List of detected Pattern objects.
    """
    patterns: list[Pattern] = []
    by_session = _group_by_session(observations)

    for session_id, session_obs in by_session.items():
        session_obs.sort(key=lambda x: x.get("timestamp", ""))
        recent_error: dict[str, Any] | None = None

        for obs in session_obs:
            event = obs.get("event", "")
            output = str(obs.get("output", ""))

            if event != "tool_complete":
                continue

            is_error = _has_error_keywords(output)

            if is_error:
                recent_error = obs
                continue

            # Success after error - create pattern
            if recent_error is None:
                continue

            error_output = str(recent_error.get("output", ""))
            patterns.append(
                _create_error_resolution_pattern(obs, session_id, error_output)
            )
            recent_error = None

    return patterns


def _is_contiguous_subsequence(shorter: tuple[str, ...], longer: tuple[str, ...]) -> bool:
    """Check if shorter is a contiguous subsequence of longer."""
    for i in range(len(longer) - len(shorter) + 1):
        if longer[i : i + len(shorter)] == shorter:
            return True
    return False


def _get_metadata_value(
    metadata: tuple[tuple[str, Any], ...], key: str, default: Any = None
) -> Any:
    """Extract a value from tuple-based metadata by key."""
    for k, v in metadata:
        if k == key:
            return v
    return default


def _extract_tool_sequences(
    by_session: dict[str, list[dict[str, Any]]]
) -> dict[str, list[str]]:
    """Extract tool sequences from grouped session observations."""
    session_sequences: dict[str, list[str]] = {}

    for session_id, session_obs in by_session.items():
        session_obs.sort(key=lambda x: x.get("timestamp", ""))
        tools = [
            obs.get("tool", "")
            for obs in session_obs
            if obs.get("event") == "tool_start" and obs.get("tool")
        ]
        if len(tools) >= MIN_WORKFLOW_SEQUENCE_LENGTH:
            session_sequences[session_id] = tools

    return session_sequences


def _find_sequence_occurrences(
    session_sequences: dict[str, list[str]]
) -> dict[tuple[str, ...], list[str]]:
    """Find all subsequences and which sessions they appear in."""
    sequence_occurrences: dict[tuple[str, ...], list[str]] = defaultdict(list)

    for session_id, tools in session_sequences.items():
        for length in range(MIN_WORKFLOW_SEQUENCE_LENGTH, len(tools) + 1):
            for start in range(len(tools) - length + 1):
                seq = tuple(tools[start : start + length])
                sequence_occurrences[seq].append(session_id)

    return sequence_occurrences


def _create_workflow_pattern(seq: tuple[str, ...], sessions: list[str]) -> Pattern:
    """Create a repeated workflow pattern from a sequence and sessions."""
    evidence_list = [
        Evidence(
            timestamp=datetime.now(timezone.utc),
            session_id=session_id,
            description=f"Workflow sequence detected: {' -> '.join(seq)}",
        )
        for session_id in sessions
    ]

    return Pattern(
        pattern_type=PatternType.REPEATED_WORKFLOW,
        trigger=f"when performing {seq[0].lower()} operations",
        description=f"Repeated workflow: {' -> '.join(seq)}",
        evidence=tuple(evidence_list),
        domain="workflow",
        metadata=(
            ("sequence", list(seq)),
            ("frequency", len(sessions)),
            ("sessions", sessions),
        ),
    )


def _remove_subset_patterns(patterns: list[Pattern]) -> list[Pattern]:
    """Remove patterns that are subsets of longer patterns."""
    if not patterns:
        return patterns

    # Sort by sequence length (longest first)
    patterns.sort(
        key=lambda p: len(_get_metadata_value(p.metadata, "sequence", [])),
        reverse=True,
    )

    unique_patterns: list[Pattern] = []
    seen_sequences: set[tuple[str, ...]] = set()

    for pattern in patterns:
        seq = tuple(_get_metadata_value(pattern.metadata, "sequence", []))

        is_subset = any(
            len(seq) < len(seen_seq)
            and _is_contiguous_subsequence(seq, seen_seq)
            for seen_seq in seen_sequences
        )

        if not is_subset:
            unique_patterns.append(pattern)
            seen_sequences.add(seq)

    return unique_patterns


def detect_repeated_workflows(observations: list[dict[str, Any]]) -> list[Pattern]:
    """Detect repeated workflow patterns.

    Detects same sequence of 3+ tools appearing in 2+ sessions.

    Args:
        observations: List of observation dictionaries.

    Returns:
        List of detected Pattern objects.
    """
    by_session = _group_by_session(observations)
    session_sequences = _extract_tool_sequences(by_session)
    sequence_occurrences = _find_sequence_occurrences(session_sequences)

    # Create patterns for sequences appearing in 2+ sessions
    patterns: list[Pattern] = []
    for seq, sessions in sequence_occurrences.items():
        unique_sessions = list(set(sessions))
        if len(unique_sessions) >= MIN_SESSIONS_FOR_PATTERN:
            patterns.append(_create_workflow_pattern(seq, unique_sessions))

    return _remove_subset_patterns(patterns)


def _count_tool_usage(
    by_session: dict[str, list[dict[str, Any]]]
) -> tuple[dict[str, set[str]], dict[str, int]]:
    """Count tool usage per session and total counts.

    Returns:
        Tuple of (tool -> sessions mapping, tool -> total count mapping).
    """
    tool_sessions: dict[str, set[str]] = defaultdict(set)
    tool_counts: dict[str, int] = defaultdict(int)

    for session_id, session_obs in by_session.items():
        for obs in session_obs:
            if obs.get("event") != "tool_start":
                continue
            tool = obs.get("tool", "")
            if not tool:
                continue
            tool_sessions[tool].add(session_id)
            tool_counts[tool] += 1

    return tool_sessions, tool_counts


def _create_tool_preference_pattern(
    tool: str, sessions: set[str], total_uses: int
) -> Pattern:
    """Create a tool preference pattern."""
    max_evidence_entries = 5
    evidence_list = [
        Evidence(
            timestamp=datetime.now(timezone.utc),
            session_id=session_id,
            description=f"Tool {tool} used in session",
        )
        for session_id in list(sessions)[:max_evidence_entries]
    ]

    return Pattern(
        pattern_type=PatternType.TOOL_PREFERENCE,
        trigger=f"when using {tool} tool",
        description=f"Consistent use of {tool} tool across {len(sessions)} sessions ({total_uses} total uses)",
        evidence=tuple(evidence_list),
        domain="tool-usage",
        metadata=(
            ("tool", tool),
            ("frequency", total_uses),
            ("sessions", len(sessions)),
        ),
    )


def detect_tool_preferences(observations: list[dict[str, Any]]) -> list[Pattern]:
    """Detect tool preference patterns.

    Detects consistent tool usage across multiple sessions.

    Args:
        observations: List of observation dictionaries.

    Returns:
        List of detected Pattern objects.
    """
    by_session = _group_by_session(observations)
    tool_sessions, tool_counts = _count_tool_usage(by_session)

    patterns: list[Pattern] = []
    for tool, sessions in tool_sessions.items():
        if len(sessions) < MIN_SESSIONS_FOR_PATTERN:
            continue

        total_uses = tool_counts[tool]
        if total_uses < MIN_TOOL_USES_FOR_PREFERENCE:
            continue

        patterns.append(_create_tool_preference_pattern(tool, sessions, total_uses))

    return patterns


def detect_all_patterns(file_path: Path) -> list[Pattern]:
    """Run all pattern detection algorithms.

    Args:
        file_path: Path to the observations.jsonl file.

    Returns:
        Combined list of detected patterns from all detectors.
    """
    observations = load_observations(file_path)

    if not observations:
        return []

    patterns: list[Pattern] = []

    # Run all detectors
    patterns.extend(detect_user_corrections(observations))
    patterns.extend(detect_error_resolutions(observations))
    patterns.extend(detect_repeated_workflows(observations))
    patterns.extend(detect_tool_preferences(observations))

    return patterns
