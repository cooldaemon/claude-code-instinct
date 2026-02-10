"""Tests for instincts.pattern_merger module.

Tests cover:
- Pattern merging from algorithm and LLM sources
- Confidence boosting for matched patterns
- LLM-only pattern confidence reduction
- Source metadata handling
"""

from datetime import datetime, timezone

from instincts.models import Evidence, Pattern, PatternType


def _create_pattern(
    pattern_type: PatternType,
    trigger: str,
    description: str,
    domain: str = "general",
    source: str = "algorithm",
) -> Pattern:
    """Helper to create a test pattern."""
    evidence = Evidence(
        timestamp=datetime.now(timezone.utc),
        session_id="test-session",
        description="Test evidence",
    )
    return Pattern(
        pattern_type=pattern_type,
        trigger=trigger,
        description=description,
        evidence=(evidence,),
        domain=domain,
        metadata=(("source", source),),
    )


class TestMergePatterns:
    """Tests for merge_patterns function (AC-R2.4, AC-R2.7, AC-R2.8)."""

    def test_boosts_confidence_when_both_detect_same_pattern(self):
        """AC-R2.4: Should boost confidence by +0.1 when both detect same pattern."""
        from instincts.pattern_merger import merge_patterns

        algo_patterns = [
            _create_pattern(
                PatternType.USER_CORRECTION,
                "when editing files",
                "User prefers small edits",
                source="algorithm",
            )
        ]

        llm_patterns = [
            _create_pattern(
                PatternType.USER_CORRECTION,
                "when editing files",
                "User prefers smaller edits",
                source="llm",
            )
        ]

        merged = merge_patterns(algo_patterns, llm_patterns)

        # Should have one merged pattern
        assert len(merged) == 1
        merged_pattern = merged[0]

        # Metadata should indicate merged source
        metadata_dict = dict(merged_pattern.metadata)
        assert metadata_dict.get("source") == "merged"

        # Should have confidence_boost metadata
        assert metadata_dict.get("confidence_boost") == 0.1

    def test_reduces_confidence_for_llm_only_patterns(self):
        """AC-R2.7: LLM-only pattern confidence should be multiplied by 0.9."""
        from instincts.pattern_merger import merge_patterns

        algo_patterns: list[Pattern] = []

        llm_patterns = [
            _create_pattern(
                PatternType.USER_CORRECTION,
                "when editing files",
                "User prefers small edits",
                source="llm",
            )
        ]

        merged = merge_patterns(algo_patterns, llm_patterns)

        assert len(merged) == 1
        merged_pattern = merged[0]

        # Metadata should indicate llm source
        metadata_dict = dict(merged_pattern.metadata)
        assert metadata_dict.get("source") == "llm"

        # Should have confidence_multiplier metadata
        assert metadata_dict.get("confidence_multiplier") == 0.9

    def test_keeps_algorithm_only_patterns_unchanged(self):
        """Algorithm-only patterns should be kept as-is."""
        from instincts.pattern_merger import merge_patterns

        algo_patterns = [
            _create_pattern(
                PatternType.USER_CORRECTION,
                "when editing files",
                "User prefers small edits",
                source="algorithm",
            )
        ]

        llm_patterns: list[Pattern] = []

        merged = merge_patterns(algo_patterns, llm_patterns)

        assert len(merged) == 1
        merged_pattern = merged[0]

        # Metadata should indicate algorithm source
        metadata_dict = dict(merged_pattern.metadata)
        assert metadata_dict.get("source") == "algorithm"

    def test_includes_source_metadata(self):
        """AC-R2.8: Merged results should include detection source metadata."""
        from instincts.pattern_merger import merge_patterns

        algo_patterns = [
            _create_pattern(
                PatternType.USER_CORRECTION,
                "when editing",
                "Edit preference",
                source="algorithm",
            )
        ]

        llm_patterns = [
            _create_pattern(
                PatternType.ERROR_RESOLUTION,
                "when build fails",
                "Fix imports",
                source="llm",
            )
        ]

        merged = merge_patterns(algo_patterns, llm_patterns)

        assert len(merged) == 2

        # Check each pattern has source metadata
        for pattern in merged:
            metadata_dict = dict(pattern.metadata)
            assert "source" in metadata_dict
            assert metadata_dict["source"] in ("algorithm", "llm", "merged")


class TestPatternSimilarity:
    """Tests for pattern similarity calculation."""

    def test_patterns_with_same_trigger_are_similar(self):
        """Patterns with same trigger should be considered similar."""
        from instincts.pattern_merger import _are_patterns_similar

        p1 = _create_pattern(
            PatternType.USER_CORRECTION,
            "when editing files",
            "Description 1",
        )

        p2 = _create_pattern(
            PatternType.USER_CORRECTION,
            "when editing files",
            "Different description",
        )

        assert _are_patterns_similar(p1, p2) is True

    def test_patterns_with_different_types_are_not_similar(self):
        """Patterns with different types should not be similar."""
        from instincts.pattern_merger import _are_patterns_similar

        p1 = _create_pattern(
            PatternType.USER_CORRECTION,
            "when editing files",
            "Description 1",
        )

        p2 = _create_pattern(
            PatternType.ERROR_RESOLUTION,
            "when editing files",
            "Description 1",
        )

        assert _are_patterns_similar(p1, p2) is False

    def test_patterns_with_very_different_triggers_are_not_similar(self):
        """Patterns with very different triggers should not be similar."""
        from instincts.pattern_merger import _are_patterns_similar

        p1 = _create_pattern(
            PatternType.USER_CORRECTION,
            "when editing files",
            "Description 1",
        )

        p2 = _create_pattern(
            PatternType.USER_CORRECTION,
            "when running tests",
            "Description 1",
        )

        assert _are_patterns_similar(p1, p2) is False


class TestMergeEmptyPatterns:
    """Tests for merging with empty pattern lists."""

    def test_returns_empty_when_both_empty(self):
        """Should return empty list when both inputs are empty."""
        from instincts.pattern_merger import merge_patterns

        merged = merge_patterns([], [])
        assert merged == []

    def test_returns_algorithm_patterns_when_llm_empty(self):
        """Should return algorithm patterns when LLM patterns are empty."""
        from instincts.pattern_merger import merge_patterns

        algo_patterns = [
            _create_pattern(
                PatternType.USER_CORRECTION,
                "when editing",
                "Edit preference",
                source="algorithm",
            )
        ]

        merged = merge_patterns(algo_patterns, [])

        assert len(merged) == 1
        assert dict(merged[0].metadata).get("source") == "algorithm"

    def test_returns_llm_patterns_when_algorithm_empty(self):
        """Should return LLM patterns (with multiplier) when algorithm patterns are empty."""
        from instincts.pattern_merger import merge_patterns

        llm_patterns = [
            _create_pattern(
                PatternType.ERROR_RESOLUTION,
                "when build fails",
                "Fix imports",
                source="llm",
            )
        ]

        merged = merge_patterns([], llm_patterns)

        assert len(merged) == 1
        metadata_dict = dict(merged[0].metadata)
        assert metadata_dict.get("source") == "llm"
        assert metadata_dict.get("confidence_multiplier") == 0.9


class TestCalculateConfidenceBoost:
    """Tests for confidence boost calculation."""

    def test_confidence_boost_is_0_1(self):
        """Merged pattern confidence boost should be 0.1."""
        from instincts.pattern_merger import CONFIDENCE_BOOST_MATCHED

        assert CONFIDENCE_BOOST_MATCHED == 0.1

    def test_llm_only_multiplier_is_0_9(self):
        """LLM-only pattern confidence multiplier should be 0.9."""
        from instincts.pattern_merger import LLM_ONLY_CONFIDENCE_MULTIPLIER

        assert LLM_ONLY_CONFIDENCE_MULTIPLIER == 0.9
