"""Shared utility functions for Instinct-Based Learning."""

import os
import re


def sanitize_id(raw_id: str, allow_dots: bool = False) -> str:
    """Sanitize an ID or filename to prevent path traversal attacks.

    This function consolidates sanitization logic used in agent.py and evolution.py
    to ensure consistent security handling (CR-003).

    Args:
        raw_id: The raw ID or filename string.
        allow_dots: If True, preserve dots (for filenames). Default False (for IDs).

    Returns:
        A safe string containing only alphanumeric characters, dash, and underscore.
        Returns 'unnamed' if input is empty or fully invalid.
    """
    # Get just the basename to prevent path traversal
    safe_id = os.path.basename(raw_id)

    # Defense in depth: handle edge cases where basename may not fully sanitize
    # (e.g., different OS path conventions, unusual characters)
    if allow_dots:
        # For filenames, keep alphanumeric, dash, underscore, and dot
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "-", safe_id)
    else:
        # For IDs, keep only alphanumeric, dash, underscore
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "-", safe_id)

    # Remove leading/trailing dashes and collapse multiple dashes
    safe_id = re.sub(r"-+", "-", safe_id).strip("-")

    # Ensure we have a valid result
    if not safe_id:
        safe_id = "unnamed"

    return safe_id


# Common stop words to remove when normalizing trigger strings
TRIGGER_STOP_WORDS: tuple[str, ...] = (
    "when",
    "creating",
    "writing",
    "adding",
    "implementing",
    "testing",
)


def normalize_trigger(trigger: str) -> str:
    """Normalize a trigger string for comparison and clustering.

    Removes common stop words and normalizes to lowercase.

    Args:
        trigger: The trigger string to normalize.

    Returns:
        Normalized trigger string.
    """
    normalized = trigger.lower()
    for keyword in TRIGGER_STOP_WORDS:
        normalized = normalized.replace(keyword, "").strip()
    return normalized
