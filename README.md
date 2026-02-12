# claude-code-instinct

An Instinct-Based Learning system that observes Claude Code operations and learns patterns.

## Comparison with Auto Memory

Claude Code has a built-in [Auto Memory](https://code.claude.com/docs/en/memory#auto-memory) feature that remembers project patterns, debugging insights, and user preferences. This section compares it with claude-code-instinct.

### Overlapping Features

| Feature | Auto Memory | claude-code-instinct |
|---------|-------------|---------------------|
| Remember project patterns | ✅ | ✅ |
| Remember user preferences | ✅ | ✅ |
| Persist across sessions | ✅ | ✅ |
| Learn workflows | ✅ | ✅ |

### Unique Features of claude-code-instinct

| Feature | Description |
|---------|-------------|
| **Confidence System** | Quantitative tracking: +0.05 on confirmation, -0.1 on contradiction, 0.02 decay per week |
| **Systematic Pattern Detection** | Four explicit algorithms: user_corrections, error_resolutions, repeated_workflows, tool_preferences |
| **Evolution** | Auto-generate skills/commands/agents by clustering related instincts |
| **Evidence-Based Learning** | Quantitative thresholds: min 2 sessions, min 3 tool uses |

### When to Use Which

**Auto Memory is sufficient when:**
- You just want Claude to remember patterns simply
- You can explicitly say "remember this"
- You don't need auto-generation of skills

**claude-code-instinct adds value when:**
- You want quantitative confidence management
- You want "wrong learnings" to decay automatically
- You want to auto-generate skills/commands from accumulated patterns
- You prefer a more systematic, scientific approach

> **Note**: For most users, Auto Memory is sufficient. This project is an experimental value proposition for "a more systematic learning system." As official features expand their coverage, the significance of this project may diminish.

## Installation

```bash
# Setup dependencies
make setup

# Install to ~/.claude/
make install
```

## Uninstallation

```bash
# Uninstall (preserves data)
make uninstall

# Complete removal (deletes all data)
make uninstall-purge
```

## Usage

After installation, the following commands are available in Claude Code:

- `/instinct-status` - Display learned instincts
- `/instinct-evolve` - Analyze observation data and evolve instincts

## Data Lifecycle

### Directory Structure

```
~/.claude/
├── settings.json                    # Hook configuration (added on install)
├── instincts/
│   ├── bin/ -> [repo]/...           # Symlink
│   ├── agents/ -> [repo]/...        # Symlink
│   ├── observations.jsonl           # Observation log (auto-generated)
│   ├── observations.archive/        # Archive (auto-generated)
│   │   └── observations-YYYYMMDD-HHMMSS.jsonl
│   └── personal/                    # Learned instincts
│       └── *.md
└── commands/
    ├── instinct-status.md -> [repo]/...
    └── instinct-evolve.md -> [repo]/...
```

### Data Types

| Data | Location | Created | Deleted |
|------|----------|---------|---------|
| Observation log | `observations.jsonl` | On each tool execution | On archive |
| Archive | `observations.archive/` | When log exceeds 10MB | On `--purge` |
| Learned instincts | `personal/*.md` | On `/instinct-evolve` execution | On `--purge` |

### Observation Log Lifecycle

```
[Tool execution]
     │
     ▼
Append to observations.jsonl
     │
     ▼ (when exceeds 10MB)
Rename to observations.archive/observations-{timestamp}.jsonl
     │
     ▼
Create new observations.jsonl
```

### Data Retention Policy

- **Standard uninstall (`make uninstall`)**
  - Symlinks: Removed
  - Hook configuration in settings.json: Removed
  - Observation logs and archives: **Preserved**
  - Learned instincts: **Preserved**

- **Complete removal (`make uninstall-purge`)**
  - All of the above + entire `~/.claude/instincts/` directory removed

### Manual Data Management

```bash
# Check observation log size
ls -lh ~/.claude/instincts/observations.jsonl

# Check archives
ls -lh ~/.claude/instincts/observations.archive/

# Clear observation logs only (preserves instincts)
rm ~/.claude/instincts/observations.jsonl
rm -rf ~/.claude/instincts/observations.archive/

# Clear learned instincts
rm -rf ~/.claude/instincts/personal/*
```

## Development

```bash
make setup      # Install dependencies
make check      # Type check + tests
make typecheck  # Type check only
make test       # Tests only
make lint       # Lint only
```

## License

MIT
