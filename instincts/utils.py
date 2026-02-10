"""Shared utility functions for Instinct-Based Learning."""

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
