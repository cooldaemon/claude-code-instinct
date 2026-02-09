# /instinct-status

Show the status of all learned instincts.

## Usage

```
/instinct-status
```

## What it shows

- Total number of instincts
- Instincts grouped by domain (code-style, testing, workflow, etc.)
- Confidence level for each instinct (0-100%)
- Trigger conditions
- Observations statistics (events logged)

## Implementation

Run the instinct CLI status command:

```bash
~/.claude/instincts/bin/instinct_cli.py status
```

## Example Output

```
============================================================
  INSTINCT STATUS - 5 total
============================================================

## CODE-STYLE (2)

  ██████████ 90%  prefer-functional-style
            trigger: when writing new functions

  ██████░░░░ 60%  use-guard-clauses
            trigger: when writing conditionals

## TESTING (3)

  █████████░ 90%  always-test-first
            trigger: when implementing new features

------------------------------------------------------------
  Observations: 142 events logged
  File: ~/.claude/instincts/observations.jsonl

============================================================
```
