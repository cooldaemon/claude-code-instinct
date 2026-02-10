"""Tests for instincts.utils module.

Tests cover:
- normalize_trigger function for trigger string normalization
"""


class TestNormalizeTrigger:
    """Tests for normalize_trigger function."""

    def test_removes_common_stop_words(self):
        """Should remove common stop words from trigger strings."""
        from instincts.utils import normalize_trigger

        result = normalize_trigger("when creating files")
        assert "when" not in result.lower()
        assert "creating" not in result.lower()
        assert "files" in result.lower()

    def test_lowercases_trigger(self):
        """Should lowercase the trigger string."""
        from instincts.utils import normalize_trigger

        result = normalize_trigger("Writing Code")
        assert result == result.lower()

    def test_strips_whitespace(self):
        """Should strip leading/trailing whitespace."""
        from instincts.utils import normalize_trigger

        result = normalize_trigger("  some trigger  ")
        assert result == result.strip()

    def test_handles_empty_string(self):
        """Should handle empty string input."""
        from instincts.utils import normalize_trigger

        result = normalize_trigger("")
        assert result == ""

    def test_handles_only_stop_words(self):
        """Should handle trigger with only stop words."""
        from instincts.utils import normalize_trigger

        result = normalize_trigger("when creating")
        assert result.strip() == ""


class TestTriggerStopWords:
    """Tests for TRIGGER_STOP_WORDS constant."""

    def test_trigger_stop_words_exists(self):
        """Should export TRIGGER_STOP_WORDS constant."""
        from instincts.utils import TRIGGER_STOP_WORDS

        assert isinstance(TRIGGER_STOP_WORDS, tuple)
        assert "when" in TRIGGER_STOP_WORDS
        assert "creating" in TRIGGER_STOP_WORDS
