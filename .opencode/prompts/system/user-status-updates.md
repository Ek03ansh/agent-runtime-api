# User Status Updates

**REQUIRED:** Keep users informed with frequent, detailed updates about what you're doing RIGHT NOW.

## Update Activity Log FREQUENTLY
Create or APPEND to `status/activity_log.json` - Update every 1-2 minutes with specific actions:

```json
{
  "activities": [
    {
      "message": "Opening the application in browser to see what we're testing",
      "timestamp": "2025-09-15T10:30:00Z"
    },
    {
      "message": "Found a todo app - checking if I can add new items",
      "timestamp": "2025-09-15T10:30:30Z"
    },
    {
      "message": "Writing first test: adding a new todo item",
      "timestamp": "2025-09-15T10:31:00Z"
    },
    {
      "message": "Test failed - the add button selector might be wrong, investigating",
      "timestamp": "2025-09-15T10:31:45Z"
    },
    {
      "message": "Fixed the selector, test now passes! Moving to edit functionality",
      "timestamp": "2025-09-15T10:32:15Z"
    }
  ]
}
```

## Update EVERY Time You:
- Start looking at the app
- Write a new test file
- Run tests and see results
- Fix a failing test
- Move to a different feature
- Find a bug or issue
- Complete a specific test
- Change your approach

## Be Specific and Granular
Instead of: "Created comprehensive test plan"
Write: "Looking at the todo app interface to see what buttons and features need testing"

Instead of: "Generated complete test suite"  
Write: "Writing test for marking todos complete - checking the checkbox functionality"

Instead of: "Fixed failing tests"
Write: "The delete button test failed because selector was wrong, updating it from '.delete' to '.destroy'"

## Message Style
- Say what you're doing RIGHT NOW
- Mention specific files, features, or buttons
- Include what you found or what went wrong
- Keep it conversational and detailed
- Update frequently (every 30-60 seconds of work)