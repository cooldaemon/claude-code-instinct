# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

claude-code-instinct is an instinct-based learning system for Claude Code that automatically learns patterns from tool usage observations. It integrates with Claude Code via hooks, observing tool usage to detect patterns and create "instincts" - learned behaviors that improve over time.

**Key Technologies**: Python 3.10+, pytest, mypy (strict), ruff, uv (package manager)

## Commands

### Development
```bash
make setup      # Install dependencies with uv
make check      # Run all verification (typecheck + test)
make test       # Run pytest with coverage
make typecheck  # Run mypy
make lint       # Run ruff linter

# Run specific test
make test-one T=tests/test_models.py
make test-one T=tests/test_models.py::TestPattern::test_pattern_is_frozen
make test-one T="-k confidence"
```

### Installation
```bash
make install           # Install to ~/.claude/
make uninstall         # Remove symlinks/hooks (preserves data)
make uninstall-purge   # Complete removal including data
```

## Architecture

### Project Structure
```
claude-code-instinct/
├── instincts/              # Core Python package
│   ├── models.py           # PatternType, Evidence, Pattern, Instinct (frozen dataclasses)
│   ├── confidence.py       # Confidence scoring and decay
│   ├── patterns.py         # 4 pattern detectors
│   ├── agent.py            # Observer Agent - analyzes observations, creates instincts
│   ├── evolution.py        # Clusters instincts, generates skills/commands/agents
│   ├── cli.py              # CLI commands (/instinct-status, /evolve, /observe-patterns)
│   ├── observer.py         # Hook handlers - writes to observations.jsonl
│   └── config.py           # Paths and constants
├── scripts/                # Install/uninstall scripts
│   ├── install.py          # Creates symlinks, configures hooks
│   ├── uninstall.py        # Removes symlinks, cleans hooks
│   └── utils.py            # Shared utilities
├── tests/                  # pytest tests (89% coverage target)
├── .claude/                # Claude Code integration
│   ├── instincts/
│   │   ├── bin/            # Entry points for hooks
│   │   └── agents/         # Agent definitions
│   └── commands/           # Slash command definitions
└── pyproject.toml          # Project configuration
```

### Runtime Data (created on install)
```
~/.claude/instincts/
├── observations.jsonl      # Tool usage events log
├── observations.archive/   # Archived logs (>10MB)
├── personal/               # Auto-learned instincts (.md files)
└── evolved/                # Generated skills/commands/agents
    ├── skills/
    ├── commands/
    └── agents/
```

### Key Components

- **Observer (observer.py)**: Hooks into PreToolUse/PostToolUse, writes events to JSONL
- **Pattern Detectors (patterns.py)**: 4 algorithms detecting user_corrections, error_resolutions, repeated_workflows, tool_preferences
- **Agent (agent.py)**: Analyzes patterns, creates/updates instinct files with confidence scoring
- **Evolution (evolution.py)**: Clusters related instincts, suggests/generates skills, commands, agents
- **CLI (cli.py)**: Implements /instinct-status, /evolve, /observe-patterns commands

### Data Flow
```
Tool Usage -> Observer Hooks -> observations.jsonl -> Pattern Detectors ->
Agent -> personal/*.md instincts -> Evolution -> evolved/*
```

## Development Workflow

### Coding Standards

1. **Immutability**: All dataclasses use `frozen=True`
2. **Type Safety**: Full type hints required, mypy strict mode
3. **Testing**: TDD approach, 89%+ coverage expected

### Naming Conventions
- **Files**: snake_case (e.g., `pattern_detector.py`)
- **Classes**: PascalCase (e.g., `AnalysisResult`)
- **Functions**: snake_case (e.g., `detect_all_patterns`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_FILE_SIZE_MB`)
- **Instinct IDs**: kebab-case (e.g., `user-correction-when-editing`)

### Testing
- Framework: pytest with pytest-cov
- Structure: Mirror source structure in tests/
- Run: `make test` for full coverage, `make test-one T=...` for specific

## Important Constants

### Confidence System (confidence.py)
| Parameter | Value | Description |
|-----------|-------|-------------|
| MIN_CONFIDENCE | 0.1 | Minimum confidence floor |
| MAX_CONFIDENCE | 0.95 | Maximum confidence ceiling |
| CONFIRM_DELTA | +0.05 | Confidence increase on confirmation |
| CONTRADICT_DELTA | -0.1 | Confidence decrease on contradiction |
| DECAY_PER_WEEK | 0.02 | Confidence decay per week |
| DORMANT_THRESHOLD | 0.2 | Below this, instinct becomes dormant |

### Initial Confidence by Evidence Count
| Evidence Count | Initial Confidence |
|----------------|-------------------|
| 0 | 0.1 |
| 1-2 | 0.3 |
| 3-5 | 0.5 |
| 6-10 | 0.7 |
| 11+ | 0.85 |

### Pattern Detection (patterns.py)
| Constant | Value |
|----------|-------|
| MIN_WORKFLOW_SEQUENCE_LENGTH | 3 |
| MIN_SESSIONS_FOR_PATTERN | 2 |
| MIN_TOOL_USES_FOR_PREFERENCE | 3 |
| MAX_OBSERVATIONS_FILE_SIZE | 50MB |
| MAX_OBSERVATIONS_LINES | 100,000 |

### Evolution (evolution.py)
| Constant | Value |
|----------|-------|
| TRIGGER_SIMILARITY_THRESHOLD | 0.3 |
| MIN_CLUSTER_SIZE_FOR_SKILL | 3 |
| MIN_AVG_CONFIDENCE_FOR_SKILL | 0.7 |
| MIN_CONFIDENCE_FOR_COMMAND | 0.85 |

### Observer (observer.py)
| Constant | Value |
|----------|-------|
| MAX_FILE_SIZE_MB | 10 (triggers archive) |
| MAX_CONTENT_LENGTH | 5000 (truncation limit) |

## Security Patterns

### Path Validation
```python
# CORRECT: Use is_relative_to() for path validation
if not resolved_path.is_relative_to(resolved_dir):
    raise ValueError("Path traversal detected")

# WRONG: Never use startswith() for path validation
if not str(path).startswith(str(base)):  # Vulnerable to /base/../attack
```

### Symlink Protection
```python
# Always check for symlinks before writing
if file_path.is_symlink():
    raise ValueError(f"Refusing to write to symlink: {file_path}")
```

### ID Sanitization
```python
# Use os.path.basename() + regex for safe IDs
safe_id = os.path.basename(instinct_id)
safe_id = re.sub(r"[^a-zA-Z0-9_-]", "-", safe_id)
```

### Directory Permissions
```python
# Create directories with restricted permissions
directory.mkdir(parents=True, exist_ok=True, mode=0o700)
```

## Gotchas and Notes

### File Handling
- observations.jsonl uses append mode, auto-archives at 10MB
- Skip invalid JSON lines silently (defensive parsing)
- Truncate input/output strings to 5000 chars

### Pattern Detection
- Patterns require observations from 2+ sessions
- Workflows need 3+ tool sequence
- Subset patterns are removed (keep longest matching sequence)

### Instinct Files
- Use YAML frontmatter format in markdown files
- Support both .yaml and .md extensions for backward compatibility
- Warning triggered at 100+ instinct files (performance concern)

### Hook Integration
- Hooks are registered in ~/.claude/settings.json
- Hook commands must be executable Python scripts
- Session IDs track cross-tool patterns

## Troubleshooting

### Common Issues
- **"No observations to analyze"**: Run some Claude Code commands first to generate observations
- **"Need at least 3 instincts"**: /evolve requires minimum instincts for meaningful analysis
- **mypy errors**: Ensure all functions have type hints, use `frozen=True` on dataclasses

### Debugging
```bash
# Check observations log
cat ~/.claude/instincts/observations.jsonl | head -20

# Check instinct files
ls -la ~/.claude/instincts/personal/

# Verify hook configuration
cat ~/.claude/settings.json | jq '.hooks'
```

## File Format Reference

### Observation Event (observations.jsonl)
```json
{
  "timestamp": "2024-01-01T00:00:00+00:00",
  "event": "tool_start|tool_complete",
  "tool": "Write|Edit|Bash|...",
  "session": "session-id",
  "input": "...",
  "output": "..."
}
```

### Instinct File (personal/*.md)
```yaml
---
id: instinct-id-kebab-case
trigger: "when <context>"
confidence: 0.5
domain: workflow|code-style|testing|...
source: user_correction|error_resolution|...
evidence_count: 3
created_at: "2024-01-01T00:00:00+00:00"
updated_at: "2024-01-01T00:00:00+00:00"
status: active|dormant
---

# Description

## Action
What to do...

## Evidence
- Evidence item 1
- Evidence item 2
```
