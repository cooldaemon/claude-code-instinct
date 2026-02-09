#!/usr/bin/env python3
"""PostToolUse hook entry point.

Reads JSON from stdin (Claude Code hook format) and records the observation.
"""

import json
import sys
from pathlib import Path

# Add project root to path for development
PROJECT_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from instincts.observer import observe_post


def main() -> int:
    """Read hook data from stdin and process."""
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            return 0

        hook_data = json.loads(input_data)
        observe_post(hook_data)
        return 0
    except json.JSONDecodeError:
        # Invalid JSON, skip silently
        return 0
    except Exception:
        # Don't crash the hook on errors
        return 0


if __name__ == "__main__":
    sys.exit(main())
