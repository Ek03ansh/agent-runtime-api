# User Status Updates

**REQUIRED:** Keep users informed with frequent updates about what you're doing.

## Activity Log: APPEND ONLY - Never Overwrite
**CRITICAL:** If `status/activity_log.json` exists, READ it first and ADD your new entry to the existing activities array. If it doesn't exist, create it with your first entry. Never replace the entire file.

## ⚠️ CRITICAL REQUIREMENTS ⚠️

### JSON Formatting:
- **MUST be valid JSON** - no trailing commas, missing quotes, or syntax errors
- **Use double quotes** for all strings (not single quotes)
- **Proper escaping** for special characters in messages
- **Consistent indentation** for readability

### Timestamp Generation:
- **NEVER use old or static dates**
- Use `new Date().toISOString()` to get the actual current time
- Each new activity entry should have a NEWER timestamp than previous entries
- Timestamps should reflect the actual current date and time
- Do NOT copy example timestamps from this instruction
- Generate fresh timestamp for EVERY new activity entry

```json
{
  "activities": [
    {
      "message": "Opening the app to see what we're testing",
      "timestamp": "[CURRENT_TIMESTAMP_HERE]"
    },
    {
      "message": "Writing test for adding new todo items", 
      "timestamp": "[NEWER_TIMESTAMP_HERE]"
    },
    {
      "message": "Test failed - fixing selector from '.add' to '.new-todo'",
      "timestamp": "[EVEN_NEWER_TIMESTAMP_HERE]"
    }
  ]
}
```

## Message Style:
- Be specific: "Writing test for delete button" not "Creating tests"  
- Include what you found: "Selector was wrong, changing to '.destroy'"
- Log every decision: "Choosing to test delete first because it's simpler"
- Report all errors/doubts: "Not sure if this selector is right, trying '.todo-item'"
- **CRITICAL:** Use `new Date().toISOString()` to generate CURRENT timestamps - never use old dates from examples
- **VALIDATE JSON:** Ensure the JSON is properly formatted and valid before writing to file
- Update frequently throughout your work - users want to see your complete thought process