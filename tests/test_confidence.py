"""Tests for instincts.confidence module.

Tests cover:
- AC-6.1: Initial confidence based on evidence count
- AC-6.2: Confidence increase on confirming observation
- AC-6.3: Confidence decrease on contradicting observation
- AC-6.4: Confidence decay over time without observations
- AC-6.5: Dormant threshold at 0.2
- EC-5: Confidence clamping to [0.1, 0.95] range
"""

from datetime import datetime, timedelta, timezone

import pytest


class TestInitialConfidence:
    """Tests for calculate_initial_confidence function (AC-6.1)."""

    def test_1_to_2_observations_gives_0_3(self):
        """1-2 observations should give confidence of 0.3."""
        from instincts.confidence import calculate_initial_confidence

        assert calculate_initial_confidence(1) == 0.3
        assert calculate_initial_confidence(2) == 0.3

    def test_3_to_5_observations_gives_0_5(self):
        """3-5 observations should give confidence of 0.5."""
        from instincts.confidence import calculate_initial_confidence

        assert calculate_initial_confidence(3) == 0.5
        assert calculate_initial_confidence(4) == 0.5
        assert calculate_initial_confidence(5) == 0.5

    def test_6_to_10_observations_gives_0_7(self):
        """6-10 observations should give confidence of 0.7."""
        from instincts.confidence import calculate_initial_confidence

        assert calculate_initial_confidence(6) == 0.7
        assert calculate_initial_confidence(7) == 0.7
        assert calculate_initial_confidence(10) == 0.7

    def test_11_plus_observations_gives_0_85(self):
        """11+ observations should give confidence of 0.85."""
        from instincts.confidence import calculate_initial_confidence

        assert calculate_initial_confidence(11) == 0.85
        assert calculate_initial_confidence(15) == 0.85
        assert calculate_initial_confidence(100) == 0.85

    def test_0_observations_gives_minimum(self):
        """0 observations should give minimum confidence of 0.1."""
        from instincts.confidence import calculate_initial_confidence

        assert calculate_initial_confidence(0) == 0.1

    def test_negative_observations_raises_error(self):
        """Negative evidence count should raise ValueError."""
        from instincts.confidence import calculate_initial_confidence

        with pytest.raises(ValueError, match="non-negative"):
            calculate_initial_confidence(-1)


class TestAdjustConfidence:
    """Tests for adjust_confidence function (AC-6.2, AC-6.3, EC-5)."""

    def test_positive_delta_increases_confidence(self):
        """Positive delta should increase confidence (AC-6.2)."""
        from instincts.confidence import adjust_confidence

        result = adjust_confidence(0.5, 0.05)
        assert result == 0.55

    def test_negative_delta_decreases_confidence(self):
        """Negative delta should decrease confidence (AC-6.3)."""
        from instincts.confidence import adjust_confidence

        result = adjust_confidence(0.5, -0.1)
        assert result == 0.4

    def test_confirm_increase_is_0_05(self):
        """Confirming observation should increase by 0.05."""
        from instincts.confidence import CONFIRM_DELTA, adjust_confidence

        assert CONFIRM_DELTA == 0.05
        result = adjust_confidence(0.5, CONFIRM_DELTA)
        assert result == 0.55

    def test_contradict_decrease_is_0_1(self):
        """Contradicting observation should decrease by 0.1."""
        from instincts.confidence import CONTRADICT_DELTA, adjust_confidence

        assert CONTRADICT_DELTA == -0.1
        result = adjust_confidence(0.5, CONTRADICT_DELTA)
        assert result == 0.4

    def test_clamps_to_maximum_0_95(self):
        """Confidence should not exceed 0.95 (EC-5)."""
        from instincts.confidence import adjust_confidence

        result = adjust_confidence(0.92, 0.1)
        assert result == 0.95

    def test_clamps_to_minimum_0_1(self):
        """Confidence should not go below 0.1 (EC-5)."""
        from instincts.confidence import adjust_confidence

        result = adjust_confidence(0.15, -0.1)
        assert result == 0.1

    def test_near_maximum_only_increases_to_max(self):
        """Confidence at 0.94 + 0.05 should equal exactly 0.95."""
        from instincts.confidence import adjust_confidence

        result = adjust_confidence(0.94, 0.05)
        assert result == 0.95

    def test_near_minimum_only_decreases_to_min(self):
        """Confidence at 0.15 - 0.1 should equal exactly 0.1 (clamped)."""
        from instincts.confidence import adjust_confidence

        result = adjust_confidence(0.15, -0.1)
        assert result == 0.1


class TestCalculateDecay:
    """Tests for calculate_decay function (AC-6.4)."""

    def test_no_decay_within_first_week(self):
        """No decay should happen within first 7 days."""
        from instincts.confidence import calculate_decay

        last_observed = datetime.now(timezone.utc) - timedelta(days=3)
        current_time = datetime.now(timezone.utc)

        decay = calculate_decay(last_observed, current_time)
        assert decay == 0.0

    def test_decay_0_02_per_week(self):
        """Decay should be 0.02 per week after first week (AC-6.4)."""
        from instincts.confidence import calculate_decay

        current_time = datetime.now(timezone.utc)
        last_observed = current_time - timedelta(days=14)  # 2 weeks

        decay = calculate_decay(last_observed, current_time)
        assert decay == pytest.approx(0.04)  # 2 weeks * 0.02

    def test_decay_accumulates_over_weeks(self):
        """Decay should accumulate over multiple weeks."""
        from instincts.confidence import calculate_decay

        current_time = datetime.now(timezone.utc)
        last_observed = current_time - timedelta(days=35)  # 5 weeks

        decay = calculate_decay(last_observed, current_time)
        assert decay == pytest.approx(0.1)  # 5 weeks * 0.02

    def test_decay_with_partial_weeks(self):
        """Decay should only count complete weeks."""
        from instincts.confidence import calculate_decay

        current_time = datetime.now(timezone.utc)
        last_observed = current_time - timedelta(days=20)  # 2.86 weeks -> 2 complete weeks

        decay = calculate_decay(last_observed, current_time)
        assert decay == pytest.approx(0.04)  # 2 weeks * 0.02


class TestApplyDecayToInstinct:
    """Tests for apply_decay_to_instinct function."""

    def test_returns_new_instinct_with_decayed_confidence(self):
        """Should return a new instinct with reduced confidence."""
        from instincts.confidence import apply_decay_to_instinct
        from instincts.models import Instinct

        old_time = datetime.now(timezone.utc) - timedelta(days=21)  # 3 weeks
        instinct = Instinct(
            id="test",
            trigger="test",
            confidence=0.7,
            domain="general",
            source="test",
            evidence_count=5,
            created_at=old_time,
            updated_at=old_time,
            content="test",
            last_observed=old_time,
        )

        decayed = apply_decay_to_instinct(instinct)

        # 3 weeks * 0.02 = 0.06 decay
        assert decayed.confidence == pytest.approx(0.64)
        assert decayed.id == instinct.id  # Other fields preserved

    def test_does_not_decay_below_minimum(self):
        """Decayed confidence should not go below 0.1."""
        from instincts.confidence import apply_decay_to_instinct
        from instincts.models import Instinct

        old_time = datetime.now(timezone.utc) - timedelta(days=365)  # 1 year
        instinct = Instinct(
            id="test",
            trigger="test",
            confidence=0.3,
            domain="general",
            source="test",
            evidence_count=2,
            created_at=old_time,
            updated_at=old_time,
            content="test",
            last_observed=old_time,
        )

        decayed = apply_decay_to_instinct(instinct)

        assert decayed.confidence == 0.1

    def test_uses_updated_at_when_last_observed_is_none(self):
        """Should use updated_at when last_observed is None."""
        from instincts.confidence import apply_decay_to_instinct
        from instincts.models import Instinct

        old_time = datetime.now(timezone.utc) - timedelta(days=14)  # 2 weeks
        instinct = Instinct(
            id="test",
            trigger="test",
            confidence=0.7,
            domain="general",
            source="test",
            evidence_count=5,
            created_at=old_time,
            updated_at=old_time,
            content="test",
            last_observed=None,  # Use updated_at
        )

        decayed = apply_decay_to_instinct(instinct)

        # 2 weeks * 0.02 = 0.04 decay
        assert decayed.confidence == pytest.approx(0.66)

    def test_does_not_modify_original_instinct(self):
        """Original instinct should remain unchanged."""
        from instincts.confidence import apply_decay_to_instinct
        from instincts.models import Instinct

        old_time = datetime.now(timezone.utc) - timedelta(days=14)
        original = Instinct(
            id="test",
            trigger="test",
            confidence=0.7,
            domain="general",
            source="test",
            evidence_count=5,
            created_at=old_time,
            updated_at=old_time,
            content="test",
            last_observed=old_time,
        )

        apply_decay_to_instinct(original)

        assert original.confidence == 0.7  # Unchanged


class TestDormantThreshold:
    """Tests for dormant threshold behavior (AC-6.5)."""

    def test_below_0_2_returns_dormant_status(self):
        """Instinct with confidence < 0.2 should be marked dormant."""
        from instincts.confidence import check_dormant_status

        assert check_dormant_status(0.19) == "dormant"
        assert check_dormant_status(0.1) == "dormant"

    def test_at_or_above_0_2_returns_active_status(self):
        """Instinct with confidence >= 0.2 should remain active."""
        from instincts.confidence import check_dormant_status

        assert check_dormant_status(0.2) == "active"
        assert check_dormant_status(0.5) == "active"
        assert check_dormant_status(0.95) == "active"


class TestConfidenceConstants:
    """Tests for confidence module constants."""

    def test_min_confidence_is_0_1(self):
        """MIN_CONFIDENCE should be 0.1."""
        from instincts.confidence import MIN_CONFIDENCE

        assert MIN_CONFIDENCE == 0.1

    def test_max_confidence_is_0_95(self):
        """MAX_CONFIDENCE should be 0.95."""
        from instincts.confidence import MAX_CONFIDENCE

        assert MAX_CONFIDENCE == 0.95

    def test_dormant_threshold_is_0_2(self):
        """DORMANT_THRESHOLD should be 0.2."""
        from instincts.confidence import DORMANT_THRESHOLD

        assert DORMANT_THRESHOLD == 0.2

    def test_decay_per_week_is_0_02(self):
        """DECAY_PER_WEEK should be 0.02."""
        from instincts.confidence import DECAY_PER_WEEK

        assert DECAY_PER_WEEK == 0.02
