# /instinct-evolve

Transform learned instincts into permanent artifacts.

## Usage

```
/instinct-evolve
```

## What it does

1. Loads learned instincts from `<project>/docs/instincts/learned/`
2. Displays instincts with confidence levels
3. Prompts for instinct selection
4. Prompts for output type selection
5. For non-CLAUDE.md outputs, prompts for scope (project or global)
6. Generates and writes the selected artifact

## Implementation

Run the instinct CLI evolve command with interactive mode:

```bash
~/.claude/instincts/bin/instinct_cli.py evolve --interactive
```

## Requirements

- At least 3 instincts are required for meaningful analysis
- Project must have `docs/instincts/learned/` directory with instinct files

## Interactive Flow

```
/instinct-evolve

Available instincts:
  1. [code-style] Use explicit return types (85%)
  2. [workflow] Run make check before committing (90%)
  3. [testing] Use pytest fixtures in conftest.py (78%)

Select instincts (e.g., 1,2,3 or 'all'):
> all

Select output type:
  1. CLAUDE.md (append to project file)
  2. Rules (.claude/rules/)
  3. Skills (.claude/skills/)
  4. Subagents (.claude/agents/)
  5. Commands (.claude/commands/)
> 1

Preview of CLAUDE.md changes:
----------------------------------------
## Learned Patterns

### Code Style
- Use explicit return types when writing TypeScript functions

### Workflow
- Run make check before committing to ensure code quality
...
----------------------------------------

Apply changes? [y/n]
> y

Written to CLAUDE.md
```

## Output Types

| Type | Description | Project Location | Global Location |
|------|-------------|------------------|-----------------|
| CLAUDE.md | Project-specific rules | `CLAUDE.md` | N/A |
| Rules | Reusable rule files | `.claude/rules/` | `~/.claude/rules/` |
| Skills | Skill definitions | `.claude/skills/` | `~/.claude/skills/` |
| Subagents | Custom agent definitions | `.claude/agents/` | `~/.claude/agents/` |
| Commands | Slash command definitions | `.claude/commands/` | `~/.claude/commands/` |

## Scope Selection

For Rules, Skills, Subagents, and Commands, you can choose:

1. **Project scope** - Files are created in the project's `.claude/` directory
2. **Global scope** - Files are created in `~/.claude/` for use across all projects

CLAUDE.md output is always project-scoped.

## Automatic Learning

Note: Instincts are created automatically when enough observations are collected.
You don't need to run any command to trigger learning - it happens automatically
after 50+ tool usages with a 5-minute cooldown between analysis runs.

## Viewing Learned Instincts

Learned instincts are stored as markdown files in:
```
<project>/docs/instincts/learned/
```

You can view them directly in your file browser or editor.
