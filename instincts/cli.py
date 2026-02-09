"""CLI module for Instinct-Based Learning.

Provides status, evolve, and observe-patterns commands for managing instincts.
"""

import logging
from collections import defaultdict
from typing import Any

from instincts.agent import analyze_observations, format_analysis_summary
from instincts.config import OBSERVATIONS_FILE, PERSONAL_DIR

logger = logging.getLogger(__name__)


def _parse_frontmatter_line(line: str, current: dict[str, Any]) -> None:
    """Parse a single YAML-like frontmatter line into the current dict."""
    if ":" not in line:
        return

    key, value = line.split(":", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")

    if key == "confidence":
        try:
            current[key] = float(value)
        except ValueError:
            current[key] = value
    else:
        current[key] = value


def _finalize_instinct(
    current: dict[str, Any], content_lines: list[str], instincts: list[dict[str, Any]]
) -> None:
    """Finalize current instinct and add to list if valid."""
    if current:
        current["content"] = "\n".join(content_lines).strip()
        instincts.append(current)


def parse_instinct_file(content: str) -> list[dict[str, Any]]:
    """Parse YAML-like instinct file format.

    Args:
        content: File content with YAML frontmatter sections.

    Returns:
        List of instinct dictionaries with id, trigger, confidence, etc.
    """
    if not content.strip():
        return []

    instincts: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    in_frontmatter = False
    content_lines: list[str] = []

    for line in content.split("\n"):
        if line.strip() == "---":
            _finalize_instinct(current, content_lines, instincts)
            current = {}
            content_lines = []
            in_frontmatter = not in_frontmatter
        elif in_frontmatter:
            _parse_frontmatter_line(line, current)
        else:
            content_lines.append(line)

    # Handle last instinct or remaining content
    if current and current.get("id"):
        current["content"] = "\n".join(content_lines).strip()
        instincts.append(current)
    elif instincts and content_lines:
        instincts[-1]["content"] = "\n".join(content_lines).strip()

    return [i for i in instincts if i.get("id")]


def load_all_instincts() -> list[dict[str, Any]]:
    """Load all instincts from PERSONAL_DIR.

    Returns:
        List of instinct dictionaries with _source_file field added.
    """
    instincts: list[dict[str, Any]] = []

    if not PERSONAL_DIR.exists():
        return instincts

    # Load both .yaml and .md files (AC-7.3)
    for pattern in ("*.yaml", "*.md"):
        for file in PERSONAL_DIR.glob(pattern):
            try:
                content = file.read_text()
                parsed = parse_instinct_file(content)
                for inst in parsed:
                    inst["_source_file"] = str(file)
                instincts.extend(parsed)
            except (OSError, IOError) as e:
                # File read error - log and skip
                logger.warning("Failed to read instinct file %s: %s", file, e)
            except (ValueError, UnicodeDecodeError) as e:
                # Parsing error - log and skip
                logger.warning("Failed to parse instinct file %s: %s", file, e)

    return instincts


def _format_confidence_bar(confidence: float) -> str:
    """Create a visual confidence bar."""
    filled = int(confidence * 10)
    return "\u2588" * filled + "\u2591" * (10 - filled)


def cmd_status() -> int:
    """Show status of all instincts.

    Returns:
        Exit code (0 for success).
    """
    instincts = load_all_instincts()

    if not instincts:
        print("No instincts found.")
        print(f"\nInstinct directory: {PERSONAL_DIR}")
        return 0

    # Group by domain
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for inst in instincts:
        domain = inst.get("domain", "general")
        by_domain[domain].append(inst)

    # Print header
    print()
    print("=" * 60)
    print(f"  INSTINCT STATUS - {len(instincts)} total")
    print("=" * 60)
    print()

    # Print by domain
    for domain in sorted(by_domain.keys()):
        domain_instincts = by_domain[domain]
        print(f"## {domain.upper()} ({len(domain_instincts)})")
        print()

        for inst in sorted(domain_instincts, key=lambda x: -x.get("confidence", 0.5)):
            conf = inst.get("confidence", 0.5)
            conf_bar = _format_confidence_bar(conf)
            print(f"  {conf_bar} {int(conf * 100):3d}%  {inst.get('id', 'unnamed')}")
            trigger = inst.get("trigger", "")
            if trigger:
                print(f"            trigger: {trigger}")
            print()

    # Observations stats
    if OBSERVATIONS_FILE.exists():
        try:
            obs_count = sum(1 for _ in OBSERVATIONS_FILE.open())
            print("-" * 60)
            print(f"  Observations: {obs_count} events logged")
            print(f"  File: {OBSERVATIONS_FILE}")
        except (OSError, IOError) as e:
            logger.warning("Failed to read observations file %s: %s", OBSERVATIONS_FILE, e)

    print()
    print("=" * 60)
    print()

    return 0


TRIGGER_STOP_WORDS: tuple[str, ...] = (
    "when",
    "creating",
    "writing",
    "adding",
    "implementing",
    "testing",
)

MIN_INSTINCTS_FOR_ANALYSIS: int = 3
MIN_CLUSTER_SIZE: int = 2
HIGH_CONFIDENCE_THRESHOLD: float = 0.8
MAX_SKILL_CANDIDATES_DISPLAY: int = 5


def _normalize_trigger(trigger: str) -> str:
    """Normalize a trigger string by removing common stop words."""
    normalized = trigger.lower()
    for keyword in TRIGGER_STOP_WORDS:
        normalized = normalized.replace(keyword, "").strip()
    return normalized


def _cluster_instincts_by_trigger(
    instincts: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Group instincts by normalized trigger."""
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for inst in instincts:
        trigger = inst.get("trigger", "")
        trigger_key = _normalize_trigger(trigger)
        clusters[trigger_key].append(inst)
    return clusters


def _build_skill_candidate(
    trigger: str, cluster: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build a skill candidate dictionary from a cluster."""
    avg_conf = sum(i.get("confidence", 0.5) for i in cluster) / len(cluster)
    domains = list(set(i.get("domain", "general") for i in cluster))
    return {
        "trigger": trigger,
        "instincts": cluster,
        "avg_confidence": avg_conf,
        "domains": domains,
    }


def _find_skill_candidates(
    instincts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Find clusters that are good skill candidates."""
    trigger_clusters = _cluster_instincts_by_trigger(instincts)

    candidates = [
        _build_skill_candidate(trigger, cluster)
        for trigger, cluster in trigger_clusters.items()
        if len(cluster) >= MIN_CLUSTER_SIZE
    ]

    candidates.sort(key=lambda x: (-len(x["instincts"]), -x["avg_confidence"]))
    return candidates


def _print_skill_candidates(candidates: list[dict[str, Any]]) -> None:
    """Print skill candidates to stdout."""
    print("\n## SKILL CANDIDATES\n")
    for i, cand in enumerate(candidates[:MAX_SKILL_CANDIDATES_DISPLAY], 1):
        print(f'{i}. Cluster: "{cand["trigger"]}"')
        print(f"   Instincts: {len(cand['instincts'])}")
        print(f"   Avg confidence: {cand['avg_confidence']:.0%}")
        print(f"   Domains: {', '.join(cand['domains'])}")
        print()


def cmd_evolve() -> int:
    """Analyze instincts and suggest evolutions.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    instincts = load_all_instincts()

    if len(instincts) < MIN_INSTINCTS_FOR_ANALYSIS:
        print("Need at least 3 instincts to analyze patterns.")
        print(f"Currently have: {len(instincts)}")
        return 1

    print()
    print("=" * 60)
    print(f"  EVOLVE ANALYSIS - {len(instincts)} instincts")
    print("=" * 60)
    print()

    high_conf_count = sum(
        1 for i in instincts if i.get("confidence", 0) >= HIGH_CONFIDENCE_THRESHOLD
    )
    print(f"High confidence instincts (>=80%): {high_conf_count}")

    skill_candidates = _find_skill_candidates(instincts)
    print(f"\nPotential skill clusters found: {len(skill_candidates)}")

    if skill_candidates:
        _print_skill_candidates(skill_candidates)

    print()
    print("=" * 60)
    print()

    return 0


MAX_PATTERNS_DISPLAY: int = 10


def _has_observations_to_analyze() -> bool:
    """Check if there are observations available for analysis."""
    if not OBSERVATIONS_FILE.exists():
        return False
    return OBSERVATIONS_FILE.stat().st_size > 0


def _print_no_observations_message() -> None:
    """Print message when no observations are available."""
    print("No observations to analyze.")
    print(f"\nObservations file: {OBSERVATIONS_FILE}")


def _print_detected_patterns(patterns: tuple[Any, ...]) -> None:
    """Print detected patterns with details."""
    print("## DETECTED PATTERNS\n")
    for i, pattern in enumerate(patterns[:MAX_PATTERNS_DISPLAY], 1):
        print(f"{i}. {pattern.pattern_type.value}: {pattern.description}")
        print(f"   Trigger: {pattern.trigger}")
        print(f"   Domain: {pattern.domain}")
        print(f"   Evidence: {len(pattern.evidence)} observations")
        print()

    remaining = len(patterns) - MAX_PATTERNS_DISPLAY
    if remaining > 0:
        print(f"   ... and {remaining} more patterns")
        print()


def cmd_observe_patterns(dry_run: bool = False) -> int:
    """Analyze observations and detect patterns.

    Args:
        dry_run: If True, show what would be created without writing files.

    Returns:
        Exit code (0 for success).
    """
    if not _has_observations_to_analyze():
        _print_no_observations_message()
        return 0

    if dry_run:
        print("DRY RUN - No files will be created\n")

    result = analyze_observations(dry_run=dry_run)
    print(format_analysis_summary(result))

    if result.patterns:
        _print_detected_patterns(result.patterns)

    return 0
