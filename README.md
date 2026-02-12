# claude-code-instinct

An Instinct-Based Learning system that observes Claude Code operations and learns patterns.

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
