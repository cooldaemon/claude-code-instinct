"""CLI module for Instinct-Based Learning.

Provides status and evolve commands for managing instincts.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from instincts.config import get_learned_dir, get_observations_file
from instincts.utils import normalize_trigger

if TYPE_CHECKING:
    from instincts.models import Instinct

logger = logging.getLogger(__name__)


def _parse_frontmatter_line(line: str, current: dict[str, Any]) -> None:
    """Parse a single YAML-like frontmatter line into the current dict.

    Args:
        line: A line from YAML frontmatter section.
        current: Dictionary to update with parsed key-value pair.
    """
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
    """Finalize current instinct and add to list if valid.

    Args:
        current: Dictionary with parsed frontmatter fields.
        content_lines: Lines of markdown content after frontmatter.
        instincts: List to append the finalized instinct to.
    """
    if not current:
        return

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


def load_all_instincts(
    project_root: Path,
) -> list[dict[str, Any]]:
    """Load all instincts from project learned directory.

    Args:
        project_root: Project root for project-scoped loading.

    Returns:
        List of instinct dictionaries with _source_file field added.
    """
    instincts: list[dict[str, Any]] = []

    instincts_dir = get_learned_dir(project_root)

    if not instincts_dir.exists():
        return instincts

    # Load both .yaml and .md files (AC-7.3)
    for pattern in ("*.yaml", "*.md"):
        for file in instincts_dir.glob(pattern):
            # Skip symlinks for defense in depth
            if file.is_symlink():
                logger.warning("Skipping symlink: %s", file)
                continue
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
    """Create a visual confidence bar using unicode block characters.

    Args:
        confidence: Confidence value between 0.0 and 1.0.

    Returns:
        A 10-character string with filled and empty blocks.
    """
    filled = int(confidence * 10)
    return "\u2588" * filled + "\u2591" * (10 - filled)


def cmd_status(project_root: Path) -> int:
    """Show status of all instincts.

    Args:
        project_root: Project root for project-scoped loading.

    Returns:
        Exit code (0 for success).
    """
    instincts = load_all_instincts(project_root)
    instincts_dir = get_learned_dir(project_root)

    if not instincts:
        print("No instincts found.")
        print(f"\nInstinct directory: {instincts_dir}")
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
    observations_file = get_observations_file(project_root)
    if observations_file.exists():
        try:
            with observations_file.open() as f:
                obs_count = sum(1 for _ in f)
            print("-" * 60)
            print(f"  Observations: {obs_count} events logged")
            print(f"  File: {observations_file}")
        except (OSError, IOError) as e:
            logger.warning("Failed to read observations file %s: %s", observations_file, e)

    print()
    print("=" * 60)
    print()

    return 0


MIN_INSTINCTS_FOR_ANALYSIS: int = 3
MIN_CLUSTER_SIZE: int = 2
HIGH_CONFIDENCE_THRESHOLD: float = 0.8
MAX_SKILL_CANDIDATES_DISPLAY: int = 5

# CR-005: Named constant for preview truncation limit
PREVIEW_TRUNCATION_LIMIT: int = 500


def _parse_instinct_selection(
    selection: str, total_instincts: int
) -> list[int]:
    """Parse user selection into validated instinct indices.

    Args:
        selection: User input string (e.g., "1,2,3" or "all").
        total_instincts: Total number of available instincts.

    Returns:
        List of validated 0-based indices.
    """
    if selection.lower() == "all":
        return list(range(total_instincts))

    try:
        raw_indices = [int(x.strip()) - 1 for x in selection.split(",")]
    except ValueError:
        print("Warning: Invalid input, using all instincts.")
        return list(range(total_instincts))

    selected_indices: list[int] = []
    invalid_indices: list[int] = []

    for idx in raw_indices:
        if 0 <= idx < total_instincts:
            selected_indices.append(idx)
        else:
            invalid_indices.append(idx + 1)

    if invalid_indices:
        print(f"Warning: Skipping invalid indices: {invalid_indices}")

    if not selected_indices:
        print("No valid indices selected, using all instincts.")
        return list(range(total_instincts))

    return selected_indices


def _convert_dict_to_instinct(inst_dict: dict[str, Any]) -> "Instinct":
    """Convert an instinct dictionary to an Instinct object.

    Args:
        inst_dict: Dictionary with instinct data.

    Returns:
        Instinct object.
    """
    from instincts.models import Instinct

    now = datetime.now(timezone.utc)
    return Instinct(
        id=inst_dict.get("id", ""),
        trigger=inst_dict.get("trigger", ""),
        confidence=float(inst_dict.get("confidence", 0.5)),
        domain=inst_dict.get("domain", "general"),
        source=inst_dict.get("source", "unknown"),
        evidence_count=int(inst_dict.get("evidence_count", 1)),
        created_at=now,
        updated_at=now,
        content=inst_dict.get("content", ""),
    )


def _handle_claudemd_evolution(
    instincts: list[dict[str, Any]],
    selected_indices: list[int],
    project_root: Path,
) -> None:
    """Handle evolution to CLAUDE.md with preview and confirmation.

    Args:
        instincts: List of all instinct dictionaries.
        selected_indices: Indices of selected instincts.
        project_root: Path to the project root.
    """
    from instincts.evolution import evolve_to_claudemd

    selected_instincts = [
        _convert_dict_to_instinct(instincts[i]) for i in selected_indices
    ]

    preview = evolve_to_claudemd(selected_instincts, project_root)
    print()
    print("Preview of CLAUDE.md changes:")
    print("-" * 40)
    print(preview[:PREVIEW_TRUNCATION_LIMIT])
    if len(preview) > PREVIEW_TRUNCATION_LIMIT:
        print("...")
    print("-" * 40)
    print()
    print("Apply changes? [y/n]")
    confirm = input("> ")

    if confirm.lower() != "y":
        return

    try:
        from instincts.claudemd import write_patterns
        claudemd_path = project_root / "CLAUDE.md"
        write_patterns(claudemd_path, preview)
        print(f"Written to {claudemd_path}")
    except OSError as e:
        print(f"Error: Failed to write to CLAUDE.md: {e}")
    except Exception as e:
        print(f"Error: Unexpected error writing CLAUDE.md: {e}")


def _cluster_instincts_by_trigger(
    instincts: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Group instincts by normalized trigger.

    Args:
        instincts: List of instinct dictionaries.

    Returns:
        Dictionary mapping normalized triggers to lists of instincts.
    """
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for inst in instincts:
        trigger = inst.get("trigger", "")
        trigger_key = normalize_trigger(trigger)
        clusters[trigger_key].append(inst)
    return clusters


def _build_skill_candidate(
    trigger: str, cluster: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build a skill candidate dictionary from a cluster.

    Args:
        trigger: The normalized trigger string.
        cluster: List of instinct dictionaries sharing the trigger.

    Returns:
        Dictionary with trigger, instincts, avg_confidence, and domains.
    """
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
    """Find clusters that are good skill candidates.

    Args:
        instincts: List of instinct dictionaries.

    Returns:
        List of skill candidate dictionaries, sorted by cluster size and confidence.
    """
    trigger_clusters = _cluster_instincts_by_trigger(instincts)

    candidates = [
        _build_skill_candidate(trigger, cluster)
        for trigger, cluster in trigger_clusters.items()
        if len(cluster) >= MIN_CLUSTER_SIZE
    ]

    candidates.sort(key=lambda x: (-len(x["instincts"]), -x["avg_confidence"]))
    return candidates


def _print_skill_candidates(candidates: list[dict[str, Any]]) -> None:
    """Print skill candidates to stdout.

    Args:
        candidates: List of skill candidate dictionaries to display.
    """
    print("\n## SKILL CANDIDATES\n")
    for i, cand in enumerate(candidates[:MAX_SKILL_CANDIDATES_DISPLAY], 1):
        print(f'{i}. Cluster: "{cand["trigger"]}"')
        print(f"   Instincts: {len(cand['instincts'])}")
        print(f"   Avg confidence: {cand['avg_confidence']:.0%}")
        print(f"   Domains: {', '.join(cand['domains'])}")
        print()


def cmd_evolve(
    project_root: Path,
    interactive: bool = False,
) -> int:
    """Analyze instincts and suggest evolutions.

    Args:
        project_root: Project root for project-scoped loading.
        interactive: If True, prompt for output type and scope selection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    instincts = load_all_instincts(project_root=project_root)

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

    # Interactive mode for output type selection
    if interactive:
        print()
        print("-" * 60)
        print("Interactive Evolution")
        print("-" * 60)
        print()

        # Display numbered list of instincts
        print("Available instincts:")
        for i, inst in enumerate(instincts, 1):
            conf = inst.get("confidence", 0.5)
            print(f"  {i}. [{inst.get('domain', 'general')}] {inst.get('id', 'unnamed')} ({conf:.0%})")

        print()
        print("Select instincts (e.g., 1,2,3 or 'all'):")
        selection = input("> ")
        selected_indices = _parse_instinct_selection(selection, len(instincts))

        # Output type selection
        print()
        print("Select output type:")
        print("  1. CLAUDE.md (append to project file)")
        print("  2. Rules (.claude/rules/)")
        print("  3. Skills (.claude/skills/)")
        print("  4. Subagents (.claude/agents/)")
        print("  5. Commands (.claude/commands/)")
        output_type = input("> ")

        if output_type == "1":
            _handle_claudemd_evolution(instincts, selected_indices, project_root)

    print()
    print("=" * 60)
    print()

    return 0
