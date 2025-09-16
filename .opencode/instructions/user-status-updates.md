# User Status Updates

**REQUIRED:** Keep users informed with frequent updates about what you're doing.

## Activity Log: APPEND ONLY - Never Overwrite
**CRITICAL:** If `status/activity_log.json` exists, READ it first and ADD your new entry to the existing activities array. If it doesn't exist, create it with your first entry. Never replace the entire file.

**TIMESTAMPS:** Always use the CURRENT real timestamp. Never use example timestamps from this instruction.

```json
{
  "activities": [
    {
      "message": "Opening the app to see what we're testing",
      "timestamp": "2025-09-17T14:30:00Z"
    },
    {
      "message": "Writing test for adding new todo items", 
      "timestamp": "2025-09-17T14:31:15Z"
    },
    {
      "message": "Test failed - fixing selector from '.add' to '.new-todo'",
      "timestamp": "2025-09-17T14:32:30Z"
    }
  ]
}
```

## Message Style:
- Be specific: "Writing test for delete button" not "Creating tests"  
- Include what you found: "Selector was wrong, changing to '.destroy'"
- Log every decision: "Choosing to test delete first because it's simpler"
- Report all errors/doubts: "Not sure if this selector is right, trying '.todo-item'"
- **Use REAL timestamps:** Generate current timestamp with `new Date().toISOString()` - never copy examples
- Update frequently throughout your work - users want to see your complete thought process