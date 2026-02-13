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
│   ├── agent.py            # Analyzes observations, creates instincts
│   ├── evolution.py        # Evolves instincts into skills/commands/agents/rules
│   ├── claudemd.py         # CLAUDE.md parsing and manipulation
│   ├── cli.py              # CLI command (/instinct-evolve)
│   ├── observer.py         # Hook handlers - writes to observations.jsonl
│   ├── utils.py            # Shared utilities (sanitize_id, etc.)
│   └── config.py           # Paths and constants
├── scripts/                # Install/uninstall scripts
│   ├── install.py          # Creates symlinks, configures hooks
│   ├── uninstall.py        # Removes symlinks, cleans hooks
│   └── utils.py            # Shared utilities
├── tests/                  # pytest tests (90% coverage)
├── .claude/                # Claude Code integration
│   ├── instincts/
│   │   ├── bin/            # Entry points for hooks
│   │   └── agents/         # Agent definitions
│   └── commands/           # Slash command definitions
└── pyproject.toml          # Project configuration
```

### Runtime Data (project-scoped)
```
<project>/
├── docs/instincts/
│   ├── observations.jsonl      # Tool usage events log
│   ├── observations.archive/   # Archived logs (>10MB)
│   └── learned/                # Auto-learned instincts (.md files)
└── .claude/
    ├── rules/                  # Evolved rules (project-specific)
    ├── skills/                 # Evolved skills (project-specific)
    ├── agents/                 # Evolved subagents (project-specific)
    └── commands/               # Evolved commands (project-specific)
```

### Key Components

- **Observer (observer.py)**: Hooks into PreToolUse/PostToolUse, writes events to JSONL with file locking
- **Pattern Detectors (patterns.py)**: 4 algorithms detecting user_corrections, error_resolutions, repeated_workflows, tool_preferences
- **Agent (agent.py)**: Analyzes patterns, creates/updates instinct files with confidence scoring
- **Evolution (evolution.py)**: Transforms instincts into 5 output types (CLAUDE.md, rules, skills, subagents, commands)
- **CLI (cli.py)**: Implements /instinct-evolve command with interactive selection

### Data Flow
```
Tool Usage -> Observer Hooks -> docs/instincts/observations.jsonl
                                        |
                         (auto-trigger at 50+ observations)
                                        |
                                        v
                              Pattern Detection
                                        |
                                        v
                         docs/instincts/learned/*.md
                                        |
                            (/instinct-evolve manual)
                                        |
                                        v
    +-----------------------------------------------------------+
    | CLAUDE.md | .claude/rules/ | .claude/skills/ | etc.       |
    +-----------------------------------------------------------+
```

## Usage

### Automatic Learning

Instincts are created **automatically** when:
- 50+ tool observations are collected
- 5-minute cooldown between analysis runs

No manual command needed for learning - just use Claude Code normally.

### Viewing Learned Instincts

```bash
# View learned instincts directly
ls docs/instincts/learned/
cat docs/instincts/learned/*.md
```

### Evolving Instincts

Use `/instinct-evolve` to transform learned instincts into permanent artifacts:

```
/instinct-evolve

Available instincts:
  1. [code-style] Use explicit return types (85%)
  2. [workflow] Run make check before committing (90%)

Select instincts (e.g., 1,2 or 'all'): all

Select output type:
  1. CLAUDE.md (append to project file)
  2. Rules (.claude/rules/)
  3. Skills (.claude/skills/)
  4. Subagents (.claude/agents/)
  5. Commands (.claude/commands/)
> 1

Preview of CLAUDE.md changes:
...
Apply changes? [y/n]
```

### Output Type Selection Guide

| Output Type | Use When | Format |
|-------------|----------|--------|
| **CLAUDE.md** | Project-specific simple rules | Bullet points in "Learned Patterns" section |
| **Rules** | Checklist/table format guidelines | Markdown with checkboxes/tables |
| **Skills** | Domain knowledge with anti-patterns | SKILL.md with frontmatter |
| **Subagents** | Complex multi-step workflows (3+ steps) | Agent definition with process flow |
| **Commands** | Simple subagent invocations | Short format (~20 lines) |

## Development Workflow

### Coding Standards

1. **Immutability**: All dataclasses use `frozen=True`
2. **Type Safety**: Full type hints required, mypy strict mode
3. **Testing**: TDD approach, 90%+ coverage expected
4. **Atomic Writes**: Use temp file + rename for file writes
5. **File Locking**: Use fcntl.flock for concurrent access

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

### Auto-Learning (config.py)
| Constant | Value | Description |
|----------|-------|-------------|
| AUTO_LEARN_OBSERVATION_THRESHOLD | 50 | Minimum observations before auto-learning |
| AUTO_LEARN_COOLDOWN_SECONDS | 300 | Cooldown between runs (5 minutes) |

### Confidence System (confidence.py)
| Parameter | Value | Description |
|-----------|-------|-------------|
| MIN_CONFIDENCE | 0.1 | Minimum confidence floor |
| MAX_CONFIDENCE | 0.95 | Maximum confidence ceiling |
| CONFIRM_DELTA | +0.05 | Confidence increase on confirmation |
| CONTRADICT_DELTA | -0.1 | Confidence decrease on contradiction |
| DECAY_PER_WEEK | 0.02 | Confidence decay per week |
| DORMANT_THRESHOLD | 0.2 | Below this, instinct becomes dormant |

### Evolution (evolution.py)
| Constant | Value | Description |
|----------|-------|-------------|
| WORKFLOW_LINE_THRESHOLD | 10 | Lines above this suggest subagent |
| MIN_EVIDENCE_FOR_SKILL | 5 | Evidence count threshold for skills |
| MIN_CLUSTER_SIZE_FOR_SKILL | 3 | Minimum instincts for skill |
| MIN_AVG_CONFIDENCE_FOR_SKILL | 0.7 | Minimum average confidence |

### Observer (observer.py)
| Constant | Value | Description |
|----------|-------|-------------|
| MAX_FILE_SIZE_MB | 10 | Triggers archive |
| MAX_CONTENT_LENGTH | 5000 | Truncation limit |

## Security Patterns

### Path Validation
```python
# CORRECT: Use is_relative_to() for path validation
if not resolved_path.is_relative_to(resolved_dir):
    raise ValueError("Path traversal detected")
```

### Symlink Protection
```python
# Always check for symlinks before writing
if file_path.is_symlink():
    raise ValueError(f"Refusing to write to symlink: {file_path}")
```

### ID Sanitization
```python
from instincts.utils import sanitize_id

safe_id = sanitize_id(user_input)  # Uses os.path.basename() + regex
```

### Atomic File Writes
```python
# Write to temp file then atomic rename
fd, temp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
try:
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    os.rename(temp_path, file_path)
except:
    os.unlink(temp_path)
    raise
```

### File Locking
```python
import fcntl

with file_path.open("a") as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    try:
        f.write(data)
        f.flush()
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

## Troubleshooting

### Common Issues
- **"No observations to analyze"**: Run some Claude Code commands first to generate observations
- **"No learned instincts found"**: Wait for 50+ observations to trigger auto-learning
- **mypy errors**: Ensure all functions have type hints, use `frozen=True` on dataclasses

### Debugging
```bash
# Check observations log
cat docs/instincts/observations.jsonl | head -20

# Check learned instincts
ls -la docs/instincts/learned/

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

### Instinct File (learned/*.md)
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
