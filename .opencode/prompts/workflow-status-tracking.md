# Workflow Status Tracking

## File: `status/workflow-status.json`
**Update every 10 seconds during active work**

## Initialize Status File
**Create this file as your first step if it doesn't exist:**
```json
{
  "workflowInfo": {
    "sessionId": "session-id-from-request",
    "appUrl": "https://app-url-from-request",
    "currentPhase": "PlanGeneration",
    "overallStatus": "InProgress",
    "updatedAt": "2025-09-12T19:23:12.000Z"
  },
  "testPlan": {
    "testSuites": []
  }
}
```

## Schema Structure
```json
{
  "workflowInfo": {
    "currentPhase": "PlanGeneration|CodeGeneration|RunningAndFixing|Completed",
    "overallStatus": "InProgress|Completed|Failed",
    "updatedAt": "ISO_timestamp"
  },
  "testPlan": {
    "testSuites": [{
      "suiteName": "string",
      "testFilePath": "tests/example.spec.ts",
      "testCases": [{
        "testCaseName": "should do something",
        "phase": "PlanGeneration|CodeGeneration|RunningAndFixing|Completed", 
        "status": "Generating|Generated|Running|Errors Found|Fixing|Fixed|Pass|Fail"
      }]
    }]
  }
}
```

## Status Flow by Phase

**PlanGeneration Phase:**
- Start: `"Generating"`
- End: `"Generated"`

**CodeGeneration Phase:**
- Start: `"Generating"` 
- End: `"Generated"`

**RunningAndFixing Phase:**
- `"Running"` (test executing)
- `"Errors Found"` (test failed)
- `"Fixing"` (working on fixes)
- `"Fixed"` (test now passes)

**Completed Phase:**
- `"Pass"` (final success)
- `"Fail"` (final failure)

## What Each Agent Does

### @playwright-test-planner
1. **Initialize** status file if it doesn't exist (see above)
2. **Set** global `currentPhase: "PlanGeneration"`
3. **Add test cases** as you identify them:
   ```json
   {
     "testCaseName": "should load homepage",
     "phase": "PlanGeneration", 
     "status": "Generating"
   }
   ```
4. **Update to** `status: "Generated"` when planning complete

### @playwright-test-generator  
1. **Set** global `currentPhase: "CodeGeneration"`
2. **For each test you work on**:
   - Change test `phase: "CodeGeneration"`
   - Set `status: "Generating"` when starting
   - Set `status: "Generated"` when file created

### @playwright-test-fixer
1. **Set** global `currentPhase: "RunningAndFixing"`  
2. **For each test you work on**:
   - Change test `phase: "RunningAndFixing"`
   - `status: "Running"` → `"Errors Found"` → `"Fixing"` → `"Fixed"`
3. **When test is final**:
   - Change test `phase: "Completed"`
   - Set `status: "Pass"` or `"Fail"`
4. **When all tests done**: Set global `currentPhase: "Completed"`

## Critical Rules
1. **Always update** `workflowInfo.updatedAt` with current ISO timestamp
2. **Individual progression**: Each test moves through phases independently
3. **Status validation**: Use only valid statuses for each phase (see table above)
4. **Update frequency**: Every 10 seconds during active work
5. **Error handling**: If status update fails, continue main work - don't break workflow

## Example: Clear State During Code Generation
```json
{
  "workflowInfo": {"currentPhase": "CodeGeneration"},
  "testPlan": {"testSuites": [{
    "testCases": [
      {"testCaseName": "test1", "phase": "CodeGeneration", "status": "Generated"},
      {"testCaseName": "test2", "phase": "CodeGeneration", "status": "Generating"}, 
      {"testCaseName": "test3", "phase": "PlanGeneration", "status": "Generated"}
    ]
  }]}
}
```
**Meaning**: Test1 coded ✅, Test2 coding 🔄, Test3 planned but not coded yet ⏳