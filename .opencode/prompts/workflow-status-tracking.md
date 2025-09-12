# Workflow Status Tracking Instructions

## Schema Definition
```typescript
interface WorkflowStatus {
  workflowInfo: {
    sessionId: string;
    appUrl: string;
    workflowType: "complete";
    startedAt: string; // ISO timestamp
    updatedAt: string; // ISO timestamp
    currentPhase: "PlanGeneration" | "CodeGeneration" | "RunningAndFixing" | "Completed";
    overallStatus: "InProgress" | "Completed" | "Failed";
  };
  testPlan: {
    testSuites: TestSuite[];
  };
}

interface TestSuite {
  suiteName: string;
  testFilePath: string; // Relative path to the test file
  testCases: TestCase[];
}

interface TestCase {
  testCaseName: string;
  status: "Generating" | "Generated" | "Running" | "Errors Found" | "Fixing" | "Fixed" | "Pass" | "Fail";
}
```

## Workflow Status File Management

### 1. Initialize Workflow Status (First Agent Only)
Create `status/workflow-status.json`:
```json
{
  "workflowInfo": {
    "sessionId": "{generate_unique_id}",
    "appUrl": "{app_url}",
    "workflowType": "complete",
    "startedAt": "{current_iso_timestamp}",
    "updatedAt": "{current_iso_timestamp}",
    "currentPhase": "PlanGeneration",
    "overallStatus": "InProgress"
  },
  "testPlan": {
    "testSuites": []
  }
}
```

### 2. Status Update Requirements
- **Update frequency**: Every 10 seconds during active work
- **File location**: `status/workflow-status.json` in project root
- **Schema compliance**: Must match `WorkflowStatus` interface exactly

### 3. Phase-Status Constraints
**Each phase only allows specific test case statuses:**

| Phase | Allowed Test Case Statuses | Description |
|-------|---------------------------|-------------|
| `PlanGeneration` | `"Generating"`, `"Generated"` | Planning and identifying test cases |
| `CodeGeneration` | `"Generating"`, `"Generated"` | Writing test code files |
| `RunningAndFixing` | `"Running"`, `"Errors Found"`, `"Fixing"`, `"Fixed"` | Executing and fixing tests |
| `Completed` | `"Pass"`, `"Fail"` | Final test results |

### 4. Phase-Specific Responsibilities

#### playwright-test-planner Phase
- **Current Phase**: `"PlanGeneration"`
- **Valid Statuses**: `"Generating"` → `"Generated"`
- **Actions**:
  1. Populate `testPlan.testSuites` array with identified test suites (including `testFilePath`)
  2. Add `testCases` with `status: "Generating"` as you identify them
  3. Update to `status: "Generated"` when test case planning is complete

**Example test suite structure:**
```json
{
  "suiteName": "Homepage Tests",
  "testFilePath": "tests/homepage.spec.ts",
  "testCases": [
    {"testCaseName": "should load homepage", "status": "Generated"}
  ]
}
```

#### playwright-test-generator Phase  
- **First Action**: Transition to `currentPhase: "CodeGeneration"` when starting
- **Current Phase**: `"CodeGeneration"`
- **Valid Statuses**: `"Generating"` → `"Generated"`
- **Actions**:
  1. Update `status: "Generating"` when starting code generation for a test case
  2. Update to `status: "Generated"` when test file is created and saved

#### playwright-test-fixer Phase
- **First Action**: Transition to `currentPhase: "RunningAndFixing"` when starting
- **Current Phase**: `"RunningAndFixing"`
- **Valid Statuses**: `"Running"` → `"Errors Found"` → `"Fixing"` → `"Fixed"`
- **Final Statuses**: `"Pass"` or `"Fail"` (when transitioning to `"Completed"` phase)
- **Actions**:
  1. Update `status: "Running"` when executing a test case
  2. Update to `status: "Errors Found"` if test fails
  3. Update to `status: "Fixing"` when attempting to fix the test
  4. Update to `status: "Fixed"` when test passes after fixes
  5. Transition to `currentPhase: "Completed"` when all test cases are `"Fixed"`
  6. Update final statuses to `"Pass"` or `"Fail"`

## Critical Requirements
1. **Always update `workflowInfo.updatedAt`** with current timestamp
2. **Maintain phase-status consistency** - only use statuses valid for current phase (see Phase-Status Constraints table above)
3. **Update every 10 seconds** during active work
4. **Transition phases** only when switching agents (except final transition to `"Completed"`)
5. **Handle errors gracefully** - never let status tracking break the main workflow
