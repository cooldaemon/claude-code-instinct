"""Pattern merging for dual-approach detection.

This module merges patterns detected by algorithm-based and LLM-based approaches,
applying confidence adjustments based on detection source.
"""

from dataclasses import replace
from difflib import SequenceMatcher

from instincts.models import Pattern, PatternSource
from instincts.utils import normalize_trigger as _normalize_trigger_base

# Confidence boost when both approaches detect the same pattern
CONFIDENCE_BOOST_MATCHED: float = 0.1

# Confidence multiplier for LLM-only patterns (slight penalty)
LLM_ONLY_CONFIDENCE_MULTIPLIER: float = 0.9

# Similarity threshold for considering patterns as matching
SIMILARITY_THRESHOLD: float = 0.7


def _normalize_trigger(trigger: str) -> str:
    """Normalize a trigger string for comparison.

    Uses the base normalize_trigger and adds additional stripping.
    """
    return _normalize_trigger_base(trigger).strip()


def _calculate_trigger_similarity(t1: str, t2: str) -> float:
    """Calculate similarity between two trigger strings.

    Args:
        t1: First trigger string.
        t2: Second trigger string.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    normalized_t1 = _normalize_trigger(t1)
    normalized_t2 = _normalize_trigger(t2)
    return SequenceMatcher(None, normalized_t1, normalized_t2).ratio()


def _are_patterns_similar(p1: Pattern, p2: Pattern) -> bool:
    """Check if two patterns are similar enough to be merged.

    Patterns are similar if they have the same type and similar triggers.

    Args:
        p1: First pattern.
        p2: Second pattern.

    Returns:
        True if patterns are similar, False otherwise.
    """
    # Must have same pattern type
    if p1.pattern_type != p2.pattern_type:
        return False

    # Check trigger similarity
    similarity = _calculate_trigger_similarity(p1.trigger, p2.trigger)
    return similarity >= SIMILARITY_THRESHOLD


def _add_metadata(pattern: Pattern, key: str, value: str | float | int | bool) -> Pattern:
    """Add metadata to a pattern immutably.

    Args:
        pattern: The pattern to modify.
        key: Metadata key.
        value: Metadata value.

    Returns:
        New Pattern with added metadata.
    """
    existing_metadata = dict(pattern.metadata)
    existing_metadata[key] = value
    new_metadata = tuple(existing_metadata.items())
    return replace(pattern, metadata=new_metadata)


def _set_source_metadata(pattern: Pattern, source: PatternSource) -> Pattern:
    """Set the source metadata on a pattern.

    Args:
        pattern: The pattern to modify.
        source: Source enum value (PatternSource.ALGORITHM, LLM, or MERGED).

    Returns:
        New Pattern with updated source metadata.
    """
    existing_metadata = dict(pattern.metadata)
    existing_metadata["source"] = source.value
    new_metadata = tuple(existing_metadata.items())
    return replace(pattern, metadata=new_metadata)


def _merge_matching_patterns(algo_pattern: Pattern, llm_pattern: Pattern) -> Pattern:
    """Merge two matching patterns from different sources.

    Args:
        algo_pattern: Pattern from algorithm detection.
        llm_pattern: Pattern from LLM detection.

    Returns:
        Merged pattern with "merged" source and confidence boost.
    """
    # Start with the algorithm pattern (more deterministic)
    merged = _set_source_metadata(algo_pattern, PatternSource.MERGED)
    merged = _add_metadata(merged, "confidence_boost", CONFIDENCE_BOOST_MATCHED)

    # Combine evidence from both patterns
    combined_evidence = algo_pattern.evidence + llm_pattern.evidence
    merged = replace(merged, evidence=combined_evidence)

    return merged


def _mark_llm_only_pattern(pattern: Pattern) -> Pattern:
    """Mark a pattern as LLM-only with confidence multiplier.

    Args:
        pattern: LLM-detected pattern.

    Returns:
        Pattern with LLM source and confidence multiplier metadata.
    """
    marked = _set_source_metadata(pattern, PatternSource.LLM)
    marked = _add_metadata(marked, "confidence_multiplier", LLM_ONLY_CONFIDENCE_MULTIPLIER)
    return marked


def merge_patterns(
    algorithm_patterns: list[Pattern], llm_patterns: list[Pattern]
) -> list[Pattern]:
    """Merge patterns from algorithm and LLM detection.

    Patterns detected by both approaches get a confidence boost.
    LLM-only patterns get a confidence multiplier (slight penalty).
    Algorithm-only patterns are kept as-is.

    Args:
        algorithm_patterns: Patterns from algorithm-based detection.
        llm_patterns: Patterns from LLM-based detection.

    Returns:
        List of merged patterns with source metadata.
    """
    if not algorithm_patterns and not llm_patterns:
        return []

    merged_patterns: list[Pattern] = []
    used_llm_indices: set[int] = set()

    # Process algorithm patterns
    for algo_pattern in algorithm_patterns:
        matched_llm_idx: int | None = None

        # Find matching LLM pattern
        for idx, llm_pattern in enumerate(llm_patterns):
            if idx in used_llm_indices:
                continue

            if _are_patterns_similar(algo_pattern, llm_pattern):
                matched_llm_idx = idx
                break

        if matched_llm_idx is not None:
            # Merge the matching patterns
            merged = _merge_matching_patterns(algo_pattern, llm_patterns[matched_llm_idx])
            merged_patterns.append(merged)
            used_llm_indices.add(matched_llm_idx)
        else:
            # Keep algorithm-only pattern
            marked = _set_source_metadata(algo_pattern, PatternSource.ALGORITHM)
            merged_patterns.append(marked)

    # Add LLM-only patterns
    for idx, llm_pattern in enumerate(llm_patterns):
        if idx not in used_llm_indices:
            marked = _mark_llm_only_pattern(llm_pattern)
            merged_patterns.append(marked)

    return merged_patterns
