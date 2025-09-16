# User Status Updates

**REQUIRED:** Keep users informed with simple, friendly updates about what you're doing.

## Update Activity Log
Create or APPEND to `status/activity_log.json`:

```json
{
  "activities": [
    {
      "message": "I'm exploring your application to understand how it works",
      "timestamp": "2025-09-15T10:30:00Z"
    },
    {
      "message": "Writing test code for the shopping cart functionality",
      "timestamp": "2025-09-15T10:32:15Z"
    }
  ]
}
```

**If file doesn't exist:** Create it with the structure above.
**If file exists:** Add your new activity to the existing activities array.

## When to Update
- Starting a new major task
- Found something important
- Switching to different work
- Encountering problems
- Completing significant work

## Message Examples
- "I'm exploring your application to understand how it works"
- "Writing test code for the shopping cart functionality" 
- "The login test failed, investigating why and fixing it"
- "All tests are working perfectly now!"

## Keep It Simple
- Use everyday language
- Be specific about current work
- One sentence per update