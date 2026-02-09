#!/usr/bin/env python3
"""Instinct CLI entry point.

Provides status and evolve subcommands for managing instincts.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for development
PROJECT_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from instincts.cli import cmd_evolve, cmd_status


def main() -> int:
    """Parse arguments and run the appropriate command."""
    parser = argparse.ArgumentParser(
        description="Instinct CLI for Continuous Learning"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # status command
    subparsers.add_parser("status", help="Show instinct status")

    # evolve command
    subparsers.add_parser("evolve", help="Analyze and evolve instincts")

    args = parser.parse_args()

    if args.command == "status":
        return cmd_status()
    elif args.command == "evolve":
        return cmd_evolve()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
