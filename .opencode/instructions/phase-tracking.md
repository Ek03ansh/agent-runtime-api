# Phase Tracking

## Objective
Track the current phase of the testing workflow to enable system monitoring and progress visibility.

## Action
Create and maintain `status/phase.json` with the current workflow phase and update counter.

## Requirements
- **File location:** `status/phase.json` (create `status/` folder if needed)
- **Update once per phase** - Set phase at the START of using each agent
- **Use ONLY these exact phase values:**
  - `"planning"` - when starting @playwright-test-planner
  - `"generating_tests"` - when starting @playwright-test-generator  
  - `"fixing_tests"` - when starting @playwright-test-fixer
- **Include update counter** (increment if file exists, or use 1)

## Output

```json
{
  "current_phase": "planning",
  "update_count": 1
}
```