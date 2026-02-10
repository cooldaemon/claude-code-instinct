"""Tests for instincts.llm_patterns module.

Tests cover:
- LLM-based pattern detection using Haiku
- API key handling
- Response parsing
- Error handling when LLM fails
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from instincts.models import PatternType


def _create_mock_anthropic(mock_client: MagicMock) -> MagicMock:
    """Create a mock anthropic module."""
    mock_module = MagicMock()
    mock_module.Anthropic = MagicMock(return_value=mock_client)
    return mock_module


class TestDetectPatternsWithLLM:
    """Tests for detect_patterns_with_llm function (AC-R2.1, AC-R2.2, AC-R2.5)."""

    def test_returns_empty_when_api_key_not_set(self):
        """AC-R2.2: Should return empty list when ANTHROPIC_API_KEY is not set."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1"},
            {"event": "tool_complete", "tool": "Write", "session": "s1"},
        ]

        with patch.dict("os.environ", {}, clear=True):
            patterns = detect_patterns_with_llm(observations, [])

        assert patterns == []

    def test_calls_anthropic_api_when_key_set(self):
        """AC-R2.1: Should call Anthropic API when ANTHROPIC_API_KEY is set."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1"},
            {"event": "tool_complete", "tool": "Write", "session": "s1"},
        ]

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"patterns": []}')]
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = _create_mock_anthropic(mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                detect_patterns_with_llm(observations, [])

        mock_client.messages.create.assert_called_once()

    def test_returns_empty_on_api_error(self):
        """AC-R2.5: Should return empty list and log warning when API error occurs."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1"},
        ]

        mock_client = MagicMock()
        # Create a mock API error
        mock_api_error = MagicMock()
        mock_api_error.__class__.__name__ = "APIError"
        mock_client.messages.create.side_effect = mock_api_error

        mock_anthropic = _create_mock_anthropic(mock_client)
        # Add mock exception classes
        mock_anthropic.APIError = type("APIError", (Exception,), {})
        mock_anthropic.APIConnectionError = type("APIConnectionError", (Exception,), {})
        mock_anthropic.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_anthropic.AuthenticationError = type("AuthenticationError", (Exception,), {})

        # Use the mock APIError
        mock_client.messages.create.side_effect = mock_anthropic.APIError("API Error")

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        assert patterns == []

    def test_returns_empty_on_rate_limit_error(self):
        """Should return empty list when rate limit is hit."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1"},
        ]

        mock_client = MagicMock()
        mock_anthropic = _create_mock_anthropic(mock_client)
        # Add mock exception classes
        mock_anthropic.APIError = type("APIError", (Exception,), {})
        mock_anthropic.APIConnectionError = type("APIConnectionError", (Exception,), {})
        mock_anthropic.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_anthropic.AuthenticationError = type("AuthenticationError", (Exception,), {})

        mock_client.messages.create.side_effect = mock_anthropic.RateLimitError("Rate limit")

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        assert patterns == []

    def test_returns_empty_on_auth_error(self):
        """Should return empty list when authentication fails."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1"},
        ]

        mock_client = MagicMock()
        mock_anthropic = _create_mock_anthropic(mock_client)
        # Add mock exception classes
        mock_anthropic.APIError = type("APIError", (Exception,), {})
        mock_anthropic.APIConnectionError = type("APIConnectionError", (Exception,), {})
        mock_anthropic.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_anthropic.AuthenticationError = type("AuthenticationError", (Exception,), {})

        mock_client.messages.create.side_effect = mock_anthropic.AuthenticationError("Invalid key")

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        assert patterns == []

    def test_returns_empty_on_connection_error(self):
        """Should return empty list on connection error."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1"},
        ]

        mock_client = MagicMock()
        mock_anthropic = _create_mock_anthropic(mock_client)
        # Add mock exception classes
        mock_anthropic.APIError = type("APIError", (Exception,), {})
        mock_anthropic.APIConnectionError = type("APIConnectionError", (Exception,), {})
        mock_anthropic.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_anthropic.AuthenticationError = type("AuthenticationError", (Exception,), {})

        mock_client.messages.create.side_effect = mock_anthropic.APIConnectionError("Connection failed")

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        assert patterns == []

    def test_parses_llm_response_to_patterns(self):
        """Should parse LLM JSON response into Pattern objects."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1"},
            {"event": "tool_complete", "tool": "Write", "session": "s1"},
        ]

        llm_response = {
            "patterns": [
                {
                    "pattern_type": "user_correction",
                    "trigger": "when editing files",
                    "description": "User prefers smaller edits",
                    "domain": "code-style",
                }
            ]
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(llm_response))]
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = _create_mock_anthropic(mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        assert len(patterns) == 1
        assert patterns[0].pattern_type == PatternType.USER_CORRECTION
        assert patterns[0].trigger == "when editing files"
        assert patterns[0].description == "User prefers smaller edits"

    def test_includes_existing_instincts_in_prompt(self):
        """AC-R2.6: LLM prompt should include existing instincts to avoid duplicates."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [
            {"event": "tool_start", "tool": "Write", "session": "s1"},
        ]

        existing_instincts = [
            {"id": "existing-pattern", "trigger": "when writing code", "domain": "code-style"}
        ]

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"patterns": []}')]
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = _create_mock_anthropic(mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                detect_patterns_with_llm(observations, existing_instincts)

        # Check that the prompt includes existing instincts
        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs.get("messages", [])
        user_message = messages[0]["content"] if messages else ""
        assert "existing-pattern" in user_message or "when writing code" in user_message


class TestLLMPatternParsing:
    """Tests for parsing LLM responses."""

    def test_handles_invalid_json_response(self):
        """Should handle invalid JSON in LLM response gracefully."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [{"event": "tool_start", "tool": "Write", "session": "s1"}]

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not valid json")]
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = _create_mock_anthropic(mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        # Should return empty list on parse error
        assert patterns == []

    def test_handles_missing_patterns_key(self):
        """Should handle missing 'patterns' key in response."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [{"event": "tool_start", "tool": "Write", "session": "s1"}]

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"other_key": "value"}')]
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = _create_mock_anthropic(mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        # Should return empty list when patterns key missing
        assert patterns == []

    def test_skips_invalid_pattern_entries(self):
        """Should skip individual patterns that fail validation."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [{"event": "tool_start", "tool": "Write", "session": "s1"}]

        llm_response = {
            "patterns": [
                # Valid pattern
                {
                    "pattern_type": "user_correction",
                    "trigger": "when editing",
                    "description": "User prefers small edits",
                    "domain": "code-style",
                },
                # Invalid pattern (missing required fields)
                {"pattern_type": "invalid_type"},
                # Another valid pattern
                {
                    "pattern_type": "error_resolution",
                    "trigger": "when build fails",
                    "description": "Fix import errors",
                    "domain": "error-handling",
                },
            ]
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(llm_response))]
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = _create_mock_anthropic(mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        # Should only have the 2 valid patterns
        assert len(patterns) == 2


class TestLLMPatternSource:
    """Tests for pattern source metadata."""

    def test_patterns_have_llm_source_in_metadata(self):
        """Patterns from LLM should have LLM source in metadata."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [{"event": "tool_start", "tool": "Write", "session": "s1"}]

        llm_response = {
            "patterns": [
                {
                    "pattern_type": "user_correction",
                    "trigger": "when editing",
                    "description": "User prefers small edits",
                    "domain": "code-style",
                }
            ]
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(llm_response))]
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = _create_mock_anthropic(mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        assert len(patterns) == 1
        # Check metadata contains source
        metadata_dict = dict(patterns[0].metadata)
        assert metadata_dict.get("source") == "llm"


class TestIsLLMAvailable:
    """Tests for is_llm_available function."""

    def test_returns_true_when_api_key_set(self):
        """Should return True when ANTHROPIC_API_KEY is set."""
        from instincts.llm_patterns import is_llm_available

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            assert is_llm_available() is True

    def test_returns_false_when_api_key_not_set(self):
        """Should return False when ANTHROPIC_API_KEY is not set."""
        from instincts.llm_patterns import is_llm_available

        with patch.dict("os.environ", {}, clear=True):
            assert is_llm_available() is False

    def test_returns_false_when_api_key_empty(self):
        """Should return False when ANTHROPIC_API_KEY is empty."""
        from instincts.llm_patterns import is_llm_available

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            assert is_llm_available() is False


class TestLLMConstants:
    """Tests for LLM pattern constants."""

    def test_max_existing_instincts_in_prompt_constant(self):
        """Should have MAX_EXISTING_INSTINCTS_IN_PROMPT constant."""
        from instincts.llm_patterns import MAX_EXISTING_INSTINCTS_IN_PROMPT

        assert MAX_EXISTING_INSTINCTS_IN_PROMPT == 20

    def test_llm_max_tokens_constant(self):
        """Should have LLM_MAX_TOKENS constant."""
        from instincts.llm_patterns import LLM_MAX_TOKENS

        assert LLM_MAX_TOKENS == 2000

    def test_llm_session_id_constant(self):
        """Should have LLM_SESSION_ID constant for session identification."""
        from instincts.llm_patterns import LLM_SESSION_ID

        assert LLM_SESSION_ID == "llm-analysis"


class TestLLMResponseValidation:
    """Tests for defensive response validation."""

    def test_handles_response_content_without_text_attribute(self):
        """Should handle response.content[0] without text attribute."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [{"event": "tool_start", "tool": "Write", "session": "s1"}]

        mock_client = MagicMock()
        mock_response = MagicMock()
        # Create content item without text attribute
        mock_content_item = MagicMock(spec=[])  # No text attribute
        mock_response.content = [mock_content_item]
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = _create_mock_anthropic(mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        # Should return empty list when text attribute missing
        assert patterns == []

    def test_handles_empty_content_list(self):
        """Should handle empty response.content list."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [{"event": "tool_start", "tool": "Write", "session": "s1"}]

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = []  # Empty content
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = _create_mock_anthropic(mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        # Should return empty list for empty content
        assert patterns == []

    def test_handles_empty_text_attribute(self):
        """Should handle empty string in response.content[0].text."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [{"event": "tool_start", "tool": "Write", "session": "s1"}]

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="")]  # Empty text
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = _create_mock_anthropic(mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        # Should return empty list for empty text
        assert patterns == []


class TestLLMExceptionHandling:
    """Tests for proper exception handling using imported exception classes."""

    def test_reraises_unexpected_exceptions(self):
        """Unexpected exceptions should be re-raised, not silently caught."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [{"event": "tool_start", "tool": "Write", "session": "s1"}]

        mock_client = MagicMock()
        mock_anthropic = _create_mock_anthropic(mock_client)

        # Raise an unexpected exception (not an API error)
        mock_client.messages.create.side_effect = ValueError("Unexpected error")

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                with pytest.raises(ValueError, match="Unexpected error"):
                    detect_patterns_with_llm(observations, [])

    def test_handles_anthropic_api_error_gracefully(self):
        """Should handle anthropic.APIError and return empty list."""
        from instincts.llm_patterns import detect_patterns_with_llm

        observations = [{"event": "tool_start", "tool": "Write", "session": "s1"}]

        mock_client = MagicMock()
        mock_anthropic = _create_mock_anthropic(mock_client)

        # Create a proper mock for APIError with the correct class name
        # The exception handling checks __mro__ for class names like "APIError"
        APIError = type("APIError", (Exception,), {})

        mock_anthropic.APIError = APIError
        mock_client.messages.create.side_effect = APIError("API error")

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                patterns = detect_patterns_with_llm(observations, [])

        assert patterns == []


class TestLLMAPITimeout:
    """Tests for LLM API timeout configuration."""

    def test_api_call_includes_timeout(self):
        """LLM API call should include timeout parameter."""
        from instincts.llm_patterns import LLM_API_TIMEOUT, detect_patterns_with_llm

        observations = [{"event": "tool_start", "tool": "Write", "session": "s1"}]

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"patterns": []}')]
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = _create_mock_anthropic(mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                detect_patterns_with_llm(observations, [])

        # Verify timeout was passed
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == LLM_API_TIMEOUT

    def test_timeout_constant_is_30_seconds(self):
        """LLM_API_TIMEOUT should be 30 seconds."""
        from instincts.llm_patterns import LLM_API_TIMEOUT

        assert LLM_API_TIMEOUT == 30.0
