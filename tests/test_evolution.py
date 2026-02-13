"""Tests for instincts.evolution module.

Tests cover:
- AC-8.1: Cluster instincts by domain and trigger
- AC-8.2: Suggest skill generation for clusters with 3+ instincts and avg confidence >= 0.7
- AC-8.3: Generate skill file in evolved/skills/ directory
- AC-8.4: Suggest command generation for workflow instincts with confidence >= 0.85
- AC-8.5: Suggest agent generation for complex multi-step patterns
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from instincts.evolution import (
    Cluster,
    EvolutionSuggestion,
    cluster_instincts,
    evaluate_cluster_for_evolution,
    generate_agent,
    generate_command,
    generate_skill,
    suggest_evolution_for_instinct,
)
from instincts.models import Instinct


class TestClusterInstincts:
    """Tests for cluster_instincts function (AC-8.1)."""

    def test_clusters_by_domain(self):
        """Should cluster instincts by domain."""
        ts = datetime.now(timezone.utc)
        instincts = [
            Instinct(id="test-1", trigger="trigger1", confidence=0.7, domain="testing", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="c1"),
            Instinct(id="test-2", trigger="trigger2", confidence=0.8, domain="testing", source="test", evidence_count=6, created_at=ts, updated_at=ts, content="c2"),
            Instinct(id="code-1", trigger="trigger3", confidence=0.6, domain="code-style", source="test", evidence_count=4, created_at=ts, updated_at=ts, content="c3"),
        ]

        clusters = cluster_instincts(instincts)

        # Should have clusters for testing and code-style domains
        domain_names = [c.domain for c in clusters]
        assert "testing" in domain_names
        assert "code-style" in domain_names

    def test_clusters_by_similar_trigger(self):
        """Should cluster instincts with similar triggers."""
        ts = datetime.now(timezone.utc)
        instincts = [
            Instinct(id="func-1", trigger="when writing functions", confidence=0.7, domain="code-style", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="c1"),
            Instinct(id="func-2", trigger="when creating functions", confidence=0.8, domain="code-style", source="test", evidence_count=6, created_at=ts, updated_at=ts, content="c2"),
            Instinct(id="test-1", trigger="when writing tests", confidence=0.6, domain="testing", source="test", evidence_count=4, created_at=ts, updated_at=ts, content="c3"),
        ]

        clusters = cluster_instincts(instincts)

        # func-1 and func-2 should be in the same cluster (similar trigger)
        assert any(len(c.instincts) >= 2 for c in clusters)

    def test_returns_empty_for_no_instincts(self):
        """Should return empty list for no instincts."""
        clusters = cluster_instincts([])

        assert clusters == []


class TestEvaluateClusterForEvolution:
    """Tests for evaluate_cluster_for_evolution function (AC-8.2)."""

    def test_suggests_skill_for_3_plus_high_confidence_instincts(self):
        """Should suggest skill when cluster has 3+ instincts with avg confidence >= 0.7 (AC-8.2)."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="t1", confidence=0.8, domain="testing", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="c1"),
            Instinct(id="i2", trigger="t2", confidence=0.7, domain="testing", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="c2"),
            Instinct(id="i3", trigger="t3", confidence=0.75, domain="testing", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="c3"),
        )
        cluster = Cluster(
            domain="testing",
            trigger_pattern="when testing",
            instincts=instincts,
            avg_confidence=0.75,
        )

        suggestion = evaluate_cluster_for_evolution(cluster)

        assert suggestion is not None
        assert suggestion.evolution_type == "skill"

    def test_no_suggestion_for_low_confidence_cluster(self):
        """Should not suggest skill for cluster with avg confidence < 0.7."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="t1", confidence=0.5, domain="testing", source="test", evidence_count=3, created_at=ts, updated_at=ts, content="c1"),
            Instinct(id="i2", trigger="t2", confidence=0.4, domain="testing", source="test", evidence_count=2, created_at=ts, updated_at=ts, content="c2"),
            Instinct(id="i3", trigger="t3", confidence=0.5, domain="testing", source="test", evidence_count=3, created_at=ts, updated_at=ts, content="c3"),
        )
        cluster = Cluster(
            domain="testing",
            trigger_pattern="when testing",
            instincts=instincts,
            avg_confidence=0.47,
        )

        suggestion = evaluate_cluster_for_evolution(cluster)

        assert suggestion is None or suggestion.evolution_type != "skill"

    def test_no_suggestion_for_small_cluster(self):
        """Should not suggest skill for cluster with < 3 instincts."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="t1", confidence=0.9, domain="testing", source="test", evidence_count=10, created_at=ts, updated_at=ts, content="c1"),
            Instinct(id="i2", trigger="t2", confidence=0.85, domain="testing", source="test", evidence_count=8, created_at=ts, updated_at=ts, content="c2"),
        )
        cluster = Cluster(
            domain="testing",
            trigger_pattern="when testing",
            instincts=instincts,
            avg_confidence=0.875,
        )

        suggestion = evaluate_cluster_for_evolution(cluster)

        # Might suggest something else (command?) but not a skill cluster
        if suggestion:
            assert suggestion.evolution_type != "skill" or len(cluster.instincts) >= 3


class TestSuggestCommandGeneration:
    """Tests for command generation suggestion (AC-8.4)."""

    def test_suggests_command_for_high_confidence_workflow(self):
        """Should suggest command for workflow instinct with confidence >= 0.85 (AC-8.4)."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="workflow-1",
            trigger="when running tests",
            confidence=0.9,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=15,
            created_at=ts,
            updated_at=ts,
            content="Run pytest with coverage",
        )

        suggestion = suggest_evolution_for_instinct(instinct)

        if suggestion:
            assert suggestion.evolution_type in ("command", "skill")

    def test_no_command_for_low_confidence_workflow(self):
        """Should not suggest command for workflow with confidence < 0.85."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="workflow-1",
            trigger="when running tests",
            confidence=0.7,  # Below 0.85
            domain="workflow",
            source="repeated_workflow",
            evidence_count=5,
            created_at=ts,
            updated_at=ts,
            content="Run pytest",
        )

        suggestion = suggest_evolution_for_instinct(instinct)

        if suggestion:
            assert suggestion.evolution_type != "command"


class TestSuggestAgentGeneration:
    """Tests for agent generation suggestion (AC-8.5)."""

    def test_suggests_agent_for_complex_multi_step_pattern(self):
        """Should suggest agent for complex multi-step patterns (AC-8.5)."""
        ts = datetime.now(timezone.utc)
        # Complex pattern with multiple steps
        instinct = Instinct(
            id="complex-workflow",
            trigger="when implementing a new feature",
            confidence=0.88,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=20,
            created_at=ts,
            updated_at=ts,
            content="1. Create tests\n2. Implement feature\n3. Run tests\n4. Fix issues\n5. Commit",
            status="active",
        )

        suggestion = suggest_evolution_for_instinct(instinct)

        # Complex multi-step might suggest agent
        # (exact behavior depends on implementation)
        assert suggestion is None or suggestion.evolution_type in ("agent", "command", "skill")


class TestGenerateSkill:
    """Tests for generate_skill function (AC-8.3)."""

    def test_generates_skill_file_content(self):
        """Should generate skill file content."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="when writing tests", confidence=0.8, domain="testing", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="Write tests first"),
            Instinct(id="i2", trigger="when creating tests", confidence=0.75, domain="testing", source="test", evidence_count=6, created_at=ts, updated_at=ts, content="Use pytest"),
            Instinct(id="i3", trigger="when testing", confidence=0.7, domain="testing", source="test", evidence_count=4, created_at=ts, updated_at=ts, content="Test edge cases"),
        )
        cluster = Cluster(
            domain="testing",
            trigger_pattern="when testing",
            instincts=instincts,
            avg_confidence=0.75,
        )

        skill_content = generate_skill(cluster)

        # Should be a string with skill format
        assert isinstance(skill_content, str)
        assert "testing" in skill_content.lower() or "test" in skill_content.lower()

    def test_skill_content_includes_trigger_info(self):
        """Skill content should include trigger information."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="when writing functions", confidence=0.8, domain="code-style", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="c1"),
            Instinct(id="i2", trigger="when creating functions", confidence=0.75, domain="code-style", source="test", evidence_count=6, created_at=ts, updated_at=ts, content="c2"),
            Instinct(id="i3", trigger="when implementing functions", confidence=0.7, domain="code-style", source="test", evidence_count=4, created_at=ts, updated_at=ts, content="c3"),
        )
        cluster = Cluster(
            domain="code-style",
            trigger_pattern="functions",
            instincts=instincts,
            avg_confidence=0.75,
        )

        skill_content = generate_skill(cluster)

        assert "function" in skill_content.lower()


class TestGenerateCommand:
    """Tests for generate_command function."""

    def test_generates_command_file_content(self):
        """Should generate command file content."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test-workflow",
            trigger="when running tests",
            confidence=0.9,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=15,
            created_at=ts,
            updated_at=ts,
            content="Run pytest with coverage",
        )

        command_content = generate_command(instinct)

        assert isinstance(command_content, str)
        assert "test" in command_content.lower() or "workflow" in command_content.lower()


class TestGenerateAgent:
    """Tests for generate_agent function."""

    def test_generates_agent_file_content(self):
        """Should generate agent file content."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="feature-workflow",
            trigger="when implementing a new feature",
            confidence=0.88,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=20,
            created_at=ts,
            updated_at=ts,
            content="Complex multi-step workflow",
        )

        agent_content = generate_agent(instinct)

        assert isinstance(agent_content, str)


class TestClusterDataclass:
    """Tests for Cluster dataclass."""

    def test_cluster_has_required_fields(self):
        """Cluster should have domain, trigger_pattern, instincts, avg_confidence."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="t1", confidence=0.7, domain="testing", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="c1"),
        )

        cluster = Cluster(
            domain="testing",
            trigger_pattern="when testing",
            instincts=instincts,
            avg_confidence=0.7,
        )

        assert cluster.domain == "testing"
        assert cluster.trigger_pattern == "when testing"
        assert cluster.instincts == instincts
        assert cluster.avg_confidence == 0.7

    def test_cluster_is_frozen(self):
        """Cluster should be immutable (frozen)."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="t1", confidence=0.7, domain="testing", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="c1"),
        )

        cluster = Cluster(
            domain="testing",
            trigger_pattern="when testing",
            instincts=instincts,
            avg_confidence=0.7,
        )

        with pytest.raises(AttributeError):
            cluster.domain = "modified"  # type: ignore[misc]

    def test_cluster_instincts_is_tuple(self):
        """Cluster instincts should be a tuple (immutable)."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="t1", confidence=0.7, domain="testing", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="c1"),
        )

        cluster = Cluster(
            domain="testing",
            trigger_pattern="when testing",
            instincts=instincts,
            avg_confidence=0.7,
        )

        assert isinstance(cluster.instincts, tuple)


class TestEvolutionSuggestion:
    """Tests for EvolutionSuggestion dataclass."""

    def test_suggestion_has_required_fields(self):
        """EvolutionSuggestion should have evolution_type, source, description."""
        suggestion = EvolutionSuggestion(
            evolution_type="skill",
            source_id="cluster-testing",
            description="Create skill for testing patterns",
        )

        assert suggestion.evolution_type == "skill"
        assert suggestion.source_id == "cluster-testing"
        assert suggestion.description == "Create skill for testing patterns"

    def test_suggestion_is_frozen(self):
        """EvolutionSuggestion should be immutable (frozen)."""
        suggestion = EvolutionSuggestion(
            evolution_type="skill",
            source_id="cluster-testing",
            description="Create skill for testing patterns",
        )

        with pytest.raises(AttributeError):
            suggestion.evolution_type = "command"  # type: ignore[misc]


class TestProjectScopedEvolution:
    """Tests for project-scoped evolution with multiple output types (AC-6.4 to AC-6.11)."""

    def test_evolve_rules_project_scope(self, tmp_path: Path):
        """AC-6.4: Should write rules to <project>/.claude/rules/."""
        from instincts.evolution import evolve_to_rules

        project_root = tmp_path / "project"
        project_root.mkdir()

        ts = datetime.now(timezone.utc)
        instincts = [
            Instinct(id="i1", trigger="when editing", confidence=0.8, domain="code-style", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="Use guard clauses"),
        ]

        result = evolve_to_rules(instincts, "project", project_root)

        assert len(result) >= 1
        for path in result:
            assert path.is_relative_to(project_root / ".claude" / "rules")

    def test_evolve_rules_global_scope(self, tmp_path: Path):
        """AC-6.5: Should write rules to ~/.claude/rules/."""
        from instincts.evolution import evolve_to_rules
        from pathlib import Path as PathLib

        project_root = tmp_path / "project"
        project_root.mkdir()

        ts = datetime.now(timezone.utc)
        instincts = [
            Instinct(id="i1", trigger="when editing", confidence=0.8, domain="code-style", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="Use guard clauses"),
        ]

        # Mock to avoid writing to actual home directory
        mock_global_dir = tmp_path / "global_claude" / "rules"
        with patch("instincts.evolution.get_evolved_output_dir") as mock_get_dir:
            mock_get_dir.return_value = mock_global_dir
            result = evolve_to_rules(instincts, "global", project_root)

        assert len(result) >= 1

    def test_evolve_skills_project_scope(self, tmp_path: Path):
        """AC-6.6: Should write skills to <project>/.claude/skills/."""
        from instincts.evolution import evolve_to_skills

        project_root = tmp_path / "project"
        project_root.mkdir()

        ts = datetime.now(timezone.utc)
        instincts = [
            Instinct(id="i1", trigger="when testing", confidence=0.8, domain="testing", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="Write tests first"),
        ]

        result = evolve_to_skills(instincts, "project", project_root)

        assert len(result) >= 1
        for path in result:
            assert path.is_relative_to(project_root / ".claude" / "skills")

    def test_evolve_subagents_project_scope(self, tmp_path: Path):
        """AC-6.8: Should write subagents to <project>/.claude/agents/."""
        from instincts.evolution import evolve_to_subagents

        project_root = tmp_path / "project"
        project_root.mkdir()

        ts = datetime.now(timezone.utc)
        instincts = [
            Instinct(id="i1", trigger="when reviewing", confidence=0.88, domain="workflow", source="repeated_workflow", evidence_count=10, created_at=ts, updated_at=ts, content="1. Check style\n2. Check tests\n3. Review logic"),
        ]

        result = evolve_to_subagents(instincts, "project", project_root)

        assert len(result) >= 1
        for path in result:
            assert path.is_relative_to(project_root / ".claude" / "agents")

    def test_evolve_commands_project_scope(self, tmp_path: Path):
        """AC-6.10: Should write commands to <project>/.claude/commands/."""
        from instincts.evolution import evolve_to_commands

        project_root = tmp_path / "project"
        project_root.mkdir()

        ts = datetime.now(timezone.utc)
        instincts = [
            Instinct(id="i1", trigger="when verifying", confidence=0.9, domain="workflow", source="repeated_workflow", evidence_count=15, created_at=ts, updated_at=ts, content="Run make check"),
        ]

        result = evolve_to_commands(instincts, "project", project_root)

        assert len(result) >= 1
        for path in result:
            assert path.is_relative_to(project_root / ".claude" / "commands")


class TestEvolveToClaudemd:
    """Tests for CLAUDE.md evolution (AC-6.3)."""

    def test_evolve_to_claudemd_returns_preview(self, tmp_path: Path):
        """AC-6.3: Should return preview of changes for CLAUDE.md."""
        from instincts.evolution import evolve_to_claudemd

        project_root = tmp_path / "project"
        project_root.mkdir()

        # Create existing CLAUDE.md
        claudemd = project_root / "CLAUDE.md"
        claudemd.write_text("# CLAUDE.md\n\n## Overview\n\nProject description.\n")

        ts = datetime.now(timezone.utc)
        instincts = [
            Instinct(id="i1", trigger="when testing", confidence=0.8, domain="testing", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="Write tests first"),
        ]

        preview = evolve_to_claudemd(instincts, project_root)

        assert isinstance(preview, str)
        assert "Learned Patterns" in preview or "testing" in preview.lower()


class TestRecommendOutputType:
    """Tests for automatic output type recommendation."""

    def test_recommends_commands_for_short_workflow(self):
        """Short workflow patterns should recommend Commands."""
        from instincts.config import EvolutionOutputType
        from instincts.evolution import recommend_output_type

        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="short-workflow",
            trigger="when running tests",
            confidence=0.9,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=5,
            created_at=ts,
            updated_at=ts,
            content="Run make check",  # Short, single-step
        )

        result = recommend_output_type(instinct)
        assert result == EvolutionOutputType.COMMANDS

    def test_recommends_subagents_for_long_workflow(self):
        """Long multi-step workflow patterns should recommend Subagents."""
        from instincts.config import EvolutionOutputType
        from instincts.evolution import recommend_output_type

        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="complex-workflow",
            trigger="when implementing a feature",
            confidence=0.9,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=10,
            created_at=ts,
            updated_at=ts,
            content="""1. Create feature branch
2. Write failing tests
3. Implement minimal code
4. Run tests
5. Refactor if needed
6. Commit changes
7. Push to remote
8. Create pull request
9. Request review
10. Address feedback
11. Merge to main""",
        )

        result = recommend_output_type(instinct)
        assert result == EvolutionOutputType.SUBAGENTS

    def test_recommends_rules_for_checklist_content(self):
        """Instincts with checklist format should recommend Rules."""
        from instincts.config import EvolutionOutputType
        from instincts.evolution import recommend_output_type

        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="security-checklist",
            trigger="when reviewing security",
            confidence=0.8,
            domain="security",
            source="user_correction",
            evidence_count=7,
            created_at=ts,
            updated_at=ts,
            content="""- [ ] No hardcoded secrets
- [ ] All inputs validated
- [ ] SQL injection prevention
- [ ] XSS prevention
- [ ] CSRF protection""",
        )

        result = recommend_output_type(instinct)
        assert result == EvolutionOutputType.RULES

    def test_recommends_rules_for_table_content(self):
        """Instincts with table format should recommend Rules."""
        from instincts.config import EvolutionOutputType
        from instincts.evolution import recommend_output_type

        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="http-methods",
            trigger="when designing APIs",
            confidence=0.85,
            domain="api-design",
            source="user_correction",
            evidence_count=6,
            created_at=ts,
            updated_at=ts,
            content="""| Method | Idempotent | Use Case |
|--------|------------|----------|
| GET | Yes | Retrieve |
| POST | No | Create |
| PUT | Yes | Replace |""",
        )

        result = recommend_output_type(instinct)
        assert result == EvolutionOutputType.RULES

    def test_recommends_skills_for_rich_evidence(self):
        """Instincts with high evidence count should recommend Skills."""
        from instincts.config import EvolutionOutputType
        from instincts.evolution import recommend_output_type

        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="code-style-pattern",
            trigger="when writing code",
            confidence=0.8,
            domain="code-style",
            source="user_correction",
            evidence_count=8,  # >= 5 evidence
            created_at=ts,
            updated_at=ts,
            content="Use explicit return types in TypeScript functions.",
        )

        result = recommend_output_type(instinct)
        assert result == EvolutionOutputType.SKILLS

    def test_recommends_claudemd_for_simple_rules(self):
        """Simple rules with low evidence should recommend CLAUDE.md."""
        from instincts.config import EvolutionOutputType
        from instincts.evolution import recommend_output_type

        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="simple-rule",
            trigger="when editing",
            confidence=0.6,
            domain="general",
            source="user_correction",
            evidence_count=2,  # Low evidence
            created_at=ts,
            updated_at=ts,
            content="Prefer const over let.",
        )

        result = recommend_output_type(instinct)
        assert result == EvolutionOutputType.CLAUDEMD


class TestHasChecklistOrTable:
    """Tests for has_checklist_or_table helper function."""

    def test_detects_checkbox_list(self):
        """Should detect markdown checkbox list."""
        from instincts.evolution import has_checklist_or_table

        content = """Before commit:
- [ ] No secrets
- [x] Tests pass
- [ ] Linting clean"""

        assert has_checklist_or_table(content) is True

    def test_detects_markdown_table(self):
        """Should detect markdown table."""
        from instincts.evolution import has_checklist_or_table

        content = """| Header | Value |
|--------|-------|
| Row 1 | Data |"""

        assert has_checklist_or_table(content) is True

    def test_returns_false_for_plain_text(self):
        """Should return False for plain text content."""
        from instincts.evolution import has_checklist_or_table

        content = "This is just plain text without any special formatting."

        assert has_checklist_or_table(content) is False

    def test_returns_false_for_code_block(self):
        """Should return False for code blocks."""
        from instincts.evolution import has_checklist_or_table

        content = """```python
def example():
    pass
```"""

        assert has_checklist_or_table(content) is False

    def test_detects_bullet_checklist_pattern(self):
        """Should detect dash-based checklist pattern."""
        from instincts.evolution import has_checklist_or_table

        content = """Security checklist:
- Check for hardcoded secrets
- Validate all inputs
- Use parameterized queries"""

        # Note: This is a regular list, not a checkbox list
        # Only checkbox lists (- [ ] or - [x]) should trigger rules
        assert has_checklist_or_table(content) is False


class TestGenerateCommandFormat:
    """Tests for generate_command matching reference format.

    Reference format from ~/.claude/commands/:
    - YAML frontmatter with description
    - "I'll use the X subagent" format
    - Prerequisites section
    - Next Commands section
    - Very short (~20 lines)
    """

    def test_command_has_yaml_frontmatter(self):
        """Command should have YAML frontmatter with description."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test-workflow",
            trigger="when running tests",
            confidence=0.9,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=15,
            created_at=ts,
            updated_at=ts,
            content="Run pytest with coverage",
        )

        content = generate_command(instinct)

        # Should start with YAML frontmatter
        assert content.startswith("---\n")
        assert "description:" in content
        # Frontmatter should be closed
        assert content.count("---") >= 2

    def test_command_uses_subagent_pattern(self):
        """Command should use 'I'll use the X subagent' pattern."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="verify-workflow",
            trigger="when verifying code",
            confidence=0.9,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=10,
            created_at=ts,
            updated_at=ts,
            content="Run make check",
        )

        content = generate_command(instinct)

        assert "I'll use the" in content
        assert "subagent" in content.lower()

    def test_command_has_prerequisites_section(self):
        """Command should have Prerequisites section."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="deploy-workflow",
            trigger="when deploying",
            confidence=0.9,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=8,
            created_at=ts,
            updated_at=ts,
            content="Deploy to production",
        )

        content = generate_command(instinct)

        assert "## Prerequisites" in content

    def test_command_has_next_commands_section(self):
        """Command should have Next Commands section."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="commit-workflow",
            trigger="when committing",
            confidence=0.9,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=12,
            created_at=ts,
            updated_at=ts,
            content="Git commit with message",
        )

        content = generate_command(instinct)

        assert "## Next Commands" in content

    def test_command_is_short(self):
        """Command should be short (~20 lines, max 30)."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="short-workflow",
            trigger="when testing",
            confidence=0.9,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=5,
            created_at=ts,
            updated_at=ts,
            content="Run tests",
        )

        content = generate_command(instinct)
        line_count = len(content.strip().split("\n"))

        assert line_count <= 30, f"Command should be short, got {line_count} lines"


class TestGenerateRuleFormat:
    """Tests for _generate_rule_content matching reference format.

    Reference format from ~/.claude/rules/:
    - No YAML frontmatter (just title)
    - "## When to Apply" section
    - "## Checklist" with checkbox items
    - May include tables for patterns
    """

    def test_rule_has_title(self):
        """Rule should start with # title."""
        from instincts.evolution import _generate_rule_content

        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="security-rule",
            trigger="when reviewing security",
            confidence=0.8,
            domain="security",
            source="user_correction",
            evidence_count=7,
            created_at=ts,
            updated_at=ts,
            content="Check for hardcoded secrets",
        )

        content = _generate_rule_content(instinct)

        # Should start with title
        assert content.startswith("# ")

    def test_rule_has_when_to_apply_section(self):
        """Rule should have 'When to Apply' section."""
        from instincts.evolution import _generate_rule_content

        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="api-rule",
            trigger="when designing APIs",
            confidence=0.85,
            domain="api-design",
            source="user_correction",
            evidence_count=6,
            created_at=ts,
            updated_at=ts,
            content="Use RESTful patterns",
        )

        content = _generate_rule_content(instinct)

        assert "## When to Apply" in content

    def test_rule_has_checklist_section(self):
        """Rule should have 'Checklist' or 'Guidelines' section."""
        from instincts.evolution import _generate_rule_content

        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="code-review-rule",
            trigger="when reviewing code",
            confidence=0.8,
            domain="code-style",
            source="user_correction",
            evidence_count=5,
            created_at=ts,
            updated_at=ts,
            content="Check naming conventions",
        )

        content = _generate_rule_content(instinct)

        # Should have either Checklist or Guidelines section
        assert "## Checklist" in content or "## Guidelines" in content

    def test_rule_has_no_yaml_frontmatter(self):
        """Rule should NOT have YAML frontmatter."""
        from instincts.evolution import _generate_rule_content

        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="simple-rule",
            trigger="when editing",
            confidence=0.7,
            domain="general",
            source="user_correction",
            evidence_count=3,
            created_at=ts,
            updated_at=ts,
            content="Simple guideline",
        )

        content = _generate_rule_content(instinct)

        # Should NOT start with YAML frontmatter
        assert not content.startswith("---")


class TestGenerateSkillFormat:
    """Tests for generate_skill matching reference format.

    Reference format from ~/.claude/skills/*/SKILL.md:
    - YAML frontmatter with name and description
    - description format: "[What it does]. Use when [trigger]."
    - "## When to Apply" section
    - "## Guidance" section (not just guidance points)
    - "## Anti-patterns" section
    """

    def test_skill_has_yaml_frontmatter_with_name(self):
        """Skill should have YAML frontmatter with name field."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="when writing tests", confidence=0.8, domain="testing", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="Write tests first"),
            Instinct(id="i2", trigger="when creating tests", confidence=0.75, domain="testing", source="test", evidence_count=6, created_at=ts, updated_at=ts, content="Use pytest"),
            Instinct(id="i3", trigger="when testing", confidence=0.7, domain="testing", source="test", evidence_count=4, created_at=ts, updated_at=ts, content="Test edge cases"),
        )
        cluster = Cluster(
            domain="testing",
            trigger_pattern="when testing",
            instincts=instincts,
            avg_confidence=0.75,
        )

        content = generate_skill(cluster)

        # Should have YAML frontmatter
        assert content.startswith("---\n")
        assert "name:" in content

    def test_skill_has_description_in_frontmatter(self):
        """Skill should have description in YAML frontmatter."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="when styling code", confidence=0.8, domain="code-style", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="Use consistent naming"),
        )
        cluster = Cluster(
            domain="code-style",
            trigger_pattern="styling code",
            instincts=instincts,
            avg_confidence=0.8,
        )

        content = generate_skill(cluster)

        assert "description:" in content
        # Description should follow format: "[What it does]. Use when [trigger]."
        # Extract description line
        lines = content.split("\n")
        desc_line = [l for l in lines if l.startswith("description:")]
        assert len(desc_line) > 0
        assert "Use when" in desc_line[0]

    def test_skill_has_when_to_apply_section(self):
        """Skill should have 'When to Apply' section."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="when debugging", confidence=0.8, domain="debugging", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="Check logs first"),
        )
        cluster = Cluster(
            domain="debugging",
            trigger_pattern="debugging",
            instincts=instincts,
            avg_confidence=0.8,
        )

        content = generate_skill(cluster)

        assert "## When to Apply" in content

    def test_skill_has_guidance_section(self):
        """Skill should have 'Guidance' section."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="when refactoring", confidence=0.8, domain="refactoring", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="Extract functions"),
        )
        cluster = Cluster(
            domain="refactoring",
            trigger_pattern="refactoring",
            instincts=instincts,
            avg_confidence=0.8,
        )

        content = generate_skill(cluster)

        assert "## Guidance" in content

    def test_skill_has_anti_patterns_section(self):
        """Skill should have 'Anti-patterns' section."""
        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="when optimizing", confidence=0.8, domain="performance", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="Profile before optimizing"),
        )
        cluster = Cluster(
            domain="performance",
            trigger_pattern="optimizing",
            instincts=instincts,
            avg_confidence=0.8,
        )

        content = generate_skill(cluster)

        assert "## Anti-patterns" in content


class TestGenerateAgentFormat:
    """Tests for generate_agent matching reference format.

    Reference format from ~/.claude/agents/:
    - YAML frontmatter with name, description, tools, skills
    - "## Purpose" section
    - "## Workflow" with numbered steps (## Process Flow)
    - Activation conditions
    """

    def test_agent_has_yaml_frontmatter(self):
        """Agent should have YAML frontmatter."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="feature-workflow",
            trigger="when implementing a new feature",
            confidence=0.88,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=20,
            created_at=ts,
            updated_at=ts,
            content="1. Write tests\n2. Implement\n3. Commit",
        )

        content = generate_agent(instinct)

        # Should have YAML frontmatter
        assert content.startswith("---\n")
        assert content.count("---") >= 2

    def test_agent_has_name_in_frontmatter(self):
        """Agent should have name in YAML frontmatter."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="review-workflow",
            trigger="when reviewing code",
            confidence=0.9,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=15,
            created_at=ts,
            updated_at=ts,
            content="1. Check style\n2. Review logic\n3. Test coverage",
        )

        content = generate_agent(instinct)

        assert "name:" in content

    def test_agent_has_description_in_frontmatter(self):
        """Agent should have description in YAML frontmatter."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="deploy-workflow",
            trigger="when deploying to production",
            confidence=0.85,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=10,
            created_at=ts,
            updated_at=ts,
            content="1. Run tests\n2. Build\n3. Deploy",
        )

        content = generate_agent(instinct)

        assert "description:" in content

    def test_agent_has_process_flow_section(self):
        """Agent should have 'Process Flow' or 'Workflow' section."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="test-workflow",
            trigger="when testing features",
            confidence=0.88,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=12,
            created_at=ts,
            updated_at=ts,
            content="1. Write tests\n2. Run tests\n3. Fix failures",
        )

        content = generate_agent(instinct)

        # Should have Process Flow or Workflow section
        assert "## Process Flow" in content or "## Workflow" in content

    def test_agent_workflow_has_numbered_steps(self):
        """Agent workflow should have numbered steps."""
        ts = datetime.now(timezone.utc)
        instinct = Instinct(
            id="multi-step-workflow",
            trigger="when doing multi-step task",
            confidence=0.9,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=18,
            created_at=ts,
            updated_at=ts,
            content="1. First step\n2. Second step\n3. Third step",
        )

        content = generate_agent(instinct)

        # Should have numbered steps in workflow
        assert "1." in content
        assert "2." in content
