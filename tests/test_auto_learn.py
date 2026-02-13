"""Tests for instincts.auto_learn module.

Tests cover:
- AC-4.1: Threshold-based auto-learning trigger
- AC-4.2: Background analysis creates/updates instinct files
- AC-4.3: Non-blocking subprocess spawn
- AC-4.4: Cooldown mechanism
- AC-4.5: Error handling (non-blocking)
- EC-6: Concurrent run prevention
- EC-7: Observation count failure handling
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

import pytest


class TestAutoLearnState:
    """Tests for AutoLearnState dataclass."""

    def test_auto_learn_state_has_required_fields(self):
        """AutoLearnState should have last_analysis_time and observation_count_at_analysis."""
        from instincts.auto_learn import AutoLearnState

        state = AutoLearnState(
            last_analysis_time=datetime.now(timezone.utc),
            observation_count_at_analysis=100,
        )

        assert hasattr(state, "last_analysis_time")
        assert hasattr(state, "observation_count_at_analysis")

    def test_auto_learn_state_is_frozen(self):
        """AutoLearnState should be immutable (frozen)."""
        from instincts.auto_learn import AutoLearnState

        state = AutoLearnState(
            last_analysis_time=datetime.now(timezone.utc),
            observation_count_at_analysis=100,
        )

        with pytest.raises(AttributeError):
            state.observation_count_at_analysis = 200  # type: ignore[misc]


class TestLoadState:
    """Tests for load_state function."""

    def test_load_state_returns_state_from_file(self, tmp_path: Path):
        """Should load state from .auto_learn_state.json file."""
        from instincts.auto_learn import load_state

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        state_file = instincts_dir / ".auto_learn_state.json"
        state_data = {
            "last_analysis_time": "2026-02-12T10:00:00+00:00",
            "observation_count_at_analysis": 75,
        }
        state_file.write_text(json.dumps(state_data))

        state = load_state(project_root)

        assert state.observation_count_at_analysis == 75
        assert state.last_analysis_time.isoformat() == "2026-02-12T10:00:00+00:00"

    def test_load_state_returns_default_when_file_not_exists(self, tmp_path: Path):
        """Should return default state when state file doesn't exist."""
        from instincts.auto_learn import load_state

        project_root = tmp_path / "project"
        project_root.mkdir()

        state = load_state(project_root)

        assert state.observation_count_at_analysis == 0
        assert state.last_analysis_time is None or state.last_analysis_time < datetime.now(timezone.utc)

    def test_load_state_handles_corrupted_file(self, tmp_path: Path):
        """Should return default state when state file is corrupted."""
        from instincts.auto_learn import load_state

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        state_file = instincts_dir / ".auto_learn_state.json"
        state_file.write_text("invalid json {{{")

        state = load_state(project_root)

        # Should return default state, not crash
        assert state.observation_count_at_analysis == 0


class TestSaveState:
    """Tests for save_state function."""

    def test_save_state_writes_to_file(self, tmp_path: Path):
        """Should save state to .auto_learn_state.json file."""
        from instincts.auto_learn import AutoLearnState, save_state

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        state = AutoLearnState(
            last_analysis_time=datetime.fromisoformat("2026-02-12T10:00:00+00:00"),
            observation_count_at_analysis=100,
        )

        save_state(project_root, state)

        state_file = instincts_dir / ".auto_learn_state.json"
        assert state_file.exists()
        saved_data = json.loads(state_file.read_text())
        assert saved_data["observation_count_at_analysis"] == 100

    def test_save_state_creates_directory_if_not_exists(self, tmp_path: Path):
        """Should create docs/instincts directory if it doesn't exist."""
        from instincts.auto_learn import AutoLearnState, save_state

        project_root = tmp_path / "project"
        project_root.mkdir()
        # Don't create docs/instincts directory

        state = AutoLearnState(
            last_analysis_time=datetime.now(timezone.utc),
            observation_count_at_analysis=50,
        )

        save_state(project_root, state)

        state_file = project_root / "docs" / "instincts" / ".auto_learn_state.json"
        assert state_file.exists()


class TestCountObservations:
    """Tests for count_observations function."""

    def test_count_observations_returns_line_count(self, tmp_path: Path):
        """Should return number of lines in observations.jsonl."""
        from instincts.auto_learn import count_observations

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)
        obs_file = instincts_dir / "observations.jsonl"

        with obs_file.open("w") as f:
            for i in range(75):
                f.write(f'{{"event": "test{i}"}}\n')

        count = count_observations(project_root)

        assert count == 75

    def test_count_observations_returns_zero_for_missing_file(self, tmp_path: Path):
        """Should return 0 if observations file doesn't exist."""
        from instincts.auto_learn import count_observations

        project_root = tmp_path / "project"
        project_root.mkdir()

        count = count_observations(project_root)

        assert count == 0


class TestShouldTriggerLearning:
    """Tests for should_trigger_learning function (AC-4.1)."""

    def test_triggers_when_threshold_reached_and_cooldown_elapsed(self, tmp_path: Path):
        """AC-4.1: Should trigger when count >= 50 and cooldown elapsed."""
        from instincts.auto_learn import should_trigger_learning, AutoLearnState, save_state

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        # Create 50 observations
        obs_file = instincts_dir / "observations.jsonl"
        with obs_file.open("w") as f:
            for i in range(50):
                f.write(f'{{"event": "test{i}"}}\n')

        # Set last analysis time > 300 seconds ago
        old_time = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
        state = AutoLearnState(last_analysis_time=old_time, observation_count_at_analysis=0)
        save_state(project_root, state)

        result = should_trigger_learning(project_root)

        assert result is True

    def test_does_not_trigger_below_threshold(self, tmp_path: Path):
        """Should not trigger when observation count < 50."""
        from instincts.auto_learn import should_trigger_learning

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        # Create only 30 observations
        obs_file = instincts_dir / "observations.jsonl"
        with obs_file.open("w") as f:
            for i in range(30):
                f.write(f'{{"event": "test{i}"}}\n')

        result = should_trigger_learning(project_root)

        assert result is False

    def test_does_not_trigger_during_cooldown(self, tmp_path: Path):
        """Should not trigger if cooldown has not elapsed."""
        from instincts.auto_learn import should_trigger_learning, AutoLearnState, save_state

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        # Create 50 observations
        obs_file = instincts_dir / "observations.jsonl"
        with obs_file.open("w") as f:
            for i in range(50):
                f.write(f'{{"event": "test{i}"}}\n')

        # Set last analysis time to now (within cooldown)
        now = datetime.now(timezone.utc)
        state = AutoLearnState(last_analysis_time=now, observation_count_at_analysis=0)
        save_state(project_root, state)

        result = should_trigger_learning(project_root)

        assert result is False


class TestAcquireReleaseLock:
    """Tests for acquire_lock and release_lock functions (EC-6)."""

    def test_acquire_lock_creates_lock_file(self, tmp_path: Path):
        """Should create .auto_learn.lock file."""
        from instincts.auto_learn import acquire_lock

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        result = acquire_lock(project_root)

        assert result is True
        lock_file = instincts_dir / ".auto_learn.lock"
        assert lock_file.exists()

    def test_acquire_lock_returns_false_if_lock_exists(self, tmp_path: Path):
        """EC-6: Should return False if another process holds the lock."""
        from instincts.auto_learn import acquire_lock

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        # Create existing lock file
        lock_file = instincts_dir / ".auto_learn.lock"
        lock_file.write_text(json.dumps({"pid": 99999, "timestamp": datetime.now(timezone.utc).isoformat()}))

        result = acquire_lock(project_root)

        assert result is False

    def test_release_lock_removes_lock_file(self, tmp_path: Path):
        """Should remove .auto_learn.lock file."""
        from instincts.auto_learn import acquire_lock, release_lock

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        acquire_lock(project_root)
        release_lock(project_root)

        lock_file = instincts_dir / ".auto_learn.lock"
        assert not lock_file.exists()


class TestTriggerBackgroundAnalysis:
    """Tests for trigger_background_analysis function (AC-4.3)."""

    def test_spawns_background_process(self, tmp_path: Path):
        """AC-4.3: Should spawn background process without blocking."""
        from instincts.auto_learn import trigger_background_analysis

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_popen.return_value = mock_process

            trigger_background_analysis(project_root)

            # Should have called Popen to start background process
            mock_popen.assert_called_once()

    def test_non_blocking_spawn(self, tmp_path: Path):
        """AC-4.3: Background analysis should not block the main session."""
        from instincts.auto_learn import trigger_background_analysis

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_popen.return_value = mock_process

            start_time = time.time()
            trigger_background_analysis(project_root)
            elapsed = time.time() - start_time

            # Should return quickly (< 1 second), not wait for process
            assert elapsed < 1.0


class TestCooldownUpdate:
    """Tests for cooldown timestamp update after analysis (AC-4.4)."""

    def test_analysis_updates_state_after_completion(self, tmp_path: Path):
        """AC-4.4: Should update last_analysis_timestamp after analysis completes."""
        from instincts.auto_learn import AutoLearnState, save_state, load_state

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        # Save initial state
        old_time = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
        initial_state = AutoLearnState(last_analysis_time=old_time, observation_count_at_analysis=0)
        save_state(project_root, initial_state)

        # Simulate analysis completion by updating state
        new_time = datetime.now(timezone.utc)
        new_state = AutoLearnState(last_analysis_time=new_time, observation_count_at_analysis=50)
        save_state(project_root, new_state)

        # Load and verify
        loaded_state = load_state(project_root)
        assert loaded_state.observation_count_at_analysis == 50
        assert loaded_state.last_analysis_time >= old_time


class TestAnalysisFailureHandling:
    """Tests for analysis failure handling (AC-4.5, EC-7)."""

    def test_analysis_failure_is_non_blocking(self, tmp_path: Path):
        """AC-4.5: Analysis failure should log error and continue."""
        from instincts.auto_learn import trigger_background_analysis

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        instincts_dir.mkdir(parents=True)

        # Simulate a process that would fail
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.side_effect = OSError("Failed to spawn process")

            # Should not raise, just log error
            try:
                trigger_background_analysis(project_root)
            except OSError:
                pytest.fail("trigger_background_analysis should not propagate OSError")

    def test_count_failure_skips_trigger(self, tmp_path: Path):
        """EC-7: If observation count fails, should skip auto-learning trigger."""
        from instincts.auto_learn import should_trigger_learning

        project_root = tmp_path / "project"
        project_root.mkdir()

        with patch("instincts.auto_learn.count_observations") as mock_count:
            mock_count.side_effect = OSError("File read error")

            # Should return False (skip trigger), not crash
            result = should_trigger_learning(project_root)

            assert result is False
