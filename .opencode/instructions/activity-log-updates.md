# Activity Log Updates

## Objective
Keep users informed of progress by logging specific activities and actions taken during the testing workflow.

## Action
Log activities to `status/activity_stream.log` using real-time append operations for immediate visibility.

## Requirements
- **File location:** `status/activity_stream.log` (create `status/` folder if needed)
- **Format:** `[TIMESTAMP] MESSAGE` - Simple text format with timestamp only
- **Use simple text logging** - Plain text append operations for immediate visibility  
- **Atomic writes** - Each log entry is a single append operation using `>>` redirect
- **CRITICAL: Use append redirect** - Always use `>> status/activity_stream.log` to ADD entries, NEVER use single `>` which DESTROYS existing logs
- **What to log:**
  - **File operations** - Actual file names, which files you're creating/reading/modifying
  - **Code changes** - Exact selectors, methods, assertions you're adding/fixing  
  - **Test activities** - Which tests you're running, specific issues you're debugging
  - **Tool usage** - Always mention which tool you're currently using for each action
  - **Complete error details** - Full error messages, exit codes, dependency issues, browser launch problems, network failures, file system errors, command failures, Playwright errors
  - **Problem solving** - Specific errors encountered and exact solutions you're trying
  - **Discoveries** - Concrete details about application structure or behavior
  - **Progress tracking** - Specific counts and completions of work items  
  - **Technical details** - Actual methods, selectors, and code patterns you're using
- **When to log** - Every major action, decision, discovery, problem, and completion
- **Frequency** - Update every 5-10 seconds during active work
- **Never copy placeholder text** - Describe your actual current actions, not generic examples

## Output Format
```
[HH:MM:SS] MESSAGE_WITH_ALL_TECHNICAL_DETAILS
```

## Technical Implementation
```bash
# CRITICAL: Always use >> for append operations - PRESERVES existing logs
echo "[$(date '+%H:%M:%S')] Your actual message here" >> status/activity_stream.log
echo "[$(date '+%H:%M:%S')] Next actual message here" >> status/activity_stream.log

# DANGER: NEVER use single > (DESTROYS all previous logs)  
# DANGER: NEVER omit the redirect (no logging occurs)
# DANGER: NEVER overwrite the file - always append with >>
```

