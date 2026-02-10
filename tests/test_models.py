"""Tests for instincts.models module.

Tests cover:
- PatternType enum values
- Evidence dataclass
- Pattern dataclass
- Instinct dataclass with all fields including timestamps
"""

from datetime import datetime, timezone

import pytest

from instincts.models import Evidence, Instinct, Pattern, PatternSource, PatternType


class TestPatternType:
    """Tests for PatternType enum."""

    def test_has_user_correction_type(self):
        """PatternType should have USER_CORRECTION value."""
        assert hasattr(PatternType, "USER_CORRECTION")
        assert PatternType.USER_CORRECTION.value == "user_correction"

    def test_has_error_resolution_type(self):
        """PatternType should have ERROR_RESOLUTION value."""
        assert hasattr(PatternType, "ERROR_RESOLUTION")
        assert PatternType.ERROR_RESOLUTION.value == "error_resolution"

    def test_has_repeated_workflow_type(self):
        """PatternType should have REPEATED_WORKFLOW value."""
        
        assert hasattr(PatternType, "REPEATED_WORKFLOW")
        assert PatternType.REPEATED_WORKFLOW.value == "repeated_workflow"

    def test_has_tool_preference_type(self):
        """PatternType should have TOOL_PREFERENCE value."""
        
        assert hasattr(PatternType, "TOOL_PREFERENCE")
        assert PatternType.TOOL_PREFERENCE.value == "tool_preference"


class TestEvidence:
    """Tests for Evidence dataclass."""

    def test_evidence_has_required_fields(self):
        """Evidence should have timestamp, session_id, description fields."""
        
        ts = datetime.now(timezone.utc)
        evidence = Evidence(
            timestamp=ts,
            session_id="session-123",
            description="User corrected function name",
        )

        assert evidence.timestamp == ts
        assert evidence.session_id == "session-123"
        assert evidence.description == "User corrected function name"

    def test_evidence_is_frozen(self):
        """Evidence should be immutable (frozen)."""
        
        evidence = Evidence(
            timestamp=datetime.now(timezone.utc),
            session_id="session-123",
            description="test",
        )

        with pytest.raises(AttributeError):
            evidence.description = "modified"  # type: ignore[misc]

    def test_evidence_optional_observation_ids(self):
        """Evidence should have optional observation_ids field."""
        
        # Without observation_ids
        evidence1 = Evidence(
            timestamp=datetime.now(timezone.utc),
            session_id="session-123",
            description="test",
        )
        assert evidence1.observation_ids == ()

        # With observation_ids
        evidence2 = Evidence(
            timestamp=datetime.now(timezone.utc),
            session_id="session-123",
            description="test",
            observation_ids=("obs-1", "obs-2"),
        )
        assert evidence2.observation_ids == ("obs-1", "obs-2")


class TestPattern:
    """Tests for Pattern dataclass."""

    def test_pattern_has_required_fields(self):
        """Pattern should have pattern_type, trigger, evidence fields."""
        
        evidence = Evidence(
            timestamp=datetime.now(timezone.utc),
            session_id="session-123",
            description="test evidence",
        )
        pattern = Pattern(
            pattern_type=PatternType.USER_CORRECTION,
            trigger="when writing function names",
            description="User prefers snake_case for function names",
            evidence=(evidence,),
        )

        assert pattern.pattern_type == PatternType.USER_CORRECTION
        assert pattern.trigger == "when writing function names"
        assert pattern.description == "User prefers snake_case for function names"
        assert len(pattern.evidence) == 1
        assert pattern.evidence[0] == evidence

    def test_pattern_is_frozen(self):
        """Pattern should be immutable (frozen)."""
        
        pattern = Pattern(
            pattern_type=PatternType.USER_CORRECTION,
            trigger="test",
            description="test",
            evidence=(
                Evidence(
                    timestamp=datetime.now(timezone.utc),
                    session_id="s1",
                    description="e1",
                ),
            ),
        )

        with pytest.raises(AttributeError):
            pattern.trigger = "modified"  # type: ignore[misc]

    def test_pattern_optional_domain(self):
        """Pattern should have optional domain field."""
        
        # Without domain (default)
        pattern1 = Pattern(
            pattern_type=PatternType.USER_CORRECTION,
            trigger="test",
            description="test",
            evidence=(
                Evidence(
                    timestamp=datetime.now(timezone.utc),
                    session_id="s1",
                    description="e1",
                ),
            ),
        )
        assert pattern1.domain == "general"

        # With domain
        pattern2 = Pattern(
            pattern_type=PatternType.USER_CORRECTION,
            trigger="test",
            description="test",
            evidence=(
                Evidence(
                    timestamp=datetime.now(timezone.utc),
                    session_id="s1",
                    description="e1",
                ),
            ),
            domain="code-style",
        )
        assert pattern2.domain == "code-style"

    def test_pattern_optional_metadata(self):
        """Pattern should have optional metadata field for extra context."""

        pattern = Pattern(
            pattern_type=PatternType.ERROR_RESOLUTION,
            trigger="when build fails",
            description="Fix imports for missing module",
            evidence=(
                Evidence(
                    timestamp=datetime.now(timezone.utc),
                    session_id="s1",
                    description="e1",
                ),
            ),
            metadata=(("error_type", "ImportError"), ("resolution", "add import")),
        )

        assert pattern.metadata == (("error_type", "ImportError"), ("resolution", "add import"))

    def test_pattern_metadata_defaults_to_empty(self):
        """Pattern metadata should default to empty tuple when not provided."""

        pattern = Pattern(
            pattern_type=PatternType.USER_CORRECTION,
            trigger="test",
            description="test",
            evidence=(
                Evidence(
                    timestamp=datetime.now(timezone.utc),
                    session_id="s1",
                    description="e1",
                ),
            ),
        )

        # Metadata should be an immutable tuple of key-value pairs
        assert pattern.metadata == ()

    def test_pattern_metadata_is_immutable_tuple(self):
        """Pattern metadata should be a tuple of key-value pairs for immutability."""

        pattern = Pattern(
            pattern_type=PatternType.ERROR_RESOLUTION,
            trigger="when build fails",
            description="Fix imports for missing module",
            evidence=(
                Evidence(
                    timestamp=datetime.now(timezone.utc),
                    session_id="s1",
                    description="e1",
                ),
            ),
            metadata=(("error_type", "ImportError"), ("resolution", "add import")),
        )

        assert pattern.metadata == (("error_type", "ImportError"), ("resolution", "add import"))
        assert isinstance(pattern.metadata, tuple)


class TestInstinct:
    """Tests for Instinct dataclass (extended from existing cli.Instinct)."""

    def test_instinct_has_all_required_fields(self):
        """Instinct should have id, trigger, confidence, domain, etc."""
        
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="prefer-snake-case",
            trigger="when naming functions",
            confidence=0.7,
            domain="code-style",
            source="pattern-detection",
            evidence_count=5,
            created_at=ts,
            updated_at=ts,
            content="Use snake_case for function names.",
        )

        assert instinct.id == "prefer-snake-case"
        assert instinct.trigger == "when naming functions"
        assert instinct.confidence == 0.7
        assert instinct.domain == "code-style"
        assert instinct.source == "pattern-detection"
        assert instinct.evidence_count == 5
        assert instinct.created_at == ts
        assert instinct.updated_at == ts
        assert instinct.content == "Use snake_case for function names."

    def test_instinct_is_frozen(self):
        """Instinct should be immutable (frozen)."""
        
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test",
            trigger="test",
            confidence=0.5,
            domain="general",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        with pytest.raises(AttributeError):
            instinct.confidence = 0.8  # type: ignore[misc]

    def test_instinct_optional_source_file(self):
        """Instinct should have optional source_file for tracking origin."""
        
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test",
            trigger="test",
            confidence=0.5,
            domain="general",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
            source_file="/path/to/file.md",
        )

        assert instinct.source_file == "/path/to/file.md"

    def test_instinct_source_file_defaults_to_none(self):
        """Instinct source_file should default to None."""
        
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test",
            trigger="test",
            confidence=0.5,
            domain="general",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        assert instinct.source_file is None

    def test_instinct_optional_status(self):
        """Instinct should have optional status field (active/dormant)."""
        
        ts = datetime.now(timezone.utc)
        # Default status
        instinct1 = Instinct(
            id="test",
            trigger="test",
            confidence=0.5,
            domain="general",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )
        assert instinct1.status == "active"

        # Explicit status
        instinct2 = Instinct(
            id="test",
            trigger="test",
            confidence=0.15,
            domain="general",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
            status="dormant",
        )
        assert instinct2.status == "dormant"

    def test_instinct_optional_last_observed(self):
        """Instinct should have optional last_observed timestamp for decay."""
        
        ts = datetime.now(timezone.utc)
        last_obs = datetime(2026, 1, 1, tzinfo=timezone.utc)

        instinct = Instinct(
            id="test",
            trigger="test",
            confidence=0.5,
            domain="general",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
            last_observed=last_obs,
        )

        assert instinct.last_observed == last_obs

    def test_instinct_last_observed_defaults_to_updated_at(self):
        """Instinct last_observed should default to None (use updated_at for decay)."""
        
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test",
            trigger="test",
            confidence=0.5,
            domain="general",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        assert instinct.last_observed is None


class TestInstinctWithConfidence:
    """Tests for Instinct.with_confidence method for immutable updates."""

    def test_with_confidence_returns_new_instinct(self):
        """with_confidence should return a new Instinct with updated confidence."""
        
        ts = datetime.now(timezone.utc)
        original = Instinct(
            id="test",
            trigger="test",
            confidence=0.5,
            domain="general",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        updated = original.with_confidence(0.7)

        assert updated.confidence == 0.7
        assert original.confidence == 0.5  # Original unchanged
        assert updated.id == original.id  # Other fields preserved

    def test_with_confidence_updates_timestamp(self):
        """with_confidence should update updated_at timestamp."""
        
        old_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        original = Instinct(
            id="test",
            trigger="test",
            confidence=0.5,
            domain="general",
            source="test",
            evidence_count=1,
            created_at=old_ts,
            updated_at=old_ts,
            content="test",
        )

        updated = original.with_confidence(0.7)

        assert updated.updated_at > old_ts


class TestInstinctWithStatus:
    """Tests for Instinct.with_status method for status transitions."""

    def test_with_status_returns_new_instinct(self):
        """with_status should return a new Instinct with updated status."""
        
        ts = datetime.now(timezone.utc)
        original = Instinct(
            id="test",
            trigger="test",
            confidence=0.15,
            domain="general",
            source="test",
            evidence_count=1,
            created_at=ts,
            updated_at=ts,
            content="test",
            status="active",
        )

        updated = original.with_status("dormant")

        assert updated.status == "dormant"
        assert original.status == "active"  # Original unchanged


class TestPatternSource:
    """Tests for PatternSource enum for dual-approach detection."""

    def test_has_algorithm_source(self):
        """PatternSource should have ALGORITHM value."""
        assert hasattr(PatternSource, "ALGORITHM")
        assert PatternSource.ALGORITHM.value == "algorithm"

    def test_has_llm_source(self):
        """PatternSource should have LLM value."""
        assert hasattr(PatternSource, "LLM")
        assert PatternSource.LLM.value == "llm"

    def test_has_merged_source(self):
        """PatternSource should have MERGED value for patterns detected by both."""
        assert hasattr(PatternSource, "MERGED")
        assert PatternSource.MERGED.value == "merged"
