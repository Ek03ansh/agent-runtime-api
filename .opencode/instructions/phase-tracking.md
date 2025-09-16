# Phase Tracking

**REQUIRED:** Track which phase of the testing workflow you're currently in.

Create `status/phase.json` with EXACTLY this structure:

```json
{
  "current_phase": "planning",
  "update_count": 1
}
```

## ⚠️ CRITICAL REQUIREMENTS ⚠️

### JSON Formatting:
- **MUST be valid JSON** - no trailing commas, missing quotes, or syntax errors
- **Use double quotes** for all strings (not single quotes)
- **Exact structure only** - no extra fields or modifications

### Phase Updates:
- **Increment `update_count`** each time you modify this file
- Start with `"update_count": 1` for first update.

**Update `current_phase` to ONE OF THESE VALUES ONLY:**
- `"planning"` when using `@playwright-test-planner`
- `"generating_tests"` when using `@playwright-test-generator`  
- `"fixing_tests"` when using `@playwright-test-fixer`

**NO OTHER VALUES ALLOWED** - System will only recognize these three phases.

