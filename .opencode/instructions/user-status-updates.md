# User Status Updates

Keep users informed by logging activities to `status/activity_log.json`.

**CRITICAL: APPEND ONLY** - If the file exists, READ it first and ADD your new entry. Never overwrite.

**Rules:**
- Increment `sequence` for each new activity (start with 1)
- Use valid JSON with double quotes
- Write clear, specific messages about what you're doing

```json
{
  "activities": [
    {
      "message": "Opening the app to see what we're testing",
      "sequence": 1
    },
    {
      "message": "Writing test for adding new todo items",
      "sequence": 2
    },
    {
      "message": "Test failed - fixing selector from '.add' to '.new-todo'",
      "sequence": 3
    }
  ]
}
```

**Message Examples:**
- "Writing test for delete button" (not "Creating tests")
- "Selector was wrong, changing to '.destroy'"
- "Test failed - trying different approach"
- Update frequently to show your thought process