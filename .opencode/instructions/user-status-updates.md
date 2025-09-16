# User Status Updates

## Objective
Keep users informed of progress by logging specific activities and actions taken during the testing workflow.

## Action
Log activities to `status/activity_log.json` with descriptive messages about what you're currently doing.

## Requirements
- **File location:** `status/activity_log.json` (create `status/` folder if needed)
- **Always read file first** - Find highest sequence number, then add new entry with sequence + 1
- **Validate JSON before writing** - Invalid JSON crashes the system
- **Log comprehensively:**
  - **Major milestones:** "Starting test generation phase", "Planning phase complete"
  - **Decisions and reasoning:** "Choosing to test delete first because it's simpler"
  - **Exploration findings:** "Successfully navigated to app - can see input field and clean interface"
  - **Analysis results:** "Analyzed test plan: 25 scenarios covering core functionality"
  - **Progress updates:** "Created comprehensive test suite with 5 test files"
  - **Errors and fixes:** "Test failed with timeout - trying different selector"
  - **Completions:** "Test generation complete - ready to run automated tests"
- **Update frequently** - Log every major action, decision, discovery, problem, and completion throughout your work
- **Regular progress updates** - Update every 30-60 seconds during active work to show what you're currently trying

## Output
```json
{
  "activities": [
    {
      "message": "Starting test generation phase - analyzing test plan",
      "sequence": 1
    },
    {
      "message": "Creating test for todo deletion - trying selector '.destroy'",
      "sequence": 2
    },
    {
      "message": "Test failed with timeout - element not found, trying different approach",
      "sequence": 3
    },
    {
      "message": "Fixed selector and test passes - generation complete",
      "sequence": 4
    }
  ]
}
```