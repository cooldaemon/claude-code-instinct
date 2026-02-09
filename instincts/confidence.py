"""Confidence scoring system for Instinct-Based Learning.

This module provides functions for:
- Calculating initial confidence based on evidence count
- Adjusting confidence for confirming/contradicting observations
- Calculating and applying confidence decay over time
- Determining dormant status based on confidence threshold
"""

from datetime import datetime, timezone

from instincts.models import Instinct, InstinctStatus

# Confidence bounds
MIN_CONFIDENCE: float = 0.1
MAX_CONFIDENCE: float = 0.95

# Confidence adjustments
CONFIRM_DELTA: float = 0.05
CONTRADICT_DELTA: float = -0.1

# Decay settings
DECAY_PER_WEEK: float = 0.02
DAYS_PER_WEEK: int = 7

# Dormant threshold
DORMANT_THRESHOLD: float = 0.2


def calculate_initial_confidence(evidence_count: int) -> float:
    """Calculate initial confidence based on evidence count.

    Args:
        evidence_count: Number of observations supporting the pattern.

    Returns:
        Initial confidence value between MIN_CONFIDENCE and 0.85.

    Raises:
        ValueError: If evidence_count is negative.
    """
    if evidence_count < 0:
        raise ValueError("Evidence count must be non-negative")

    if evidence_count == 0:
        return MIN_CONFIDENCE
    elif evidence_count <= 2:
        return 0.3
    elif evidence_count <= 5:
        return 0.5
    elif evidence_count <= 10:
        return 0.7
    else:
        return 0.85


def adjust_confidence(current: float, delta: float) -> float:
    """Adjust confidence by delta, clamping to valid range.

    Args:
        current: Current confidence value.
        delta: Amount to adjust (positive or negative).

    Returns:
        New confidence value clamped to [MIN_CONFIDENCE, MAX_CONFIDENCE].
    """
    new_confidence = current + delta
    return max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, new_confidence))


def calculate_decay(last_observed: datetime, current_time: datetime) -> float:
    """Calculate confidence decay based on time since last observation.

    Decay is 0.02 per week, starting after the first week.

    Args:
        last_observed: Timestamp of last observation.
        current_time: Current timestamp.

    Returns:
        Total decay amount (always non-negative).
    """
    days_elapsed = (current_time - last_observed).days
    weeks_elapsed = days_elapsed // DAYS_PER_WEEK

    # No decay within first week
    if weeks_elapsed <= 0:
        return 0.0

    return weeks_elapsed * DECAY_PER_WEEK


def apply_decay_to_instinct(
    instinct: Instinct, current_time: datetime | None = None
) -> Instinct:
    """Apply confidence decay to an instinct.

    Args:
        instinct: The instinct to decay.
        current_time: Optional current time (defaults to now).

    Returns:
        A new Instinct with decayed confidence.
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    # Use last_observed if available, otherwise use updated_at
    last_observed = instinct.last_observed or instinct.updated_at

    decay = calculate_decay(last_observed, current_time)

    if decay == 0.0:
        return instinct

    new_confidence = adjust_confidence(instinct.confidence, -decay)
    return instinct.with_confidence(new_confidence)


def check_dormant_status(confidence: float) -> InstinctStatus:
    """Check if confidence level indicates dormant status.

    Args:
        confidence: Current confidence value.

    Returns:
        "dormant" if confidence < DORMANT_THRESHOLD, "active" otherwise.
    """
    if confidence < DORMANT_THRESHOLD:
        return "dormant"
    return "active"
