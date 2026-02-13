"""Evolution system for Instinct-Based Learning.

This module provides the evolution system that:
- Clusters related instincts by domain and trigger
- Evaluates clusters for evolution into skills/commands/agents
- Generates skill, command, and agent files
- Recommends optimal output types for instinct evolution

Output Type Recommendation Logic:
1. Workflow patterns with <= 10 lines -> Commands (subagent calls)
2. Workflow patterns with > 10 lines -> Subagents (complex multi-step)
3. Checklist/table format content -> Rules
4. High evidence count (>= 5) -> Skills (domain knowledge)
5. Default (simple patterns) -> CLAUDE.md (project-specific rules)
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from instincts.claudemd import generate_patterns_content, insert_patterns
from instincts.config import (
    EvolutionOutputType,
    EvolutionScope,
    get_evolved_output_dir,
)
from instincts.models import Instinct

# Evolution thresholds
MIN_CLUSTER_SIZE_FOR_SKILL: int = 3
MIN_AVG_CONFIDENCE_FOR_SKILL: float = 0.7
MIN_CONFIDENCE_FOR_COMMAND: float = 0.85

# Trigger similarity threshold for clustering instincts
TRIGGER_SIMILARITY_THRESHOLD: float = 0.3

# Thresholds for output type recommendation
WORKFLOW_LINE_THRESHOLD: int = 10  # Lines above this suggest subagent
MIN_EVIDENCE_FOR_SKILL: int = 5  # Evidence count threshold for skills


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
    """Extract meaningful keywords from a trigger string.

    Filters out common stop words and short words to identify
    key terms for trigger similarity comparison.

    Args:
        trigger: The trigger string to extract keywords from.

    Returns:
        Set of lowercase keywords.
    """
    stop_words = {"when", "the", "a", "an", "to", "for", "of", "in", "on", "is", "are"}
    words = trigger.lower().split()
    return {w for w in words if w not in stop_words and len(w) > 2}


def _trigger_similarity(trigger1: str, trigger2: str) -> float:
    """Calculate Jaccard similarity between two triggers based on keyword overlap.

    Args:
        trigger1: First trigger string.
        trigger2: Second trigger string.

    Returns:
        Similarity score between 0.0 and 1.0 (Jaccard index).
    """
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
    """Group instincts by their domain.

    Args:
        instincts: List of instincts to group.

    Returns:
        Dictionary mapping domain names to lists of instincts.
    """
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
    """Calculate a trigger pattern from common keywords in cluster instincts.

    Args:
        cluster_instincts: List of instincts in the cluster.
        default: Default pattern to return if no keywords found.

    Returns:
        Space-separated string of up to 3 common keywords, or the default.
    """
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
    """Find instincts similar to seed based on trigger similarity.

    Args:
        seed_instinct: The seed instinct to compare against.
        candidates: List of candidate instincts to search.
        used_indices: Set of indices already assigned to clusters (modified in-place).
        start_index: Index of the seed instinct in candidates.

    Returns:
        List of similar instincts including the seed.
    """
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
    """Create a Cluster object from a list of instincts.

    Args:
        domain: The domain for the cluster.
        cluster_instincts: List of instincts to include in the cluster.

    Returns:
        Cluster object with calculated average confidence and trigger pattern.
    """
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

# Patterns for detecting checklist and table content
CHECKBOX_PATTERN = re.compile(r"^\s*-\s*\[[x ]\]", re.MULTILINE | re.IGNORECASE)
TABLE_PATTERN = re.compile(r"^\s*\|[^|]+\|[^|]+\|", re.MULTILINE)


def has_checklist_or_table(content: str) -> bool:
    """Check if content contains checklist (checkbox) or table format.

    Args:
        content: The content to check.

    Returns:
        True if content contains checkbox list (- [ ] or - [x]) or markdown table.
    """
    # Check for checkbox list pattern
    if CHECKBOX_PATTERN.search(content):
        return True

    # Check for markdown table pattern
    if TABLE_PATTERN.search(content):
        return True

    return False


def recommend_output_type(instinct: Instinct) -> EvolutionOutputType:
    """Recommend the best output type for evolving an instinct.

    The recommendation logic follows these priorities:
    1. Workflow patterns with few lines -> Commands (subagent calls)
    2. Workflow patterns with many lines -> Subagents (complex multi-step)
    3. Checklist/table format -> Rules
    4. High evidence count -> Skills (domain knowledge)
    5. Default -> CLAUDE.md (simple project rules)

    Args:
        instinct: The instinct to analyze.

    Returns:
        Recommended EvolutionOutputType.
    """
    content_lines = len(instinct.content.split("\n"))

    # CR-008: Combined workflow source check with else clause
    if instinct.source in WORKFLOW_SOURCES:
        # Multi-step workflow with few lines -> Commands (subagent call)
        if content_lines <= WORKFLOW_LINE_THRESHOLD:
            return EvolutionOutputType.COMMANDS
        # Complex workflow with many lines -> Subagents
        else:
            return EvolutionOutputType.SUBAGENTS

    # Checklist/table format -> Rules
    if has_checklist_or_table(instinct.content):
        return EvolutionOutputType.RULES

    # Rich domain knowledge (high evidence) -> Skills
    if instinct.evidence_count >= MIN_EVIDENCE_FOR_SKILL:
        return EvolutionOutputType.SKILLS

    # Simple rules -> CLAUDE.md
    return EvolutionOutputType.CLAUDEMD


def _has_multi_step_workflow(content: str) -> bool:
    """Check if content suggests a multi-step workflow.

    Args:
        content: The content to check.

    Returns:
        True if content contains indicators like numbered steps or "then".
    """
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


def _generate_skill_name(domain: str) -> str:
    """Generate a kebab-case skill name from domain.

    Args:
        domain: The domain name.

    Returns:
        Kebab-case formatted skill name.
    """
    return domain.lower().replace(" ", "-").replace("_", "-")


def generate_skill(cluster: Cluster) -> str:
    """Generate skill file content from a cluster of instincts.

    Format follows reference from ~/.claude/skills/*/SKILL.md:
    - YAML frontmatter with name and description
    - description: "[What it does]. Use when [trigger]."
    - "## When to Apply" section
    - "## Guidance" section
    - "## Anti-patterns" section

    Args:
        cluster: The cluster to generate a skill from.

    Returns:
        Skill file content as a string.
    """
    skill_name = _generate_skill_name(cluster.domain)

    # Collect all guidance from instincts
    guidance_points: list[str] = []
    for inst in cluster.instincts:
        # Extract key points from instinct content
        if inst.content:
            # Take the first paragraph or action section
            lines = inst.content.split("\n")
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#") and len(line) > 10:
                    guidance_points.append(f"- {line}")
                    break

    # Format guidance section
    guidance_section = (
        "\n".join(guidance_points)
        if guidance_points
        else "- Follow learned patterns for this domain"
    )

    # Build description for frontmatter
    description = f"{cluster.domain.title()} patterns learned from observations. Use when {cluster.trigger_pattern}."

    content = f"""---
name: {skill_name}
description: "{description}"
---

# {cluster.domain.title()} Skill

## When to Apply

{cluster.trigger_pattern}

## Guidance

{guidance_section}

## Anti-patterns

- Avoid inconsistent patterns within this domain
- Do not ignore learned conventions
"""

    return content


def _generate_command_name(instinct_id: str) -> str:
    """Generate a kebab-case command name from instinct ID.

    Args:
        instinct_id: The instinct ID.

    Returns:
        Kebab-case formatted command name.
    """
    return instinct_id.lower().replace("_", "-")


def generate_command(instinct: Instinct) -> str:
    """Generate command file content from an instinct.

    Format follows reference from ~/.claude/commands/:
    - YAML frontmatter with description
    - "I'll use the X subagent" pattern
    - Prerequisites section
    - Next Commands section
    - Very short (~20 lines)

    Args:
        instinct: The instinct to generate a command from.

    Returns:
        Command file content as a string.
    """
    command_name = _generate_command_name(instinct.id)
    agent_name = command_name.replace("-workflow", "").replace("-", "-")

    content = f"""---
description: "{instinct.trigger.capitalize()} using a learned workflow pattern."
---

I'll use the {agent_name} subagent to handle this process.

The {agent_name} subagent will:
- {instinct.content}

## Prerequisites
- Required context available

## Next Commands
After completion:
- Continue with next workflow step
"""

    return content


def _generate_agent_name(instinct_id: str) -> str:
    """Generate a kebab-case agent name from instinct ID.

    Args:
        instinct_id: The instinct ID.

    Returns:
        Kebab-case formatted agent name with '-workflow' suffix removed.
    """
    name = instinct_id.lower().replace("_", "-")
    if name.endswith("-workflow"):
        name = name[:-9]  # Remove "-workflow" suffix
    return name


def generate_agent(instinct: Instinct) -> str:
    """Generate agent file content from a complex workflow instinct.

    Format follows reference from ~/.claude/agents/:
    - YAML frontmatter with name, description, tools, skills
    - "## Process Flow" with numbered steps
    - Clear activation conditions

    Args:
        instinct: The instinct to generate an agent from.

    Returns:
        Agent file content as a string.
    """
    agent_name = _generate_agent_name(instinct.id)

    content = f"""---
name: {agent_name}
description: {instinct.trigger.capitalize()}
tools: Bash, Read, Grep, Glob
skills: []
---

You are an expert {agent_name} specialist. Handle this workflow professionally.

## Process Flow

{instinct.content}

## Activation

This agent activates when: {instinct.trigger}

## When to Ask User

Only ask for help if:
- Error is unclear or ambiguous
- Fix requires decisions outside this workflow
"""

    return content


def _sanitize_filename(name: str) -> str:
    """Sanitize a string to be a safe filename.

    Args:
        name: The raw name string.

    Returns:
        A safe filename-compatible string.
    """
    from instincts.utils import sanitize_id

    return sanitize_id(name, allow_dots=True)


def _get_evolved_filename(
    evolution_type: str, source: Cluster | Instinct
) -> str:
    """Generate filename for an evolved file.

    Args:
        evolution_type: Type of evolution ("skill", "command", "agent").
        source: The source Cluster or Instinct.

    Returns:
        Sanitized filename with appropriate suffix.
    """
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


def _write_evolved_file_to_dir(
    directory: Path,
    filename: str,
    content: str,
) -> Path:
    """Write an evolved file to a specific directory.

    Args:
        directory: Directory to write to.
        filename: Name of the file.
        content: The file content to write.

    Returns:
        Path to the created file.
    """
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    file_path = directory / filename
    _validate_file_path(file_path, directory)

    file_path.write_text(content)
    return file_path


def _generate_rule_content(instinct: Instinct) -> str:
    """Generate rule file content from an instinct.

    Format follows reference from ~/.claude/rules/:
    - No YAML frontmatter (just title)
    - "## When to Apply" section
    - "## Checklist" or "## Guidelines" section
    - May include tables for patterns
    """
    # Convert content to checklist format if not already
    content_lines = instinct.content.strip().split("\n")
    checklist_items: list[str] = []
    for line in content_lines:
        line = line.strip()
        if line and not line.startswith("#"):
            # Convert to checklist item if not already
            if line.startswith("- [ ]") or line.startswith("- [x]"):
                checklist_items.append(line)
            elif line.startswith("- "):
                checklist_items.append(f"- [ ] {line[2:]}")
            else:
                checklist_items.append(f"- [ ] {line}")

    checklist_section = "\n".join(checklist_items) if checklist_items else f"- [ ] {instinct.content}"

    return f"""# {instinct.trigger.title()}

## When to Apply

{instinct.trigger}

## Checklist

{checklist_section}
"""


def evolve_to_rules(
    instincts: list[Instinct],
    scope: EvolutionScope,
    project_root: Path,
) -> list[Path]:
    """Evolve instincts to rule files.

    Args:
        instincts: List of instincts to evolve.
        scope: Scope of the output (project or global).
        project_root: Path to the project root.

    Returns:
        List of paths to created rule files.
    """
    directory = get_evolved_output_dir(EvolutionOutputType.RULES, scope, project_root)
    created_files: list[Path] = []

    for instinct in instincts:
        content = _generate_rule_content(instinct)
        filename = f"{_sanitize_filename(instinct.id)}.md"
        file_path = _write_evolved_file_to_dir(directory, filename, content)
        created_files.append(file_path)

    return created_files


def evolve_to_skills(
    instincts: list[Instinct],
    scope: EvolutionScope,
    project_root: Path,
) -> list[Path]:
    """Evolve instincts to skill files.

    Args:
        instincts: List of instincts to evolve.
        scope: Scope of the output (project or global).
        project_root: Path to the project root.

    Returns:
        List of paths to created skill files.
    """
    directory = get_evolved_output_dir(EvolutionOutputType.SKILLS, scope, project_root)
    created_files: list[Path] = []

    # Group by domain for better organization
    by_domain: dict[str, list[Instinct]] = {}
    for inst in instincts:
        if inst.domain not in by_domain:
            by_domain[inst.domain] = []
        by_domain[inst.domain].append(inst)

    for domain, domain_instincts in by_domain.items():
        cluster = _create_cluster_from_instincts(domain, domain_instincts)
        content = generate_skill(cluster)
        filename = f"{_sanitize_filename(domain)}-skill.md"
        file_path = _write_evolved_file_to_dir(directory, filename, content)
        created_files.append(file_path)

    return created_files


def evolve_to_subagents(
    instincts: list[Instinct],
    scope: EvolutionScope,
    project_root: Path,
) -> list[Path]:
    """Evolve instincts to subagent files.

    Args:
        instincts: List of instincts to evolve.
        scope: Scope of the output (project or global).
        project_root: Path to the project root.

    Returns:
        List of paths to created subagent files.
    """
    directory = get_evolved_output_dir(EvolutionOutputType.SUBAGENTS, scope, project_root)
    created_files: list[Path] = []

    for instinct in instincts:
        content = generate_agent(instinct)
        filename = f"{_sanitize_filename(instinct.id)}-agent.md"
        file_path = _write_evolved_file_to_dir(directory, filename, content)
        created_files.append(file_path)

    return created_files


def evolve_to_commands(
    instincts: list[Instinct],
    scope: EvolutionScope,
    project_root: Path,
) -> list[Path]:
    """Evolve instincts to command files.

    Args:
        instincts: List of instincts to evolve.
        scope: Scope of the output (project or global).
        project_root: Path to the project root.

    Returns:
        List of paths to created command files.
    """
    directory = get_evolved_output_dir(EvolutionOutputType.COMMANDS, scope, project_root)
    created_files: list[Path] = []

    for instinct in instincts:
        content = generate_command(instinct)
        filename = f"{_sanitize_filename(instinct.id)}-command.md"
        file_path = _write_evolved_file_to_dir(directory, filename, content)
        created_files.append(file_path)

    return created_files


def evolve_to_claudemd(
    instincts: list[Instinct],
    project_root: Path,
) -> str:
    """Evolve instincts to CLAUDE.md content.

    Args:
        instincts: List of instincts to evolve.
        project_root: Path to the project root.

    Returns:
        Preview of the CLAUDE.md content with patterns added.
    """
    claudemd_path = project_root / "CLAUDE.md"
    patterns_content = generate_patterns_content(instincts)
    return insert_patterns(claudemd_path, patterns_content)
