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


class TestSanitizeId:
    """Tests for sanitize_id function (CR-003)."""

    def test_sanitize_id_removes_path_traversal(self):
        """CR-003: Should remove path traversal characters."""
        from instincts.utils import sanitize_id

        result = sanitize_id("../../../etc/passwd")
        assert "/" not in result
        assert ".." not in result

    def test_sanitize_id_removes_dangerous_characters(self):
        """CR-003: Should remove dangerous characters, keeping only alphanumeric, dash, underscore."""
        from instincts.utils import sanitize_id

        result = sanitize_id("test!@#$%^&*()id")
        assert result == "test-id"

    def test_sanitize_id_collapses_multiple_dashes(self):
        """CR-003: Should collapse multiple dashes into one."""
        from instincts.utils import sanitize_id

        result = sanitize_id("test---multiple---dashes")
        assert result == "test-multiple-dashes"

    def test_sanitize_id_strips_leading_trailing_dashes(self):
        """CR-003: Should strip leading and trailing dashes."""
        from instincts.utils import sanitize_id

        result = sanitize_id("---test-id---")
        assert result == "test-id"

    def test_sanitize_id_handles_empty_string(self):
        """CR-003: Should return 'unnamed' for empty or fully-invalid input."""
        from instincts.utils import sanitize_id

        result = sanitize_id("")
        assert result == "unnamed"
        result = sanitize_id("!@#$%")
        assert result == "unnamed"

    def test_sanitize_id_handles_path_basename(self):
        """CR-003: Should use basename to prevent path traversal."""
        from instincts.utils import sanitize_id

        result = sanitize_id("/some/path/to/instinct-id")
        assert "/" not in result
        assert "instinct-id" in result

    def test_sanitize_id_preserves_dots_for_filenames(self):
        """CR-003: Should optionally preserve dots for filename use."""
        from instincts.utils import sanitize_id

        result = sanitize_id("test.md", allow_dots=True)
        assert result == "test.md"

    def test_sanitize_id_removes_dots_by_default(self):
        """CR-003: Should remove dots by default (for IDs)."""
        from instincts.utils import sanitize_id

        result = sanitize_id("test.md")
        assert "." not in result
