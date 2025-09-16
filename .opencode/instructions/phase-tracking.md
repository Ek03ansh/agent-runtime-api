# Phase Tracking

**REQUIRED:** Track which phase of the testing workflow you're currently in.

Create `status/phase.json` with EXACTLY this structure:

```json
{
  "current_phase": "planning",
  "updated_at": "[CURRENT_TIMESTAMP_HERE]"
}
```

## ⚠️ CRITICAL REQUIREMENTS ⚠️

### JSON Formatting:
- **MUST be valid JSON** - no trailing commas, missing quotes, or syntax errors
- **Use double quotes** for all strings (not single quotes)
- **Exact structure only** - no extra fields or modifications

### Timestamp Generation:
- **NEVER use old or static dates**
- Use `new Date().toISOString()` to get the actual current time
- Each update should have a NEWER timestamp than the previous one
- Timestamps should reflect the actual current date and time
- Do NOT copy example timestamps from instructions
- Do NOT use static dates from examples or previous runs

**Update `current_phase` to:**
- `"planning"` when using `@playwright-test-planner`
- `"generating_tests"` when using `@playwright-test-generator`  
- `"fixing_tests"` when using `@playwright-test-fixer`

**VALIDATE before writing:**
- Ensure JSON is properly formatted and valid
- No trailing commas, missing quotes, or syntax errors
- Exact structure only - no extra fields or modifications