# /evolve

Analyze learned instincts and suggest evolutions into skills, commands, or agents.

## Usage

```
/evolve
```

## What it does

1. Analyzes all instincts in `~/.claude/instincts/personal/`
2. Identifies high-confidence instincts (>=80%)
3. Finds clusters of related instincts
4. Suggests potential evolutions:
   - **Skills**: Clusters of related instincts
   - **Commands**: Workflow instincts with high confidence
   - **Agents**: Complex multi-step patterns

## Implementation

Run the instinct CLI evolve command:

```bash
~/.claude/instincts/bin/instinct_cli.py evolve
```

## Requirements

- At least 3 instincts are required for meaningful analysis

## Example Output

```
============================================================
  EVOLVE ANALYSIS - 8 instincts
============================================================

High confidence instincts (>=80%): 3

Potential skill clusters found: 2

## SKILL CANDIDATES

1. Cluster: "new functions"
   Instincts: 3
   Avg confidence: 85%
   Domains: code-style, testing

2. Cluster: "error handling"
   Instincts: 2
   Avg confidence: 72%
   Domains: code-style

============================================================
```

## Evolution Types

| Type | Description | Output Location |
|------|-------------|-----------------|
| Skill | Reusable patterns | `~/.claude/skills/` |
| Command | Custom slash commands | `~/.claude/commands/` |
| Agent | Specialist agents | `~/.claude/agents/` |
