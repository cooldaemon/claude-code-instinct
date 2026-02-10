"""LLM-based pattern detection for Instinct-Based Learning.

This module provides LLM-based pattern detection using Anthropic's Claude API.
It analyzes observations using Claude Haiku to identify patterns that may not
be detected by algorithm-based approaches.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from instincts.config import ANTHROPIC_API_KEY_ENV, DEFAULT_LLM_MODEL
from instincts.models import Evidence, Pattern, PatternType

logger = logging.getLogger(__name__)

# Maximum observations to include in LLM prompt (prevents token overflow)
MAX_OBSERVATIONS_IN_PROMPT: int = 100

# Maximum existing instincts to include in LLM prompt
MAX_EXISTING_INSTINCTS_IN_PROMPT: int = 20

# Maximum tokens for LLM response
LLM_MAX_TOKENS: int = 2000

# API timeout in seconds
LLM_API_TIMEOUT: float = 30.0

# Session ID for LLM-generated patterns
LLM_SESSION_ID: str = "llm-analysis"

# Pattern type mapping from string to enum
PATTERN_TYPE_MAP: dict[str, PatternType] = {
    "user_correction": PatternType.USER_CORRECTION,
    "error_resolution": PatternType.ERROR_RESOLUTION,
    "repeated_workflow": PatternType.REPEATED_WORKFLOW,
    "tool_preference": PatternType.TOOL_PREFERENCE,
}


def is_llm_available() -> bool:
    """Check if LLM-based detection is available.

    Returns:
        True if ANTHROPIC_API_KEY is set and non-empty, False otherwise.
    """
    api_key = os.environ.get(ANTHROPIC_API_KEY_ENV, "")
    return bool(api_key)


def _build_prompt(
    observations: list[dict[str, Any]], existing_instincts: list[dict[str, Any]]
) -> str:
    """Build the prompt for LLM pattern detection.

    Args:
        observations: List of observation dictionaries.
        existing_instincts: List of existing instinct dictionaries to avoid duplicates.

    Returns:
        The formatted prompt string.
    """
    # Limit observations to prevent token overflow
    recent_obs = (
        observations[-MAX_OBSERVATIONS_IN_PROMPT:]
        if len(observations) > MAX_OBSERVATIONS_IN_PROMPT
        else observations
    )

    observations_json = json.dumps(recent_obs, indent=2)

    existing_summary = ""
    if existing_instincts:
        existing_items = [
            f"- {inst.get('id', 'unknown')}: {inst.get('trigger', 'unknown')}"
            for inst in existing_instincts[:MAX_EXISTING_INSTINCTS_IN_PROMPT]
        ]
        existing_summary = "\n".join(existing_items)

    prompt = f"""Analyze the following tool usage observations and identify behavioral patterns.

## Existing Instincts (avoid duplicates)
{existing_summary if existing_summary else "None yet."}

## Recent Observations
{observations_json}

## Instructions
Identify patterns in the observations. Look for:
1. User corrections (Write followed by Edit, correction keywords)
2. Error resolutions (errors followed by successful fixes)
3. Repeated workflows (same tool sequences across sessions)
4. Tool preferences (consistent tool usage patterns)

Return a JSON object with a "patterns" array. Each pattern should have:
- pattern_type: one of "user_correction", "error_resolution", "repeated_workflow", "tool_preference"
- trigger: when this pattern applies (e.g., "when editing files")
- description: what the pattern is
- domain: category (e.g., "code-style", "workflow", "error-handling")

Only include patterns that are NOT already captured by existing instincts.
If no new patterns found, return {{"patterns": []}}.

Return ONLY valid JSON, no markdown formatting."""

    return prompt


def _parse_pattern(pattern_data: dict[str, Any]) -> Pattern | None:
    """Parse a single pattern from LLM response.

    Args:
        pattern_data: Dictionary with pattern fields from LLM.

    Returns:
        Pattern object or None if parsing fails.
    """
    try:
        pattern_type_str = pattern_data.get("pattern_type", "")
        pattern_type = PATTERN_TYPE_MAP.get(pattern_type_str)
        if not pattern_type:
            return None

        trigger = pattern_data.get("trigger", "")
        description = pattern_data.get("description", "")
        domain = pattern_data.get("domain", "general")

        if not trigger or not description:
            return None

        evidence = Evidence(
            timestamp=datetime.now(timezone.utc),
            session_id=LLM_SESSION_ID,
            description="Detected by LLM analysis",
        )

        return Pattern(
            pattern_type=pattern_type,
            trigger=trigger,
            description=description,
            evidence=(evidence,),
            domain=domain,
            metadata=(("source", "llm"),),
        )
    except (KeyError, TypeError, ValueError) as e:
        logger.warning("Failed to parse LLM pattern: %s", e)
        return None


def _parse_llm_response(response_text: str) -> list[Pattern]:
    """Parse LLM response text into Pattern objects.

    Args:
        response_text: Raw JSON text from LLM response.

    Returns:
        List of parsed Pattern objects.
    """
    try:
        data = json.loads(response_text)
        patterns_data = data.get("patterns", [])

        if not isinstance(patterns_data, list):
            return []

        patterns: list[Pattern] = []
        for pattern_data in patterns_data:
            pattern = _parse_pattern(pattern_data)
            if pattern:
                patterns.append(pattern)

        return patterns
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse LLM JSON response: %s", e)
        return []


def detect_patterns_with_llm(
    observations: list[dict[str, Any]], existing_instincts: list[dict[str, Any]]
) -> list[Pattern]:
    """Detect patterns using LLM analysis.

    Args:
        observations: List of observation dictionaries.
        existing_instincts: List of existing instinct dictionaries to avoid duplicates.

    Returns:
        List of detected Pattern objects. Empty list if LLM unavailable or on error.
    """
    if not is_llm_available():
        logger.debug("LLM not available (ANTHROPIC_API_KEY not set)")
        return []

    if not observations:
        return []

    try:
        # Import here to avoid requiring anthropic package when not using LLM
        import anthropic  # type: ignore[import-not-found]

        client = anthropic.Anthropic()
        prompt = _build_prompt(observations, existing_instincts)

        response = client.messages.create(
            model=DEFAULT_LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
            timeout=LLM_API_TIMEOUT,
        )

        if not response.content:
            return []

        # Defensive check for text attribute
        first_content = response.content[0]
        if not hasattr(first_content, "text"):
            return []

        response_text = first_content.text
        return _parse_llm_response(response_text)

    except ImportError:
        logger.warning("anthropic package not installed, LLM detection disabled")
        return []
    except Exception as e:
        # Dynamically check if exception is an Anthropic API error.
        # We check parent classes to handle the inheritance hierarchy properly.
        anthropic_error_names = {
            "APIError",
            "APIConnectionError",
            "RateLimitError",
            "AuthenticationError",
            "APIStatusError",
            "BadRequestError",
            "InternalServerError",
        }
        error_class_names = {cls.__name__ for cls in type(e).__mro__}

        if error_class_names & anthropic_error_names:
            logger.warning("LLM API error: %s", type(e).__name__)
            return []

        # Re-raise unexpected exceptions
        raise
