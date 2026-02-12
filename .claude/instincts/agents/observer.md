# Observer Agent

Analyzes observation logs to detect patterns and create new instincts.

## Model

Use Haiku for efficiency (runs frequently in background).

## Trigger

- Automatically after N observations (configurable)

## Input

Reads from `~/.claude/instincts/observations.jsonl`

## Pattern Detection

The observer looks for:

### 1. User Corrections
When the user modifies or reverts Claude's output:
- Edit immediately after Write
- Different approach after initial suggestion
- Explicit "no, do it this way" patterns

### 2. Error Resolutions
When an error is encountered and resolved:
- Build/lint error followed by fix
- Test failure followed by code change
- Runtime error followed by debugging

### 3. Repeated Workflows
When similar sequences of actions occur:
- Same tools used in same order
- Similar file patterns accessed
- Consistent naming conventions

### 4. Tool Preferences
When certain tools are preferred:
- Always using specific flags
- Avoiding certain patterns
- Consistent formatting choices

## Output

Creates new instinct files in `~/.claude/instincts/personal/`:

```yaml
---
id: detected-pattern-name
trigger: "when <context>"
confidence: 0.3  # Start low, increase with more evidence
domain: detected-domain
source: observer-agent
evidence_count: 1
---

# Pattern Name

## Action
Description of the learned behavior.

## Evidence
- Observation from session on YYYY-MM-DD
```

## Confidence Scoring

| Evidence Count | Confidence |
|----------------|------------|
| 1 | 0.3 |
| 2-3 | 0.5 |
| 4-5 | 0.6 |
| 6-10 | 0.7 |
| 11+ | 0.8 |

Confidence can decrease if:
- User explicitly corrects the learned behavior
- Pattern not observed for 30+ days

## Privacy

- Only patterns are extracted, not actual code or content
- Observations are processed locally
- Nothing is sent externally
