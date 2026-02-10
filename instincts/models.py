"""Data models for Instinct-Based Learning.

This module contains the core data structures:
- PatternType: Enum for different pattern types
- Evidence: Evidence of a detected pattern
- Pattern: A detected behavioral pattern
- Instinct: A learned instinct with confidence scoring
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

# Valid status values for Instinct
InstinctStatus = Literal["active", "dormant"]


class PatternType(Enum):
    """Types of patterns that can be detected."""

    USER_CORRECTION = "user_correction"
    ERROR_RESOLUTION = "error_resolution"
    REPEATED_WORKFLOW = "repeated_workflow"
    TOOL_PREFERENCE = "tool_preference"


class PatternSource(Enum):
    """Source of pattern detection for dual-approach analysis."""

    ALGORITHM = "algorithm"  # Detected by algorithm-based detection
    LLM = "llm"  # Detected by LLM-based detection
    MERGED = "merged"  # Detected by both approaches


@dataclass(frozen=True)
class Evidence:
    """Evidence of a detected pattern.

    Attributes:
        timestamp: When the evidence was observed.
        session_id: The session in which the evidence was observed.
        description: Human-readable description of the evidence.
        observation_ids: Optional tuple of observation IDs that contributed to this evidence.
    """

    timestamp: datetime
    session_id: str
    description: str
    observation_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Pattern:
    """A detected behavioral pattern.

    Attributes:
        pattern_type: The type of pattern detected.
        trigger: The condition that triggers this pattern.
        description: Human-readable description of the pattern.
        evidence: Tuple of Evidence objects supporting this pattern.
        domain: The domain this pattern belongs to (default: "general").
        metadata: Additional metadata as tuple of key-value pairs (immutable).
                  Example: (("key1", "value1"), ("key2", "value2"))
    """

    pattern_type: PatternType
    trigger: str
    description: str
    evidence: tuple[Evidence, ...]
    domain: str = "general"
    metadata: tuple[tuple[str, Any], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Instinct:
    """A learned instinct with confidence scoring.

    Attributes:
        id: Unique identifier for the instinct (kebab-case).
        trigger: The condition that triggers this instinct.
        confidence: Confidence score between 0.1 and 0.95.
        domain: The domain this instinct belongs to.
        source: How this instinct was created (e.g., "pattern-detection").
        evidence_count: Number of observations supporting this instinct.
        created_at: When the instinct was created.
        updated_at: When the instinct was last updated.
        content: The markdown content of the instinct.
        source_file: Optional path to the source file.
        status: Status of the instinct ("active" or "dormant").
        last_observed: Optional timestamp of last confirming observation.
    """

    id: str
    trigger: str
    confidence: float
    domain: str
    source: str
    evidence_count: int
    created_at: datetime
    updated_at: datetime
    content: str
    source_file: str | None = None
    status: InstinctStatus = "active"
    last_observed: datetime | None = None

    def with_confidence(self, new_confidence: float) -> "Instinct":
        """Return a new Instinct with updated confidence and timestamp.

        Args:
            new_confidence: The new confidence value.

        Returns:
            A new Instinct instance with the updated confidence.
        """
        return replace(
            self,
            confidence=new_confidence,
            updated_at=datetime.now(timezone.utc),
        )

    def with_status(self, new_status: InstinctStatus) -> "Instinct":
        """Return a new Instinct with updated status.

        Args:
            new_status: The new status ("active" or "dormant").

        Returns:
            A new Instinct instance with the updated status.
        """
        return replace(
            self,
            status=new_status,
            updated_at=datetime.now(timezone.utc),
        )
