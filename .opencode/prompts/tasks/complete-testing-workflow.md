# Complete Testing Workflow

Execute the complete testing workflow for **{app_url}**:

1. @playwright-test-planner create a test plan for '{app_url}' and save as `specs/test-plan.md` (EXACT filename required - no variations)
2. @playwright-test-generator read the test plan from `specs/test-plan.md` and create tests ONLY in the `tests/` folder (no subfolders)
3. @playwright-test-fixer run the tests in the `tests/` folder and fix any failures (only look in `tests/` folder)

Execute these steps in sequence.
