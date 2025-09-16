# Phase Tracking

**REQUIRED:** Track which phase of the testing workflow you're currently in.

Create `status/phase.json` with EXACTLY this structure:

```json
{
  "current_phase": "planning",
  "updated_at": "2025-09-17T14:30:00Z"
}
```

**IMPORTANT:** Always use the CURRENT real timestamp, not example timestamps from this instruction.

**Update `current_phase` to:**
- `"planning"` when using `@playwright-test-planner`
- `"generating_tests"` when using `@playwright-test-generator`  
- `"fixing_tests"` when using `@playwright-test-fixer`

**NO other fields. NO extra content. EXACT structure only.**