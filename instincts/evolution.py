"""Evolution system for Instinct-Based Learning.

This module provides the evolution system that:
- Clusters related instincts by domain and trigger
- Evaluates clusters for evolution into skills/commands/agents
- Generates skill, command, and agent files
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from instincts.config import (
    EVOLVED_AGENTS_DIR,
    EVOLVED_COMMANDS_DIR,
    EVOLVED_SKILLS_DIR,
)
from instincts.models import Instinct

# Evolution thresholds
MIN_CLUSTER_SIZE_FOR_SKILL: int = 3
MIN_AVG_CONFIDENCE_FOR_SKILL: float = 0.7
MIN_CONFIDENCE_FOR_COMMAND: float = 0.85

# Trigger similarity threshold for clustering instincts
TRIGGER_SIMILARITY_THRESHOLD: float = 0.3


@dataclass(frozen=True)
class Cluster:
    """A cluster of related instincts.

    Attributes:
        domain: The common domain of instincts in this cluster.
        trigger_pattern: The common trigger pattern.
        instincts: Tuple of instincts in this cluster (immutable).
        avg_confidence: Average confidence of instincts in cluster.
    """

    domain: str
    trigger_pattern: str
    instincts: tuple[Instinct, ...]
    avg_confidence: float


@dataclass(frozen=True)
class EvolutionSuggestion:
    """A suggestion for evolving instincts.

    Attributes:
        evolution_type: Type of evolution ("skill", "command", "agent").
        source_id: ID of the source (cluster name or instinct ID).
        description: Human-readable description of the suggestion.
    """

    evolution_type: str
    source_id: str
    description: str


def _extract_trigger_keywords(trigger: str) -> set[str]:
    """Extract keywords from a trigger string."""
    # Remove common words and extract meaningful keywords
    stop_words = {"when", "the", "a", "an", "to", "for", "of", "in", "on", "is", "are"}
    words = trigger.lower().split()
    return {w for w in words if w not in stop_words and len(w) > 2}


def _trigger_similarity(trigger1: str, trigger2: str) -> float:
    """Calculate similarity between two triggers based on keyword overlap."""
    keywords1 = _extract_trigger_keywords(trigger1)
    keywords2 = _extract_trigger_keywords(trigger2)

    if not keywords1 or not keywords2:
        return 0.0

    intersection = keywords1 & keywords2
    union = keywords1 | keywords2

    return len(intersection) / len(union) if union else 0.0


def _group_instincts_by_domain(
    instincts: list[Instinct],
) -> dict[str, list[Instinct]]:
    """Group instincts by their domain."""
    by_domain: dict[str, list[Instinct]] = {}
    for instinct in instincts:
        domain = instinct.domain
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(instinct)
    return by_domain


def _calculate_cluster_trigger_pattern(
    cluster_instincts: list[Instinct], default: str
) -> str:
    """Calculate a trigger pattern from common keywords in cluster instincts."""
    max_keywords = 3
    all_keywords: set[str] = set()
    for inst in cluster_instincts:
        all_keywords.update(_extract_trigger_keywords(inst.trigger))

    if not all_keywords:
        return default

    return " ".join(sorted(all_keywords)[:max_keywords])


def _find_similar_instincts(
    seed_instinct: Instinct,
    candidates: list[Instinct],
    used_indices: set[int],
    start_index: int,
) -> list[Instinct]:
    """Find instincts similar to seed based on trigger similarity."""
    similar = [seed_instinct]
    used_indices.add(start_index)

    for j, candidate in enumerate(candidates):
        if j in used_indices:
            continue

        similarity = _trigger_similarity(seed_instinct.trigger, candidate.trigger)
        if similarity >= TRIGGER_SIMILARITY_THRESHOLD:
            similar.append(candidate)
            used_indices.add(j)

    return similar


def _create_cluster_from_instincts(
    domain: str, cluster_instincts: list[Instinct]
) -> Cluster:
    """Create a Cluster object from a list of instincts."""
    avg_conf = sum(inst.confidence for inst in cluster_instincts) / len(
        cluster_instincts
    )
    trigger_pattern = _calculate_cluster_trigger_pattern(cluster_instincts, domain)

    return Cluster(
        domain=domain,
        trigger_pattern=trigger_pattern,
        instincts=tuple(cluster_instincts),
        avg_confidence=avg_conf,
    )


def cluster_instincts(instincts: list[Instinct]) -> list[Cluster]:
    """Cluster instincts by domain and similar triggers.

    Args:
        instincts: List of instincts to cluster.

    Returns:
        List of Cluster objects.
    """
    if not instincts:
        return []

    by_domain = _group_instincts_by_domain(instincts)
    clusters: list[Cluster] = []

    for domain, domain_instincts in by_domain.items():
        used_indices: set[int] = set()

        for i, seed_instinct in enumerate(domain_instincts):
            if i in used_indices:
                continue

            cluster_list = _find_similar_instincts(
                seed_instinct, domain_instincts, used_indices, i
            )
            clusters.append(_create_cluster_from_instincts(domain, cluster_list))

    return clusters


def evaluate_cluster_for_evolution(cluster: Cluster) -> EvolutionSuggestion | None:
    """Evaluate if a cluster should be evolved into a skill.

    Args:
        cluster: The cluster to evaluate.

    Returns:
        EvolutionSuggestion if cluster meets criteria, None otherwise.
    """
    # Check if cluster meets skill criteria (AC-8.2)
    if (
        len(cluster.instincts) >= MIN_CLUSTER_SIZE_FOR_SKILL
        and cluster.avg_confidence >= MIN_AVG_CONFIDENCE_FOR_SKILL
    ):
        return EvolutionSuggestion(
            evolution_type="skill",
            source_id=f"cluster-{cluster.domain}-{cluster.trigger_pattern}",
            description=f"Create skill for {cluster.domain} domain: {len(cluster.instincts)} related instincts with {cluster.avg_confidence:.0%} avg confidence",
        )

    return None


MULTI_STEP_INDICATORS: tuple[str, ...] = ("1.", "2.", "3.", "step", "then", "->")
WORKFLOW_SOURCES: tuple[str, ...] = ("repeated_workflow", "pattern-detection")


def _has_multi_step_workflow(content: str) -> bool:
    """Check if content suggests a multi-step workflow."""
    content_lower = content.lower()
    return any(indicator in content_lower for indicator in MULTI_STEP_INDICATORS)


def suggest_evolution_for_instinct(instinct: Instinct) -> EvolutionSuggestion | None:
    """Suggest evolution for a single high-confidence instinct.

    Args:
        instinct: The instinct to evaluate.

    Returns:
        EvolutionSuggestion if instinct meets criteria, None otherwise.
    """
    if instinct.confidence < MIN_CONFIDENCE_FOR_COMMAND:
        return None

    if instinct.source not in WORKFLOW_SOURCES:
        return None

    if _has_multi_step_workflow(instinct.content):
        return EvolutionSuggestion(
            evolution_type="agent",
            source_id=instinct.id,
            description=f"Create agent for complex workflow: {instinct.trigger}",
        )

    return EvolutionSuggestion(
        evolution_type="command",
        source_id=instinct.id,
        description=f"Create command for: {instinct.trigger}",
    )


def generate_skill(cluster: Cluster) -> str:
    """Generate skill file content from a cluster of instincts.

    Args:
        cluster: The cluster to generate a skill from.

    Returns:
        Skill file content as a string.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Collect all guidance from instincts
    guidance_points: list[str] = []
    for inst in cluster.instincts:
        # Extract key points from instinct content
        if inst.content:
            # Take the first paragraph or action section
            lines = inst.content.split("\n")
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#") and len(line) > 20:
                    guidance_points.append(f"- {line}")
                    break

    # Format guidance section
    guidance_section = (
        "\n".join(guidance_points)
        if guidance_points
        else "- Follow learned patterns for this domain"
    )

    # Build source instincts section
    source_instincts = "\n".join(
        f"- {inst.id} (confidence: {inst.confidence:.0%})"
        for inst in cluster.instincts
    )

    content = f"""# {cluster.domain.title()} Skill

Generated from {len(cluster.instincts)} learned instincts.
Average confidence: {cluster.avg_confidence:.0%}

## When to Apply

{cluster.trigger_pattern}

## Guidance

{guidance_section}

## Source Instincts

{source_instincts}

---
Generated: {now}
"""

    return content


def generate_command(instinct: Instinct) -> str:
    """Generate command file content from an instinct.

    Args:
        instinct: The instinct to generate a command from.

    Returns:
        Command file content as a string.
    """
    now = datetime.now(timezone.utc).isoformat()

    content = f"""# {instinct.trigger.title()}

A command generated from a learned workflow pattern.

## Usage

When: {instinct.trigger}

## Action

{instinct.content}

---
Source instinct: {instinct.id}
Confidence: {instinct.confidence:.0%}
Generated: {now}
"""

    return content


def generate_agent(instinct: Instinct) -> str:
    """Generate agent file content from a complex workflow instinct.

    Args:
        instinct: The instinct to generate an agent from.

    Returns:
        Agent file content as a string.
    """
    now = datetime.now(timezone.utc).isoformat()

    content = f"""# {instinct.trigger.title()} Agent

An agent generated from a learned multi-step workflow pattern.

## Purpose

{instinct.trigger}

## Workflow

{instinct.content}

## Activation

This agent activates when: {instinct.trigger}

---
Source instinct: {instinct.id}
Confidence: {instinct.confidence:.0%}
Evidence count: {instinct.evidence_count}
Generated: {now}
"""

    return content


def _sanitize_filename(name: str) -> str:
    """Sanitize a string to be a safe filename.

    Args:
        name: The raw name string.

    Returns:
        A safe filename-compatible string.
    """
    # Get just the basename to prevent path traversal
    safe_name = os.path.basename(name)
    # Defense in depth: handle edge cases where basename may not fully sanitize
    # (e.g., different OS path conventions, unusual characters)

    # Remove dangerous characters, keep only alphanumeric, dash, underscore, dot
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "-", safe_name)

    # Remove leading/trailing dashes and collapse multiple dashes
    safe_name = re.sub(r"-+", "-", safe_name).strip("-")

    # Ensure we have a valid filename
    if not safe_name:
        safe_name = "unnamed"

    return safe_name


def _get_evolution_directory(evolution_type: str) -> Path:
    """Get the directory for a given evolution type."""
    directory_map = {
        "skill": EVOLVED_SKILLS_DIR,
        "command": EVOLVED_COMMANDS_DIR,
        "agent": EVOLVED_AGENTS_DIR,
    }
    return directory_map.get(evolution_type, EVOLVED_AGENTS_DIR)


def _get_evolved_filename(
    evolution_type: str, source: Cluster | Instinct
) -> str:
    """Generate filename for an evolved file."""
    if evolution_type == "skill":
        if isinstance(source, Cluster):
            base_name = _sanitize_filename(source.domain.lower().replace(" ", "-"))
        else:
            base_name = _sanitize_filename(source.id)
        return f"{base_name}-skill.md"

    if isinstance(source, Instinct):
        base_name = _sanitize_filename(source.id)
        return f"{base_name}-{evolution_type}.md"

    return f"{evolution_type}.md"


def _validate_file_path(file_path: Path, directory: Path) -> None:
    """Validate that file path is safe to write to.

    Raises:
        ValueError: If the path is a symlink or outside the directory.
    """
    if file_path.is_symlink():
        raise ValueError(f"Refusing to write to symlink: {file_path}")

    resolved_path = file_path.resolve()
    resolved_dir = directory.resolve()
    if not resolved_path.is_relative_to(resolved_dir):
        raise ValueError("Path traversal detected")


def write_evolved_file(
    evolution_type: str,
    source: Cluster | Instinct,
    content: str,
) -> Path:
    """Write an evolved file to the appropriate directory.

    Args:
        evolution_type: Type of evolution ("skill", "command", "agent").
        source: The source Cluster or Instinct.
        content: The file content to write.

    Returns:
        Path to the created file.

    Raises:
        ValueError: If the resulting path would be outside the directory or is a symlink.
    """
    directory = _get_evolution_directory(evolution_type)
    filename = _get_evolved_filename(evolution_type, source)

    directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    file_path = directory / filename
    _validate_file_path(file_path, directory)

    file_path.write_text(content)
    return file_path
