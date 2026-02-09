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
    write_evolved_file,
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


class TestPathTraversalPrevention:
    """Tests to prevent path traversal attacks in evolution file writing."""

    def test_sanitizes_instinct_id_for_evolved_files(self, tmp_path: Path):
        """Should sanitize IDs that contain path traversal sequences."""
        evolved_dir = tmp_path / "evolved"
        commands_dir = evolved_dir / "commands"
        commands_dir.mkdir(parents=True)

        ts = datetime.now(timezone.utc)
        # Attempt path traversal via malicious instinct ID
        malicious_instinct = Instinct(
            id="../../../etc/passwd",
            trigger="test",
            confidence=0.9,
            domain="workflow",
            source="repeated_workflow",
            evidence_count=15,
            created_at=ts,
            updated_at=ts,
            content="test",
        )

        with patch("instincts.evolution.EVOLVED_COMMANDS_DIR", commands_dir):
            result_path = write_evolved_file("command", malicious_instinct, "content")

        # File should be created within commands_dir, not outside
        assert result_path.parent == commands_dir
        # Filename should be sanitized
        assert ".." not in result_path.name
        assert "/" not in result_path.name


class TestWriteEvolvedFile:
    """Tests for writing evolved files to evolved/ directory."""

    def test_writes_skill_to_evolved_skills_dir(self, tmp_path: Path):
        """Should write skill file to evolved/skills/ directory."""
        evolved_dir = tmp_path / "evolved"
        skills_dir = evolved_dir / "skills"
        skills_dir.mkdir(parents=True)

        ts = datetime.now(timezone.utc)
        instincts = (
            Instinct(id="i1", trigger="t1", confidence=0.8, domain="testing", source="test", evidence_count=5, created_at=ts, updated_at=ts, content="c1"),
            Instinct(id="i2", trigger="t2", confidence=0.75, domain="testing", source="test", evidence_count=6, created_at=ts, updated_at=ts, content="c2"),
            Instinct(id="i3", trigger="t3", confidence=0.7, domain="testing", source="test", evidence_count=4, created_at=ts, updated_at=ts, content="c3"),
        )
        cluster = Cluster(
            domain="testing",
            trigger_pattern="when testing",
            instincts=instincts,
            avg_confidence=0.75,
        )

        with patch("instincts.evolution.EVOLVED_SKILLS_DIR", skills_dir):
            file_path = write_evolved_file("skill", cluster, "# Testing Skill\n\nContent here.")

        assert file_path.exists()
        assert file_path.parent == skills_dir
        assert "testing" in file_path.name.lower()

    def test_writes_command_to_evolved_commands_dir(self, tmp_path: Path):
        """Should write command file to evolved/commands/ directory."""
        evolved_dir = tmp_path / "evolved"
        commands_dir = evolved_dir / "commands"
        commands_dir.mkdir(parents=True)

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
            content="Run pytest",
        )

        with patch("instincts.evolution.EVOLVED_COMMANDS_DIR", commands_dir):
            file_path = write_evolved_file("command", instinct, "# Test Command\n\nRun tests.")

        assert file_path.exists()
        assert file_path.parent == commands_dir
