# User Status Updates

## Objective
Keep users informed of progress by logging specific activities and actions taken during the testing workflow.

## Action
Log activities to `status/activity_log.json` with descriptive messages about what you're currently doing.

## Requirements
- **File location:** `status/activity_log.json` (create `status/` folder if needed)
- **Always read file first** - Find highest sequence number, then add new entry with sequence + 1
- **Validate JSON before writing** - Invalid JSON crashes the system
- **Log specific actions you're taking:**
  - **File operations:** Which files you're creating, reading, or modifying
  - **Code changes:** Exact selectors, methods, or assertions you're adding/fixing
  - **Test activities:** Which tests you're running, what specific issues you're debugging
  - **Problem solving:** Specific errors encountered and exact solutions you're trying
  - **Discoveries:** Concrete details about application structure or behavior
  - **Progress tracking:** Specific counts and completions of work items
  - **Technical details:** Actual methods, selectors, and code patterns you're using
- **Update frequently** - Log every major action, decision, discovery, problem, and completion throughout your work
- **Regular progress updates** - Update every 5-10 seconds during active work to show what you're currently trying

## Output
```json
{
  "activities": [
    {
      "message": "[YOUR_SPECIFIC_MESSAGE_HERE]",
      "sequence": 1
    }
  ]
}
```