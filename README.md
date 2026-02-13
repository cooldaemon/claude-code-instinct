# claude-code-instinct

An Instinct-Based Learning system that observes Claude Code operations and learns patterns automatically.

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
| **Evolution to Artifacts** | Auto-generate skills/commands/agents/rules by clustering related instincts |
| **Evidence-Based Learning** | Quantitative thresholds: min 2 sessions, min 3 tool uses |
| **Project-Scoped Storage** | All data stored in project directory, version-controllable |

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
- You want project-specific, version-controllable learning data

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
# Uninstall (preserves project data)
make uninstall

# Complete removal (removes hooks and symlinks)
make uninstall-purge
```

## Usage

### Automatic Learning

After installation, learning happens **automatically**:
1. Claude Code tool usage is observed via hooks
2. Observations are written to `<project>/docs/instincts/observations.jsonl`
3. After 50+ observations, pattern analysis runs automatically
4. Learned instincts are created in `<project>/docs/instincts/learned/`

No manual commands needed - just use Claude Code normally.

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
```

This interactive command lets you:
1. Select which instincts to evolve
2. Choose output type (CLAUDE.md, rules, skills, subagents, commands)
3. For non-CLAUDE.md outputs, choose scope (project or global)
4. Preview and confirm changes

### Output Types

| Type | Description | Project Location | Global Location |
|------|-------------|------------------|-----------------|
| CLAUDE.md | Project-specific rules | `CLAUDE.md` | N/A |
| Rules | Reusable rule files | `.claude/rules/` | `~/.claude/rules/` |
| Skills | Skill definitions | `.claude/skills/` | `~/.claude/skills/` |
| Subagents | Custom agent definitions | `.claude/agents/` | `~/.claude/agents/` |
| Commands | Slash command definitions | `.claude/commands/` | `~/.claude/commands/` |

## Data Lifecycle

### Directory Structure

```
<project>/
├── docs/instincts/
│   ├── observations.jsonl           # Observation log (auto-generated)
│   ├── observations.archive/        # Archive (auto-generated when >10MB)
│   │   └── observations-YYYYMMDD-HHMMSS-PID.jsonl
│   └── learned/                     # Learned instincts (auto-generated)
│       └── *.md
└── .claude/
    ├── rules/                       # Evolved rules
    ├── skills/                      # Evolved skills
    ├── agents/                      # Evolved subagents
    └── commands/                    # Evolved commands

~/.claude/
├── settings.json                    # Hook configuration (added on install)
├── instincts/
│   ├── bin/ -> [repo]/...           # Symlink
│   └── agents/ -> [repo]/...        # Symlink
└── commands/
    └── instinct-evolve.md -> [repo]/...
```

### Data Types

| Data | Location | Created | Deleted |
|------|----------|---------|---------|
| Observation log | `docs/instincts/observations.jsonl` | On each tool execution | On archive |
| Archive | `docs/instincts/observations.archive/` | When log exceeds 10MB | Manual |
| Learned instincts | `docs/instincts/learned/*.md` | Auto (50+ observations) | Manual |
| Evolved artifacts | `.claude/*/` | On `/instinct-evolve` | Manual |

### Data Retention

- **Standard uninstall (`make uninstall`)**
  - Symlinks: Removed
  - Hook configuration in settings.json: Removed
  - Project data (observations, instincts): **Preserved**

- **Complete removal (`make uninstall-purge`)**
  - All of the above + symlinks and hooks removed

### Manual Data Management

```bash
# Check observation log size
ls -lh docs/instincts/observations.jsonl

# Check archives
ls -lh docs/instincts/observations.archive/

# Clear observation logs only (preserves instincts)
rm docs/instincts/observations.jsonl
rm -rf docs/instincts/observations.archive/

# Clear learned instincts
rm -rf docs/instincts/learned/*
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
